import bpy
from bpy.props import StringProperty, IntProperty, BoolProperty


class TexLinkPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    sp_executable_path: StringProperty(
        name="Substance Painter Executable",
        description="Path to the Substance Painter executable (.exe on Windows)",
        subtype="FILE_PATH",
        default="",
    )

    export_mesh_dir: StringProperty(
        name="Mesh Export Folder",
        description="Folder where FBX files are exported before opening in SP",
        subtype="DIR_PATH",
        default="",
    )

    texture_watch_dir: StringProperty(
        name="Texture Watch Folder",
        description="Folder where Substance Painter exports textures (monitored for changes)",
        subtype="DIR_PATH",
        default="",
    )

    poll_interval: IntProperty(
        name="Poll Interval (s)",
        description="How often Blender checks the texture folder for changes",
        min=1,
        max=60,
        default=5,
    )

    sp_plugins_dir: StringProperty(
        name="SP Plugins Folder",
        description="Substance Painter Python plugins folder (for Deploy SP Plugin). "
                    "Leave empty to use the default Documents location",
        subtype="DIR_PATH",
        default="",
    )

    use_project_folders: BoolProperty(
        name="Use Project Folders",
        description="Export mesh and textures into a TexLink/<MeshName>/ subfolder "
                    "of the saved .blend project. If the project is not saved, a folder "
                    "is created on the Desktop instead",
        default=True,
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "use_project_folders")
        col = layout.column()
        col.enabled = not self.use_project_folders
        col.prop(self, "export_mesh_dir")
        col.prop(self, "texture_watch_dir")
        layout.prop(self, "sp_executable_path")
        layout.prop(self, "poll_interval")
        layout.prop(self, "sp_plugins_dir")


def register():
    bpy.utils.register_class(TexLinkPreferences)


def unregister():
    bpy.utils.unregister_class(TexLinkPreferences)
