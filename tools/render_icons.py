# -*- coding: utf-8 -*-
"""Растеризация SVG-иконок из index.html в анти-алиасные PNG (Pillow)."""
import math, os, re
from PIL import Image, ImageDraw, ImageFilter

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "noiseclean", "assets")
os.makedirs(OUT, exist_ok=True)
SS = 4          # супер-сэмплинг
VIEW = 24.0     # viewBox 24x24
SW = 1.8        # stroke-width из CSS

GREEN = (49, 223, 120)
GREEN_DARK = (22, 138, 74)
MUTED = (110, 119, 133)
GRAYI = (186, 193, 204)
BLUE = (75, 146, 255)

NUM = r'[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?'
TOKEN = re.compile(r'([MmLlHhVvCcSsQqTtAaZz])|(' + NUM + r')')


def tokenize(d):
    out = []
    for m in TOKEN.finditer(d):
        if m.group(1):
            out.append(('c', m.group(1)))
        else:
            out.append(('n', float(m.group(2))))
    return out


def cubic(p0, p1, p2, p3, n=28):
    pts = []
    for i in range(n + 1):
        t = i / n; mt = 1 - t
        x = mt**3*p0[0] + 3*mt**2*t*p1[0] + 3*mt*t**2*p2[0] + t**3*p3[0]
        y = mt**3*p0[1] + 3*mt**2*t*p1[1] + 3*mt*t**2*p2[1] + t**3*p3[1]
        pts.append((x, y))
    return pts


def arc_points(x1, y1, rx, ry, phi, large, sweep, x2, y2, n=40):
    if rx == 0 or ry == 0:
        return [(x2, y2)]
    phi = math.radians(phi)
    cosp, sinp = math.cos(phi), math.sin(phi)
    dx = (x1 - x2) / 2.0; dy = (y1 - y2) / 2.0
    x1p = cosp*dx + sinp*dy
    y1p = -sinp*dx + cosp*dy
    rx, ry = abs(rx), abs(ry)
    lam = x1p**2/rx**2 + y1p**2/ry**2
    if lam > 1:
        s = math.sqrt(lam); rx *= s; ry *= s
    num = rx**2*ry**2 - rx**2*y1p**2 - ry**2*x1p**2
    den = rx**2*y1p**2 + ry**2*x1p**2
    co = math.sqrt(max(0.0, num/den)) if den else 0.0
    if large == sweep:
        co = -co
    cxp = co*rx*y1p/ry
    cyp = -co*ry*x1p/rx
    cx = cosp*cxp - sinp*cyp + (x1+x2)/2.0
    cy = sinp*cxp + cosp*cyp + (y1+y2)/2.0

    def ang(ux, uy, vx, vy):
        d = math.hypot(ux, uy)*math.hypot(vx, vy)
        c = max(-1.0, min(1.0, (ux*vx+uy*vy)/d)) if d else 1.0
        a = math.acos(c)
        return -a if (ux*vy - uy*vx) < 0 else a

    th1 = ang(1, 0, (x1p-cxp)/rx, (y1p-cyp)/ry)
    dth = ang((x1p-cxp)/rx, (y1p-cyp)/ry, (-x1p-cxp)/rx, (-y1p-cyp)/ry)
    if not sweep and dth > 0:
        dth -= 2*math.pi
    if sweep and dth < 0:
        dth += 2*math.pi
    pts = []
    for i in range(n + 1):
        t = th1 + dth*i/n
        x = cosp*rx*math.cos(t) - sinp*ry*math.sin(t) + cx
        y = sinp*rx*math.cos(t) + cosp*ry*math.sin(t) + cy
        pts.append((x, y))
    return pts


