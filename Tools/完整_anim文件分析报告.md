# `.anim` 文件完整反推分析报告

> 分析对象：`PnF_Template_Files.zip` 中的 4 个 `.anim` 文件：`Rotation_Z_15rpm.anim`、`Rotation2rpm.anim`、`JM6031_ARP2024_Iona.anim`、`JM6032_ARP2024_Yamato.anim`。  
> 说明：用户口述为 `.anime`，压缩包内实际文件扩展名为 `.anim`。以下均按 `.anim` 分析。

## 1. 样本总览

| 文件 | 大小 bytes | 帧数 | FPS | 时长秒 | 节点/骨骼数 | storage_mode | 已识别编码 |
|---|---:|---:|---:|---:|---:|---:|---|
| `Rotation_Z_15rpm.anim` | 242 | 120 | 30.0 | 4.000000 | 1 | 1 | `keyed_rotation_curve_sample` |
| `Rotation2rpm.anim` | 362 | 901 | 30.0 | 30.033333 | 1 | 1 | `keyed_rotation_curve_sample` |
| `JM6031_ARP2024_Iona.anim` | 718459 | 206 | 30.0 | 6.866667 | 87 | 0 | `baked_dense_pose` |
| `JM6032_ARP2024_Yamato.anim` | 990653 | 281 | 30.0 | 9.366667 | 88 | 0 | `baked_dense_pose` |

结论：当前样本至少存在两类 `.anim` 存储方式：

1. `storage_mode = 0`：逐帧烘焙姿态数据。每帧、每节点固定 40 bytes，即 10 个 float32，字段为 `tx, ty, tz, qx, qy, qz, qw, sx, sy, sz`。这是大文件 `JM6031`、`JM6032` 使用的格式。
2. `storage_mode = 1`：关键帧旋转曲线数据。当前两个小文件都是单骨骼单旋转通道，包含关键帧时间数组和四元数数组。尾部 34 bytes 仍有未完全命名字段，但主旋转曲线可稳定解析。

## 2. 全局文件头结构

所有样本共享相同的全局文件头。字节序为 little-endian。

| 相对偏移 | 类型 | 字段名 | 样本值/说明 |
|---:|---|---|---|
| `0x00` | `uint32` | `frame_count` | 动画帧数/持续帧数。例：`120`、`901`、`206`、`281`。 |
| `0x04` | `float32` | `fps` | 当前样本均为 `30.0`。 |
| `0x08` | `float32` | `start_time_or_zero` | 当前样本均为 `0.0`。 |
| `0x0C` | `uint8` | `flag_a` | 小旋转文件为 `1`，逐帧烘焙文件为 `0`。 |
| `0x0D` | `uint8` | `flag_b` | 小旋转文件为 `1`，逐帧烘焙文件为 `0`。 |
| `0x0E` | `float32` | `epsilon_or_tolerance_1` | 当前样本均为约 `0.001`。疑似压缩/误差容差。 |
| `0x12` | `float32` | `epsilon_or_tolerance_2` | 当前样本均为约 `0.03`。疑似压缩/误差容差。 |
| `0x16` | `float32` | `epsilon_or_tolerance_3` | 当前样本均为约 `0.01`。疑似压缩/误差容差。 |
| `0x1A` | `uint8` | `zero_byte` | 当前样本均为 `0`。 |
| `0x1B` | `uint32` | `node_count` | 节点/骨骼名数量。注意这里是非 4 字节对齐偏移。 |
| `0x1F` 起 | `node_name[]` | 节点名表 | 每项为 `uint32 name_len + ASCII bytes`，无 `\0` 结尾。 |

节点名表结构：

```c
for i in range(node_count):
    uint32 name_len;
    char name[name_len];  // ASCII, no null terminator
```

## 3. 节点名表后的容器头

节点名表结束后紧接容器头：

| 类型 | 字段名 | 说明 |
|---|---|---|
| `uint32` | `storage_mode` | 已见 `0` 与 `1`。`0` = 逐帧烘焙姿态；`1` = 关键帧曲线。 |
| `uint32` | `payload_len` | 从后续 `payload_off` 到文件末尾的总字节数。验证公式：`payload_len == file_size - payload_off`。 |
| `uint32` | `duration_or_frame_count` | 与全局 `frame_count` 一致。 |
| `uint32` | `controlled_node_count` | 与全局 `node_count` 一致。 |
| `float32` | `payload_fps` | 与全局 `fps` 一致，当前为 `30.0`。 |
| ... | `body` | 根据 `storage_mode` 进入不同数据体。 |

