bl_info = {
    "name": "TexLink",
    "author": "Rocco Brugioni",
    "version": (1, 1, 0),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > TexLink",
    "description": "Live link between Blender and Substance Painter via filesystem",
    "category": "Import-Export",
}

# Chiave di registrazione dell'addon in context.preferences.addons.
# Legacy: "texlink". Extension: "bl_ext.<repo>.texlink".
# __package__ qui (nel root) coincide con tale chiave. I sottomoduli la importano
# con `from .. import ADDON_ID` (import relativo, robusto in entrambi i casi).
ADDON_ID = __package__

from . import preferences, operators, panels, utils, translations


def register():
    translations.register()
    preferences.register()
    operators.register()
    panels.register()
    utils.register()


def unregister():
    utils.unregister()
    panels.unregister()
    operators.unregister()
    preferences.unregister()
    translations.unregister()
