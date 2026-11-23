# Nosh Blender Presentation Scenes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One `.blend`, rebuilt by script, with two animated, labelled scenes of the Nosh + RK055 + enclosure: "Closed" (display and edge connectors) and "Exploded" (stack and main components).

**Architecture:** `kicad-cli` exports the board as GLB; a Blender Python build script imports it, adds stand-ins, the RK055, the enclosure STLs, studio, cameras, animation and labels; a second Blender script checks the result against `mech/params.py` and `mech/board.json`. All dimensions come from those two files.

**Tech Stack:** Blender 4.5.12 (`/Applications/Blender.app/Contents/MacOS/Blender --background --python`), `bpy`, KiCad 10 `kicad-cli` (`/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli`), Eevee.

**Spec:** `docs/superpowers/specs/2026-11-22-nosh-blender-scenes-design.md`

## Global Constraints

- Never write under `Kicad/`. Never commit (the user commits by asking).
- All new files under `mech/blender/`. Generated files (`build/board.glb`, `out/*.png`) are reproducible.
- Units: Blender metres at real size (board is 0.1539 m long); helper `mm(v) = v / 1000`. Camera `clip_start` 0.005.
- World frame = the `mech/` model frame: X east, Y = board-south (the user's north, audio jacks), Z up, display on top, Z = 0 at the table. Heights from `params.levels()`.
- GLB to world: the GLB has x east, y = -south, components at +z, component face at z = +1.6 mm. Parent the import to an empty `Nosh` rotated 180 degrees about X and placed at z = `levels()['split']`, so world y = -y_glb and the component face lands at `levels()['comp']`.
- Render: Eevee, 1920x1080, 30 fps. Previews 960x540. No full animation render in this plan.
- Label text comes only from `labels.py`; targets only from `board.json` (`footprints` for positions, `parts` for bodies) or named model points.
- Scripts take no `__main__` guard assumptions beyond `if __name__ == '__main__':` working under `blender --python`; arguments after `--`.

## Review Focus

- A label that is correct in the table but points at the wrong object after the X-flip (board y sign). Expect: `check_scenes.py` compares each target's world position with the `board.json` position transformed by the same rule, within 1 mm.
- Labels overlapping at a hold frame once the camera moves. Expect: screen-space plate rectangles tested pairwise at every hold frame.
- A re-run of `build_scenes.py` leaving duplicates or stale objects. Expect: the build starts from factory-empty and the check counts objects per collection.
- Text too small at 1080p. Expect: projected text height at each hold frame is at least 28 px.
- The lid STL being in print orientation (flipped). Expect: assembled lid bounding box z range equals `lid0`..`face` from `levels()` within 0.2 mm.

---

### Task 1: Board export and import

**Files:** Create `mech/blender/export_board.sh`, `mech/blender/common.py`, `mech/blender/build_scenes.py`, `mech/blender/check_scenes.py`.

**Interfaces:**
- Produces: `common.mm(v)`, `common.PARAMS`, `common.Z` (= `params.levels()`), `common.BOARD` (board.json), `common.board_to_world(x, y, z_above_comp_face=0.0) -> Vector` (board mm to world metres; a part on TOP sits below the board, so its world z = `Z['comp'] - z_above`), `common.ref_object(ref) -> Object` (the empty named `ref` under `Nosh`).
- Produces: `build_scenes.py` with `build_board()`; writes `mech/blender/nosh_presentation.blend`.
- Produces: `check_scenes.py` with a `CHECKS` list of functions returning `(name, ok, detail)`; prints `CHECK PASS/FAIL` lines and `CHECKS n/m`; exit code 1 on any failure.

- [ ] **Step 1:** `export_board.sh`: `kicad-cli pcb export glb --subst-models --include-tracks --include-pads --include-zones --include-silkscreen --include-soldermask -f -o mech/blender/build/board.glb Kicad/Nosh.kicad_pcb` (absolute paths). Run it. Expected: "Binary GLTF file ... created", about 64 MB.
- [ ] **Step 2:** Write checks in `check_scenes.py`: `board_refs` (empties exist for U9, U10, U6, J1, J3, J4, J5, J11, SW1, SW2, SW3, SW4), `board_frame` (for each of those refs, `ref_object(ref).matrix_world.translation` xy equals `board_to_world(*footprint_xy)` within 1 mm), `board_extent` (board mesh bbox x 0..153.9, y 0..81.8 mm within 0.2).
- [ ] **Step 3:** Run `Blender --background mech/blender/nosh_presentation.blend --python mech/blender/check_scenes.py`. Expected: FAIL (no .blend yet).
- [ ] **Step 4:** Implement `common.py` and `build_board()` (factory-empty, import GLB, parent to `Nosh`, collection `Board`, save).
- [ ] **Step 5:** Run build then check. Expected: `CHECKS 3/3`.

### Task 2: Stand-ins, RK055, enclosure, studio

**Files:** Modify `build_scenes.py`, `check_scenes.py`. Create `mech/blender/materials.py`.

**Interfaces:**
- Consumes: Task 1 `common.*`.
- Produces: objects/empties named `U1`, `U2`, `U15`, `J2`, `J6`, `J7`, `J8`, `J9`, `M2_Card`, `SD_Card` under `Nosh`; `RK055` (empty) with children `RK055_Carrier`, `RK055_Glass`, `RK055_Screen`, `RK055_Standoff_1..4`, `RK055_Ribbon`; `Lid`, `Tray`; `Screw_Tray_1..4`, `Screw_Lid_1..4`; collections `Board`, `Display`, `Enclosure`, `Studio`.
- Produces: `materials.get(name)` for `plastic_grey`, `pcb_black` (carrier), `glass`, `screen` (image slot, default dark), `ic_black`, `metal`, `ribbon`, `backdrop`, `label_text`, `label_plate`, `label_line`.

- [ ] **Step 1:** Checks: `standins` (each ref above exists; xy centre within 1 mm of board.json; U1 14.1 x 14.1 x 1.5, others from `params.BOXES`; U2/U15 sizes from the footprint names in `Kicad/Nosh.kicad_pcb`, read once and written as constants in `common.py` with the footprint name in a comment); `stack` (carrier z `car0..car1`, glass top at `glass`, tray bbox z 0..`tongue`, lid bbox z `lid0`..`face`, all within 0.2 mm); `glass_pos` (glass x0 = 11.0, y0 = 2.0 from the board-y = 0 edge, size 133.96 x 79.24); `screen_pos` (120.96 x 68.04 centred in the glass, UV top toward +Y world, the audio-jack edge); `collections` (nothing in the scene root collection).
- [ ] **Step 2:** Run check. Expected: the new checks FAIL.
- [ ] **Step 3:** Implement. Lid STL: derive the print-orientation transform from `mech/build_enclosure.py` (read how it exports the lid). Ribbon: a 20.4 mm wide curve-extruded strip from the carrier edge at x 70.65, out 35 mm beyond the case at board y = 0 side, down and back in to J7. Shade the STLs smooth-by-angle 30 degrees. Studio: curved backdrop, three area lights, world colour light grey.
- [ ] **Step 4:** Run build then check. Expected: all PASS.
- [ ] **Step 5:** Render one still (960x540, any three-quarter camera) to `mech/blender/out/00_model.png`, look at it, and fix anything visibly wrong (inside-out normals, a flipped part, a missing colour).

### Task 3: Label system

**Files:** Create `mech/blender/labels.py`, `mech/blender/label_rig.py`. Modify `check_scenes.py`.

**Interfaces:**
- Produces: `labels.SCENE1`, `labels.SCENE2`: lists of `dict(key, text, targets=[ref or (x, y, z) world mm], offset=(dx, dy, dz) mm, cue=frame, out=frame or None, hold=frame)`.
- Produces: `label_rig.add_label(scene, camera, spec) -> Object` (root empty `Label_<key>` in collection `Labels_<scene.name>`): text + rounded plate with a Copy Rotation to the camera, a driver or keyed scale keeping text height constant on screen (target 36 px at 1080p), one leader per target, target dots; material alpha keyed 0 to 1 over 12 frames at `cue` and back at `out`.
- Produces: `check_scenes.screen_rect(scene, obj, frame) -> (x0, y0, x1, y1)` in pixels via `bpy_extras.object_utils.world_to_camera_view`.

- [ ] **Step 1:** Checks, run per scene over its label table: `label_targets` (target exists; within 1 mm of board.json where it is a ref), `label_visible` (at `hold`: target in front of camera and inside the frame; alpha 1), `label_size` (text height at `hold` at least 28 px), `label_overlap` (no two plates with alpha above 0 intersect at any `hold` frame), `label_text` (object text equals the table).
- [ ] **Step 2:** Run check. Expected: FAIL (no labels).
- [ ] **Step 3:** Implement `label_rig.py`; fill the tables in Tasks 4 and 5.

### Task 4: Scene 1, "Closed"

**Files:** Modify `build_scenes.py`, `labels.py`.

**Interfaces:** Consumes Tasks 1-3. Produces scene `Closed`, frames 1-750, camera `Cam_Closed`, collection `Labels_Closed`.

- [ ] **Step 1:** `labels.SCENE1` (text exactly): "5.5 inch touch display, 720 x 1280" (glass centre); "5 V power in" (J4); "Line out" (J8); "Line in" (J9); "USB-C: device and power" (J3); "Micro-USB: host" (J2); "microSD card" (J5); "Display ribbon" (ribbon loop apex). Cues grouped per edge as in the spec; each hold about 90 frames.
- [ ] **Step 2:** Camera: an empty at the case centre with the camera parented, keyed rotation about Z with Bezier easing; order: three-quarter from the microSD side (user's south) so the screen reads upright, then west, north, east, south, back.
- [ ] **Step 3:** Run build then check. Expected: all PASS. Adjust offsets until `label_overlap` and `label_size` pass.
- [ ] **Step 4:** Render each `hold` frame at 960x540 to `out/closed_<key>.png`; look at every one.

### Task 5: Scene 2, "Exploded"

**Files:** Modify `build_scenes.py`, `labels.py`.

**Interfaces:** Consumes Tasks 1-3. Produces scene `Exploded` (linked copy of the same objects with its own animation: use a second scene with full copies made by the build, not linked data, so actions do not collide), frames 1-750, camera `Cam_Exploded`, collection `Labels_Exploded`.

- [ ] **Step 1:** Check `explode_pose`: at frame 1 the stack equals `levels()` (same as `stack`); at frame 240 the vertical order top to bottom is Lid, RK055, Nosh, Tray with at least 25 mm clear between neighbouring bounding boxes; screws clear of their holes.
- [ ] **Step 2:** `labels.SCENE2` phase A (cue after the explode, out before phase B): "Lid", "RK055 display", "Nosh board", "Tray". Phase B, 45 frames apart, on the component side: "i.MX RT1176 processor" (U1); "128 MB SDRAM" (U9, U10, two leaders; README: 2 x 512 Mb); "QSPI flash" (U2); "SGTL5000 audio codec" (U15); "M.2 Key E slot with Wi-Fi / Bluetooth card" (M2_Card); "3.3 V buck regulator" (U6); "SWD debug header" (J1); "Debug UART" (J11); "Reset" (SW1); "On/off and wake-up" (SW2, SW3); "Boot-mode switch" (SW4).
- [ ] **Step 3:** Animation: screws back out (frames 1-60), lid up (40-120), display up (80-170), board up and turned component-side-up about its long axis (140-240), camera settles over the board by 300.
- [ ] **Step 4:** Run build then check. Expected: all PASS.
- [ ] **Step 5:** Render each `hold` frame at 960x540 to `out/exploded_<key>.png`; look at every one. Write `mech/blender/README.md`: how to rebuild, check, hide labels, drop in a screen image, and render the animation.
