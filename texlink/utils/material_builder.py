import bpy
import os
from datetime import datetime
from .texture_mapper import map_texture_to_slot, detect_colorspace, split_set_and_slot

SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".exr", ".tif", ".tiff"}

# Slot che richiedono un nodo Normal Map tra texture e BSDF
_NORMAL_SLOTS = {"Normal"}
# Slot non collegabili direttamente al BSDF (gestiti separatamente)
_SPECIAL_SLOTS = {"AO", "Height"}


# ------------------------------------------------------------------
# Shared state helpers (log + timestamp su WindowManager)
# ------------------------------------------------------------------

def log(message: str) -> None:
    """Append a message to the watcher log (WindowManager collection)."""
    wm = bpy.context.window_manager
    if not hasattr(wm, "texlink_log"):
        return
    entry = wm.texlink_log.add()
    entry.message = message
    while len(wm.texlink_log) > 20:
        wm.texlink_log.remove(0)


def set_last_update() -> None:
    wm = bpy.context.window_manager
    if hasattr(wm, "texlink_last_update"):
        wm.texlink_last_update = datetime.now().strftime("%H:%M:%S")


def force_viewport_update(mat=None) -> None:
    """Forza i viewport a ridisegnarsi dopo image.reload().

    tag_redraw() da un bpy.app.timers non forza SEMPRE il ridisegno effettivo (vedi
    KI-008), quindi forziamo un draw+swap reale con wm.redraw_timer (stesso effetto del
    click manuale). Chiamare operatori da bpy.app.timers è supportato; testato ok."""
    if mat is not None:
        mat.update_tag()
    wm = bpy.context.window_manager
    for win in wm.windows:
        for area in win.screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()
                for region in area.regions:
                    if region.type == "WINDOW":
                        region.tag_redraw()
    try:
        bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=1)
    except Exception:  # noqa: BLE001
        pass


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------

def reload_image(filepath: str) -> None:
    """Reload an existing image datablock or load it fresh. Refreshes pixels
    globally for every material sharing this image (shared datablock).
    gl_free() libera la texture GPU così EEVEE/Material Preview la ri-carica
    alla prossima draw (evita l'aggiornamento intermittente)."""
    fname = os.path.basename(filepath)
    img = bpy.data.images.get(fname)
    if img:
        img.reload()
        try:
            img.gl_free()
        except Exception:  # noqa: BLE001
            pass
        print(f"TexLink | reloaded: {fname}")
    else:
        bpy.data.images.load(filepath, check_existing=True)
        print(f"TexLink | loaded: {fname}")


def build_material(obj: bpy.types.Object, texture_dir: str) -> dict:
    """Create or update a Principled BSDF material on obj using textures in
    texture_dir. Returns {updated: bool, slots: list, warning: str|None}."""
    result = {"updated": False, "slots": [], "warning": None}

    if obj is None or obj.type != "MESH":
        result["warning"] = "Active object is not a mesh."
        return result

    groups = _group_textures(texture_dir)
    if not groups:
        return result

    # Edge case: mesh senza UV → le texture non si mappano correttamente
    if not obj.data.uv_layers:
        result["warning"] = f"Mesh '{obj.name}' has no UV map — textures won't display correctly."

    wired = set()
    if len(groups) == 1:
        # Single texture set → un materiale sullo slot 0 (comportamento storico)
        textures = next(iter(groups.values()))
        mat = _get_or_create_material(obj)
        mat.use_nodes = True
        wired.update(_rebuild_material(mat, textures))
        force_viewport_update(mat)
    else:
        # Multi texture set → un materiale per set, assegnato allo slot giusto
        for key, textures in sorted(groups.items()):
            mat = _get_or_create_material_for_set(obj, key)
            mat.use_nodes = True
            wired.update(_rebuild_material(mat, textures))
        force_viewport_update(None)

    result["updated"] = True
    result["slots"] = sorted(wired)
    return result


# ------------------------------------------------------------------
# Internals
# ------------------------------------------------------------------

