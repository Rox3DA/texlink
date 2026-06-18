"""
Blender TexLink — plugin lato Substance Painter (auto-export integrato).

Installazione: copiare in
    Documents/Adobe/Adobe Substance 3D Painter/python/plugins/
e abilitarlo dal menu Python di Substance Painter.
(L'addon Blender lo copia automaticamente con "Install plugin in Substance Painter".)

Funzioni:
- Legge ~/.texlink/config.json (scritto da Blender): cartella texture, nome mesh.
- Pannello con: preset, formato, bit depth, risoluzione, auto-export a timer (on/off),
  export al salvataggio (opzione), "Export Now", e stato (mesh + cartella di destinazione).
- Esporta partendo da un preset, riscrivendo i nomi in "<NomeMesh>_<TextureSet>_<Canale>".

Testato contro l'API di Substance 3D Painter 12.0.3 (PySide6).
"""
import os
import json
import re
from datetime import datetime

import PySide6.QtWidgets as QtWidgets
import PySide6.QtCore as QtCore

import substance_painter.ui as spui
import substance_painter.export as spexport
import substance_painter.project as spproject
import substance_painter.textureset as sptextureset
import substance_painter.logging as splog
import substance_painter.event as spevent

_CFG_DIR = os.path.join(os.path.expanduser("~"), ".texlink")
CONFIG_PATH = os.path.join(_CFG_DIR, "config.json")
REQUEST_PATH = os.path.join(_CFG_DIR, "export_request.json")
MESH_RELOAD_PATH = os.path.join(_CFG_DIR, "mesh_reload_request.json")
STATUS_PATH = os.path.join(_CFG_DIR, "sp_status.json")
DEFAULT_PRESET = "PBR Metallic Roughness"
LIVE_PRESET_NAME = "Blender Live Link"

_FORMATS = ["png", "tga", "tiff", "jpeg", "exr"]
_BITDEPTHS = ["8", "16"]
# etichetta -> sizeLog2 (None = risoluzione del documento)
_RESOLUTIONS = {"Document": None, "512": 9, "1024": 10, "2048": 11, "4096": 12}

_CHANNEL_KEYWORDS = [
    "BaseColor", "Roughness", "Metallic", "Normal",
    "Height", "Displacement", "Emissive", "AmbientOcclusion", "Opacity",
]

_plugin = None


def _log(msg):
    splog.info(f"[Blender Live Link] {msg}")


def _read_config():
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def _clean_map_keyword(file_name: str):
    for kw in _CHANNEL_KEYWORDS:
        if re.search(kw, file_name, re.IGNORECASE):
            return kw
    return None


