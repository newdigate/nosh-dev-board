"""Compose the YouTube thumbnail (1280x720) from hero_<frame>.png.
Run: python3 compose.py [frame]   -> nosh_thumbnail.png, nosh_thumbnail_small.png (phone-size check)"""
import os
import sys
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
frame = sys.argv[1] if len(sys.argv) > 1 else '1290'
W, H = 1280, 720
AVENIR = '/System/Library/Fonts/Avenir Next.ttc'
COND = '/System/Library/Fonts/Avenir Next Condensed.ttc'


def font(path, size, style):
    for i in range(16):
        try:
            f = ImageFont.truetype(path, size, index=i)
        except OSError:
            break
        if f.getname()[1] == style:
            return f
    raise SystemExit('font style not found: %s' % style)


# backdrop: dark blue, lighter behind the model
bg = Image.new('RGB', (W, H), (10, 14, 24))
glow = Image.new('L', (W, H), 0)
ImageDraw.Draw(glow).ellipse((680, 40, 1320, 700), fill=150)
glow = glow.filter(ImageFilter.GaussianBlur(140))
bg = Image.composite(Image.new('RGB', (W, H), (52, 86, 130)), bg, glow)

# model: crop to its alpha box, scale to the frame height, sit on the right
hero = Image.open(os.path.join(HERE, 'hero_%s.png' % frame)).convert('RGBA')
hero = hero.crop(hero.getchannel('A').getbbox())
s = min(690.0 / hero.height, 540.0 / hero.width)
hero = hero.resize((int(hero.width * s), int(hero.height * s)), Image.LANCZOS)
hx = W - 22 - hero.width
hy = (H - hero.height) // 2
shadow = Image.new('RGBA', (W, H), (0, 0, 0, 0))
shadow.paste((0, 0, 0, 150), (hx + 10, hy + 16), hero.getchannel('A'))
bg.paste(shadow.filter(ImageFilter.GaussianBlur(18)), (0, 0), shadow.filter(ImageFilter.GaussianBlur(18)))
bg.paste(hero, (hx, hy), hero)

d = ImageDraw.Draw(bg)
x = 56
big = font(AVENIR, 204, 'Heavy')
d.text((x - 6, 58), '1 GHz', font=big, fill=(255, 196, 0))
mid = font(AVENIR, 82, 'Heavy')
d.text((x, 322), 'OPEN-SOURCE', font=mid, fill=(255, 255, 255))
d.text((x, 414), 'DEV BOARD', font=mid, fill=(255, 255, 255))
d.rectangle((x, 540, x + 120, 548), fill=(255, 196, 0))
small = font(COND, 50, 'Demi Bold')
d.text((x, 578), 'M7 + M4  ·  128 MB  ·  KiCad  ·  MIT', font=small, fill=(200, 214, 232))

bg.save(os.path.join(HERE, 'nosh_thumbnail.png'))
bg.resize((320, 180), Image.LANCZOS).save(os.path.join(HERE, 'nosh_thumbnail_small.png'))
print('WROTE hero x0 %d; text right edges: %d %d %d' % (hx, x + d.textlength('1 GHz', font=big), x + d.textlength('OPEN-SOURCE', font=mid), x + d.textlength('M7 + M4  ·  128 MB  ·  KiCad  ·  MIT', font=small)))
