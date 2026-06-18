import bpy
import os
import sys
import subprocess

from .. import ADDON_ID


def _watch_dir(context) -> str:
    wd = getattr(context.scene, "texlink_watch_dir", "").strip()
    if wd:
        return wd
    addon_entry = context.preferences.addons.get(ADDON_ID)
    if addon_entry:
        return addon_entry.preferences.texture_watch_dir.strip()
    return ""


class TEXLINK_OT_open_texture_folder(bpy.types.Operator):
    bl_idname = "texlink.open_texture_folder"
    bl_label = "Open Texture Folder"
    bl_description = "Open the monitored texture folder in the system file browser"

    def execute(self, context):
        wd = _watch_dir(context)
        if not wd or not os.path.isdir(wd):
            self.report({"ERROR"}, "Texture folder not set or missing (send a mesh first).")
            return {"CANCELLED"}
        try:
            if sys.platform == "win32":
                os.startfile(wd)  # noqa: S606
            elif sys.platform == "darwin":
                subprocess.Popen(["open", wd])
            else:
                subprocess.Popen(["xdg-open", wd])
        except Exception as e:  # noqa: BLE001
            self.report({"ERROR"}, f"Could not open folder: {e}")
            return {"CANCELLED"}
        return {"FINISHED"}


class TEXLINK_OT_rebuild_material(bpy.types.Operator):
    bl_idname = "texlink.rebuild_material"
    bl_label = "Rebuild Material"
    bl_description = "Reload textures from the folder and rebuild the material now"

    def execute(self, context):
        obj = context.active_object
        if obj is None or obj.type != "MESH":
            self.report({"ERROR"}, "Select a mesh object first.")
            return {"CANCELLED"}

        wd = _watch_dir(context)
        if not wd or not os.path.isdir(wd):
            self.report({"ERROR"}, "Texture folder not set or missing (send a mesh first).")
            return {"CANCELLED"}

        from ..utils import material_builder
        # Ricarica i pixel dai file prima di ricostruire
        for fname in os.listdir(wd):
            if os.path.splitext(fname)[1].lower() in material_builder.SUPPORTED_EXTENSIONS:
                material_builder.reload_image(os.path.join(wd, fname))

        res = material_builder.build_material(obj, wd)
        if res["warning"]:
            self.report({"WARNING"}, res["warning"])
        if res["updated"]:
            self.report({"INFO"}, f"Material rebuilt: {', '.join(res['slots'])}")
        else:
            self.report({"WARNING"}, "No recognized textures found in the folder.")
        return {"FINISHED"}


class TEXLINK_OT_request_sp_export(bpy.types.Operator):
    bl_idname = "texlink.request_sp_export"
    bl_label = "Request Export from SP"
    bl_description = (
        "Ask the Substance Painter plugin to export textures now "
        "(SP must be open with the plugin enabled)"
    )

    def execute(self, context):
        from ..utils import livelink_config
        try:
            n = livelink_config.write_export_request()
        except OSError as e:
            self.report({"ERROR"}, f"Could not write request: {e}")
            return {"CANCELLED"}
        self.report({"INFO"}, f"Export requested from Substance Painter (#{n}).")
        return {"FINISHED"}


def register():
    bpy.utils.register_class(TEXLINK_OT_open_texture_folder)
    bpy.utils.register_class(TEXLINK_OT_rebuild_material)
    bpy.utils.register_class(TEXLINK_OT_request_sp_export)


def unregister():
    bpy.utils.unregister_class(TEXLINK_OT_request_sp_export)
    bpy.utils.unregister_class(TEXLINK_OT_rebuild_material)
    bpy.utils.unregister_class(TEXLINK_OT_open_texture_folder)
