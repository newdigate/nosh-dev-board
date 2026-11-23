# Nosh presentation scenes in Blender — design

Date: 2026-11-22. Status: awaiting approval.

## Intent

Two animated shots for an informative YouTube video about the Nosh dev board.

- **Scene 1, "Closed":** the viewer comes away knowing that the unit has a display on top
  and which connector sits on which edge.
- **Scene 2, "Exploded":** the viewer comes away knowing how the stack goes together
  (lid, display, board, tray) and what the main components on the Nosh are.

## Goals

- One `.blend` holding both scenes, rebuilt from a script, like the enclosure.
- Labels inside the 3D scene: text with a leader line, facing the camera, fading in on cue.
- Labels can be switched off as a group, so each shot can also be rendered clean.
- Geometry true to the real thing: same model and dimensions as `mech/`.

## Non-goals

- Voice-over, music, titles, editing. The output is footage for the user's editor.
- Photoreal materials or Cycles-only effects.
- A detailed model of the RK055 (no vendor model exists).
- Any change to `Kicad/` or to the enclosure design.

## Anti-goals

- A label that names the wrong part or the wrong edge. Every label's text and target
  comes from `mech/board.json` / the schematic, not from memory.
- Labels that overlap each other or sit unreadably small at 1080p.
- A scene that only the script author can adjust: the `.blend` must open and be
  editable by hand (named objects, sensible collections).

## Constraints

- Blender 4.5.12 LTS at `/Applications/Blender.app`, driven headless with `--background --python`.
- Machine: 2017 Intel MacBook Pro, Radeon Pro 560 4 GB. Renderer is Eevee, 1920x1080, 30 fps.
- Blender has no STEP import. The board goes through FreeCAD
  (`/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd`) to a mesh format.
- Sources: `mech/Nosh.step` (board), `mech/out/tray.stl`, `mech/out/lid.stl`,
  `mech/params.py` (stack heights, glass position), `mech/board.json` (part positions).
- Orientation as the user holds it, display up: audio jacks north, USB east,
  microSD and ribbon south, power west. This is the model frame of `mech/`
  flipped north/south relative to the board frame; labels use the user's compass only
  if they name a direction at all.
- Nothing is committed unless the user asks. `mech/` is untracked today.

## Approaches

1. **Animated, labels in the scene (chosen by the user).** Tracked labels are the
   tedious part in a video editor; hiding one collection still gives clean plates.
2. Animated clean plates, labels added in the editor. Full control of type in the
   edit, but every label is placed by hand and cannot follow a moving camera.
3. Labelled stills only. Fastest, but loses the explode motion.

## Design

### Files

Everything under `mech/blender/`:

- `export_meshes.py` (freecadcmd): `mech/Nosh.step` -> one mesh file with one object per
  part, colours kept, objects named by reference where the position matches
  `board.json` (same relabelling as `build_enclosure.py`).
- `build_scenes.py` (Blender): builds the whole `.blend` from scratch.
- `labels.py`: the label tables for both scenes (text, target reference or point, cue frame).
- `check_scenes.py` (Blender): the checks below.
- `nosh_presentation.blend`: the result. `out/`: preview stills and renders.

### Model

- Board from the exported mesh. Stand-in blocks, coloured to read as the real part, for
  the parts with no 3D model that the shots point at: U1 (RT1176), J8/J9 audio jacks,
  J2 micro-USB, J6 M.2 socket, J7 FPC connector. Sizes from `params.BOXES`.
- RK055: carrier PCB 153.9 x 81.8 x 2.0, glass 133.96 x 79.24 standing 4.0 above the
  carrier, at the offsets in `params.py`; four standoffs; a flat ribbon from the carrier's
  south edge looping to J7. The glass has an image slot (default: dark glass with a faint
  reflection) so a screenshot of the DJ deck can be dropped in later.
- Enclosure: tray and lid from the STLs, matte printed-plastic grey, smooth-shaded
  with sharp edges kept.
- Studio: seamless light-grey backdrop, three soft area lights, a soft contact shadow.

### Scene 1, "Closed" (about 25 s, 750 frames)

Assembled, closed case. Camera on a path around it at a slightly raised angle:

