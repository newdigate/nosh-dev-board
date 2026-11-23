# Nosh Enclosure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A parametric two-shell FDM enclosure (tray + lid) for the Nosh board and RK055 display stack, modelled in FreeCAD, checked by script and exported as STEP and STL.

**Architecture:** One pcbnew script reads the board into `mech/board.json`. One FreeCAD script builds the whole document from `mech/params.py` and that JSON (reference stack, keep-outs, tray, lid) and exports the shells. A second FreeCAD script opens the result and asserts every clearance, writing the check report. All scripts are re-runnable from the command line.

**Tech Stack:** KiCad 10.0.5 bundled python (`pcbnew`, LoadBoard only); FreeCAD 1.1.4 `freecadcmd` (`Part`, `Import`, `Mesh`, `Spreadsheet`); the freecad MCP GUI tools for rendered views only.

**Spec:** `docs/superpowers/specs/2026-11-21-nosh-enclosure-design.md`

## Global Constraints

- Never write to anything under `Kicad/`. Load the board with `pcbnew.LoadBoard` only.
- No commits and no pushes. Never stage `Kicad/tools/busrouter/m2_exits.py`, `docs/design-review-2026-10-28*` or `docs/mipi-reroute-handoff-2026-11-01.md`.
- Absolute paths in every command; scripts in files; shell is bash 3.2.
- Interpreters: `/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3` and `/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd`.
- Model frame: board frame x east, y **south positive**, origin at the board's NW corner; z up with the display on top; z = 0 is the table (tray floor underside). The imported STEP (y north-positive, component side +z) is mirrored into this frame by a 180 degree rotation about the x axis, then translated.
- Every number in a report is tagged measured, derived or assumed, as in the spec.
- Wall 2.0, clearance 0.5, floor 2.0, cavity 10.0, PCB 1.6, gap 16.0, carrier 2.0, panel 4.0, lid face 0.2 below the glass, window gap 0.5, rim gap 0.3, tongue 1.0 x 1.5, boss 7.5, pad 7.0, screw hole 3.4, countersink head 6.0.

## Review Focus

1. A plug whose overmould is larger than the assumed generic size: the notch should still admit it or the report should state the largest overmould each notch takes.
2. Glass position off by the +-0.5 mm of the derived margin: the window must still clear the glass; the report states the remaining gap at each edge for +-0.5 mm.
3. A locked microSD card (1.075 mm past the edge) and the push-to-eject over-travel: the card must be reachable and never rub the notch.
4. The lid lowered over a fitted ribbon: nothing of the lid may pass through the ribbon keep-out during a straight vertical move.
5. A standoff of 16.1 mm rather than 16.0: the rim gap must stay positive and under 0.5 mm.

Each of these has an assertion in Task 4.

---

### Task 1: Board table

**Files:**
- Create: `mech/board_table.py`, output `mech/board.json`, `mech/board_table.md`

**Interfaces:**
- Produces: `mech/board.json`: `{"outline": [w, h], "thickness": t, "holes": {"H1": [x, y], ...}, "parts": {ref: {"value", "side", "edge", "at": [x, y], "rot", "body": [x0, y0, x1, y1], "protrude", "height", "height_src", "opening": [w, h], "opening_src"}}}` for J1-J9, J11, SW1-SW4, H5, D6, D7, D10, D11, U1. `body` is the footprint's F.Fab/B.Fab extent (not the courtyard or text). `edge` is N/E/S/W in board frame or null. `height` comes from Task 2's STEP probe for parts with a model and from the datasheet for J2 (2.7 assumed until read), J6, J7, J8/J9, H5, U1; `height_src` says which.

- [ ] **Step 1:** Write `board_table.py` (pcbnew): fill everything except `height`; write the JSON and a Markdown table with columns reference, part, side, edge, centre, opening, protrusion, height.
- [ ] **Step 2:** Run it. Expected: outline `[153.9, 81.8]`; H1 `[3.32, 4.45]`; J2 protrude 0.70 on E; J5 on N; J8/J9 on S; J4 on W; J7 side BOT.
- [ ] **Step 3:** Read the datasheets for J2 (Molex 47590-0001), J8/J9 (CUI SJ-3524-SMT), J6 (M.2 key E socket + 2230 card), J7 (Wurth 68714014022) and fill their heights and mouth sizes with `*_src: "datasheet"`. Where a datasheet cannot be read, keep the value, set `*_src: "assumed"`.

### Task 2: Reference stack

**Files:**
- Create: `mech/params.py`, `mech/build_enclosure.py` (first half), output `mech/Nosh-enclosure.FCStd`

**Interfaces:**
- Consumes: `mech/board.json`, `mech/Nosh.step`.
- Produces: `params.P` (dict of the Global Constraints values plus `glass_x0=11.0`, `glass_y0=2.0`, `glass=[133.96, 79.24]`, `ribbon_x=70.65`, `ribbon_w=20.4`, `ribbon_margin=2.0`, plug overmoulds, screw lengths) and derived levels `z_pcb_comp = 12.0`, `z_split = 13.6`, `z_carrier0 = 29.6`, `z_carrier1 = 31.6`, `z_glass = 35.6`, `z_lid_face = 35.4`.
- `build_enclosure.py` functions: `load_board(doc) -> App::Part` (STEP into the model frame, component face at `z_pcb_comp`), `make_stack(doc) -> dict[str, Part.Shape]` with keys `carrier`, `panel`, `standoffs`, `ribbon_keepout`, `plugs` (one solid per edge connector: overmould cross-section extruded 30 mm outward from the connector mouth; for J5 the card at locked and over-travel positions), `boxes` (datasheet boxes for parts with no model), and `to_model(x, y, zc)` mapping board coordinates.
- A `Spreadsheet::Sheet` named `Params` in the document holds every `P` value with an alias.

