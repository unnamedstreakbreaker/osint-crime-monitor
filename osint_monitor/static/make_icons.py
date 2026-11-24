"""Draw the app icon: brass eye emblem on police navy (same as the header)."""
import sys
from PIL import Image, ImageDraw

NAVY, BRASS = (19, 35, 63), (184, 145, 58)


def icon(size, maskable=False, out=None):
    s = size * 4                                   # supersample for smooth edges
    im = Image.new("RGB", (s, s), NAVY)
    d = ImageDraw.Draw(im)
    if not maskable:                               # rounded tile look for plain icons
        im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.rounded_rectangle([0, 0, s - 1, s - 1], radius=int(s * 0.22), fill=NAVY)
    zone = 0.62 if maskable else 0.78              # maskable: keep inside the 80% safe circle
    r = s * zone / 2
    c = s / 2
    w = max(2, int(s * 0.035))
    d.ellipse([c - r, c - r, c + r, c + r], outline=BRASS, width=w)              # badge ring
    def lens(a, h):                                                              # almond-shaped eye
        top = [(c + a * t / 60, c - h * (1 - (t / 60) ** 2)) for t in range(-60, 61)]
        bot = [(c + a * t / 60, c + h * (1 - (t / 60) ** 2)) for t in range(60, -61, -1)]
        return top + bot
    a, h = r * 0.68, r * 0.38
    d.polygon(lens(a, h), fill=BRASS)
    d.polygon(lens(a - w * 1.6, h - w * 0.95), fill=NAVY)
    pr = r * 0.2
    d.ellipse([c - pr, c - pr, c + pr, c + pr], fill=BRASS)                      # pupil
    im = im.resize((size, size), Image.LANCZOS)
    im.save(out)


base = sys.argv[1]
icon(192, out=f"{base}/icon-192.png")
icon(512, out=f"{base}/icon-512.png")
icon(512, maskable=True, out=f"{base}/icon-maskable-512.png")
icon(180, maskable=True, out=f"{base}/apple-touch-icon.png")
icon(32, out=f"{base}/favicon-32.png")