def _group_textures(texture_dir: str) -> dict:
    """Raggruppa le texture per texture set: {group_key: {slot: filepath}}.
    Con un solo texture set ritorna un unico gruppo (caso single-material)."""
    groups: dict[str, dict] = {}
    try:
        for fname in os.listdir(texture_dir):
            ext = os.path.splitext(fname)[1].lower()
            if ext not in SUPPORTED_EXTENSIONS:
                continue
            key, slot = split_set_and_slot(fname)
            if slot:
                groups.setdefault(key, {})[slot] = os.path.join(texture_dir, fname)
    except OSError:
        pass
    return groups


def _get_or_create_material_for_set(obj: bpy.types.Object, key: str) -> bpy.types.Material:
    """Materiale per un texture set (multi-material).

    IMPORTANTE: NON rinomina i materiali degli slot. Il nome del materiale = nome del
    texture set in SP; rinominarlo romperebbe il reload mesh di SP (che mappa i set per
    nome). Quindi riusa il materiale esistente sullo slot (mantenendo il nome) e lo
    tagga con 'texlink_set' per ritrovarlo nei rebuild successivi."""
    # 1) già taggato come nostro
    for slot in obj.material_slots:
        if slot.material and slot.material.get("texlink_set") == key:
            return slot.material

    # 2) slot il cui materiale combacia col set (key = "<mesh>_<set>", slot mat = "<set>")
    for slot in obj.material_slots:
        m = slot.material
        if m and (key == m.name or key.endswith("_" + m.name)):
            m["texlink_set"] = key  # tagga, MANTIENE il nome (texture set stabile)
            return m

    # 3) fallback: slot vuoto / nuovo. Nome = ultima parte del key (nome del set).
    set_name = key.rsplit("_", 1)[-1] if "_" in key else key
    new = bpy.data.materials.get(set_name) or bpy.data.materials.new(set_name)
    new["texlink_set"] = key
    new.use_nodes = True
    for slot in obj.material_slots:
        if slot.material is None:
            slot.material = new
            return new
    obj.data.materials.append(new)
    return new


def _get_or_create_material(obj: bpy.types.Object) -> bpy.types.Material:
    """Return the material on obj, reusing a stable '<obj>_SP' datablock to avoid
    accumulating duplicates (_SP.001, _SP.002, …) across rebuilds."""
    if obj.material_slots and obj.material_slots[0].material:
        return obj.material_slots[0].material

    mat_name = f"{obj.name}_SP"
    mat = bpy.data.materials.get(mat_name)  # riusa se già esiste
    if mat is None:
        mat = bpy.data.materials.new(name=mat_name)
    if obj.material_slots:
        obj.material_slots[0].material = mat
    else:
        obj.data.materials.append(mat)
    return mat


def _rebuild_material(mat: bpy.types.Material, textures: dict) -> list:
    """Wire texture nodes (dict {slot: filepath}) into the Principled BSDF of mat."""
    if not textures:
        return []

    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    # Ricostruzione pulita: rimuove nodi orfani da canali non più presenti
    nodes.clear()
    bsdf = _get_or_create_bsdf(nodes, links)

    wired = []
    # 1) Slot diretti / Normal
    for slot, filepath in textures.items():
        if slot in _SPECIAL_SLOTS:
            continue
        _wire_texture(nodes, links, bsdf, slot, filepath)
        wired.append(slot)

    # 2) AO → moltiplicato sulla Base Color (richiede la Base Color)
    if "AO" in textures and "Base Color" in textures:
        _wire_ao(nodes, links, bsdf, textures["AO"])
        wired.append("AO")

    # 3) Height → Bump (eventualmente combinato con la Normal Map)
    if "Height" in textures:
        _wire_height(nodes, links, bsdf, textures["Height"])
        wired.append("Height")

    _layout_nodes(nodes)
    print(f"TexLink | material '{mat.name}' updated with {wired}")
    return wired


def _get_or_create_bsdf(nodes, links) -> bpy.types.Node:
    """Return existing Principled BSDF or create one wired to Material Output."""
    bsdf = next((n for n in nodes if n.type == "BSDF_PRINCIPLED"), None)
    if bsdf:
        return bsdf

    nodes.clear()
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (0, 0)
    output = nodes.new("ShaderNodeOutputMaterial")
    output.location = (300, 0)
    links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])
    return bsdf