def parse_path(d):
    toks = tokenize(d)
    i = 0; cx = cy = 0.0; start = None
    subs = []; cur = []; cmd = None

    def nextnum():
        nonlocal i
        v = toks[i][1]; i += 1; return v

    while i < len(toks):
        if toks[i][0] == 'c':
            cmd = toks[i][1]; i += 1
        c = cmd
        if c in ('M', 'm'):
            x = nextnum(); y = nextnum()
            if c == 'm':
                x += cx; y += cy
            if cur:
                subs.append(cur)
            cur = [(x, y)]; cx, cy = x, y; start = (x, y)
            cmd = 'L' if c == 'M' else 'l'
        elif c in ('L', 'l'):
            x = nextnum(); y = nextnum()
            if c == 'l':
                x += cx; y += cy
            cur.append((x, y)); cx, cy = x, y
        elif c in ('H', 'h'):
            x = nextnum()
            if c == 'h':
                x += cx
            cur.append((x, cy)); cx = x
        elif c in ('V', 'v'):
            y = nextnum()
            if c == 'v':
                y += cy
            cur.append((cx, y)); cy = y
        elif c in ('C', 'c'):
            a = [nextnum() for _ in range(6)]
            if c == 'c':
                a = [a[0]+cx, a[1]+cy, a[2]+cx, a[3]+cy, a[4]+cx, a[5]+cy]
            pts = cubic((cx, cy), (a[0], a[1]), (a[2], a[3]), (a[4], a[5]))
            cur.extend(pts[1:]); cx, cy = a[4], a[5]
        elif c in ('A', 'a'):
            rx = nextnum(); ry = nextnum(); xr = nextnum()
            la = nextnum(); sw = nextnum(); x = nextnum(); y = nextnum()
            if c == 'a':
                x += cx; y += cy
            pts = arc_points(cx, cy, rx, ry, xr, int(la), int(sw), x, y)
            cur.extend(pts[1:]); cx, cy = x, y
        elif c in ('Z', 'z'):
            if cur and start:
                cur.append(start)
            if cur:
                subs.append(cur)
            cur = []
            if start:
                cx, cy = start
            cmd = None
        else:
            i += 1
    if cur:
        subs.append(cur)
    return subs


def render_paths(paths, size, color):
    px = int(size * SS)
    scale = px / VIEW
    w = max(1, int(round(SW * scale)))
    r = w / 2.0
    img = Image.new("RGBA", (px, px), (0, 0, 0, 0))
    dr = ImageDraw.Draw(img)
    col = color + (255,)
    for d in paths:
        for sub in parse_path(d):
            sp = [(x*scale, y*scale) for (x, y) in sub]
            if len(sp) >= 2:
                dr.line(sp, fill=col, width=w, joint="curve")
            for (x, y) in sp:
                dr.ellipse([x-r, y-r, x+r, y+r], fill=col)
    return img.resize((size, size), Image.Resampling.LANCZOS)


def render_bars(size, color, heights=(12, 22, 30, 22, 12), bw=3, gap=4):
    px = int(size * SS)
    img = Image.new("RGBA", (px, px), (0, 0, 0, 0))
    dr = ImageDraw.Draw(img)
    col = color + (255,)
    n = len(heights)
    total = (n*bw + (n-1)*gap) * SS
    x = (px - total)/2.0
    cyc = px/2.0
    for h in heights:
        hh = h*SS
        x0 = x; x1 = x + bw*SS
        y0 = cyc - hh/2.0; y1 = cyc + hh/2.0
        dr.rounded_rectangle([x0, y0, x1, y1], radius=bw*SS/2.0, fill=col)
        x += (bw+gap)*SS
    return img.resize((size, size), Image.Resampling.LANCZOS)


def render_power_face(size, on, glyph_img):
    """Круг кнопки питания (кольцо + свечение) + глиф, со сглаживанием."""
    px = int(size * SS)
    img = Image.new("RGBA", (px, px), (0, 0, 0, 0))
    cx = cy = px / 2.0
    r = size * 0.42 * SS
    dr = ImageDraw.Draw(img)
    if on:
        ring = (49, 223, 120, 255); fill = (16, 39, 27, 255)
        # тонкое внешнее кольцо-ореол
        dr.ellipse([cx-r-5*SS, cy-r-5*SS, cx+r+5*SS, cy+r+5*SS],
                   outline=(49, 223, 120, 70), width=max(1, int(1.3*SS)))
    else:
        ring = (43, 49, 59, 255); fill = (22, 26, 33, 255)
    dr.ellipse([cx-r, cy-r, cx+r, cy+r], fill=fill, outline=ring, width=int(2*SS))
    out = img.resize((size, size), Image.Resampling.LANCZOS)
    if glyph_img is not None:
        gx = (size - glyph_img.size[0]) // 2
        gy = (size - glyph_img.size[1]) // 2
        out.alpha_composite(glyph_img, (gx, gy))
    return out


