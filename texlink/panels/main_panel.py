import bpy

from .. import ADDON_ID

_CATEGORY = "TexLink"


# ------------------------------------------------------------------
# Shared helpers
# ------------------------------------------------------------------

def _is_dev(context) -> bool:
    """True if the addon is loaded from a script (no formal install)."""
    return context.preferences.addons.get(ADDON_ID) is None


def _use_project(context) -> bool:
    addon_entry = context.preferences.addons.get(ADDON_ID)
    if addon_entry:
        return addon_entry.preferences.use_project_folders
    return getattr(context.scene, "texlink_use_project_folders", True)


# ------------------------------------------------------------------
# Main panel — primary action
# ------------------------------------------------------------------

class TEXLINK_PT_main(bpy.types.Panel):
    bl_label = "TexLink"
    bl_idname = "TEXLINK_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = _CATEGORY

    def draw(self, context):
        layout = self.layout
        obj = context.active_object

        col = layout.column(align=True)
        if obj and obj.type == "MESH":
            col.label(text=obj.name, icon="MESH_DATA")
            if not obj.data.uv_layers:
                col.label(text="Missing UV map", icon="ERROR")
        else:
            col.label(text="No mesh selected", icon="ERROR")

        layout.operator(
            "texlink.export_to_sp",
            text="Send to Substance Painter",
            icon="EXPORT",
        )
        layout.operator(
            "texlink.update_mesh_in_sp",
            text="Update Mesh in SP",
            icon="FILE_REFRESH",
        )

        # Where the files will go
        if _use_project(context):
            if bpy.data.is_saved:
                row = layout.row()
                row.scale_y = 0.8
                row.label(text="Folder: project / TexLink", icon="FILE_FOLDER")
            else:
                warn = layout.box()
                warn.scale_y = 0.85
                warn.label(text="Project not saved", icon="ERROR")
                warn.label(text="Files will be saved to Desktop")


# ------------------------------------------------------------------
# Sub-panel: Texture Update (watcher)
# ------------------------------------------------------------------

class TEXLINK_PT_sync(bpy.types.Panel):
    bl_label = "Texture Update"
    bl_idname = "TEXLINK_PT_sync"
    bl_parent_id = "TEXLINK_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = _CATEGORY

    def draw(self, context):
        layout = self.layout
        wm = context.window_manager
        scene = context.scene
        active = wm.texlink_watcher_active

        row = layout.row(align=True)
        if not active:
            row.operator("texlink.start_watcher", text="Start", icon="PLAY")
        else:
            row.operator("texlink.stop_watcher", text="Stop", icon="PAUSE")

        box = layout.box()
        box.scale_y = 0.85
        box.label(
            text="Active" if active else "Paused",
            icon="RADIOBUT_ON" if active else "RADIOBUT_OFF",
        )
        if active and wm.texlink_last_update:
            box.label(text="Last update: " + wm.texlink_last_update, icon="TIME")
        wd = scene.texlink_watch_dir
        if wd:
            box.label(text="…" + wd[-26:], icon="FILE_FOLDER")
        else:
            box.label(text="Send a mesh first", icon="INFO")

        row = layout.row(align=True)
        row.operator("texlink.rebuild_material", text="Rebuild", icon="NODE_MATERIAL")
        row.operator("texlink.open_texture_folder", text="Folder", icon="FILE_FOLDER")

        layout.operator(
            "texlink.refresh_cycles",
            text="Refresh Cycles View",
            icon="FILE_REFRESH",
        )

        # Trigger bidirezionale: chiedi a SP di esportare + stato di SP
        layout.separator()
        layout.operator(
            "texlink.request_sp_export",
            text="Request Export from SP",
            icon="IMPORT",
        )
        from ..utils import livelink_config
        status = livelink_config.read_sp_status()
        if status:
            sub = layout.column()
            sub.scale_y = 0.8
            state = status.get("state", "?")
            icon = "RADIOBUT_ON" if state in ("ready", "exported") else "RADIOBUT_OFF"
            sub.label(text="SP: " + state + " (" + status.get("last_export", "") + ")", icon=icon)


