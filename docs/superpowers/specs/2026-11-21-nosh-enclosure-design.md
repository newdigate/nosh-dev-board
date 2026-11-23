# Nosh enclosure design

Date: 2026-11-21. Status: draft for approval. Not committed (repo rule: commit only when asked).

## Intent

A printed case that holds the Nosh board and the RK055HDMIPI4MA0 display as one unit, so the
touch-driven DJ deck can sit on a table as a finished device. The display is the face. The
user plugs in power, USB, audio and a microSD card from the sides and never touches the board.

## Goals

- Display facing up, glass fully exposed (no bezel overlap, so edge touches work).
- Only the edge connectors are reachable from outside.
- Two FDM-printed shells, no supports, no bridged openings.
- Parametric FreeCAD model driven by a spreadsheet, built by a script that can be re-run.
- The board file is only read. Nothing in `Kicad/` changes.

## Non-goals

- No access to SW1-SW3, the SW4 boot DIP, J1 SWD, J11 debug UART or the M.2 card with the case
  closed. No light pipes for D6, D7, D10, D11. Opening the case is the way in.
- No tilt stand, no battery, no antenna provisions.

## Anti-goals

- A case that needs the ribbon cable threaded through a closed hole, or a specific cable length.
- A wall that stops a plug from seating fully.
- Any dimension of the display kit filled in by guess and not flagged.

## Orientation

The board frame is KiCad's: origin at the board's north-west corner, x east, y south, seen from
Nosh's component side. In use the stack is turned over about its long axis, display up. The
user's compass therefore swaps north and south relative to the board frame:

| User's side | Board edge | What is there |
|---|---|---|
| North | y = 81.8 (board south) | J8 line out, J9 line in |
| South | y = 0 (board north) | J5 microSD (component side), ribbon window (gap) |
| East | x = 153.9 | J3 USB-C, J2 micro-AB |
| West | x = 0 | J4 barrel jack |

All positions below are in the board frame. "Down" is toward the table.

## Facts and where they come from

Measured by the user (callipers, 2026-11-21 and earlier):

- Nosh and carrier outline 153.9 x 81.8 mm, square corners.
- Carrier PCB thickness 2 mm.
- Glass surface 4 mm above the carrier's top face.
- Glass edge 11 mm from the carrier's west edge, 2 mm from the ribbon-side edge (board y = 0).
- Gap between Nosh and the carrier 16 mm (standoff nominal 0.635 in = 16.1 mm).
- Ribbon 20.4 mm wide, centred about x = 70.65; the current cable loops about 35 mm out past
  the edge.

From the board file (`Kicad/Nosh.kicad_pcb`, read with pcbnew):

- Board thickness 1.6 mm.
- H1-H4 at (3.32, 4.45), (150.58, 4.45), (150.58, 77.35), (3.32, 77.35); 3.531 mm holes.
- Connector positions, sides and protrusions (table to be generated in `mech/`).

From the Rocktech RK055MHD091A0-CTG datasheet (rev 1.0):

- Module outline 79.24 x 133.96 x 3.90 mm, active area 68.04 x 120.96 mm. The 3.90 mm agrees
  with the user's 4 mm reading.

Derived, not measured:

- Glass occupies x 11.00..144.96, y 2.00..81.24. That leaves 8.94 mm on the east and 0.56 mm on
  the audio-jack side. The 0.56 mm is the difference of two readings and is only good to about
  +-0.5 mm.

Assumed, to confirm before printing:

- The standoffs are threaded M3 female at both ends, with a screw from each board.
- Nothing on the carrier's east strip (panel flex tail) or west strip (header pads) stands more
  than 1.5 mm above the carrier's top face (the lid plate's underside is 1.8 mm above it).
- The carrier's own ribbon connector is on its underside, inside the gap (user observation,
  2026-10-06), so the ribbon never passes the carrier's edge or top.
- A 7 mm pad around each carrier hole is free of parts on the carrier's top face (the photo
  shows only the screw heads there).
- Plug overmould sizes (generic cables): USB-C 12.5 x 6.5 mm, micro-B 11 x 7 mm, 3.5 mm audio
  plug body 10 mm diameter, barrel plug body 11 mm diameter.

Parts with no 3D model in the STEP export, to be modelled as datasheet boxes: J2 micro-AB,
J8/J9 audio jacks, J6 M.2 socket (plus a 2230 card), J7 FPC connector, H5 nut, U1. The other
missing models (ESD diodes, F1, U2, U15, U17) are under 1 mm tall and do not affect the case.

## Approaches

1. **Clamp through the four existing M3 positions (chosen).** Screws come up through bosses in
   the tray floor into the standoffs; the four display-side screws pass through the lid
   corners. No extra fasteners, the case is about 5 mm larger than the board, the stack is
   held rigidly. Four recessed screw heads show on the face.
2. **Separate lid fixing.** Stack screwed to the tray only; lid snaps or screws on outside the
   board outline. Clean face, but about 8 mm larger each way and FDM snap lips need iteration.
3. **Laser-cut plates and spacers.** Rejected: the sides stay open, which contradicts "only
   edge connectors exposed".

The user chose FDM with two shells. The fixing choice (1) is my call; the user was offered 1
or 2 and did not pick.

## Design

Split plane: Nosh's display-side face (my call after review). The tray wall rises past the PCB
edge, so the PCB sits inside the tray and the lid skirt starts above it. Stack, from the table
up:

| Layer | Height (mm) | Source |
|---|---|---|
| Tray floor | 2.0 | my call |
| Component cavity | 10.0 | STEP: J4 barrel jack stands 9.0 above the board face, J11 UART header 8.5; plus 1.0 clearance |
| Nosh PCB | 1.6 | board file |
| Standoff gap | 16.0 | user |
| Carrier | 2.0 | user |
| Panel | 4.0 | user |

