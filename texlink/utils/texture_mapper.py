import re

# Maps filename pattern (case-insensitive) to Principled BSDF input name
_SLOT_PATTERNS = [
    (re.compile(r"basecolor|base_color|diffuse|albedo", re.I), "Base Color"),
    (re.compile(r"roughness|rough", re.I), "Roughness"),
    (re.compile(r"metallic|metalness|metal", re.I), "Metallic"),
    (re.compile(r"normal|nrm|nrml", re.I), "Normal"),
    (re.compile(r"emissive|emission|emiss", re.I), "Emission Color"),
    (re.compile(r"(?<![a-z])ao(?![a-z])|ambient.?occlusion", re.I), "AO"),
    (re.compile(r"height|displacement|disp", re.I), "Height"),
    (re.compile(r"opacity|alpha|transparency", re.I), "Alpha"),
]


def map_texture_to_slot(filename: str) -> str | None:
    """Return the Principled BSDF slot name for a texture filename, or None if unrecognized."""
    stem = filename.rsplit(".", 1)[0]  # strip extension
    for pattern, slot in _SLOT_PATTERNS:
        if pattern.search(stem):
            return slot
    return None


def split_set_and_slot(filename: str):
    """Per il multi-materiale: ritorna (group_key, slot).

    Il canale è l'ULTIMO token separato da underscore (convenzione del plugin SP:
    <mesh>_<textureset>_<canale>), così un nome di set che contiene parole chiave
    (es. 'Metal') non viene scambiato per il canale. group_key = <mesh>_<textureset>
    identifica il texture set. Ritorna (stem, None) se non riconosciuto."""
    stem = filename.rsplit(".", 1)[0]
    if "_" in stem:
        prefix, last = stem.rsplit("_", 1)
        slot = map_texture_to_slot(last)
        if slot:
            return prefix, slot
    return stem, map_texture_to_slot(filename)


# Substance Painter codifica il colorspace nel nome file come ultimo segmento
# separato da underscore, es: "..._BaseColor_Linear Rec.709.png", "..._Metallic_Non-Color.png".
# Mappa il suffisso SP (case-insensitive) al nome colorspace di Blender.
_COLORSPACE_SUFFIXES = {
    "linear rec.709": "Linear Rec.709",
    "non-color": "Non-Color",
    "noncolor": "Non-Color",
    "raw": "Non-Color",
    "srgb": "sRGB",
    "linear srgb": "Linear Rec.709",
}


def detect_colorspace(filename: str) -> str | None:
    """Estrae il colorspace dal suffisso del filename (convenzione SP).
    Ritorna il nome colorspace di Blender, o None se non riconosciuto."""
    stem = filename.rsplit(".", 1)[0]  # strip extension
    if "_" not in stem:
        return None
    suffix = stem.rsplit("_", 1)[1].strip().lower()
    return _COLORSPACE_SUFFIXES.get(suffix)
