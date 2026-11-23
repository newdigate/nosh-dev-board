# Nosh presentation scenes (Blender)

`nosh_presentation.blend` holds two shots of the Nosh, the RK055 display and the enclosure,
for video footage. It is rebuilt from scripts; Blender 4.5 LTS.

| Scene | Frames | What it shows |
|---|---|---|
| `Closed` | 1-750 (25 s) | The closed case; the camera goes round the four edges and names the display and each connector. |
| `Exploded` | 1001-1750 (25 s) | Lid, display and board lift apart and are named; the board then comes forward, turns component side up, and its main parts are named. |

Both scenes share the same objects. The explode animation is keyed from frame 1001, which is
why the second scene starts there.

## Rebuild

```bash
./export_board.sh
```

```bash
/Applications/Blender.app/Contents/MacOS/Blender --background --python build_scenes.py -- --model --stills
```

```bash
/Applications/Blender.app/Contents/MacOS/Blender --background nosh_presentation.blend --python check_scenes.py
```

- `export_board.sh` writes `build/board.glb` from `Kicad/Nosh.kicad_pcb` (read-only, about 80 s). Only needed when the board changes.
- `--model` rebuilds `build/model.blend` (geometry, materials, lights). Leave it off to rebuild only cameras, animation and labels (much faster).
- `--stills` renders preview frames at 960x540 into `out/`; add names (`closed_0195 exploded_1740`) to render only those.
- The checks print `CHECK PASS/FAIL` lines and end with `CHECKS 18/18`. Read that line, not the exit code.
- On this Mac, Blender aborts (exit 134) as it quits from background mode. The files are written before that; ignore it.
- Label dots and leader lines ride with the part they point at; the label plates stay where they were placed.

A rebuild replaces the `.blend`, so hand edits belong in the scripts, or in a copy of the file.

## Where things are

- `labels.py`: every label's text, target, position and timing. Edit, rebuild, run the checks.
- `build_scenes.py`: `build_shots()` has the camera keys and the explode timing.
- `materials.py`: colours. `../params.py` and `../board.json`: all dimensions and part positions.
- In the file: collections `Board`, `Display`, `Enclosure`, `Studio` (shared), and per scene `Shot_<name>` (camera rig) and `Labels_<name>`.

## Common jobs

- **Render without labels:** in the Outliner, untick `Labels_Closed` / `Labels_Exploded` (exclude from view layer).
- **Put a screenshot on the display:** in material `screen`, load an image into the node `Screen Image` and set `Screen Mix` factor to 1. The image is landscape, 1280 x 720, top edge toward the audio jacks.
- **Render the animation:** pick the scene, set an output folder, Render > Render Animation (Eevee, 1920x1080, 30 fps). Estimated one to two hours per scene on this machine; not measured.

## What is approximate

- Stand-in blocks for parts with no 3D model: RT1176, flash, codec, audio jacks, micro-USB, M.2 socket and card, FPC connector, microSD card.
- The RK055 is a carrier, a glass block and four standoffs from measured sizes; the active area is assumed centred in the glass.
- The ribbon is a simple loop standing 35 mm out of the case.
- In the exploded shot only the four lid screws move; the tray stays on the table.
