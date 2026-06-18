# Changelog

## 1.1.0 — 2026-06-18

First public release of **TexLink**, a filesystem-based live link between Blender and
Adobe Substance 3D Painter.

- **Send to Substance Painter**: export the selected mesh as FBX and open it in Painter.
- **Automatic texture sync**: a folder watcher reloads exported maps and rebuilds a clean
  Principled BSDF (Base Color, Roughness, Metallic, Normal, AO, Height) with the correct
  color spaces.
- **Multi-material / multi–texture-set**: each set is wired to the right material slot.
- **Update Mesh in SP**: reload changed geometry in Painter while preserving paint work.
- **Bundled Substance Painter plugin**: auto-export on a timer or on demand, with
  preset/format/resolution controls and a two-way "request export" trigger.
- **English & Italian UI**.
- Network-free: communicates only through files on disk. Works with Painter open or closed.
