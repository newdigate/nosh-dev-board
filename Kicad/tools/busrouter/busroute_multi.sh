#!/bin/bash
# Run the bus router with several seeds in parallel (one process per core) and report each result.
# usage: busroute_multi.sh in.kicad_pcb outdir [rounds] [seeds...]
IN=$1; OUT=$2; ROUNDS=${3:-60}; shift 3; SEEDS=${@:-1 2 3 4}
PY=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3
HERE=$(cd "$(dirname "$0")" && pwd); mkdir -p "$OUT"
for s in $SEEDS; do
  ( $PY "$HERE/busroute.py" "$IN" "$OUT/bus_seed$s.kicad_pcb" all "$ROUNDS" 1 "$s" 2>&1 | grep -v 'memory leak\|wxApp\|GetWidth called' > "$OUT/seed$s.log" ) &
done
wait
for s in $SEEDS; do echo "== seed $s: $(grep -E '^round' "$OUT/seed$s.log" | tail -1)"; grep -E 'keeping' "$OUT/seed$s.log" | cut -c1-120; done
