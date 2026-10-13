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

## BGA escape rework (2026-10-12, not applied)

- `bga_strip.py in out [x0 y0 x1 y1]` — clears the copper in a window round U1 (default the package + 2 mm) except the
  SDRAM bus, the fan-out vias and their dog-bones; `WHOLE=1` removes the whole route chains touching the window.
- `bga_escape.py in out [dest.json]` — negotiated escape router: rings 0/1 leave from the pad on F.Cu, inner rings from
  their fan-out via on SIG/B.Cu through the lattice channels (one 0.1 mm track per channel); plane nets get a via into
  the plane outside the field; targets are a band outside the window on the destination side and/or the net's own
  copper. Env: `SEED`, `WIDEN` (rounds of trouble before more sides are allowed), `ROUNDS`, `MODE=pref`, `WINDOW=board`.
  On the cleared field it places 130-138 of 146 escapes, DRC clean, in 2-5 min; the EVKB escapes the same part the same way.
- `unlock_old.py board base out` — lock only SDRAM, fan-out and new copper (for a Freerouting pass on the rest).

Result: every way of joining the escapes back to the rest of the board (greedy genroute with cut route ends, with
whole chains removed, board-wide negotiation, Freerouting with the escapes locked) ended at 109-173 open against
98 on the committed board, because the 2 mm ring round the chip saturates: radial escapes and tangential joins
cannot share it. The committed board was left as it was. Sealed balls without a rework: DCDC_MODE N4, DCDC_PSWITCH
P3 (inside the SDRAM lanes), DCDC_DIG K8/K9/L8 and DCDC_ANA M7/M8 (need PWR islands), GND corners A1/U1.

Applied to the board (2026-10-12, option 1 reduced): SEMC_D30's top-layer run under U3/U4 cut and re-joined by
genroute (31.2 -> 36.9 mm, 6 vias), which let DCDC_LP (U3/T3) and DCDC_LN (U4/T4) reach L1 as 0.1 mm placeholders
(widen by hand); DCDC_IN PWR island under L5/M5/N5 (C23/C24 still need vias, no free site yet); VDD_SOC island
trimmed to x >= 69.6; the three duplicate/too-close GND stitch vias cleaned up. 98 -> 95 open, DRC otherwise as before.
The C145 move and the SEMC_A3 cut were NOT applied: both collide with existing copper on the routed board.

## Fan-out first (branch fanout-first, 2026-10-12)

Start from the placed board with no routing. `../fanout2.py` moves the DC-DC block to U1's south edge, builds
PWR islands for DCDC_IN / DCDC_ANA / DCDC_DIG (plus a VDD_SOC lobe for R6) with via-free corridors through the
lattice, and gives every ring >= 2 ball a via on a free cell (power balls first). Then `bga_escape.py` with
everything negotiable at 0.1 mm (3 seeds + a second pass) and `widen_power.py` afterwards. Result: all 247
connected balls out of the field (194 escapes, 7 plane vias, 46 on planes), DRC clean. Lesson: route the power
escapes with the rest and widen afterwards; wide tracks routed first cut diagonally across the outer-ring lanes.

SDRAM bus on the fan-out-first board: strip the SDRAM balls' escapes back to the fan-out (the escape router's lane
order is arbitrary) and clear the non-SDRAM escapes that wandered into the NW corner (`WHOLE=1 bga_strip.py ... 62 32
70 44`), run `sdram_prebuild.py`, then `west_stubs.py` (fixed top-layer exits for the ring-1 balls of column 2 through
the gap above each; the negotiation never settled that 15-into-16 chain by itself), then `busroute_multi.sh` with
8 seeds x 150 rounds: 5 of 8 converged (seed 51 kept: U9 22-67 mm, U10 20-69 mm). `busroute.py` now keeps the outer
ring of lattice cells via-free (a routed via in a ring-0/1 gap cell sealed the ring-1 exits). `bustune.py` meandered
six short data nets; SEMC_D16 stays 29 mm short of U10's clock (no straight segment with room). The cleared balls were
then re-escaped with `bga_escape.py` and the power tracks widened with `widen_power.py`.

Rest of the board (fan-out-first, 2026-10-12): stitch_planes (261 vias), then genroute greedy at 0.1 mm: ~176 open.
Freerouting on the same board: 315 open (it fights the locked 0.1 mm copper), not used. The DC-DC block was
re-placed a second time (tools/dcdc_block2.py): caps and R5/R6 south of the escape fan (y 58-64) in four columns
over 1.1 mm wide PWR lobes that jog under L1; a no-via strip (67.4..73.8 x 49.0..51.6) keeps the escapes' layer
changes out of the jog zone and a top-layer keep-out keeps through-traffic off the cap columns; L1, R7, R90, R37,
R13, TP40, C44, C50, C144 moved out of the way. Result 178 open, DRC clean; DCDC_IN connected, DCDC_ANA/DIG still
need their cap vias (sites exist, the greedy router does not reach them).