# ------------------------------------------------------------------
# Sub-panel: Activity Log
# ------------------------------------------------------------------

class TEXLINK_PT_log(bpy.types.Panel):
    bl_label = "Activity Log"
    bl_idname = "TEXLINK_PT_log"
    bl_parent_id = "TEXLINK_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = _CATEGORY
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        wm = context.window_manager

        header = layout.row()
        header.operator("texlink.clear_log", text="Clear log", icon="TRASH")

        if len(wm.texlink_log) == 0:
            layout.label(text="No events.", icon="INFO")
            return
        col = layout.column(align=True)
        col.scale_y = 0.8
        for entry in reversed(wm.texlink_log):
            col.label(text=entry.message)


# ------------------------------------------------------------------
# Sub-panel: Substance Painter Plugin
# ------------------------------------------------------------------

class TEXLINK_PT_plugin(bpy.types.Panel):
    bl_label = "Substance Painter Plugin"
    bl_idname = "TEXLINK_PT_plugin"
    bl_parent_id = "TEXLINK_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = _CATEGORY
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        info = layout.column(align=True)
        info.scale_y = 0.8
        info.label(text="Auto-export textures")
        info.label(text="directly from Substance Painter.")

        layout.operator(
            "texlink.deploy_sp_plugin",
            text="Install plugin in Substance Painter",
            icon="PLUGIN",
        )
        if _is_dev(context):
            layout.prop(scene, "texlink_sp_plugins_dir", text="SP plugins folder")


# ------------------------------------------------------------------
# Sub-panel: Settings
# ------------------------------------------------------------------

class TEXLINK_PT_settings(bpy.types.Panel):
    bl_label = "Settings"
    bl_idname = "TEXLINK_PT_settings"
    bl_parent_id = "TEXLINK_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = _CATEGORY
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        is_dev = _is_dev(context)
        use_project = _use_project(context)

        if is_dev:
            layout.prop(scene, "texlink_use_project_folders", text="Use project folders")
            layout.prop(scene, "texlink_sp_exe", text="Substance Painter (.exe)")
            layout.prop(scene, "texlink_poll_interval", text="Check interval (s)")
            if not use_project:
                box = layout.box()
                box.label(text="Manual folders:", icon="FILE_FOLDER")
                box.prop(scene, "texlink_export_dir", text="Mesh")
                box.prop(scene, "texlink_watch_dir", text="Texture")
        else:
            layout.operator(
                "preferences.addon_show",
                text="Open Addon Preferences",
                icon="PREFERENCES",
            ).module = ADDON_ID


# ------------------------------------------------------------------
# Scene properties + registration
# ------------------------------------------------------------------

_CLASSES = (
    TEXLINK_PT_main,
    TEXLINK_PT_sync,
    TEXLINK_PT_log,
    TEXLINK_PT_plugin,
    TEXLINK_PT_settings,
)


def _register_scene_props():
    bpy.types.Scene.texlink_sp_exe = bpy.props.StringProperty(
        name="SP Executable", subtype="FILE_PATH", default="",
    )
    bpy.types.Scene.texlink_export_dir = bpy.props.StringProperty(
        name="Export Directory", subtype="DIR_PATH", default="",
    )
    bpy.types.Scene.texlink_watch_dir = bpy.props.StringProperty(
        name="Watch Directory", subtype="DIR_PATH", default="",
    )
    bpy.types.Scene.texlink_poll_interval = bpy.props.IntProperty(
        name="Poll Interval", min=1, max=60, default=5,
    )
    bpy.types.Scene.texlink_use_project_folders = bpy.props.BoolProperty(
        name="Use Project Folders", default=True,
    )


def _unregister_scene_props():
    del bpy.types.Scene.texlink_sp_exe
    del bpy.types.Scene.texlink_export_dir
    del bpy.types.Scene.texlink_watch_dir
    del bpy.types.Scene.texlink_poll_interval
    del bpy.types.Scene.texlink_use_project_folders


def register():
    _register_scene_props()
    for cls in _CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)
    _unregister_scene_props()
