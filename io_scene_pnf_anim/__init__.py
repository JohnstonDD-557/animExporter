bl_info = {
    "name": "PnF/WoWS Animation Exporter",
    "author": "OpenAI",
    "version": (0, 0, 1),
    "blender": (5, 0, 0),
    "location": "File > Export > PnF Animation (.anim)",
    "category": "Import-Export",
}

import bpy
from .export_anim import ExportPnFAnim


def menu_func_export(self, context):
    self.layout.operator(
        ExportPnFAnim.bl_idname,
        text="PnF Animation (.anim)"
    )


def register():
    bpy.utils.register_class(ExportPnFAnim)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)


def unregister():
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)
    bpy.utils.unregister_class(ExportPnFAnim)