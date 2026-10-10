# SDRAM bus router

Routes the SEMC bus between U1 and the two TSOPs on a board where `../sdram_prebuild.py` has already built the
chip-side geometry. Grid A* on F.Cu / SIG / B.Cu (0.05 mm grid) with negotiated congestion (PathFinder): every net
routes, overlaps cost more each round, nets that still overlap are ripped up and rerouted.

- `astar.c` — the search core, called through ctypes. Build: `clang -O3 -shared -fPIC -o libastar.dylib astar.c`
  (the .dylib is not committed). About 50x faster than the original pure-Python search.
- `busroute.py in.kicad_pcb out.kicad_pcb [nets|all] [rounds] [threads] [seed]` — run with KiCad's bundled
  python3. Keep threads = 1: rerouting many nets at once against the previous round oscillates; sequential rounds
  converge. Each round takes about a second.
- `busroute_multi.sh in.kicad_pcb outdir rounds seed...` — one process per seed in parallel (net order is shuffled
  per seed); keep the best. About 1 seed in 8 converges fully; seed 77 is on the board.
- `busconn.py board` — independent connectivity check (KiCad's DRC report stops listing unconnected items at 499).
- `busreport.py board` — per-net lengths and vias against each chip's clock branch.
- `render_hist.py board out.png` — heat map of where nets kept overlapping (from `<out>.hist`).
- `rank_seeds.sh dir...` — rank converged seed outputs by per-chip length span.
- `buslength.py board [via_mm] [out.json]` — per-pin flight length (MCU ball to chip pin) against each chip's clock.
- `bustune.py in out requests.json` — meanders ({"NET": extra_mm}) on the net's straight segments where they fit.
- `strip_routes.py routed pre out NETS` — remove some nets' routed copper (keeps prebuilt and fan-out) to reroute them.
- Waypoints: `BUS_WAYPOINTS='{"NET": [x, y, half]}' busroute.py ...` routes NET through that square (for nets too
  boxed in to meander).

Model: other nets' pads, prebuilt copper and fan-out are hard obstacles; only routed copper is negotiable (soft).
Neighbour rip-up kicks in when a run stalls on a few conflicts.

Never `pcbnew.SaveBoard` into `Kicad/` a board that was loaded from another folder: KiCad's Python then writes
default project settings over `Kicad/Nosh.kicad_pro`. Copy the file into `Kicad/` first and load it from there.
