import bpy
import os
import shutil

from .. import ADDON_ID


def _default_sp_plugins_dir() -> str:
    return os.path.join(
        os.path.expanduser("~"), "Documents",
        "Adobe", "Adobe Substance 3D Painter", "python", "plugins",
    )


def _bundled_plugin_path() -> str:
    # addon/operators/deploy_sp_plugin.py -> addon/sp_plugin/blender_live_link.py
    here = os.path.dirname(__file__)
    return os.path.normpath(os.path.join(here, "..", "sp_plugin", "blender_live_link.py"))


class TEXLINK_OT_deploy_sp_plugin(bpy.types.Operator):
    bl_idname = "texlink.deploy_sp_plugin"
    bl_label = "Deploy SP Plugin"
    bl_description = (
        "Copy the Substance Painter live-link plugin into SP's plugins folder. "
        "Enable it once from SP's Python menu afterwards."
    )

    def execute(self, context):
        src = _bundled_plugin_path()
        if not os.path.isfile(src):
            self.report({"ERROR"}, f"Bundled plugin not found: {src}")
            return {"CANCELLED"}

        addon_entry = context.preferences.addons.get(ADDON_ID)
        target_dir = (addon_entry.preferences.sp_plugins_dir.strip()
                      if addon_entry else "")
        if not target_dir:
            target_dir = getattr(context.scene, "texlink_sp_plugins_dir", "")
        if not target_dir:
            target_dir = _default_sp_plugins_dir()

        try:
            os.makedirs(target_dir, exist_ok=True)
            dst = os.path.join(target_dir, os.path.basename(src))
            shutil.copy2(src, dst)
        except OSError as e:
            self.report({"ERROR"}, f"Copy failed: {e}")
            return {"CANCELLED"}

        self.report({"INFO"}, f"Plugin deployed: {dst}")
        return {"FINISHED"}


def register():
    bpy.utils.register_class(TEXLINK_OT_deploy_sp_plugin)
    bpy.types.Scene.texlink_sp_plugins_dir = bpy.props.StringProperty(
        name="SP Plugins Dir", subtype="DIR_PATH", default="",
    )


def unregister():
    bpy.utils.unregister_class(TEXLINK_OT_deploy_sp_plugin)
    del bpy.types.Scene.texlink_sp_plugins_dir