def _get_tex_node(nodes, slot: str, filepath: str):
    """Return an Image Texture node for filepath (reused if già presente), with
    colorspace applicato. Il label porta lo slot per ritrovarlo nei rebuild."""
    fname = os.path.basename(filepath)
    tex_node = next(
        (n for n in nodes if n.type == "TEX_IMAGE" and n.image and n.image.name == fname),
        None,
    )
    if tex_node is None:
        tex_node = nodes.new("ShaderNodeTexImage")
        tex_node.image = bpy.data.images.load(filepath, check_existing=True)
    tex_node.label = slot
    _apply_colorspace(tex_node.image, slot)
    return tex_node


def _wire_texture(nodes, links, bsdf, slot: str, filepath: str) -> None:
    """Load image and connect it to the correct BSDF input."""
    tex_node = _get_tex_node(nodes, slot, filepath)
    if slot in _NORMAL_SLOTS:
        _wire_normal(nodes, links, bsdf, tex_node)
    else:
        target_input = bsdf.inputs.get(slot)
        if target_input:
            links.new(tex_node.outputs["Color"], target_input)


def _wire_ao(nodes, links, bsdf, ao_filepath: str) -> None:
    """Multiply AO over Base Color: BaseColor + AO → MixRGB(Multiply) → BSDF Base Color."""
    ao_node = _get_tex_node(nodes, "AO", ao_filepath)
    base_node = next(
        (n for n in nodes if n.type == "TEX_IMAGE" and n.label == "Base Color"), None
    )
    if base_node is None:
        return

    mix = next((n for n in nodes if n.type == "MIX_RGB" and n.label == "AO Mix"), None)
    if mix is None:
        mix = nodes.new("ShaderNodeMixRGB")
        mix.label = "AO Mix"
        mix.blend_type = "MULTIPLY"
        mix.inputs["Fac"].default_value = 1.0
    links.new(base_node.outputs["Color"], mix.inputs["Color1"])
    links.new(ao_node.outputs["Color"], mix.inputs["Color2"])
    links.new(mix.outputs["Color"], bsdf.inputs["Base Color"])


def _wire_height(nodes, links, bsdf, height_filepath: str) -> None:
    """Height → Bump → BSDF Normal. Se esiste una Normal Map, la combina nel Bump."""
    height_node = _get_tex_node(nodes, "Height", height_filepath)

    bump = next((n for n in nodes if n.type == "BUMP"), None)
    if bump is None:
        bump = nodes.new("ShaderNodeBump")
    links.new(height_node.outputs["Color"], bump.inputs["Height"])

    normal_map = next((n for n in nodes if n.type == "NORMAL_MAP"), None)
    if normal_map is not None:
        links.new(normal_map.outputs["Normal"], bump.inputs["Normal"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])


def _apply_colorspace(image, slot: str) -> None:
    """Set image colorspace. Preferisce il suffisso SP nel filename; altrimenti
    usa l'euristica per-slot (sRGB per color, Non-Color per il resto)."""
    detected = detect_colorspace(image.name)
    if detected is None:
        detected = "sRGB" if slot in ("Base Color", "Emission Color") else "Non-Color"
    try:
        image.colorspace_settings.name = detected
    except (TypeError, RuntimeError):
        # Colorspace non disponibile in questa config OCIO: lascia il default
        print(f"TexLink | colorspace '{detected}' non disponibile per {image.name}")


def _wire_normal(nodes, links, bsdf, tex_node) -> None:
    """Insert a Normal Map node between tex_node and BSDF Normal input."""
    normal_map = next((n for n in nodes if n.type == "NORMAL_MAP"), None)
    if normal_map is None:
        normal_map = nodes.new("ShaderNodeNormalMap")
        normal_map.location = (tex_node.location.x + 300, tex_node.location.y)
    links.new(tex_node.outputs["Color"], normal_map.inputs["Color"])
    links.new(normal_map.outputs["Normal"], bsdf.inputs["Normal"])


def _layout_nodes(nodes) -> None:
    """Arrange nodes in readable columns."""
    col_x = {
        "TEX_IMAGE": -600,
        "NORMAL_MAP": -250, "MIX_RGB": -250, "BUMP": -250,
        "BSDF_PRINCIPLED": 100, "OUTPUT_MATERIAL": 420,
    }
    counters: dict[str, int] = {}
    for n in nodes:
        col = col_x.get(n.type, 0)
        row = counters.get(n.type, 0)
        n.location = (col, -row * 280)
        counters[n.type] = row + 1
