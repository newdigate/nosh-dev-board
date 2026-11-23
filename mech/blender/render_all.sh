#!/bin/bash
# Render both shots of nosh_presentation.blend to PNG frames and encode them to MP4.
#   ./render_all.sh            both scenes
#   ./render_all.sh closed     only one (closed | exploded)
# Frames: render/<scene>/<scene>_NNNN.png (1920x1080, Eevee). Video: render/nosh_<scene>.mp4, 30 fps.
# About 8 s a frame on this Mac, so roughly 100 minutes per scene.
# Blender aborts (exit 134) as it quits from background mode here; the script counts frames instead.
cd "$(dirname "$0")" || exit 1
BLENDER=/Applications/Blender.app/Contents/MacOS/Blender
WANT="${1:-closed exploded}"

render_scene() {
  name=$1; scene=$2; first=$3; last=$4
  mkdir -p "render/$name"
  rm -f "render/$name/${name}_"*.png
  "$BLENDER" --background nosh_presentation.blend -S "$scene" -o "//render/$name/${name}_####" -F PNG \
      -s "$first" -e "$last" -a > "render/$name.log" 2>&1
  n=$(ls "render/$name" | grep -c "^${name}_[0-9]*\.png$")
  want=$((last - first + 1))
  echo "RENDER $name: $n of $want frames"
  if [ "$n" -ne "$want" ]; then
    echo "RENDER $name INCOMPLETE"
    return 1
  fi
  ffmpeg -y -loglevel error -framerate 30 -start_number "$first" -i "render/$name/${name}_%04d.png" \
      -c:v libx264 -crf 18 -preset slow -pix_fmt yuv420p -movflags +faststart "render/nosh_$name.mp4" \
    && echo "VIDEO render/nosh_$name.mp4 written"
}

for w in $WANT; do
  case $w in
    closed) render_scene closed Closed 1 750 ;;
    exploded) render_scene exploded Exploded 1001 1750 ;;
    *) echo "unknown scene $w" ;;
  esac
done
echo "RENDER DONE"
