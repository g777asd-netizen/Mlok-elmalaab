# -*- coding: utf-8 -*-
"""
visuals.py — مشاهد رسومية متحركة أصلية (فيكتور بالكود) لفيديوهات ملوك الملعب
==========================================================================
لا صور ولا لقطات من أي مصدر: كل حاجة مرسومة بـ Pillow.
مشاهد بيانات (من الخبر نفسه، بعد فحص الأرقام ضد نص الخبر):
    match  = لوحة نتيجة بعدّاد   | stats = أعمدة مقارنة | player = كارت لاعب برقم
مشاهد عامة (ديكور حركي، بلا ادعاء معلومات):
    pitch = ملعب وتكتيك | goal = كرة في المرمى | orbit = كرة بحلقات | bars = أعمدة نبض
    radar = رادار | shield = درع بأشعة
plan_scenes بتوزع المشاهد على الشرائح وبتنوّعها وتبدّلها من فيديو لفيديو.
"""
import math
import re
import zlib
import random
import PIL.Image
from PIL import ImageDraw

from branding import BRAND, get_font, draw_anchored, text_size

GENERIC = ['pitch', 'goal', 'orbit', 'bars', 'radar', 'shield']
NAVY = (8, 22, 45)


# ---------------------------------------------------------------- بيانات
def _num_in_source(n, source):
    """الرقم لازم يظهر في نص الخبر (أرقام لاتينية أو هندية)"""
    s = source.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))
    return re.search(r'(?<!\d)' + re.escape(str(n)) + r'(?!\d)', s) is not None


def validate_visuals(raw, source_text):
    """يفلتر بيانات المشاهد اللي طلعها النموذج: أي رقم مش موجود في الخبر يتشال"""
    out = {}
    if not isinstance(raw, dict):
        return out
    try:
        m = raw.get('match')
        if isinstance(m, dict):
            hg, ag = int(m['home_goals']), int(m['away_goals'])
            home, away = str(m['home']).strip()[:22], str(m['away']).strip()[:22]
            if home and away and 0 <= hg <= 20 and 0 <= ag <= 20 and \
               _num_in_source(hg, source_text) and _num_in_source(ag, source_text):
                out['match'] = dict(home=home, away=away, hg=hg, ag=ag)
    except Exception:
        pass
    try:
        rows = []
        for s in (raw.get('stats') or [])[:4]:
            a, b = float(s['home']), float(s['away'])
            fa, fb = (int(a) if a == int(a) else a), (int(b) if b == int(b) else b)
            if str(s.get('label', '')).strip() and 0 <= a <= 1000 and 0 <= b <= 1000 and a + b > 0 \
               and _num_in_source(fa, source_text) and _num_in_source(fb, source_text):
                rows.append(dict(label=str(s['label']).strip()[:22], a=a, b=b))
        if len(rows) >= 2:
            out['stats'] = rows
            out['stats_names'] = (str(raw.get('match', {}).get('home', '') or 'الأول')[:14],
                                  str(raw.get('match', {}).get('away', '') or 'التاني')[:14])
    except Exception:
        pass
    try:
        p = raw.get('player')
        if isinstance(p, dict):
            num, name = int(p['number']), str(p['name']).strip()[:24]
            if name and 1 <= num <= 99 and _num_in_source(num, source_text):
                out['player'] = dict(name=name, number=num)
    except Exception:
        pass
    return out


