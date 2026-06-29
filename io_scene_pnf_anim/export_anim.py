import bpy
import struct

from bpy.types import Operator
from bpy.props import StringProperty, IntProperty
from bpy_extras.io_utils import ExportHelper
from mathutils import Matrix


WOwS_CONVERT = Matrix((
    (1, 0, 0, 0),
    (0, 0, 1, 0),
    (0, 1, 0, 0),
    (0, 0, 0, 1)
))

# 顶点组名称的默认结尾 (轴为ABC,则对应的顶点组名称为 ABC_BlendBone)
animNode_suffix = "_BlendBone"

class ExportPnFAnim(Operator, ExportHelper):

    bl_idname = "export_scene.pnf_anim"
    bl_label = "Export PnF Animation"

    filename_ext = ".anim"

    filter_glob: StringProperty(
        default="*.anim",
        options={'HIDDEN'}
    )

    start_frame: IntProperty(
        name="Start Frame",
        default=0
    )

    end_frame: IntProperty(
        name="End Frame",
        default=250
    )

    def execute(self, context):

        armature = context.object

        if armature is None:
            self.report({'ERROR'}, "No armature selected")
            return {'CANCELLED'}

        if armature.type != 'ARMATURE':
            self.report({'ERROR'}, "Selected object is not Armature")
            return {'CANCELLED'}

        scene = context.scene
        fps = float(scene.render.fps)

        bones = list(armature.pose.bones)

        frame_count = self.end_frame - self.start_frame + 1

        body = bytearray()

        depsgraph = context.evaluated_depsgraph_get()

        for frame in range(self.start_frame, self.end_frame + 1):

            scene.frame_set(frame)

            arm_eval = armature.evaluated_get(depsgraph)

            for bone in arm_eval.pose.bones:

                if bone.parent:
                    local = (
                        bone.parent.matrix.inverted()
                        @ bone.matrix
                    )
                else:
                    local = bone.matrix.copy()

                local = (
                    WOwS_CONVERT
                    @ local
                    @ WOwS_CONVERT.inverted()
                )

                loc, rot, scale = local.decompose()

                body += struct.pack(
                    "<10f",

                    loc.x,
                    loc.y,
                    loc.z,

                    rot.x,
                    rot.y,
                    rot.z,
                    rot.w,

                    scale.x,
                    scale.y,
                    scale.z
                )

        output = bytearray()

        output += struct.pack("<I", frame_count)
        output += struct.pack("<f", fps)
        output += struct.pack("<f", 0.0)

        output += bytes([0, 0])

        output += struct.pack("<f", 0.001)
        output += struct.pack("<f", 0.03)
        output += struct.pack("<f", 0.01)

        output += bytes([0])

        output += struct.pack("<I", len(bones))

        for bone in bones:

            name = bone.name

            # 去除结尾的 _BlendBone
            # print(name)
            if (animNode_suffix in name):
                name = name[:-len(animNode_suffix)]
                # print(name)

            name = name.encode(
                "ascii",
                errors="ignore"
            )

            output += struct.pack(
                "<I",
                len(name)
            )

            output += name

        payload_len = 12 + len(body)

        output += struct.pack("<I", 0)
        output += struct.pack("<I", payload_len)

        output += struct.pack("<I", frame_count)
        output += struct.pack("<I", len(bones))
        output += struct.pack("<f", fps)

        output += body

        with open(self.filepath, "wb") as f:
            f.write(output)

        self.report(
            {'INFO'},
            f"Exported {frame_count} frames"
        )

        return {'FINISHED'}