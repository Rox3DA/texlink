import bpy
import os

from .. import ADDON_ID
from ..utils import material_builder
from ..utils.material_builder import log, set_last_update
from ..utils.texture_mapper import map_texture_to_slot

# Stato interno del watcher (module-level, persiste tra i timer tick)
_watched_mtimes: dict[str, float] = {}
_is_running = False
# Tiene traccia dei file junk già loggati come ignorati (evita spam nel log)
_ignored_logged: set[str] = set()

SUPPORTED_EXTENSIONS = material_builder.SUPPORTED_EXTENSIONS


def _get_watch_dir(context=None) -> str:
    ctx = context or bpy.context
    # Priorità: scene (impostata dall'export, per-mesh/progetto) → prefs manuale
    wd = getattr(ctx.scene, "texlink_watch_dir", "").strip()
    if wd:
        return wd
    addon_entry = ctx.preferences.addons.get(ADDON_ID)
    if addon_entry:
        return addon_entry.preferences.texture_watch_dir.strip()
    return ""


def _get_poll_interval(context=None) -> float:
    ctx = context or bpy.context
    addon_entry = ctx.preferences.addons.get(ADDON_ID)
    if addon_entry:
        return float(addon_entry.preferences.poll_interval)
    return float(getattr(ctx.scene, "texlink_poll_interval", 5))


def _scan_folder(watch_dir: str) -> dict[str, float]:
    """Return {filepath: mtime} for all supported texture files in watch_dir."""
    result = {}
    try:
        for fname in os.listdir(watch_dir):
            ext = os.path.splitext(fname)[1].lower()
            if ext in SUPPORTED_EXTENSIONS:
                fpath = os.path.join(watch_dir, fname)
                result[fpath] = os.path.getmtime(fpath)
    except OSError:
        pass
    return result


def _poll_texture_folder() -> float | None:
    """Timer callback — returns next interval or None to stop."""
    global _watched_mtimes, _is_running

    if not _is_running:
        return None  # rimuove il timer

    wm = bpy.context.window_manager
    if not getattr(wm, "texlink_watcher_active", False):
        _is_running = False
        return None

    watch_dir = _get_watch_dir()
    if not watch_dir or not os.path.isdir(watch_dir):
        return _get_poll_interval()

    current = _scan_folder(watch_dir)

    changed = []
    for fpath, mtime in current.items():
        if fpath not in _watched_mtimes:
            changed.append(("new", fpath))
        elif mtime != _watched_mtimes[fpath]:
            changed.append(("modified", fpath))

    _watched_mtimes = current

    if changed:
        _process_changes(changed, watch_dir)

    return _get_poll_interval()


def _process_changes(changed: list, watch_dir: str) -> None:
    """Reload recognized textures, ignore junk, then rebuild material once."""
    recognized = False
    for event, fpath in changed:
        fname = os.path.basename(fpath)
        if map_texture_to_slot(fname) is None:
            # Naming non standard: logga una volta sola, poi ignora
            if fname not in _ignored_logged:
                log(f"[IGNORED] {fname} (naming non riconosciuto)")
                _ignored_logged.add(fname)
            continue
        log(f"[{event.upper()}] {fname}")
        print(f"TexLink | {event}: {fpath}")
        material_builder.reload_image(fpath)
        recognized = True

    if not recognized:
        return

    # Build del materiale UNA volta sola sull'oggetto attivo
    obj = bpy.context.active_object
    res = material_builder.build_material(obj, watch_dir)

    if res["warning"]:
        log(f"[WARN] {res['warning']}")
    if res["updated"]:
        log(f"[MATERIAL] aggiornato: {', '.join(res['slots'])}")
        set_last_update()


