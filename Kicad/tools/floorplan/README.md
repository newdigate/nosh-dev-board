# Floor-plan search (simulated annealing on the macro parts)

Run with KiCad's bundled python3 (`/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3`).
Work files go to `work/` (or `$GP`).

1. `extract.py` — reads `Kicad/Nosh.kicad_pcb` into `work/model.json`: the macro parts (MCU, SDRAM, M.2, flash,
   codec, level shifters, chokes, crystals, buttons, connectors) with their signal pads; two-pin passives are
   collapsed (their two nets merged) so series parts do not break a connection; plane nets are ignored.
2. `place.py <scenario> <seed> <iters> <out>` — anneals positions/rotations. Cost = sum of per-net MST airwire
   length (power nets x0.5) + 3 mm per pair of crossing airwires + 3000 per scenario violation. Edge connectors
   stay on an edge facing out; the M.2 card area and corner holes are keepouts; J7 and the holes are fixed.
   Scenarios: `free`, `sdramN|E|S|W`, `m2N|E|S|W`, combinable with `_` (e.g. `m2W_sdramS`).
   Env: `START=file.json` initial state, `LOCK=U1,J2,...` parts not to move, `T0=` start temperature.
3. `render.py run.json out.png` — picture of a placement with its airwires; `montage.py out.png a.png b.png ...`.
4. `summarise.py` — table of all `work/run_*.json`.
5. `apply.py run.json out.kicad_pcb` — puts the macro placement on a copy of the board (fan-out follows U1),
   re-places passives and test points next to their nets (same optimiser as `optimise_placement.py`), refills
   zones, prints the full rats-nest length.

2026-10-08 result: the EVKB-style floor plan (SDRAM west, M.2 east) is already the best side assignment; other
sides for the SDRAM or the M.2 came out equal or worse. A locked-floor-plan polish of the small blocks (flash
north of the MCU, SD slot on the north edge, level shifters east, codec next to the jacks) cut the macro
rats-nest from 5331 to 4677 mm and the crossings from 1976 to 1507; full rats-nest 4839 -> 4683 mm.
