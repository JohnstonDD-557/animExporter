#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WoWS/PnF .anim 样本解析器
基于 PnF_Template_Files.zip 中 4 个 .anim 样本反推。
支持：
  1) baked dense pose 格式：每帧每骨骼 40 bytes = 10 个 float32
  2) keyed rotation curve 格式：当前样本中的单骨骼旋转曲线

用法：
  python anim_parser.py input.anim --summary
  python anim_parser.py input.anim --json out.json
  python anim_parser.py input.anim --dump-frame 0
"""
from __future__ import annotations

import argparse
import json
import math
import struct
from pathlib import Path
from typing import Any, Dict, List, Tuple


def u32(data: bytes, off: int) -> int:
    return struct.unpack_from("<I", data, off)[0]


def f32(data: bytes, off: int) -> float:
    return struct.unpack_from("<f", data, off)[0]


def read_names(data: bytes, off: int, count: int) -> Tuple[List[str], int]:
    names: List[str] = []
    for _ in range(count):
        n = u32(data, off)
        off += 4
        raw = data[off:off + n]
        off += n
        names.append(raw.decode("ascii", errors="replace"))
    return names, off


def parse_header(data: bytes) -> Dict[str, Any]:
    off = 0
    frame_count = u32(data, off); off += 4
    fps = f32(data, off); off += 4
    start_time_or_zero = f32(data, off); off += 4
    flag_a = data[off]
    flag_b = data[off + 1]
    off += 2
    epsilon_1 = f32(data, off); off += 4
    epsilon_2 = f32(data, off); off += 4
    epsilon_3 = f32(data, off); off += 4
    zero_byte = data[off]; off += 1
    node_count = u32(data, off); off += 4
    names, off = read_names(data, off, node_count)

    return {
        "frame_count": frame_count,
        "fps": fps,
        "start_time_or_zero": start_time_or_zero,
        "flags": [flag_a, flag_b],
        "epsilon_or_tolerance": [epsilon_1, epsilon_2, epsilon_3],
        "zero_byte": zero_byte,
        "node_count": node_count,
        "node_names": names,
        "after_name_table_offset": off,
    }


def parse_baked_dense(data: bytes, body_off: int, duration: int, node_count: int) -> Dict[str, Any]:
    record_size = 40
    expected = duration * node_count * record_size
    available = len(data) - body_off
    records = []

    # 不默认输出全部帧，避免 JSON 过大；只给首帧、末帧和校验信息。
    def read_record(frame: int, node: int) -> List[float]:
        off = body_off + (frame * node_count + node) * record_size
        return list(struct.unpack_from("<10f", data, off))

    first_frame = [read_record(0, i) for i in range(min(node_count, 5))]
    last_frame = [read_record(duration - 1, i) for i in range(min(node_count, 5))]

    return {
        "encoding": "baked_dense_pose",
        "record_layout": ["tx", "ty", "tz", "qx", "qy", "qz", "qw", "sx", "sy", "sz"],
        "order": "frame-major: for frame, then for node in node name table order",
        "record_size": record_size,
        "expected_body_bytes": expected,
        "available_body_bytes": available,
        "body_size_matches": expected == available,
        "sample_first_frame_first_nodes": first_frame,
        "sample_last_frame_first_nodes": last_frame,
    }


def parse_keyed_rotation_sample(data: bytes, body_off: int, duration: int, node_count: int) -> Dict[str, Any]:
    """
    当前样本 Rotation_Z_15rpm.anim / Rotation2rpm.anim 的 keyframe 结构。
    注意：若真实游戏文件含多通道/位移/缩放曲线，需要继续扩展。
    """
    channel_count = u32(data, body_off + 0)
    constant_48 = u32(data, body_off + 4)

    # 当前样本只出现一个通道。下面的偏移已经由两个样本交叉验证。
    ch_off = body_off + 8
    value_class = u32(data, ch_off + 0)
    data_block_len = u32(data, ch_off + 4)
    unknown_a = u32(data, ch_off + 8)
    bone_index = u32(data, ch_off + 12)
    transform_channel = u32(data, ch_off + 16)
    unknown_b = u32(data, ch_off + 20)
    value_code = u32(data, ch_off + 24)
    unknown_c = u32(data, ch_off + 28)
    unknown_byte = data[ch_off + 32]
    key_count = u32(data, ch_off + 33)

    t_off = ch_off + 37
    times = list(struct.unpack_from(f"<{key_count}f", data, t_off))
    q_off = t_off + key_count * 4
    quats = []
    angles_deg = []
    for i in range(key_count):
        q = list(struct.unpack_from("<4f", data, q_off + i * 16))
        quats.append(q)
        # 只作为单轴旋转文件的辅助观测：选择绝对值最大的 xyz 分量推回角度
        axis_idx = max(range(3), key=lambda j: abs(q[j]))
        angle = math.degrees(2.0 * math.atan2(q[axis_idx], q[3]))
        angles_deg.append(angle)

    tail_off = q_off + key_count * 16
    tail = data[tail_off:]

    return {
        "encoding": "keyed_rotation_curve_sample",
        "channel_count": channel_count,
        "constant_48": constant_48,
        "channel_header_observed": {
            "value_class": value_class,
            "data_block_len": data_block_len,
            "unknown_a": unknown_a,
            "bone_index": bone_index,
            "transform_channel": transform_channel,
            "unknown_b": unknown_b,
            "value_code": value_code,
            "unknown_c": unknown_c,
            "unknown_byte": unknown_byte,
        },
        "key_count": key_count,
        "times_seconds": times,
        "quaternion_xyzw": quats,
        "single_axis_angles_deg_observed": angles_deg,
        "tail_offset": tail_off,
        "tail_bytes_hex": tail.hex(" "),
        "tail_note": "当前样本尾部长度为 34 bytes，疑似静态位移/缩放或通道默认值块；字段语义未完全确认。",
    }


def parse_anim(path: str | Path) -> Dict[str, Any]:
    path = Path(path)
    data = path.read_bytes()
    header = parse_header(data)
    off = header["after_name_table_offset"]

    storage_mode = u32(data, off + 0)
    payload_len = u32(data, off + 4)
    payload_off = off + 8

    duration = u32(data, payload_off + 0)
    controlled_node_count = u32(data, payload_off + 4)
    payload_fps = f32(data, payload_off + 8)
    body_off = payload_off + 12

    result: Dict[str, Any] = {
        "file": str(path),
        "file_size": len(data),
        "header": header,
        "container": {
            "storage_mode_observed": storage_mode,
            "payload_len": payload_len,
            "payload_off": payload_off,
            "duration_or_frame_count": duration,
            "controlled_node_count": controlled_node_count,
            "payload_fps": payload_fps,
            "body_off": body_off,
            "payload_len_matches": payload_len == len(data) - payload_off,
            "duration_matches_header": duration == header["frame_count"],
            "node_count_matches_header": controlled_node_count == header["node_count"],
        },
    }

    if storage_mode == 0:
        result["body"] = parse_baked_dense(data, body_off, duration, controlled_node_count)
    elif storage_mode == 1:
        result["body"] = parse_keyed_rotation_sample(data, body_off, duration, controlled_node_count)
    else:
        result["body"] = {"encoding": "unknown", "note": "未在样本中出现的 storage_mode。"}

    return result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("anim")
    ap.add_argument("--json", help="写出完整解析 JSON")
    ap.add_argument("--summary", action="store_true", help="打印摘要")
    ap.add_argument("--dump-frame", type=int, help="baked dense 格式：打印指定帧前 10 个骨骼的记录")
    args = ap.parse_args()

    parsed = parse_anim(args.anim)

    if args.json:
        Path(args.json).write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.summary or not args.json:
        h = parsed["header"]
        c = parsed["container"]
        b = parsed["body"]
        print(f"file: {parsed['file']}")
        print(f"size: {parsed['file_size']}")
        print(f"frames: {h['frame_count']}  fps: {h['fps']}  duration_seconds: {h['frame_count'] / h['fps']:.6f}")
        print(f"nodes: {h['node_count']}  storage_mode: {c['storage_mode_observed']}  encoding: {b.get('encoding')}")
        print(f"payload matches: {c['payload_len_matches']}  body offset: {c['body_off']}")
        if b.get("encoding") == "keyed_rotation_curve_sample":
            print(f"key_count: {b['key_count']}")
            print("times:", b["times_seconds"])
            print("quaternion_xyzw first/last:", b["quaternion_xyzw"][0], b["quaternion_xyzw"][-1])
        elif b.get("encoding") == "baked_dense_pose":
            print(f"record layout: {b['record_layout']}")
            print(f"body size matches: {b['body_size_matches']}")

    if args.dump_frame is not None:
        if parsed["body"].get("encoding") != "baked_dense_pose":
            raise SystemExit("--dump-frame 只支持 baked_dense_pose。")
        data = Path(args.anim).read_bytes()
        h = parsed["header"]
        c = parsed["container"]
        frame = args.dump_frame
        node_count = c["controlled_node_count"]
        body_off = c["body_off"]
        if frame < 0 or frame >= c["duration_or_frame_count"]:
            raise SystemExit("frame 越界。")
        for i, name in enumerate(h["node_names"][:10]):
            off = body_off + (frame * node_count + i) * 40
            vals = struct.unpack_from("<10f", data, off)
            print(i, name, vals)


if __name__ == "__main__":
    main()