伪代码：

```python
storage_mode = read_u32()
payload_len = read_u32()
payload_off = current_offset

duration = read_u32()
controlled_node_count = read_u32()
payload_fps = read_f32()

body_off = current_offset
```

## 4. `storage_mode = 0`：逐帧烘焙姿态格式

这是 `JM6031_ARP2024_Iona.anim` 与 `JM6032_ARP2024_Yamato.anim` 的格式。此格式已经可以完整解析。

### 4.1 数据体大小公式

```text
body_bytes = duration * controlled_node_count * 40
```

验证：

| 文件 | duration | node_count | 公式计算 | 实际 body bytes | 是否一致 |
|---|---:|---:|---:|---:|---|
| `JM6031_ARP2024_Iona.anim` | 206 | 87 | 716880 | 716880 | 是 |
| `JM6032_ARP2024_Yamato.anim` | 281 | 88 | 989120 | 989120 | 是 |

### 4.2 单条记录结构

每条记录 40 bytes，等于 10 个 little-endian float32：

```c
struct PoseRecord {
    float tx;
    float ty;
    float tz;
    float qx;
    float qy;
    float qz;
    float qw;
    float sx;
    float sy;
    float sz;
};
```

字段意义：

| 字段 | 含义 |
|---|---|
| `tx, ty, tz` | 该节点当前帧的局部位移。 |
| `qx, qy, qz, qw` | 该节点当前帧的局部旋转四元数，顺序为 `xyzw`。四元数模长在样本中接近 1。 |
| `sx, sy, sz` | 该节点当前帧的局部缩放。多数接近 `1,1,1`。 |

### 4.3 记录排列顺序

排列顺序是 frame-major：

```python
for frame in range(duration):
    for node_index in range(controlled_node_count):
        PoseRecord
```

也就是第 `frame` 帧第 `node_index` 个节点记录偏移：

```python
record_off = body_off + (frame * controlled_node_count + node_index) * 40
```

### 4.4 样本首帧记录

`JM6031_ARP2024_Iona.anim` 首帧前 3 个节点：

```text
node 0 root:
  T = (0.0, 0.0, 0.0)
  Q = (0.70710683, 0.0, 0.0, 0.70710671)
  S = (1.0, 1.0, 1.0)

node 1 Root:
  T = (0.0, 0.0, 0.0)
  Q = (0.50000006, 0.49999994, 0.5, 0.5)
  S = (1.0, 1.0, 1.0)

node 2 arm_stretch.l:
  T = (0.10533856, -0.00190091, 0.00932881)
  Q = (0.03747708, -0.69642550, 0.69775605, 0.16347311)
  S = (1.00000024, 1.00000012, 0.99999988)
```

## 5. `storage_mode = 1`：关键帧旋转曲线格式

这是 `Rotation_Z_15rpm.anim` 与 `Rotation2rpm.anim` 的格式。当前样本均为单节点、单旋转通道。

### 5.1 当前样本可验证的数据体布局

在 `body_off` 处开始：

| 相对 `body_off` 偏移 | 类型 | 字段 | 样本值/说明 |
|---:|---|---|---|
| `+0x00` | `uint32` | `channel_count` | 当前样本为 `1`。 |
| `+0x04` | `uint32` | `constant_48` | 当前样本为 `48`，疑似通道头/块头相关常量。 |
| `+0x08` | `uint32` | `value_class` | 当前样本为 `2`。疑似表示旋转曲线/四元数类。 |
| `+0x0C` | `uint32` | `data_block_len` | `Rotation_Z` 为 `157`，`Rotation2rpm` 为 `277`。与关键帧数线性相关。 |
| `+0x10` | `uint32` | `unknown_a` | 当前样本为 `1`。 |
| `+0x14` | `uint32` | `bone_index` | 当前样本为 `0`，对应唯一节点。 |
| `+0x18` | `uint32` | `transform_channel` | 当前样本为 `2`，高度疑似 rotation channel。 |
| `+0x1C` | `uint32` | `unknown_b` | 当前样本为 `0`。 |
| `+0x20` | `uint32` | `value_code` | 当前样本为 `17`，疑似四元数/值类型代码。 |
| `+0x24` | `uint32` | `unknown_c` | 当前样本为 `1`。 |
| `+0x28` | `uint8` | `unknown_byte` | 当前样本为 `0`。 |
| `+0x29` | `uint32` | `key_count` | `Rotation_Z` 为 `5`，`Rotation2rpm` 为 `11`。注意这里是非 4 字节对齐。 |
| `+0x2D` | `float32[key_count]` | `key_times_seconds` | 关键帧时间，单位已确认是秒。 |
| 后续 | `float32[key_count][4]` | `quaternion_xyzw` | 每个关键帧一个四元数，顺序 `x,y,z,w`。 |
| 后续 | `34 bytes` | `tail` | 当前两个样本均为 34 bytes；疑似静态位移/缩放或默认值块，语义未完全确认。 |

