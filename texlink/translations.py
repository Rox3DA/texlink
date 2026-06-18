"""
Traduzioni native via bpy.app.translations.

Le etichette dell'interfaccia sono in inglese (msgid). Se l'utente imposta Blender
in italiano (Preferences > Interface > Translation, con 'Interface' attivo), Blender
mostra automaticamente le stringhe tradotte qui sotto. Nessun toggle custom.
"""
import bpy

# (context, english_msgid) -> traduzione italiana. Context "*" = default UI.
translations_dict = {
    "it_IT": {
        # Pannelli (bl_label)
        ("*", "Texture Update"): "Aggiornamento Texture",
        ("*", "Activity Log"): "Registro Attività",
        ("*", "Substance Painter Plugin"): "Plugin Substance Painter",
        ("*", "Settings"): "Impostazioni",
        # Pannello principale
        ("*", "Missing UV map"): "Manca la mappa UV",
        ("*", "No mesh selected"): "Nessuna mesh selezionata",
        ("*", "Send to Substance Painter"): "Invia a Substance Painter",
        ("*", "Folder: project / TexLink"): "Cartella: progetto / TexLink",
        ("*", "Project not saved"): "Progetto non salvato",
        ("*", "Files will be saved to Desktop"): "I file verranno salvati sul Desktop",
        # Aggiornamento texture
        ("*", "Start"): "Avvia",
        ("*", "Stop"): "Ferma",
        ("*", "Active"): "Attivo",
        ("*", "Paused"): "In pausa",
        ("*", "Send a mesh first"): "Invia prima una mesh",
        ("*", "Refresh Cycles View"): "Aggiorna vista Cycles",
        # Registro
        ("*", "Clear log"): "Pulisci registro",
        ("*", "No events."): "Nessun evento.",
        # Plugin
        ("*", "Auto-export textures"): "Esporta texture in automatico",
        ("*", "directly from Substance Painter."): "direttamente da Substance Painter.",
        ("*", "Install plugin in Substance Painter"): "Installa plugin in Substance Painter",
        ("*", "SP plugins folder"): "Cartella plugin SP",
        # Impostazioni
        ("*", "Use project folders"): "Usa cartelle del progetto",
        ("*", "Check interval (s)"): "Intervallo controllo (s)",
        ("*", "Manual folders:"): "Cartelle manuali:",
        ("*", "Mesh"): "Mesh",
        ("*", "Texture"): "Texture",
        ("*", "Open Addon Preferences"): "Apri Preferenze Addon",

        # Testi dei pulsanti (contesto "Operator")
        ("Operator", "Send to Substance Painter"): "Invia a Substance Painter",
        ("Operator", "Start"): "Avvia",
        ("Operator", "Stop"): "Ferma",
        ("Operator", "Refresh Cycles View"): "Aggiorna vista Cycles",
        ("Operator", "Rebuild"): "Ricostruisci",
        ("Operator", "Folder"): "Cartella",
        ("Operator", "Request Export from SP"): "Richiedi export a SP",
        ("Operator", "Update Mesh in SP"): "Aggiorna mesh in SP",
        ("Operator", "Clear log"): "Pulisci registro",
        ("Operator", "Install plugin in Substance Painter"): "Installa plugin in Substance Painter",
        ("Operator", "Open Addon Preferences"): "Apri Preferenze Addon",
    }
}

_TRANSLATION_ID = "texlink"


def register():
    try:
        bpy.app.translations.unregister(_TRANSLATION_ID)
    except Exception:
        pass
    bpy.app.translations.register(_TRANSLATION_ID, translations_dict)


def unregister():
    try:
        bpy.app.translations.unregister(_TRANSLATION_ID)
    except Exception:
        pass