1. Establishing three-quarter view; label "5.5 inch 720 x 1280 touch display".
2. Moves to each edge in turn, holds about 3 s, that edge's labels fade in and stay
   until the camera leaves: power (5 V barrel jack); audio (line out, line in);
   USB (USB-C device / power, micro-USB host); microSD and the display ribbon window.
3. Returns to the establishing view.

### Scene 2, "Exploded" (about 25 s, 750 frames)

1. Starts on the closed case. Lid lifts, display with its standoffs rises, the board
   lifts out of the tray; the four layers end spaced on the vertical axis. Four labels:
   lid, RK055 display, Nosh board, tray.
2. Camera settles over the board's component side (the side facing the tray, so the
   board turns over or the camera goes beneath: builder's choice, whichever reads best).
   Layer labels fade out.
3. Component labels fade in one at a time, about 1.5 s apart: RT1176 processor,
   SDRAM (two chips, one label with two leaders), QSPI flash, SGTL5000 audio codec,
   M.2 Key E slot (Wi-Fi / Bluetooth), 3.3 V buck regulator, SWD debug header,
   debug UART header, buttons (reset, on/off, wake-up), boot-mode switch.
   References and positions are looked up in `board.json` / the schematic.

### Labels

A label is: a text object (sans-serif, white on a dark rounded plate), a thin leader
line, and a small dot at the target. Text and plate are constrained to face the active
camera and scaled so the text height is constant on screen. Fade is a keyframed
material alpha. All labels of a scene sit in a `Labels` collection that can be excluded
from the render.

### Checks (`check_scenes.py`)

- Every label target exists and lies within 1 mm of its `board.json` position.
- At each label's hold frame: the target is in front of the camera and inside the frame,
  the text is at least 28 px tall, and no two visible label plates overlap in screen space.
- Stack heights in the assembled pose equal `params.levels()`.
- No object left in the default collection; both scenes have a camera and a frame range.

### Output

The build writes the `.blend` and preview stills: one per label hold, both scenes, at
960x540. The user looks at those before any full render. A full render (1,500 frames,
estimated one to two hours on this machine) is run only when the user asks.

## Left to the builder

- Mesh interchange format between FreeCAD and Blender, as long as parts stay separate
  objects with their colours.
- Exact camera path, easing, light positions, label placement offsets.
- Which way the board is shown for the component labels in scene 2.

## Calls made by Claude, not the user

Eevee at 1080p/30; stand-in blocks; the scene 2 label list; the studio look; scene
lengths of about 25 s each; previews first, full render on request; files in `mech/blender/`.

## Settled after the builder check (2026-11-22, Claude's calls unless marked)

- **More stand-ins:** U2 (QSPI flash) and U15 (SGTL5000) have no body in the STEP, so
  they get stand-in blocks at package nominal size (read the package from the footprint
  name in `Kicad/Nosh.kicad_pcb`), placed at the footprint position.
- **Mesh route:** `kicad-cli pcb export glb` (reads `Kicad/Nosh.kicad_pcb` read-only) is
  allowed in place of FreeCAD if headless FreeCAD loses the colours. Whichever route is
  used, objects the labels point at must be findable by reference.
- **Ribbon:** a flat loop from the carrier's south edge standing about 35 mm outside the
  case (as the real cable does), into J7. In the explode it stays with the display and
  is shown unplugged from J7.
- **Optional items shown:** the M.2 radio card on its nut, a microSD card in J5, and the
  eight M3 screws, which back out along their axes at the start of the explode. The M.2
  label points at the card and reads "M.2 Key E slot with Wi-Fi / Bluetooth card".
- **Buttons:** two labels: "Reset" on SW1, "On/off and wake-up" on SW2/SW3 (two leaders).
- **Screen image:** mapped onto the active area, 120.96 x 68.04 (datasheet), centred in
  the glass (assumed; the offset was not measured). The top of the image is the audio-jack
  edge (user, 2026-11-22), so the establishing shot looks from the microSD side.
- **Mesh route, tried 2026-11-22:** `kicad-cli pcb export glb` works (85 s, 64 MB,
  1.16 M triangles, 26 materials). Blender imports it with each part under an empty
  named by its reference (U9, J3, SW1...). This is the route; FreeCAD is not needed
  for the board.