class BlenderLiveLink:
    def __init__(self):
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self._on_timer)
        self._dirty = True
        self._exporting = False
        self._scheduled = False
        # Trigger bidirezionale: polling delle richieste da Blender (export + reload mesh)
        self._last_request = self._read_counter(REQUEST_PATH)
        self._last_mesh_reload = self._read_counter(MESH_RELOAD_PATH)
        self._reloading = False
        self.req_timer = QtCore.QTimer()
        self.req_timer.timeout.connect(self._poll_request)
        self.req_timer.start(1500)
        self.widget = None
        self.dock = None
        self._build_ui()
        self._write_status("ready")
        # Traccia modifiche (painting + struttura layer) per esportare solo se serve
        self._change_events = (spevent.TextureStateEvent, spevent.LayerStacksModelDataChanged)
        for ev in self._change_events:
            try:
                spevent.DISPATCHER.connect(ev, self._on_changed)
            except Exception as e:  # noqa: BLE001
                _log(f"connect {ev.__name__} fallito: {e}")
        self._refresh_status()

    # ---------------- UI ----------------

    def _build_ui(self):
        self.widget = QtWidgets.QWidget()
        self.widget.setWindowTitle("Blender Live Link")
        layout = QtWidgets.QVBoxLayout(self.widget)

        form = QtWidgets.QFormLayout()
        self.cmb_preset = QtWidgets.QComboBox()
        self._populate_presets()
        form.addRow("Preset:", self.cmb_preset)

        self.cmb_format = QtWidgets.QComboBox()
        self.cmb_format.addItems(_FORMATS)
        form.addRow("Format:", self.cmb_format)

        self.cmb_depth = QtWidgets.QComboBox()
        self.cmb_depth.addItems(_BITDEPTHS)
        form.addRow("Bit depth:", self.cmb_depth)

        self.cmb_res = QtWidgets.QComboBox()
        self.cmb_res.addItems(list(_RESOLUTIONS.keys()))
        form.addRow("Resolution:", self.cmb_res)
        layout.addLayout(form)

        self.chk_auto = QtWidgets.QCheckBox("Auto-export (timer)")
        self.chk_auto.toggled.connect(self._on_toggle_auto)
        layout.addWidget(self.chk_auto)

        row = QtWidgets.QHBoxLayout()
        row.addWidget(QtWidgets.QLabel("Interval (s):"))
        self.spin_interval = QtWidgets.QSpinBox()
        self.spin_interval.setRange(1, 300)
        self.spin_interval.setValue(5)
        self.spin_interval.valueChanged.connect(self._on_interval_changed)
        row.addWidget(self.spin_interval)
        layout.addLayout(row)

        self.btn_export = QtWidgets.QPushButton("Export Now")
        self.btn_export.clicked.connect(self._on_export_now)
        layout.addWidget(self.btn_export)

        self.lbl_status = QtWidgets.QLabel()
        self.lbl_status.setWordWrap(True)
        layout.addWidget(self.lbl_status)

        layout.addStretch()
        self.dock = spui.add_dock_widget(self.widget)

    def _populate_presets(self):
        self.cmb_preset.clear()
        names = []
        try:
            names = [p.resource_id.name for p in spexport.list_resource_export_presets()]
        except Exception as e:  # noqa: BLE001
            _log(f"lista preset fallita: {e}")
        if not names:
            names = [DEFAULT_PRESET]
        self.cmb_preset.addItems(names)
        if DEFAULT_PRESET in names:
            self.cmb_preset.setCurrentText(DEFAULT_PRESET)

    def _set_status(self, text):
        cfg = _read_config()
        target = cfg.get("export_path") if cfg else "(config Blender non trovata)"
        mesh = cfg.get("mesh_name") if cfg else "?"
        self.lbl_status.setText(f"Mesh: {mesh}\nCartella: {target}\n{text}")
        _log(text)

    def _refresh_status(self):
        self._set_status("Pronto.")

    # ---------------- Slots ----------------

    def _on_toggle_auto(self, checked):
        if checked:
            self.timer.start(self.spin_interval.value() * 1000)
            self._set_status(f"Auto-export ON (ogni {self.spin_interval.value()}s)")
        else:
            self.timer.stop()
            self._set_status("Auto-export OFF")

    def _on_interval_changed(self, value):
        if self.timer.isActive():
            self.timer.start(value * 1000)

    def _on_changed(self, *args):
        self._dirty = True

    def _on_timer(self):
        if self._dirty:
            self.export()

    # ---------------- Trigger bidirezionale ----------------

    def _read_counter(self, path) -> int:
        try:
            with open(path, encoding="utf-8") as f:
                return int(json.load(f).get("counter", 0))
        except (OSError, json.JSONDecodeError, ValueError):
            return 0

    def _poll_request(self):
        # Export richiesto da Blender
        counter = self._read_counter(REQUEST_PATH)
        if counter > self._last_request:
            self._last_request = counter
            self.export(force=True)
        # Reload mesh richiesto da Blender
        mr = self._read_counter(MESH_RELOAD_PATH)
        if mr > self._last_mesh_reload:
            self._last_mesh_reload = mr
            self.reload_mesh()

    def reload_mesh(self):
        if self._reloading or not spproject.is_open():
            return
        cfg = _read_config()
        mesh_path = (cfg or {}).get("mesh_path", "")
        if not mesh_path:
            try:
                mesh_path = spproject.last_imported_mesh_path()
            except Exception:  # noqa: BLE001
                mesh_path = ""
        if not mesh_path or not os.path.isfile(mesh_path):
            self._set_status("Reload mesh: file FBX non trovato.")
            return

        def _do():
            self._reloading = True
            try:
                settings = spproject.MeshReloadingSettings(
                    import_cameras=False, preserve_strokes=True)

                def _cb(status):
                    ok = status == spproject.ReloadMeshStatus.SUCCESS
                    self._set_status("Mesh ricaricata." if ok else "Reload mesh fallito.")
                    self._reloading = False

                spproject.reload_mesh(mesh_path, settings, _cb)
                self._set_status("Reload mesh in corso…")
            except Exception as e:  # noqa: BLE001
                self._reloading = False
                self._set_status(f"Reload mesh fallito: {e}")

        spproject.execute_when_not_busy(_do)

    def _write_status(self, state: str, n: int = 0):
        try:
            os.makedirs(_CFG_DIR, exist_ok=True)
            with open(STATUS_PATH, "w", encoding="utf-8") as f:
                json.dump({
                    "state": state,
                    "last_export": datetime.now().strftime("%H:%M:%S"),
                    "textures": n,
                }, f)
        except OSError:
            pass

    def _on_export_now(self):
        self.export(force=True)

    # ---------------- Export ----------------

    def export(self, force=False):
        if self._exporting or self._scheduled:
            return
        if not spproject.is_open():
            self._set_status("Nessun progetto aperto.")
            return

        cfg = _read_config()
        if not cfg or not cfg.get("export_path"):
            self._set_status("Config Blender non trovata (esporta la mesh da Blender prima).")
            return

        # Differisce l'export a quando SP non è occupato: evita "The project is locked"
        # (chiamare export/preset mentre il progetto è bloccato fallisce).
        self._scheduled = True
        spproject.execute_when_not_busy(lambda: self._do_export(cfg))

    def _do_export(self, cfg):
        self._scheduled = False
        if self._exporting:
            return

        export_path = cfg["export_path"]
        mesh_name = cfg.get("mesh_name") or self._mesh_name_fallback()
        try:
            os.makedirs(export_path, exist_ok=True)
            export_config = self._build_export_config(export_path, mesh_name)
        except Exception as e:  # noqa: BLE001
            self._set_status(f"Errore preparazione export: {e}")
            return

        self._exporting = True
        try:
            result = spexport.export_project_textures(export_config)
            n = sum(len(v) for v in result.textures.values()) if result.textures else 0
            self._dirty = False
            self._set_status(f"Esportate {n} texture.")
            self._write_status("exported", n)
        except Exception as e:  # noqa: BLE001
            self._set_status(f"Export fallito: {e}")
        finally:
            self._exporting = False

    def _mesh_name_fallback(self):
        try:
            path = spproject.last_imported_mesh_path()
            return os.path.splitext(os.path.basename(path))[0]
        except Exception:  # noqa: BLE001
            return "Mesh"

    def _build_export_config(self, export_path, mesh_name):
        source_name = self.cmb_preset.currentText() or DEFAULT_PRESET
        preset = None
        for p in spexport.list_resource_export_presets():
            if p.resource_id.name == source_name:
                preset = p
                break
        if preset is None:
            raise RuntimeError(f"Preset '{source_name}' non trovato.")

        maps = preset.list_output_maps()
        for m in maps:
            kw = _clean_map_keyword(m.get("fileName", ""))
            m["fileName"] = (f"{mesh_name}_$textureSet_{kw}" if kw
                             else f"{mesh_name}_$textureSet_" + m.get("fileName", "Map"))

        texture_sets = [ts.name() for ts in sptextureset.all_texture_sets()]

        params = {
            "fileFormat": self.cmb_format.currentText(),
            "bitDepth": self.cmb_depth.currentText(),
            "paddingAlgorithm": "infinite",
        }
        size = _RESOLUTIONS.get(self.cmb_res.currentText())
        if size is not None:
            params["sizeLog2"] = size

        return {
            "exportShaderParams": False,
            "exportPath": export_path,
            "defaultExportPreset": LIVE_PRESET_NAME,
            "exportPresets": [{"name": LIVE_PRESET_NAME, "maps": maps}],
            "exportList": [{"rootPath": ts} for ts in texture_sets],
            "exportParameters": [{"parameters": params}],
        }

    # ---------------- Cleanup ----------------

    def shutdown(self):
        self.timer.stop()
        self.req_timer.stop()
        self._write_status("closed")
        for ev in getattr(self, "_change_events", ()):
            try:
                spevent.DISPATCHER.disconnect(ev, self._on_changed)
            except Exception:  # noqa: BLE001
                pass
        if self.dock is not None:
            spui.delete_ui_element(self.dock)
            self.dock = None
            self.widget = None


def start_plugin():
    global _plugin
    _plugin = BlenderLiveLink()
    _log("Plugin avviato.")


def close_plugin():
    global _plugin
    if _plugin is not None:
        _plugin.shutdown()
        _plugin = None
    _log("Plugin chiuso.")


if __name__ == "__main__":
    start_plugin()
