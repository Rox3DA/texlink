"""
Config condivisa tra l'addon Blender e il plugin Substance Painter.

Entrambi i lati calcolano lo stesso path (~/.texlink/config.json) in modo
indipendente: il plugin SP non ha bisogno che Blender gli comunichi dove cercare.

Blender SCRIVE; il plugin SP LEGGE.
"""
import os
import json

CONFIG_VERSION = 1
_CONFIG_DIRNAME = ".texlink"
_CONFIG_FILENAME = "config.json"

# Nome della cartella radice creata per organizzare mesh e texture
ROOT_FOLDER = "TexLink"


def resolve_project_paths(mesh_name: str) -> dict:
    """Calcola le cartelle per-mesh relative al progetto Blender.

    Struttura: <root>/TexLink/<mesh_name>/{mesh,textures}
    - root = cartella del .blend se salvato
    - altrimenti fallback su Desktop (on_desktop=True) con avviso lato chiamante
    """
    import bpy
    safe_mesh = bpy.path.clean_name(mesh_name) if mesh_name else "Mesh"
    if bpy.data.is_saved:
        base = os.path.join(os.path.dirname(bpy.data.filepath), ROOT_FOLDER, safe_mesh)
        on_desktop = False
    else:
        base = os.path.join(os.path.expanduser("~"), "Desktop", ROOT_FOLDER, safe_mesh)
        on_desktop = True
    return {
        "mesh_dir": os.path.join(base, "mesh"),
        "texture_dir": os.path.join(base, "textures"),
        "on_desktop": on_desktop,
    }


def get_config_dir() -> str:
    return os.path.join(os.path.expanduser("~"), _CONFIG_DIRNAME)


def get_config_path() -> str:
    return os.path.join(get_config_dir(), _CONFIG_FILENAME)


def write_config(export_path: str, mesh_name: str,
                 file_format: str = "png", bit_depth: str = "8",
                 mesh_path: str = "") -> str:
    """Scrive la config che il plugin SP leggerà. Ritorna il path scritto."""
    os.makedirs(get_config_dir(), exist_ok=True)
    data = {
        "version": CONFIG_VERSION,
        "export_path": export_path.replace("\\", "/"),
        "mesh_name": mesh_name,
        "file_format": file_format,
        "bit_depth": bit_depth,
        "mesh_path": mesh_path.replace("\\", "/"),
    }
    path = get_config_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return path


def read_config() -> dict | None:
    """Legge la config se esiste (usata anche per debug lato Blender)."""
    return _read_json(get_config_path())


# ------------------------------------------------------------------
# Trigger bidirezionale: Blender chiede l'export, SP scrive lo stato
# ------------------------------------------------------------------

def get_request_path() -> str:
    return os.path.join(get_config_dir(), "export_request.json")


def get_status_path() -> str:
    return os.path.join(get_config_dir(), "sp_status.json")


def write_export_request() -> int:
    """Incrementa un contatore in export_request.json. Il plugin SP, vedendo il
    contatore cambiato, esegue un export. Ritorna il nuovo valore."""
    os.makedirs(get_config_dir(), exist_ok=True)
    data = _read_json(get_request_path()) or {}
    counter = int(data.get("counter", 0)) + 1
    with open(get_request_path(), "w", encoding="utf-8") as f:
        json.dump({"counter": counter}, f)
    return counter


def read_sp_status() -> dict | None:
    """Stato scritto dal plugin SP (ultimo export, mesh, conteggio)."""
    return _read_json(get_status_path())


def get_mesh_reload_request_path() -> str:
    return os.path.join(get_config_dir(), "mesh_reload_request.json")


def write_mesh_reload_request() -> int:
    """Incrementa un contatore: il plugin SP, vedendolo cambiato, ricarica la geometria
    (project.reload_mesh) dal file FBX indicato in config (mantenendo il painting)."""
    os.makedirs(get_config_dir(), exist_ok=True)
    data = _read_json(get_mesh_reload_request_path()) or {}
    counter = int(data.get("counter", 0)) + 1
    with open(get_mesh_reload_request_path(), "w", encoding="utf-8") as f:
        json.dump({"counter": counter}, f)
    return counter


def _read_json(path: str) -> dict | None:
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