### 5.2 关键帧时间单位

时间数组单位是秒，不是帧。证明：

`Rotation_Z_15rpm.anim`：

- 全局帧数 `120`
- FPS `30`
- 时长 `120 / 30 = 4.0s`
- 最后关键帧时间 `3.9666669s`，约等于第 119 帧时间 `119 / 30 = 3.9666667s`

`Rotation2rpm.anim`：

- 全局帧数 `901`
- FPS `30`
- 时长 `901 / 30 = 30.033333s`
- 最后关键帧时间 `30.0000019s`

### 5.3 四元数顺序

四元数顺序为 `x, y, z, w`。理由：

1. 四元数模长接近 1。
2. `Rotation_Z_15rpm.anim` 的有效旋转分量集中在 `z` 与 `w`。
3. `Rotation2rpm.anim` 的有效旋转分量集中在 `y` 与 `w`。
4. 与文件名 `Rotate_Z`、`Rotate_Y` 相互对应。

`Rotation_Z_15rpm.anim` 关键帧：

| index | time 秒 | qx | qy | qz | qw | 单轴角度观测 |
|---:|---:|---:|---:|---:|---:|---:|
| 0 | 0.000000 | -0.000000 | 0.000000 | 0.026177 | 0.999657 | 约 3° |
| 1 | 1.200000 | 0.000000 | 0.000000 | 0.824126 | 0.566406 | 约 111° |
| 2 | 2.400000 | 0.000000 | 0.000000 | 0.942641 | -0.333807 | 约 219° |
| 3 | 3.000000 | -0.000000 | 0.000000 | -0.688355 | 0.725374 | 约 -87° / 273° |
| 4 | 3.966667 | -0.000000 | 0.000000 | -0.000000 | 1.000000 | 约 0° / 360° |

`Rotation2rpm.anim` 关键帧时间：

```text
0.000000
5.866667
6.366667
6.700000
8.666667
18.666668
19.433334
21.733334
22.533335
23.600000
30.000002
```

### 5.4 尾部 34 bytes 的当前判断

当前两个关键帧样本在四元数数组之后都剩余 34 bytes。尾部与旋转主曲线无关，因为删除/误读不会影响上文关键帧时间和四元数数组的完整性判断。它更可能是：

- 静态 translation / scale 默认值块；
- 通道结束标记；
- 插值、循环或额外常量；
- 上述几项的混合结构。

目前只有两个单旋转通道样本，无法严谨命名这 34 bytes。可以解析并保留原样，编辑器写回时应原样复制，避免破坏兼容性。

## 6. 两种格式的用途判断

### 6.1 逐帧烘焙格式适合角色/复杂骨骼动画

`JM6031`、`JM6032` 这类文件记录了每一帧每个骨骼的完整 TRS，因此读取简单、体积较大、对复杂动作兼容性强。

优点：
- 解析稳定；
- 不需要插值曲线求值；
- 可直接转成逐帧骨骼姿态。

缺点：
- 文件体积较大；
- 修改局部动作需要重写大量记录。

### 6.2 关键帧曲线格式适合简单部件旋转

`Rotation_Z_15rpm.anim`、`Rotation2rpm.anim` 只记录关键帧时间和旋转四元数，更像部件旋转动画。

优点：
- 体积小；
- 修改转速只需要重算关键帧时间/四元数；
- 对 `seq` 调用部件旋转很合适。

缺点：
- 当前样本不足以覆盖多通道、多骨骼、位移/缩放曲线；
- 尾部字段未完全命名，写回时应保留。

## 7. 修改/生成建议

### 7.1 如果要生成复杂骨骼动画

