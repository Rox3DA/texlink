import bpy
import os
import subprocess

from .. import ADDON_ID


def _get_prefs(context):
    return context.preferences.addons.get(ADDON_ID)


def _export_fbx(context, fbx_path):
    """Esporta l'oggetto attivo come FBX (scala/tangenti adatte a SP)."""
    obj = context.active_object
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.ops.export_scene.fbx(
        filepath=fbx_path,
        use_selection=True,
        apply_scale_options="FBX_SCALE_ALL",
        use_space_transform=True,
        bake_space_transform=False,
        object_types={"MESH"},
        use_mesh_modifiers=True,
        mesh_smooth_type="FACE",
        use_tspace=True,
        add_leaf_bones=False,
        path_mode="COPY",
    )


def prepare_export(op, context):
    """Risolve le cartelle, esporta l'FBX, scrive la config e punta il watcher.
    NON lancia SP. Ritorna (fbx_path, mesh_name) o None (con report di errore su op)."""
    from ..utils import livelink_config

    addon_entry = context.preferences.addons.get(ADDON_ID)
    prefs = addon_entry.preferences if addon_entry else None
    scene = context.scene

    obj = context.active_object
    if obj is None or obj.type != "MESH":
        op.report({"ERROR"}, "Select a mesh object before exporting.")
        return None
    mesh_name = bpy.path.clean_name(obj.name)

    # Garantisce un materiale: il nome del materiale = nome del texture set in SP.
    # Senza materiali SP userebbe "DefaultMaterial" → lo creiamo esplicitamente così il
    # nome resta stabile e il reload mesh di SP non perde il painting.
    if not obj.data.materials:
        mat = bpy.data.materials.get("DefaultMaterial") or bpy.data.materials.new("DefaultMaterial")
        obj.data.materials.append(mat)

    use_project = (prefs.use_project_folders if prefs
                   else getattr(scene, "texlink_use_project_folders", True))

    if use_project:
        paths = livelink_config.resolve_project_paths(obj.name)
        export_dir, watch_dir = paths["mesh_dir"], paths["texture_dir"]
        if paths["on_desktop"]:
            op.report({"WARNING"},
                      "Progetto non salvato: uso Desktop/TexLink. "
                      "Salva il .blend per tenere i file col progetto.")
    else:
        export_dir = ((prefs.export_mesh_dir if prefs else "").strip()
                      or getattr(scene, "texlink_export_dir", ""))
        watch_dir = ((prefs.texture_watch_dir if prefs else "").strip()
                     or getattr(scene, "texlink_watch_dir", ""))
        if not export_dir:
            op.report({"ERROR"}, "Cartella export non impostata (o attiva 'Use Project Folders').")
            return None

    try:
        os.makedirs(export_dir, exist_ok=True)
        if watch_dir:
            os.makedirs(watch_dir, exist_ok=True)
    except OSError as e:
        op.report({"ERROR"}, f"Impossibile creare le cartelle: {e}")
        return None

    fbx_path = os.path.join(export_dir, mesh_name + ".fbx")
    try:
        _export_fbx(context, fbx_path)
    except Exception as e:  # noqa: BLE001
        op.report({"ERROR"}, f"FBX export failed: {e}")
        return None
    op.report({"INFO"}, f"Exported: {fbx_path}")

    if watch_dir:
        scene.texlink_watch_dir = watch_dir
        try:
            livelink_config.write_config(watch_dir, mesh_name, mesh_path=fbx_path)
        except OSError as e:
            op.report({"WARNING"}, f"Could not write SP config: {e}")

    return fbx_path, mesh_name


class TEXLINK_OT_export_to_sp(bpy.types.Operator):
    bl_idname = "texlink.export_to_sp"
    bl_label = "Send to Substance Painter"
    bl_description = "Export selected mesh as FBX and open it in Substance Painter"

    def execute(self, context):
        prefs = _get_prefs(context)
        prefs = prefs.preferences if prefs else None
        sp_exe = ((prefs.sp_executable_path if prefs else "").strip()
                  or getattr(context.scene, "texlink_sp_exe", ""))

        if sp_exe and not os.path.isfile(sp_exe):
            self.report({"ERROR"}, f"Substance Painter executable not found: {sp_exe}")
            return {"CANCELLED"}
        if not sp_exe:
            self.report({"WARNING"}, "SP path non impostato — FBX esportato ma SP non si apre.")

        res = prepare_export(self, context)
        if res is None:
            return {"CANCELLED"}
        fbx_path, _ = res

        if not self._launch_sp(sp_exe, fbx_path):
            return {"CANCELLED"}
        return {"FINISHED"}

    def _launch_sp(self, sp_exe, fbx_path):
        if not sp_exe:
            return True
        try:
            if os.name == "nt":
                subprocess.Popen(
                    [sp_exe, "--mesh", fbx_path],
                    creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
                )
            else:
                subprocess.Popen([sp_exe, "--mesh", fbx_path])
            self.report({"INFO"}, "Substance Painter launched.")
            return True
        except Exception as e:  # noqa: BLE001
            self.report({"ERROR"}, f"Failed to launch Substance Painter: {e}")
            return False


class TEXLINK_OT_update_mesh_in_sp(bpy.types.Operator):
    bl_idname = "texlink.update_mesh_in_sp"
    bl_label = "Update Mesh in SP"
    bl_description = (
        "Re-export the FBX and ask Substance Painter to reload the geometry, "
        "keeping the existing paint work"
    )

    def execute(self, context):
        from ..utils import livelink_config

        res = prepare_export(self, context)
        if res is None:
            return {"CANCELLED"}

        try:
            n = livelink_config.write_mesh_reload_request()
        except OSError as e:
            self.report({"ERROR"}, f"Could not write mesh-reload request: {e}")
            return {"CANCELLED"}
        self.report({"INFO"}, f"Mesh reload requested in Substance Painter (#{n}).")
        return {"FINISHED"}


def register():
    bpy.utils.register_class(TEXLINK_OT_export_to_sp)
    bpy.utils.register_class(TEXLINK_OT_update_mesh_in_sp)


def unregister():
    bpy.utils.unregister_class(TEXLINK_OT_update_mesh_in_sp)
    bpy.utils.unregister_class(TEXLINK_OT_export_to_sp)
