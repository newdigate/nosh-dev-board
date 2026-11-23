#!/bin/bash
# Export the Nosh board as GLB for Blender. Reads Kicad/Nosh.kicad_pcb, writes build/board.glb.
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
set -o pipefail
mkdir -p "$HERE/build"
rm -f "$HERE/build/board.glb"
/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli pcb export glb \
  --subst-models --include-tracks --include-pads --include-zones \
  --include-silkscreen --include-soldermask -f \
  -o "$HERE/build/board.glb" "$REPO/Kicad/Nosh.kicad_pcb" 2>&1 | grep -v 'Error retrieving source file attributes' || true
ls -la "$HERE/build/board.glb"
