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

## Rest of the board

- `../fr_export.py board out.dsn` — DSN for Freerouting: outer GND pours left out, through-hole padstacks grown by
  0.073 mm per side (Freerouting's 0.127 mm then gives JLCPCB's 0.2 mm pad-to-trace for through-hole pads). Locked
  copper exports as fixed.
- `genroute.py in out NETS|all|power|signal track_mm [rounds] [base.kicad_pcb]` — general router on the same C core.
  Every pad, track and via is fixed; each net's copper is grouped into islands (vias in a filled plane zone of the net
  count as joined) and the islands are linked, or a 0.45/0.3 via is dropped into the net's plane. Through-hole pads
  keep 0.2 mm, keep-outs and the board edge are respected. `GREEDY=1` fixes each new link at once (one pass, no
  conflicts possible) - the mode that worked; `SEED`, `U1_FIRST=1` change the order. Negotiating against an
  autorouter's copper (`base` argument) diverged on this board and is not recommended.
- `window_strip.py board base out x0 y0 x1 y1` — remove copper not in `base` inside a window.

2026-10-11: Freerouting (20 + 12 passes) then one greedy pass at 0.1 mm left 98 open connections (57 power, 41 signal),
DRC clean. Re-routing round the BGA first, or in other orders, did not do better.
