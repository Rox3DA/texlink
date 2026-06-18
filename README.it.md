# TexLink — Blender ↔ Substance Painter

*Lingua: **Italiano** · [English](README.md)*

Live link tra **Blender** e **Substance 3D Painter** via file system: esporti la mesh con
un click, dipingi in SP, e Blender aggiorna automaticamente il materiale (Principled BSDF)
quando SP esporta le texture.

- **Blender**: 4.x / 5.x (testato su 5.1)
- **Substance Painter**: standalone (testato su Adobe Substance 3D Painter 12)
- **Dipendenze**: nessuna (solo `bpy` + stdlib)

---

## Installazione

### 1) Addon Blender

**Addon legacy** (qualsiasi 4.x / 5.x):
1. `Edit → Preferences → Add-ons`
2. In alto a destra: `⌄ → Install from Disk…`
3. Seleziona **`texlink.zip`**
4. Abilita **"TexLink"** (compare nella sidebar `N` → tab **TexLink**)

**Extension** (Blender 4.2+, consigliato): installa **`texlink_extension.zip`**
trascinandolo nella finestra di Blender, oppure `Preferences → Get Extensions → ⌄ → Install from Disk…`.

> Per ricostruire gli zip dopo modifiche:
> `build_zip.ps1` (legacy) / `build_extension.ps1` (extension).

### 2) Configurazione (Preferenze addon)
Nel pannello, tendina **Settings → Open Addon Preferences** (o `Edit → Preferences → Add-ons → TexLink`):
- **Substance Painter Executable**: percorso del `.exe`
  (es. `C:\Program Files\Adobe\Adobe Substance 3D Painter\Adobe Substance 3D Painter.exe`)
- **Use Project Folders**: consigliato ON (vedi sotto)

### 3) Plugin lato Substance Painter
1. Nel pannello Blender: **Substance Painter Plugin → Install plugin in Substance Painter**
   (copia il plugin nella cartella plugin di SP)
2. In SP: `Python → Reload Plugins Folder` e abilita **`blender_live_link`**
3. Compare il pannello **Blender Live Link** in SP

---

## Flusso di lavoro

1. Seleziona una mesh in Blender → **Send to Substance Painter**
   - Esporta l'FBX e apre SP con la mesh caricata
   - Hai modificato la mesh dopo? **Update Mesh in SP** ri-esporta e ricarica la geometria
     in SP mantenendo il lavoro di painting
2. In Blender: tendina **Texture Update → Start** (avvia il monitoraggio)
3. In SP: dipingi, poi esporta le texture. Tre modi:
   - **Export Now** (manuale) dal pannello Blender Live Link
   - **Auto-export (timer)**: spunta la casella + intervallo → esporta da solo mentre dipingi
   - **Request Export from SP**: bottone in **Blender** che chiede a SP di esportare
4. Blender rileva le texture e **ricostruisce il materiale** entro pochi secondi

### Organizzazione file (Use Project Folders = ON)
```
<progetto.blend>/
└── TexLink/
    └── <NomeMesh>/
        ├── mesh/      ← FBX
        └── textures/  ← texture da SP
```
Se il progetto **non è salvato**, i file vanno in `Desktop/TexLink/<NomeMesh>/`
(con avviso nel pannello). Con *Use Project Folders* OFF si usano percorsi manuali.

---

## Convenzione dei nomi texture

Il materiale viene costruito dai **nomi dei file**. Pattern riconosciuti (in qualsiasi punto):

| Canale     | Pattern                                   | Slot Principled BSDF        |
|------------|-------------------------------------------|-----------------------------|
| Base Color | `BaseColor`, `diffuse`, `albedo`          | Base Color                  |
| Roughness  | `Roughness`, `rough`                      | Roughness                   |
| Metallic   | `Metallic`, `metalness`, `metal`          | Metallic                    |
| Normal     | `Normal`, `nrm`                           | Normal (via Normal Map)     |
| Emissive   | `Emissive`, `emission`                    | Emission Color              |
| AO         | `AO`, `ambient_occlusion`                 | moltiplicato su Base Color  |
| Height     | `Height`, `displacement`                  | Bump (+ Normal Map)         |
| Opacity    | `opacity`, `alpha`                        | Alpha                       |

Il plugin SP nomina i file `NomeMesh_TextureSet_Canale` (compatibile in automatico).
Il **colorspace** viene letto dal suffisso SP se presente (es. `_Linear Rec.709`, `_Non-Color`),
altrimenti dedotto dal canale.

### Multi-materiale
Mesh con più materiali → più texture set in SP. L'addon crea un materiale per set e lo
assegna allo slot corretto (match per nome del materiale originale, poi mantenuto via
una custom property). **Nota**: il canale dev'essere l'ultimo token del nome file.

---

## Riferimento pannello (sidebar N → "TexLink")

- **TexLink**: mesh attiva + **Send to Substance Painter** + cartella di destinazione
- **Texture Update**: Start/Stop watcher, stato + ultimo aggiornamento, **Rebuild**,
  **Folder** (apri cartella), **Refresh Cycles View**, **Request Export from SP**, stato SP
- **Activity Log**: eventi recenti + pulisci
- **Substance Painter Plugin**: installa/aggiorna il plugin SP
- **Settings**: toggle cartelle progetto, eseguibile SP, intervallo (o Preferenze)

L'interfaccia è in **inglese**; se imposti Blender in **italiano** si traduce da sola.

---

## Limiti noti

- **Cycles / Material Preview**: l'aggiornamento automatico del viewport non è sempre
  garantito (limite di Blender sul redraw da timer). In caso, usa **Refresh Cycles View**.
- **Export al salvataggio SP**: non supportato (durante il salvataggio il progetto è bloccato).
  Usa Export Now, il timer, o Request Export from SP.
- **Nomi materiale con parole chiave canale** (es. un materiale chiamato "Normal"): possono
  confondere il parsing in casi limite.

---

## Risoluzione problemi

- *Il pannello non appare*: verifica che l'addon sia abilitato nelle Preferenze.
- *SP non si apre*: controlla il percorso dell'eseguibile nelle Preferenze.
- *Le texture non si aggiornano*: il watcher è su **Start**? La cartella monitorata è
  quella dove SP esporta? Prova **Rebuild**.
- *Preview ferma in Cycles*: clicca **Refresh Cycles View**.
- *Errori del plugin SP*: guarda il **Log** di Substance Painter (`Window → Views → Log`).