class TEXLINK_OT_start_watcher(bpy.types.Operator):
    bl_idname = "texlink.start_watcher"
    bl_label = "Start Watcher"
    bl_description = "Start monitoring the texture folder for changes"

    def execute(self, context):
        global _is_running, _watched_mtimes, _ignored_logged

        watch_dir = _get_watch_dir(context)
        if not watch_dir:
            self.report({"ERROR"}, "Texture watch folder not set.")
            return {"CANCELLED"}
        if not os.path.isdir(watch_dir):
            self.report({"ERROR"}, f"Watch folder does not exist: {watch_dir}")
            return {"CANCELLED"}
        # Self-heal: "in esecuzione" solo se il timer è DAVVERO registrato.
        # (Dopo un reinstall/reload il flag può restare stale senza timer attivo.)
        if _is_running and bpy.app.timers.is_registered(_poll_texture_folder):
            self.report({"WARNING"}, "Watcher already running.")
            return {"CANCELLED"}
        if bpy.app.timers.is_registered(_poll_texture_folder):
            try:
                bpy.app.timers.unregister(_poll_texture_folder)
            except Exception:  # noqa: BLE001
                pass

        # Snapshot iniziale — non triggerare reload per file già esistenti
        _watched_mtimes = _scan_folder(watch_dir)
        _ignored_logged = set()
        _is_running = True
        context.window_manager.texlink_watcher_active = True

        interval = _get_poll_interval(context)
        bpy.app.timers.register(_poll_texture_folder, first_interval=interval, persistent=True)

        log(f"Watcher started — {watch_dir} (every {interval:.0f}s)")
        self.report({"INFO"}, f"Watching: {watch_dir}")
        return {"FINISHED"}


class TEXLINK_OT_stop_watcher(bpy.types.Operator):
    bl_idname = "texlink.stop_watcher"
    bl_label = "Stop Watcher"
    bl_description = "Stop monitoring the texture folder"

    def execute(self, context):
        global _is_running
        _is_running = False
        context.window_manager.texlink_watcher_active = False
        log("Watcher stopped.")
        self.report({"INFO"}, "Watcher stopped.")
        return {"FINISHED"}


class TEXLINK_OT_clear_log(bpy.types.Operator):
    bl_idname = "texlink.clear_log"
    bl_label = "Clear Log"
    bl_description = "Clear the event log"

    def execute(self, context):
        context.window_manager.texlink_log.clear()
        return {"FINISHED"}


# --- Log entry property ---

class TexLinkLogEntry(bpy.types.PropertyGroup):
    message: bpy.props.StringProperty()


def register():
    bpy.utils.register_class(TexLinkLogEntry)
    bpy.utils.register_class(TEXLINK_OT_start_watcher)
    bpy.utils.register_class(TEXLINK_OT_stop_watcher)
    bpy.utils.register_class(TEXLINK_OT_clear_log)

    bpy.types.WindowManager.texlink_watcher_active = bpy.props.BoolProperty(
        name="Watcher Active", default=False,
    )
    bpy.types.WindowManager.texlink_log = bpy.props.CollectionProperty(
        type=TexLinkLogEntry,
    )
    bpy.types.WindowManager.texlink_last_update = bpy.props.StringProperty(
        name="Last Update", default="",
    )

    # All'enable il timer non è in esecuzione: allinea la UI (evita "Stop" fantasma).
    # bpy.data è ristretto durante register(): tentativo best-effort.
    global _is_running
    _is_running = False
    try:
        for wm in bpy.data.window_managers:
            wm.texlink_watcher_active = False
    except Exception:  # noqa: BLE001  (bpy.data ristretto durante register)
        pass


def unregister():
    global _is_running
    _is_running = False

    bpy.utils.unregister_class(TEXLINK_OT_clear_log)
    bpy.utils.unregister_class(TEXLINK_OT_start_watcher)
    bpy.utils.unregister_class(TEXLINK_OT_stop_watcher)
    bpy.utils.unregister_class(TexLinkLogEntry)

    del bpy.types.WindowManager.texlink_watcher_active
    del bpy.types.WindowManager.texlink_log
    del bpy.types.WindowManager.texlink_last_update