Outside size about 158.9 x 86.8 x 35.4 mm (lid face 0.2 mm below the glass) (0.5 mm clearance and 2.0 mm wall on each side).

The STEP board body is 1.47 mm thick (dielectric only); component-side parts sit on z = 1.55.
The case uses the nominal 1.6 mm. J4's and J11's through-hole pins stand 1.45 mm into the
standoff gap, which is harmless.

**Tray.** Floor plus walls up to the split plane. Four solid corner bosses under H1-H4, 7.5 mm
diameter with a 3.4 mm through hole and a countersink in the floor's outer face, merged into
the corner walls. The PCB rests on the bosses. Every connector opening is a notch from the rim down:

- West wall: J4 barrel jack.
- East wall: J3 USB-C and J2 micro-AB.
- Board-north wall: J5 microSD, wide enough for a fingertip to push the card.
- Board-south wall: J8, J9.

Each notch is sized for the plug overmould, not just the connector mouth, plus 0.5 mm.
Floor: vent slots under U1 at (72, 42). Stick-on feet go on the flat floor; no recesses, so the
build-plate face has no bridged pockets.

**Lid.** A top plate 2 mm thick whose outer face is 0.2 mm below the glass surface, with a
skirt down to the split plane. The skirt surrounds the gap and the carrier.
The window is the glass outline plus 0.5 mm all round. Corner pads under the plate bear on the
carrier around H1-H4, 7 mm in diameter, with 3.4 mm holes countersunk from the face. On the audio-jack side the
window edge runs straight into the wall: there is no plate ledge there, which is accepted. Where a plug
overmould reaches above the split plane, the skirt has a matching relief notch, open downward.

**Ribbon window.** A notch in the lid skirt on the board-north side, centred on x = 70.65,
24.4 mm wide (ribbon + 2 mm each side), the full height of the standoff gap, open downward to
the split plane. The ribbon loop hangs outside; the lid lowers over it.

**Halves located** by a tongue 1 mm thick and 1.5 mm tall on the inner half of the tray rim,
fitting a rebate inside the lid skirt. The tongue is in segments: it stops at every connector
notch and at the ribbon window.

**Closed height** is set by the lid pads on the carrier. The skirt stops 0.3 mm short of the
tray rim so the two contacts do not fight.

**Fasteners** (to buy): countersunk M3 (DIN 7991, 6 mm head). Tray side 4 x M3x18: 13.6 mm
of plastic and PCB, 4.4 mm of thread in the standoff. Lid side 4 x M3x10: 5.8 mm of plastic
and carrier, 4.2 mm of thread. Together 8.6 mm of the 16 mm standoff. Lengths are spreadsheet
parameters and depend on the standoff-thread assumption above.

**Assembly order.** Stack already assembled on its standoffs with the ribbon fitted. Remove the
four Nosh-side screws. Lower the stack into the tray. Fit the four long screws from below.
Remove the four display-side screws, lower the lid, refit with the longer screws.

**Printing.** PETG. Tray prints floor down; lid prints face down. All openings are open to a
rim, so there are no bridges or supports; the countersinks are 45 degree cones on the build plate. The largest part is about 159 x 87 mm.

## Deliverables (all under `mech/`)

- `Nosh.step`: board export from kicad-cli 10.0.5 (done; component occurrences carry reference
  designators, so KiCad StepUp is not needed).
- `board_table.md`: reference, part, side, edge, centre, opening size, protrusion, height.
- `build_enclosure.py`: FreeCAD script; parameters in a spreadsheet inside the document.
- `Nosh-enclosure.FCStd`: assembly (board, carrier, panel, standoffs, ribbon keep-out, tray,
  lid, plug keep-outs).
- `out/tray.step`, `out/tray.stl`, `out/lid.step`, `out/lid.stl`, and rendered views.
- A check report: clearance to every part, plug overmould clearance, microSD insert and eject
  travel, screw access, ribbon window, assembly order, with each number marked measured,
  derived or assumed.

## Left to the builder

Notch sizes per connector from the datasheets, boss and recess details, lip geometry, vent
pattern, corner radii, foot recess size.

## As built (2026-11-21)

Approved by the user and built. Differences from the text above:

- The J2/J3 notches and the J8/J9 notches are joined: the posts between them would have been
  1.25 mm and 2 mm wide.
- The barrel-plug notch dips 1 mm into the floor at the west wall (the plug axis is 5.0 mm
  below the board face, so an 11 mm overmould reaches below the cavity floor).
- The microSD slot is 20 mm wide and 9 mm deep below the board face, after review found the
  first 15 x 6 mm slot was fingernail-only.
- The tongue and its rebate have rounded corners concentric with the outer corner radius, and
  the lid pads have webs to the corner walls.
- The spreadsheet in the FreeCAD document mirrors `mech/params.py`; it does not drive the
  geometry. Edit `params.py` and re-run the scripts.
- The boxes for J2, J6, J7, J8, J9, H5 and U1 use assumed heights; no connector datasheet was
  re-read. The plug overmould sizes are also assumed.
- No section view through J3 was rendered.

## Revision 2 (2026-11-23): thicker walls for resin

The user ordered the shells in 9600 resin (SLA) and the printer warned of warping. Changes:
walls 2.0 -> 3.0 mm (outside 160.9 x 88.8 x 35.4), tongue fit 0.2 -> 0.35 mm, corner radius
2.5 -> 3.5 mm, lid lip beside the rebate 0.8 -> 1.65 mm, and a 1 mm deep finger relief in the
outer wall around the microSD slot so the card is no further behind the wall face than before
(1.43 mm). Floor and lid plate stay 2.0 mm. The 2 mm exports are kept in `mech/out/v1_wall2/`.