建议优先生成 `storage_mode = 0` 烘焙格式，因为结构已完全确认：

```python
for frame in range(frame_count):
    for node in node_names:
        write_float32(tx, ty, tz)
        write_float32(qx, qy, qz, qw)
        write_float32(sx, sy, sz)
```

必须保证：

```text
payload_len = 12 + frame_count * node_count * 40
file_size = header_and_name_table + 8 + payload_len
```

其中 `12` 是 payload 内部的 `duration + node_count + fps`。

### 7.2 如果要生成简单单轴旋转动画

可以基于 `Rotation_Z_15rpm.anim` / `Rotation2rpm.anim` 改写：

1. 保留文件头、节点名表、通道头和尾部。
2. 修改 `frame_count`、payload 内部 `duration`。
3. 修改关键帧数量 `key_count`。
4. 写入 `float32[key_count]` 时间数组，单位秒。
5. 写入 `float32[key_count][4]` 四元数数组，顺序 `x,y,z,w`。
6. 同步更新 `data_block_len` 与 `payload_len`。

当前样本中单旋转通道的长度规律：

```text
data_block_len = 57 + key_count * 20
payload_len    = file_size - payload_off
```

其中每个关键帧消耗：

```text
time: 4 bytes
quaternion: 16 bytes
合计: 20 bytes/key
```

这个规律已在 5 关键帧和 11 关键帧两个样本上验证。

## 8. 骨骼/节点差异摘要

`JM6031_ARP2024_Iona.anim`：
- `node_count = 87`
- `duration = 206`
- body 为 `206 * 87 * 40 = 716880 bytes`

`JM6032_ARP2024_Yamato.anim`：
- `node_count = 88`
- `duration = 281`
- body 为 `281 * 88 * 40 = 989120 bytes`

两者骨骼表不完全一致。`JM6032` 比 `JM6031` 多 `spine_03.x`，且若干 `c_kilt_*` 名称不同。因此跨文件套用动画时，不能只按骨骼名数量硬套；应以节点名表做映射，缺失节点用默认姿态或跳过。

## 9. 当前仍不应强行命名的字段

以下字段可以稳定读取，但语义暂不应武断命名：

| 字段 | 当前观测 | 建议 |
|---|---|---|
| `flag_a / flag_b` | 烘焙格式为 `0,0`，关键帧格式为 `1,1` | 暂称 flags，不要直接等同于 storage_mode。 |
| `epsilon_or_tolerance_1/2/3` | 固定约 `0.001, 0.03, 0.01` | 疑似压缩误差或导出参数。 |
| `storage_mode=1` 下的 `constant_48` | 当前为 `48` | 疑似块头尺寸或常量。 |
| `storage_mode=1` 下的 `value_class/transform_channel/value_code` | 当前为 `2/2/17` | 很可能表示旋转四元数通道，但需更多样本验证。 |
| `storage_mode=1` 尾部 `34 bytes` | 当前两个样本均存在 | 写回时原样保留。 |

## 10. 已附带解析器

本报告附带 `anim_parser.py`，可直接解析当前样本并输出 JSON 摘要。

常用命令：

```bash
python anim_parser.py Rotation_Z_15rpm.anim --summary
python anim_parser.py JM6031_ARP2024_Iona.anim --summary
python anim_parser.py JM6031_ARP2024_Iona.anim --json iona.json
python anim_parser.py JM6031_ARP2024_Iona.anim --dump-frame 0
```

解析器输出的 `anim_summary.json` 已包含本次 4 个样本的结构化结果。

## 11. 核心结论

1. `.anim` 文件不是 XML，也不是普通文本，而是 little-endian 二进制动画数据。
2. 开头第一个 `uint32` 不是随机编号，而是帧数/持续帧数。
3. `00 00 F0 41` 是 `float32 30.0`，表示 FPS。
4. 节点名表是 `uint32 长度 + ASCII 名称` 的数组。
5. 大型角色动画采用逐帧烘焙 TRS，每节点每帧 40 bytes。
6. 小型旋转动画采用关键帧时间 + 四元数曲线，时间单位为秒，四元数顺序为 `xyzw`。
7. 对复杂角色动画，当前最稳妥的生成/编辑路径是 `storage_mode = 0` 烘焙格式。
8. 对简单旋转动画，可以编辑 `storage_mode = 1` 的时间数组与四元数数组，但尾部 34 bytes 建议原样保留。