- `plane_vias.py in out [NETS]` — for every pad of a plane net not yet tied to its plane, the nearest via site
  within 3 mm that lies inside the net's filled plane, keeps the JLCPCB clearances from everything (0.2 mm
  hole-to-copper, 0.554 mm to the net's own vias), is outside no-via areas (except the islands' own region
  KO_DCDC_JOG) and can be reached by a straight track on the pad's layer. `DEBUG=REF,...` prints why a pad found
  nothing. The whole DC-DC lobe region (67.4..73.8 x 49.0..64.5) is a no-via area for the routers during the
  pipeline so other nets' vias cannot cut the 1.1 mm lobes; the rule areas are removed when the result is applied.
  VDD_SOC also has a pocket under its north caps (C16/C18/C21/C22) through a via-free neck at column 9.
  Result on the fan-out-first board: 166 open (DC-DC block and VDD_SOC fully tied in).

- `plane_cleanup.py in out NET[,NET]` — removes a plane net's floating copper: track/via clusters that reach no via
  inside the net's MAIN plane fill and no through-hole pad that sits inside it. KiCad keeps a tiny island of fill
  round a stray via, so "inside the fill" must be tested against the largest outline; for GND (two full planes
  tied by hundreds of vias) that test is wrong, so GND is left out. plane_vias.py uses the same test.
  Island reshaping (2026-10-12): +5V gives back x 23-40 south-west to the 1.8 V regulator block (U8, C72-C74,
  C81, R104, R29), SDRAM_3V3 loses its bottom strip (y > 56.2 for x < 41) and gets a notch for R36; the D2 tongue
  is 4 mm wide so a +3V3 strip still reaches the C82 notch. Board: 158 open, +3V3 fully tied in.

### Decoupling, shields and the rest (2026-10-12)

- `local_links.py in out drc.json [max_mm] [NETS]` — closes the short ratsnest lines of a DRC report (the
  `unconnected_items` of `kicad-cli pcb drc --format json`): for every pair whose two ends are within 3 mm (5 mm
  for the USB shield nets) a straight or L-shaped track on a layer both ends share, else a via beside the midpoint
  with a track from each end (0.2 mm power / 0.15 mm signal, JLCPCB clearances, the via's hole outside the pad
  copper). A foreign via may not sit in a 1.1 mm PWR lobe nor bite its edge by more than 0.2 mm (an early version
  dropped two GND vias in the DC-DC lobes and necked DCDC_ANA to 0.25 mm). The report's pairs form a spanning
  tree, so closing them never doubles a connection; pads stacked top/bottom (TP over cap, ferrite over cap),
  connector shell tabs and pads beside a locked track end are the typical hits. 157 -> 120 open in one pass.