def render_radio(size, selected):
    px = int(size * SS); s = px / 20.0
    img = Image.new("RGBA", (px, px), (0, 0, 0, 0))
    dr = ImageDraw.Draw(img)
    if selected:
        dr.ellipse([2*s, 2*s, 18*s, 18*s], outline=GREEN+(255,), width=int(2*s))
        dr.ellipse([6*s, 6*s, 14*s, 14*s], fill=GREEN+(255,))
    else:
        dr.ellipse([2*s, 2*s, 18*s, 18*s], outline=(43, 49, 59, 255),
                   width=max(1, int(1.6*s)))
    return img.resize((size, size), Image.Resampling.LANCZOS)


def render_thumb(size):
    px = int(size * SS); r = 9 * SS
    img = Image.new("RGBA", (px, px), (0, 0, 0, 0))
    dr = ImageDraw.Draw(img)
    cx = cy = px / 2.0
    dr.ellipse([cx-r, cy-r, cx+r, cy+r], fill=(255, 255, 255, 255),
               outline=GREEN_DARK+(255,), width=int(2.5*SS))
    return img.resize((size, size), Image.Resampling.LANCZOS)


def render_tray(size):
    """Иконка в системном трее: зелёный скруглённый квадрат с полосами."""
    px = int(size * SS)
    img = Image.new("RGBA", (px, px), (0, 0, 0, 0))
    dr = ImageDraw.Draw(img)
    dr.rounded_rectangle([0, 0, px-1, px-1], radius=px*0.24, fill=(16, 39, 27, 255))
    heights = (0.28, 0.46, 0.64, 0.46, 0.28)
    bw = px*0.10; gap = px*0.07
    total = len(heights)*bw + (len(heights)-1)*gap
    x = (px - total)/2.0
    cy = px/2.0
    for h in heights:
        hh = h*px
        dr.rounded_rectangle([x, cy-hh/2, x+bw, cy+hh/2], radius=bw/2,
                             fill=GREEN+(255,))
        x += bw + gap
    return img.resize((size, size), Image.Resampling.LANCZOS)


POWER = ["M12 2v10", "M6.3 5.8a8 8 0 1 0 11.4 0"]
LEAF = ["M19.5 4.5C13 5 7.5 8 5 13.5c-1 2.2.3 4.6 2.5 5.3 2.6.8 5-.8 6-3.1C15 12.5 16.6 8.2 19.5 4.5z",
        "M6.5 18.5c2.5-3 5.2-5.2 8.5-6.8"]
EQ = ["M4 12h2M8 8v8M12 5v14M16 8v8M20 10v4"]
MIC = ["M12 3a4 4 0 0 1 4 4v4a4 4 0 0 1-8 0v-4a4 4 0 0 1 4-4z",
       "M5 11a7 7 0 0 0 14 0M12 18v3M9 21h6"]
MON = ["M7 4h10v12H7z", "M10 19h4M12 16v3"]

jobs = [
    ("brand", lambda: render_bars(40, GREEN)),
    ("power_on", lambda: render_paths(POWER, 44, GREEN)),
    ("power_off", lambda: render_paths(POWER, 44, MUTED)),
    ("leaf", lambda: render_paths(LEAF, 28, GREEN)),
    ("equalizer", lambda: render_paths(EQ, 28, GRAYI)),
    ("mic", lambda: render_paths(MIC, 22, BLUE)),
    ("monitor", lambda: render_paths(MON, 22, BLUE)),
    ("power_face_on", lambda: render_power_face(78, True, imgs["power_on"])),
    ("power_face_off", lambda: render_power_face(78, False, imgs["power_off"])),
    ("radio_on", lambda: render_radio(20, True)),
    ("radio_off", lambda: render_radio(20, False)),
    ("gain_thumb", lambda: render_thumb(22)),
    ("tray", lambda: render_tray(64)),
]

imgs = {}
for name, fn in jobs:
    im = fn()
    im.save(os.path.join(OUT, name + ".png"))
    imgs[name] = im
    print("saved", name, im.size)

# .ico для иконки exe (несколько размеров)
ico = render_tray(256)
ico.save(os.path.join(OUT, "app.ico"),
         sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (256, 256)])
print("saved app.ico")
print("DONE ->", OUT)
