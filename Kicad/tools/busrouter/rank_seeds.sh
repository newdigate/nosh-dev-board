#!/bin/bash
# Rank converged router outputs by length quality. usage: rank_seeds.sh dir [dir...]
PY=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3
HERE=$(cd "$(dirname "$0")" && pwd)
for d in "$@"; do
  for log in "$d"/seed*.log; do
    s=$(basename "$log" .log); s=${s#seed}; pcb="$d/bus_seed$s.kicad_pcb"
    grep -q 'keeping the best round' "$log" && continue          # did not converge
    [ -f "$pcb" ] || continue
    line=$($PY "$HERE/buslength.py" "$pcb" 0.8 "$pcb.len.json" 2>&1 | grep -E '^SPAN')
    echo "$line   <- $pcb"
  done
done | sort -t' ' -k8 -n