def plan_scenes(n, data, title, is_shorts):
    """نوع المشهد لكل شريحة. مشاهد البيانات في أماكن ثابتة، والباقي عام مبدّل بحسب العنوان.
    كل 4 شرائح تقريباً شريحة نص بس لتهدئة الإيقاع."""
    rng = random.Random(zlib.crc32((title or '').encode('utf-8')))
    kinds = [None] * n
    if n == 0:
        return kinds
    slots = []
    if 'match' in data:
        slots.append(('match', 0 if n < 3 else 1))
    if 'stats' in data:
        slots.append(('stats', max(2, n // 3) if n > 3 else min(1, n - 1)))
    if 'player' in data:
        slots.append(('player', max(3, (2 * n) // 3) if n > 4 else n - 1))
    for k, i in slots:
        i = min(i, n - 1)
        while kinds[i] is not None and i < n - 1:
            i += 1
        if kinds[i] is None:
            kinds[i] = k
    pool = GENERIC[:]
    rng.shuffle(pool)
    pi, last = 0, None
    for i in range(n):
        if kinds[i] is not None:
            last = kinds[i]
            continue
        if i % 4 == 3 and not is_shorts or (is_shorts and i % 5 == 4):
            kinds[i] = 'card'
        else:
            k = pool[pi % len(pool)]
            pi += 1
            if k == last:
                k = pool[pi % len(pool)]
                pi += 1
            kinds[i] = k
        last = kinds[i]
    return kinds


# ---------------------------------------------------------------- أدوات رسم
def _ease(x):
    x = min(max(x, 0.0), 1.0)
    return 1 - (1 - x) ** 3


def _glow(d, cx, cy, r, color, steps=6):
    for k in range(steps, 0, -1):
        rr = r * (1 + k * 0.12)
        d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=color + (int(18 / k * 2),))


_BALL = {}


def _ball_sprite(size):
    if size in _BALL:
        return _BALL[size]
    S = size * 3
    img = PIL.Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    c, r = S / 2, S / 2 - 4
    d.ellipse([c - r, c - r, c + r, c + r], fill=(245, 245, 245, 255), outline=(20, 20, 30, 255), width=max(3, S // 60))

    def pent(cx, cy, rad, rot):
        return [(cx + rad * math.cos(rot + k * 2 * math.pi / 5), cy + rad * math.sin(rot + k * 2 * math.pi / 5))
                for k in range(5)]
    d.polygon(pent(c, c, r * 0.30, -math.pi / 2), fill=(20, 20, 30, 255))
    for k in range(5):
        a = -math.pi / 2 + k * 2 * math.pi / 5
        ex, ey = c + r * 0.60 * math.cos(a), c + r * 0.60 * math.sin(a)
        d.line([(c + r * 0.30 * math.cos(a), c + r * 0.30 * math.sin(a)), (ex, ey)], fill=(20, 20, 30, 255), width=max(3, S // 70))
        px, py = c + r * 0.93 * math.cos(a + math.pi / 5), c + r * 0.93 * math.sin(a + math.pi / 5)
        d.polygon(pent(px, py, r * 0.20, a + math.pi / 5 + math.pi), fill=(20, 20, 30, 255))
    # قص على الدائرة
    mask = PIL.Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).ellipse([c - r, c - r, c + r, c + r], fill=255)
    img.putalpha(PIL.Image.composite(img.getchannel("A"), mask, mask))
    img = img.resize((size, size), PIL.Image.LANCZOS)
    _BALL[size] = img
    return img


def _paste_ball(img, cx, cy, size, angle):
    sp = _ball_sprite(int(size)).rotate(angle, resample=PIL.Image.BICUBIC)
    img.alpha_composite(sp, (int(cx - sp.width / 2), int(cy - sp.height / 2)))


def _t(d, x, y, text, size, fill, anchor='ma', bold=True):
    draw_anchored(d, (x, y), text, get_font(max(8, int(size)), bold=bold), fill, anchor=anchor)


# ---------------------------------------------------------------- مشاهد عامة
def _pitch(img, d, w, h, p, t, u):
    mx, my = w * 0.07, h * 0.1
    x0, y0, x1, y1 = mx, my, w - mx, h - my
    d.rectangle([x0, y0, x1, y1], fill=(14, 52, 44, 255), outline=(235, 235, 235, 230), width=max(2, int(3 * u)))
    for k in range(1, 8):  # شرائط العشب
        if k % 2:
            d.rectangle([x0 + (x1 - x0) * k / 8, y0 + 2, x0 + (x1 - x0) * (k + 1) / 8, y1 - 2], fill=(17, 62, 52, 255))
    d.line([((x0 + x1) / 2, y0), ((x0 + x1) / 2, y1)], fill=(235, 235, 235, 200), width=max(2, int(2 * u)))
    r = (y1 - y0) * 0.17
    d.ellipse([(x0 + x1) / 2 - r, (y0 + y1) / 2 - r, (x0 + x1) / 2 + r, (y0 + y1) / 2 + r], outline=(235, 235, 235, 200), width=max(2, int(2 * u)))
    bw, bh = (x1 - x0) * 0.14, (y1 - y0) * 0.5
    for sx in (x0, x1 - bw):
        d.rectangle([sx, (y0 + y1) / 2 - bh / 2, sx + bw, (y0 + y1) / 2 + bh / 2], outline=(235, 235, 235, 200), width=max(2, int(2 * u)))
    # لاعبين دائرين حركياً
    gold = [(0.22, 0.30), (0.40, 0.68), (0.62, 0.32), (0.80, 0.55)]
    blue = [(0.30, 0.48), (0.52, 0.52), (0.68, 0.72), (0.48, 0.25)]
    def pos(b, i, col):
        a = t * 0.9 + i * 1.7 + (0 if col == 'g' else 2.0)
        return (x0 + (x1 - x0) * (b[0] + 0.035 * math.sin(a)), y0 + (y1 - y0) * (b[1] + 0.05 * math.cos(a * 1.2)))
    gp = [pos(b, i, 'g') for i, b in enumerate(gold)]
    bp = [pos(b, i, 'b') for i, b in enumerate(blue)]
    rr = max(7, 12 * u)
    for (x, y) in bp:
        d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=(60, 120, 210, 255), outline=(255, 255, 255, 255), width=2)
    # الكرة تتنقل بين اللاعبين الذهبيين + سهم متقطع
    seg = (t * 0.7) % len(gp)
    i0 = int(seg)
    a, b = gp[i0], gp[(i0 + 1) % len(gp)]
    f = _ease(seg - i0)
    steps = 14
    for k in range(steps):
        if k % 2 == 0:
            s0, s1 = k / steps, (k + 1) / steps
            d.line([(a[0] + (b[0] - a[0]) * s0, a[1] + (b[1] - a[1]) * s0), (a[0] + (b[0] - a[0]) * s1, a[1] + (b[1] - a[1]) * s1)],
                   fill=BRAND['gold'] + (200,), width=max(2, int(3 * u)))
    for (x, y) in gp:
        d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=BRAND['gold'] + (255,), outline=(255, 255, 255, 255), width=2)
    _paste_ball(img, a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f, 22 * u + 6, t * 300)


def _goal(img, d, w, h, p, t, u):
    gx0, gx1, gy0, gy1 = w * 0.12, w * 0.88, h * 0.18, h * 0.66
    for k in range(0, 15):  # الشبكة
        x = gx0 + (gx1 - gx0) * k / 14
        d.line([(x, gy0), (x, gy1)], fill=(255, 255, 255, 55), width=1)
    for k in range(0, 8):
        y = gy0 + (gy1 - gy0) * k / 7
        d.line([(gx0, y), (gx1, y)], fill=(255, 255, 255, 55), width=1)
    d.line([(gx0, gy1), (gx0, gy0), (gx1, gy0), (gx1, gy1)], fill=(245, 245, 245, 255), width=max(4, int(8 * u)), joint='curve')
    d.line([(w * 0.02, gy1 + 4), (w * 0.98, gy1 + 4)], fill=BRAND['gold'] + (200,), width=max(2, int(3 * u)))
    cyc = (t % 2.6) / 2.6
    if cyc < 0.7:
        f = _ease(cyc / 0.7)
        bx = w * 0.20 + (w * 0.64 - w * 0.20) * f
        by = h * 0.92 - (h * 0.92 - h * 0.34) * f - math.sin(f * math.pi) * h * 0.30
        sz = (46 - 22 * f) * u + 6
    else:  # بعد الدخول: الكرة تهتز في الشبكة + وميض
        k = (cyc - 0.7) / 0.3
        bx, by, sz = w * 0.64 + math.sin(k * 14) * 6 * (1 - k), h * 0.34 + k * 10, 24 * u + 6
        _glow(d, w * 0.5, h * 0.4, w * 0.18 * (1 - k * 0.5), BRAND['gold'])
    _paste_ball(img, bx, by, sz, t * 420)


def _orbit(img, d, w, h, p, t, u):
    cx, cy = w / 2, h / 2
    R = min(w, h) * 0.18
    _glow(d, cx, cy, R * 1.3, BRAND['gold'])
    for k, rad in enumerate((1.6, 2.2, 2.8)):
        rr = R * rad
        d.ellipse([cx - rr, cy - rr * 0.6, cx + rr, cy + rr * 0.6], outline=BRAND['gold'] + (120 - k * 30,), width=max(2, int(3 * u)))
        a = t * (1.2 - k * 0.3) + k * 2
        sx, sy = cx + rr * math.cos(a), cy + rr * 0.6 * math.sin(a)
        d.ellipse([sx - 8 * u - 3, sy - 8 * u - 3, sx + 8 * u + 3, sy + 8 * u + 3], fill=(255, 235, 150, 255))
    bob = math.sin(t * 2.4) * R * 0.18
    _paste_ball(img, cx, cy + bob, R * 2 * (1 + 0.04 * math.sin(t * 5)), t * 120)


def _bars(img, d, w, h, p, t, u):
    n = 11
    bw = w * 0.80 / n
    base = h * 0.82
    for k in range(n):
        x = w * 0.10 + k * bw
        amp = 0.35 + 0.65 * (0.5 + 0.5 * math.sin(t * 2.2 + k * 0.9)) * (0.6 + 0.4 * math.sin(t * 0.8 + k))
        hh = (base - h * 0.15) * amp * _ease(p * 1.6 - k * 0.05)
        d.rounded_rectangle([x + 4, base - hh, x + bw - 4, base], radius=int(bw * 0.25),
                            fill=BRAND['gold'] + (255,) if k % 3 else (255, 235, 150, 255))
        d.rectangle([x + 4, base + 6, x + bw - 4, base + 6 + max(3, hh * 0.18)], fill=BRAND['gold'] + (45,))
    d.line([(w * 0.08, base + 2), (w * 0.92, base + 2)], fill=(255, 255, 255, 200), width=max(2, int(3 * u)))


def _radar(img, d, w, h, p, t, u):
    cx, cy, R = w / 2, h / 2, min(w, h) * 0.40
    for k in range(1, 5):
        rr = R * k / 4
        d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], outline=(120, 170, 235, 110), width=max(2, int(2 * u)))
    d.line([(cx - R, cy), (cx + R, cy)], fill=(120, 170, 235, 90), width=2)
    d.line([(cx, cy - R), (cx, cy + R)], fill=(120, 170, 235, 90), width=2)
    a = t * 2.0
    for k in range(18):  # ذيل الكنس
        aa = a - k * 0.06
        d.line([(cx, cy), (cx + R * math.cos(aa), cy + R * math.sin(aa))], fill=BRAND['gold'] + (int(150 - k * 8),), width=max(2, int(5 * u)))
    rng = random.Random(11)
    for k in range(6):
        ba, br = rng.uniform(0, 6.28), rng.uniform(0.25, 0.9) * R
        diff = (a - ba) % 6.28
        if diff < 3:
            al = int(255 * (1 - diff / 3))
            bx, by = cx + br * math.cos(ba), cy + br * math.sin(ba)
            d.ellipse([bx - 9 * u - 2, by - 9 * u - 2, bx + 9 * u + 2, by + 9 * u + 2], fill=(255, 240, 160, al))


def _shield(img, d, w, h, p, t, u):
    cx, cy = w / 2, h * 0.5
    S = min(w, h) * 0.34
    for k in range(10):  # أشعة دوارة
        a = t * 0.5 + k * math.pi / 5
        d.polygon([(cx, cy), (cx + S * 2.4 * math.cos(a - 0.07), cy + S * 2.4 * math.sin(a - 0.07)),
                   (cx + S * 2.4 * math.cos(a + 0.07), cy + S * 2.4 * math.sin(a + 0.07))], fill=BRAND['gold'] + (26,))
    pts = [(cx - S, cy - S * 1.1), (cx + S, cy - S * 1.1), (cx + S, cy + S * 0.15),
           (cx, cy + S * 1.25), (cx - S, cy + S * 0.15)]
    d.polygon(pts, fill=(12, 34, 68, 255), outline=BRAND['gold'] + (255,), width=max(4, int(7 * u)))
    inner = [(cx + (x - cx) * 0.8, cy + (y - cy) * 0.8) for x, y in pts]
    d.polygon(inner, outline=BRAND['gold'] + (150,), width=max(2, int(3 * u)))
    star = []
    for k in range(10):
        r = S * (0.42 if k % 2 == 0 else 0.18)
        a = -math.pi / 2 + k * math.pi / 5
        star.append((cx + r * math.cos(a), cy - S * 0.1 + r * math.sin(a)))
    pulse = 0.5 + 0.5 * math.sin(t * 3)
    d.polygon(star, fill=(255, int(215 + 30 * pulse), int(80 + 100 * pulse), 255))


# ---------------------------------------------------------------- مشاهد البيانات
def _match(img, d, w, h, p, t, u, data):
    m = data['match']
    _t(d, w / 2, h * 0.06, "المباراة", 30 * u, BRAND['gold'])
    cw = w * 0.40
    for side, name, goals in ((0, m['away'], m['ag']), (1, m['home'], m['hg'])):
        x = w * 0.06 + side * (w * 0.88 - cw)   # البيت يمين (اتجاه عربي)
        d.rounded_rectangle([x, h * 0.22, x + cw, h * 0.80], radius=int(18 * u), fill=(12, 34, 68, 255),
                            outline=BRAND['gold'] + (255,), width=max(3, int(4 * u)))
        _t(d, x + cw / 2, h * 0.27, name, 34 * u if len(name) < 12 else 26 * u, (255, 255, 255, 255))
        val = int(round(goals * _ease((p - 0.15) * 1.4)))
        _t(d, x + cw / 2, h * 0.43, str(val), 120 * u, BRAND['gold'] + (255,))
    _t(d, w / 2, h * 0.50, "-", 70 * u, (255, 255, 255, 255))
    rr = 6 * u + 2
    for k in range(7):  # أضواء مبهرجة
        a = t * 2 + k
        d.ellipse([w * (0.1 + 0.8 * k / 6) - rr, h * 0.90 - rr + math.sin(a) * 6, w * (0.1 + 0.8 * k / 6) + rr, h * 0.90 + rr + math.sin(a) * 6],
                  fill=(255, 235, 150, int(120 + 100 * math.sin(a * 1.5))))


def _stats(img, d, w, h, p, t, u, data):
    rows = data['stats']
    names = data.get('stats_names', ('', ''))
    _t(d, w * 0.80, h * 0.045, names[0], 24 * u, BRAND['gold'] + (255,))
    _t(d, w * 0.20, h * 0.045, names[1], 24 * u, (130, 180, 245, 255))
    n = len(rows)
    area_top, area_h = h * 0.14, h * 0.80
    for i, r in enumerate(rows):
        y = area_top + area_h * i / n
        f = _ease(p * 1.5 - i * 0.18)
        tot = r['a'] + r['b']
        full = w * 0.84
        wa, wb = full * (r['a'] / tot) * f, full * (r['b'] / tot) * f
        bh = area_h / n * 0.30
        by = y + area_h / n * 0.45
        _t(d, w / 2, y + 2, r['label'], 24 * u, (255, 255, 255, 255))
        x_r, x_l = w * 0.92, w * 0.08
        d.rounded_rectangle([x_r - wa, by, x_r, by + bh], radius=int(bh / 2), fill=BRAND['gold'] + (255,))
        d.rounded_rectangle([x_l, by, x_l + wb, by + bh], radius=int(bh / 2), fill=(70, 130, 215, 255))
        fa = int(r['a']) if r['a'] == int(r['a']) else r['a']
        fb = int(r['b']) if r['b'] == int(r['b']) else r['b']
        _t(d, x_r - 6, by + bh + 4, str(fa), 22 * u, (255, 255, 255, 255), anchor='ra')
        _t(d, x_l + 6, by + bh + 4, str(fb), 22 * u, (255, 255, 255, 255), anchor='la')


def _player(img, d, w, h, p, t, u, data):
    pl = data['player']
    cx = w / 2
    cw, ch = min(w * 0.62, h * 0.62), h * 0.86
    x0, y0 = cx - cw / 2, h * 0.07 + (1 - _ease(p * 1.3)) * 30
    d.rounded_rectangle([x0, y0, x0 + cw, y0 + ch], radius=int(26 * u), fill=(12, 34, 68, 255),
                        outline=BRAND['gold'] + (255,), width=max(4, int(6 * u)))
    # لمعة تعدّي على الكارت
    sh_x = x0 + ((t * 0.5) % 1.6 - 0.3) * cw
    d.polygon([(sh_x, y0), (sh_x + cw * 0.12, y0), (sh_x - cw * 0.08, y0 + ch), (sh_x - cw * 0.20, y0 + ch)],
              fill=(255, 255, 255, 22))
    # قميص فيكتور
    sx, sy, sw, sh = cx, y0 + ch * 0.12, cw * 0.62, ch * 0.5
    shirt = [(sx - sw * 0.5, sy + sh * 0.15), (sx - sw * 0.28, sy), (sx - sw * 0.12, sy + sh * 0.08),
             (sx + sw * 0.12, sy + sh * 0.08), (sx + sw * 0.28, sy), (sx + sw * 0.5, sy + sh * 0.15),
             (sx + sw * 0.38, sy + sh * 0.38), (sx + sw * 0.30, sy + sh * 0.32), (sx + sw * 0.30, sy + sh),
             (sx - sw * 0.30, sy + sh), (sx - sw * 0.30, sy + sh * 0.32), (sx - sw * 0.38, sy + sh * 0.38)]
    d.polygon(shirt, fill=(190, 25, 50, 255), outline=(255, 255, 255, 255))
    _t(d, sx, sy + sh * 0.28, str(pl['number']), sh * 0.55, (255, 255, 255, 255))
    nm = pl['name']
    _t(d, cx, y0 + ch * 0.74, nm, (34 if len(nm) < 14 else 24) * u, BRAND['gold'] + (255,))


DRAWERS = dict(pitch=_pitch, goal=_goal, orbit=_orbit, bars=_bars, radar=_radar, shield=_shield)
DATA_DRAWERS = dict(match=_match, stats=_stats, player=_player)


def render_panel(kind, data, size, p, t):
    """يرجع صورة RGBA بحجم size للمشهد عند الزمن t (p = تقدّم الظهور 0..1)"""
    w, h = size
    img = PIL.Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img, "RGBA")
    d.rounded_rectangle([0, 0, w - 1, h - 1], radius=int(min(w, h) * 0.05), fill=NAVY + (205,),
                        outline=BRAND['gold'] + (255,), width=max(3, int(min(w, h) * 0.008)))
    u = min(w, h) / 500.0
    if kind in DATA_DRAWERS:
        DATA_DRAWERS[kind](img, d, w, h, p, t, u, data)
    else:
        DRAWERS[kind](img, d, w, h, p, t, u)
    return img