- [ ] **Step 1:** Write `params.py`.
- [ ] **Step 2:** Write `load_board` and `make_stack`; run headless; save the FCStd.
- [ ] **Step 3:** Verify by print: board bbox x 0..153.9, y 0..81.8 (allow J2 and J5 overhang), component parts between z 1.45 and 12.0 with J4 lowest at about z 3.0; carrier z 29.6..31.6; glass x 11.00..144.96, y 2.00..81.24, top 35.6. Write the per-reference heights back into `board.json`.

### Task 3: Tray and lid

**Files:**
- Modify: `mech/build_enclosure.py` (second half); output `mech/out/tray.step`, `tray.stl`, `lid.step`, `lid.stl`

**Interfaces:**
- Consumes: Task 2's `P`, levels, `make_stack` shapes.
- Produces: `make_tray(P, stack) -> Part.Shape`, `make_lid(P, stack) -> Part.Shape`, `export(doc)`; document objects named `Tray` and `Lid`.

- [ ] **Step 1: Tray.** Outer box x -2.5..156.4, y -2.5..84.3, z 0..13.6, hollowed to floor 2.0 and inner wall at 0.5 from the board. Four bosses 7.5 mm, z 2..12, 3.4 mm hole, 90 degree countersink 6.0 mm at z = 0. Tongue on the inner half of the rim, z 13.6..15.1. Notches: for each tray-side connector, cut the plug solid grown by 0.5 mm, extended up through the rim. Vent slots: six 2 x 20 mm slots at 5 mm pitch centred on U1.
- [ ] **Step 2: Lid.** Outer box same plan, z 13.9..35.4. Skirt 2.0 thick; plate z 33.4..35.4; window = glass + 0.5; rebate for the tongue + 0.2 fit; pads 7.0 mm from z 31.6 to 33.4 at H1-H4 with 3.4 mm holes countersunk at z 35.4. Ribbon notch x 58.45..82.85 on the y = 0 wall from z 13.9 to 29.6. Relief notches where a grown plug solid crosses z 13.9.
- [ ] **Step 3:** Export STEP and STL (linear deflection 0.05 mm) of each shell in print orientation: tray as modelled, lid turned face down.
- [ ] **Step 4:** Verify by print: each shell is one valid closed solid (`isValid()`, one `Solid`); bounding boxes 158.9 x 86.8 x 15.1 (tray with tongue) and 158.9 x 86.8 x 21.5 (lid).

### Task 4: Checks and report

**Files:**
- Create: `mech/check_enclosure.py`, output `mech/check_report.md`

**Interfaces:**
- Consumes: `Nosh-enclosure.FCStd` objects `Tray`, `Lid`, the stack shapes, `board.json`.

- [ ] **Step 1:** Write the checks, each an assertion that also writes a report row:
  - `Tray` and `Lid` have zero common volume with the board, every component, the datasheet boxes, carrier, panel, standoffs, every plug solid and the ribbon keep-out.
  - Minimum distance from each shell to the PCB edge >= 0.45; to every component >= 0.5; cavity floor to J4 >= 0.9.
  - Each plug solid grown by 0.4 mm still has zero common volume with both shells (Review Focus 1); report the largest overmould each notch admits.
  - Glass shifted +-0.5 mm in x and in y: zero common volume with the lid (Review Focus 2); report the remaining gap per edge.
  - J5: card at locked (1.075 out) and at 0.5 mm over-travel clear of the tray; notch at least 14 mm wide for a fingertip (Review Focus 3).
  - Lid translated +z in 1 mm steps over 25 mm: zero common volume with the stack and ribbon keep-out at every step; same for the stack lifted out of the tray (Review Focus 4, assembly order).
  - With gap 16.1: rim gap between 0.0 and 0.5 (Review Focus 5).
  - Screw engagement: tray side >= 4.0, lid side >= 4.0, sum <= 14.
  - No downward-facing horizontal face on either shell in print orientation other than the build-plate face (no bridges).
- [ ] **Step 2:** Run. Expected: every row PASS. A FAIL is fixed in `build_enclosure.py` or `params.py`, never by loosening the check, unless the spec is wrong, in which case stop and report.

### Task 5: Views and hand-over

- [ ] **Step 1:** Open `Nosh-enclosure.FCStd` in the FreeCAD GUI; render: closed case isometric from the user's south-east and north-west, each of the four sides square-on, exploded view (tray, stack, lid), and a section through J3. Save PNGs to `mech/out/`.
- [ ] **Step 2:** Look at every image for anything the checks cannot see (thin slivers, a notch that reads wrong, an ugly corner) and fix.
- [ ] **Step 3:** Report to the user: files, the check table, measured versus derived versus assumed, and the three items to confirm before printing.