- genroute.py grew `FIELD=x0,y0,x1,y1` (islands centred in the BGA field are left to the escape router instead of
  failing every round), `DEBUG=1` (an ASCII map of the grid round every unreached island and round the far end of
  the base island: `T` island, `F` other nets' copper, `o` own, `c` negotiable routes, `v` no-via), `EXP` (A*
  budget) and a final pass: after the best round, nets still conflicting are re-routed one by one at prohibitive
  pressure and a net that still conflicts loses its negotiable copper instead of being written back over the
  routes made through its cells (that wrote shorts before). Pad keys are now unique per pad: a pin and its tab
  share a number (U8's +1V8 tab) and the second one's halo read as foreign copper, sealing the pad.
- Why the greedy pass left ~80 pairs outside the field: a greedy route cannot be moved, and early routes ran along
  component pads (CODEC_1V8 down the west side of the codec's 0.4 mm pads sealed pads 16-19) and along the escape
  band as north-south highways, boxing in the escape ends. Negotiating the whole board at once (every greedy route
  negotiable, 64 nets) churned: rip-ups round boxed-in islands grew to 70+ nets a round and never settled.
  Per-region negotiation works: `esc/cluster_route.sh in tag x0 y0 x1 y1 NETS [rounds]` makes only the greedy
  copper touching the window negotiable (base = blk7/pv, the pre-greedy board; plane and SEMC copper stays fixed)
  and routes the region's open nets; `esc/rest_pipeline.sh` runs south, north, east1, east2 in turn.
- `tools/rest_moves.py`: R74/R75 (LPI2C5 pull-ups) 0.5 mm west of U15 (at x 96.0 they left a 0.65 mm corridor in
  front of the codec's west pads: two tracks, and pads 17/18/19 needed three), their old +3V3 stubs removed; the
  VDD_SOC_IN island gets a tongue 73.5-78.3 x 50.0-52.8 under C17/R8 (only GND vias there).
- Result of the round (2026-10-13): 157 -> 102 open, DRC clean apart from the known J2/J3 library hole clearances.
  Done: VDDA_1P8, VDD_USB_3P3, NVCC_GPIO, +1V8 (U8 tab), VDD_SOC_IN (C17/R8 via the tongue), VDD_MIPI_1P8,
  VDD_MIPI_1P0, NVCC_DISP1, VDDA_1P0, VDD_SNVS_IN, DCDC_MODE, both USB shields, J10's +3V3 pin, LCD_RST_B,
  the DC-DC block signals (PMIC_*, ONOFF, WAKEUP, BOOT_MODE*, JTAG, RTC_XTALI), M2_SDIO_D0. What the region
  negotiations could not settle was reverted rather than written back: the east band (SAI1_*, SD_DAT*, FLEXSPI_A_*,
  USB1_DP/DN, BT/WIFI wake lines - escape ends sealed by earlier greedy highways at x 79.5-81), U15's west pads
  16-19 (still boxed after the R74/R75 move and the NVCC_SD1 clean-up; needs a look by hand), VDDA_ADC_3P3 at
  FB1/TP35 and the two USB2 switch pads, USB2_CON_DN at U4, GND R96 (no via site inside the band's web).
  43 of the 102 pairs end at the ball grid (the hand-route list); genroute's lobe rule and the main-outline plane
  test now hold without the KO_* rule areas, and net_strip.py + bga_escape WINDOW=board re-escape a sealed ball.
- `net_strip.py in out NET[,NET]` strips a net back to its fan-out via and dog-bone; with
  `WINDOW=board MODE=pref NETSEL=... PREFSIDE=NET:N bga_escape.py` the ball is re-escaped straight to the net's own
  copper anywhere (VDD_MIPI_1P8, NVCC_DISP1 and LCD_RST_B, whose first escapes ended sealed in the band, 4 s).
- `tools/rest_moves.py` also drops any routed copper under a moved part's courtyard (re-routed afterwards).
- `tools/strip_parts.py in out [REFS]` (2026-10-13): takes the expansion header J10 and every test point off a
  copy of the board (recorded in out.removed.json so they can be put back), keeps the routes that met at a removed
  pad by joining their ends (a pad used as a junction splits the net otherwise), drops the copper of nets left with
  one pad (header-only GPIOs keep just their fan-out) and prunes dangling branches - a track end counts as attached
  when it sits on a pad, a via, or the middle of another track (genroute joins islands mid-segment). Phases run in
  fresh interpreters: pcbnew cannot iterate a board after Remove() nor reload one it just saved. Result: 102 -> 126
  open on removal, a greedy pass brings it to 80 (45 at the grid, 35 elsewhere); the regional negotiations gain
  nothing on top of that (each stage drops more conflicting copper than it routes), so the greedy board is the one
  to compare. genroute also keeps the VDD_SOC neck mouth (71.0-72.2 x 33.4-36.6) via-free outright: a via in the
  pocket beside the join cut the neck although it sat in a wide region.

### East band (2026-10-13)

What was in the way was not routing but parts: the band x 78.9-84 beside the field held U3 (USB2 VBUS switch) with
R23/R24, D3/C51 (USB1 VBUS schottky) and six BOOT_CFG pull-downs plus R39, and the corridor east of it (x 84-90)
carried U11 (BT UART level shifter), the SD/codec/M.2 traffic and three power snakes (NVCC_SD2 39 mm, USB2_VBUS 21,
DCDC_ANA to C26 19 mm of north-south track). Clearing the band's routed copper and re-routing with any order or
band cost (genroute FIRST, BANDCOST) gave 79-92 against 78, so the parts were moved (`tools/move_out.py`: first free
spot of a box, courtyards + 0.25 mm, old plane stubs and routed copper under the new courtyard dropped):
- U3, R23, R24, D3, C51 into the free south-east pocket (87-96 x 58-63); the +5V patch at 79.5-83.6 x 29.5-43 is
  gone and a +5V tongue 80.5-96.3 x 57.8-63.4 feeds them (the +5V island is one piece again);
- R93, R95, R98, R100, R102, R103 and R39 to the north-east (90.5-97.5 x 18.5-29.3);
- the six SD-card nets (SD_CMD, SD_CLK, SD_DAT0-3) re-escaped north (net_strip + bga_escape MODE=pref PREFSIDE=N)
  so they run along the top to the socket instead of through the band.
Then `busrouter/band_strip.py` (the routed copper inside the band; WHOLE=1 takes whole signal routes that cross
it, power nets keep their pieces) and greedy at 0.1 mm with FIRST=the band-end nets, BANDCOST=78.9,84,4, then the
power nets at 0.2 mm, plane_vias. Two genroute fixes came out of it: an island whose centroid lies in the FIELD box
(a ball and its escape) is now a routing *target* and a net with one such island plus one outside counts as open
(before, every strap and cap that only had its escape to reach was silently skipped), and the VDD_SOC neck mouth
is via-free outright. Result: 78 -> 75 open (34 at the grid, 41 elsewhere), DRC clean apart from J2/J3.

### U15 west pads (2026-10-13)

The codec's pads 16-20 (0.4 mm pitch) with the I2C pull-ups 0.5 mm in front of them defeated every router: each
run sent one exit along the pad row and sealed the rest. `busrouter/u15_exits.py` lays the five exits by hand
(R74/R75 swap places so each pull-up sits beside its own pad; SDA/SCL go straight to them; RXD0 goes north and
joins its existing via; TXD0 drops to SIG at (96.45, 68.1) and runs 5 mm west under the pull-ups; CODEC_1V8 goes
south) and removes the old CODEC_1V8 exit and NVCC_SD1's pieces in the corridor. With the exits in place the other
ends were the problem: the band-end stubs of SAI1_RXD0/TXD0 at (80-81, 42) had been boxed in by the east-band
re-route (genroute's DEBUG dump now names the fixed items in the window: BT_CFG11's track, the SD_DAT3/SD_CD_B/
LPUART1_TXD/GND vias). A negotiation over the whole east-south quadrant with the exits pinned (`cluster_route.sh`
takes `PVB=` as the fixed-copper base; `esc/dec/u15/pvb.kicad_pcb` = blk7/pv + the exits) connected both, dropping
VDDA_1P8, WL_DEV_WAKE, SAI1_RX_SYNC, +1V8, LPUART1_TXD, BT_CFG7 and SD_DAT3 copper, which `esc/restore.py` put back
where it still fitted (two DRC-driven passes). Result: 75 -> 71 open (35 at the grid, 36 elsewhere); the codec
pocket is closed (RXD0, TXD0, SDA, SCL, CODEC_1V8); BT_CFG7 (2), SD_DAT3, LPUART1_TXD and +1V8 (R5) lost a link each.

### Targeted re-escape of the stuck balls (2026-10-13)

Of the 247 connected balls, 114 are escaped and connected, 58 are the SDRAM bus, 10 became single-pad when the
header went, 42 are unconnected, and ~45 are open at the grid - but only 15 never left the chip: A1/A4/U1/U17
(ring 0, no via by design) and D4, D12, D14, E7, D10, D7, E14, J14, N12, N7, N8, whose dog-bone via is there and
whose escape stopped inside the grid. The others have their escape and lack the continuation outside.
- `busrouter/ball_strip.py in out BALLS` strips the copper hanging off given balls back to the dog-bone;
  `WIN=x0,y0,x1,y1` limits that to the escape inside the box (a connected neighbour's route beyond it stays).
- Re-escaping the 15 alone fails outright (their lanes are taken by fixed neighbours). Re-escaping them with the
  non-bus, non-plane, single-ball neighbours within one cell (40 balls, 40 nets) in band mode places all 40 in
  6 s (seed 3). WINDOW=board (escapes routed all the way to their destination) does not converge for a group
  that size; a radius-2 neighbourhood (73 balls, with multi-ball power nets) loses more than it gains.
- The continuation is the hard half: the new band ends sit elsewhere than the old route ends, so local_links +
  greedy reconnect only part of them; putting back the broken nets' old copper where it still fits (esc/restore.py,
  DRC-driven, two passes) recovers most. Results against 71 (35 at the grid): radius-1 whole-island strip +
  repair 66 (29 / 37); escape-only strip (WIN) + repair 66 (28 / 38) - applied. The grid is down to 28 open
  connections; the balls that moved out are BT_CFG1, CTP_INT, LPI2C5_SDA, NVCC_DISP1, NVCC_SD1, SD_CMD, SD_DAT2,
  USB_OTG2_OC; seven neighbours (BT_CFG8/11, NVCC_LPSR, SD_CLK, SD_DAT1, USER_LED, VDD_LPSR_DIG) now wait for their
  continuation at the band instead, and BT_CFG1, LPI2C5_SCL, NVCC_DISP2, SAI1_RXD0, SD_DAT0/2, USB_OTG2_OC each
  lost an outside link.
