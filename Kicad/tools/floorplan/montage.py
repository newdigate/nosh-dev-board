import sys, os
from PIL import Image
files = sys.argv[2:]; out = sys.argv[1]
ims = [Image.open(f) for f in files]
w, h = ims[0].size; cols = 2; rows = (len(ims) + 1) // 2
sc = 0.6; tw, th = int(w * sc), int(h * sc)
m = Image.new('RGB', (cols * tw, rows * th), 'white')
for i, im in enumerate(ims): m.paste(im.resize((tw, th), Image.LANCZOS), ((i % cols) * tw, (i // cols) * th))
m.save(out); print('saved', out, m.size)
