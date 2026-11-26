# -*- coding: utf-8 -*-
"""
branding.py — الهوية البصرية الموحدة لقناة ملوك الملعب
=======================================================
- ألوان ثابتة: كحلي + ذهبي (نفس هوية القناة)
- خط Cairo العربي (يُحمّل تلقائياً من Google Fonts ويُخزّن في assets/fonts)
- رسم عربي صحيح: raqm أولاً، ومع arabic_reshaper + python-bidi كخطة بديلة
- مكونات: شريط سفلي (Lower Third) + بطاقة افتتاحية + بطاقة ختامية + تحسين الصور
"""

import os
import requests
import PIL.Image
from PIL import ImageDraw, ImageFont, ImageFilter, ImageEnhance, features

# ====================== الهوية ======================
BRAND = {
    "navy": (10, 26, 51),        # الكحلي الأساسي
    "navy_dark": (6, 17, 34),    # كحلي أغمق للتدرج
    "gold": (212, 175, 55),      # الذهبي
    "white": (255, 255, 255),
    "gray": (200, 205, 215),
    "red": (198, 16, 46),        # شارة "عاجل"
}

CHANNEL_NAME_AR = "ملوك الملعب"
CHANNEL_NAME_EN = "KINGS OF THE STADIUM"

# ====================== الخطوط ======================
FONT_DIR = os.path.join("assets", "fonts")
CAIRO_FONT_PATH = os.path.join(FONT_DIR, "Cairo.ttf")
CAIRO_FONT_URL = "https://raw.githubusercontent.com/google/fonts/main/ofl/cairo/Cairo%5Bslnt%2Cwght%5D.ttf"


def ensure_fonts():
    """تحميل خط Cairo مرة واحدة وتخزينه محلياً"""
    os.makedirs(FONT_DIR, exist_ok=True)
    if not os.path.exists(CAIRO_FONT_PATH) or os.path.getsize(CAIRO_FONT_PATH) < 100000:
        print("🔤 تحميل خط Cairo ...")
        r = requests.get(CAIRO_FONT_URL, timeout=60)
        r.raise_for_status()
        with open(CAIRO_FONT_PATH, "wb") as f:
            f.write(r.content)
    return CAIRO_FONT_PATH


def get_font(size, bold=True):
    """خط Cairo بوزن Bold/Regular من الخط المتغير، مع بدائل آمنة"""
    candidates = [
        CAIRO_FONT_PATH,
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    ]
    for path in candidates:
        try:
            font = ImageFont.truetype(path, int(size))
            if "Cairo" in path:
                try:
                    font.set_variation_by_name("Bold" if bold else "Regular")
                except Exception:
                    pass
            return font
        except Exception:
            continue
    return ImageFont.load_default()


# ====================== رسم النص العربي ======================
RAQM = features.check("raqm")

_reshaper = None
_get_display = None
if not RAQM:
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display
        _reshaper = arabic_reshaper
        _get_display = get_display
    except ImportError:
        pass


def _ar(text):
    """إرجاع (النص، kwargs) المناسبين لرسم عربي صحيح الاتجاه والتشكيل"""
    if RAQM:
        return text, {"direction": "rtl", "language": "ar"}
    if _reshaper and _get_display:
        return _get_display(_reshaper.reshape(text)), {}
    return text, {}


def draw_rtl(draw, xy, text, font, fill, **kwargs):
    t, kw = _ar(text)
    draw.text(xy, t, font=font, fill=fill, **kw, **kwargs)


def text_size(draw, text, font):
    t, kw = _ar(text)
    try:
        bbox = draw.textbbox((0, 0), t, font=font, **kw)
        return bbox[2] - bbox[0], bbox[3] - bbox[1]
    except Exception:
        return len(text) * font.size // 2, font.size


def wrap_rtl(draw, text, font, max_width, max_lines=3):
    """تقسيم النص لسطور بعرض أقصى. يرجع (السطور، هل تم الاختصار)"""
    words = text.split()
    lines, current = [], ""
    for w in words:
        trial = (current + " " + w).strip()
        if not current or text_size(draw, trial, font)[0] <= max_width:
            current = trial
        else:
            lines.append(current)
            current = w
    if current:
        lines.append(current)
    truncated = len(lines) > max_lines
    if truncated:
        lines = lines[:max_lines]
        used = len(" ".join(lines).split())
        if used < len(words):
            lines[-1] = lines[-1].rstrip("،,. ") + " ..."
    return lines, truncated


# ====================== المكونات ======================
def create_brand_overlay(width, height, breaking=True, out_path=None):
    """الشريط السفلي الموحد: شريط كحلي بخط ذهبي + اسم القناة + شارة عاجل"""
    img = PIL.Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    bar_h = int(height * 0.13)
    bar_y = height - bar_h

    # الشريط الكحلي + الخط الذهبي أعلاه
    draw.rectangle([(0, bar_y), (width, height)], fill=BRAND["navy"] + (235,))
    draw.rectangle([(0, bar_y), (width, bar_y + max(4, height // 180))], fill=BRAND["gold"] + (255,))

    # اسم القناة بالعربي (يمين) بالذهبي — مواضع ثابتة داخل الشريط
    name_font = get_font(bar_h * 0.38, bold=True)
    nw, nh = text_size(draw, CHANNEL_NAME_AR, name_font)
    pad = int(width * 0.02)
    draw_rtl(draw, (width - pad - nw, bar_y + bar_h * 0.10), CHANNEL_NAME_AR,
             name_font, BRAND["gold"] + (255,))

    # الاسم الإنجليزي تحته صغير
    en_font = get_font(bar_h * 0.17, bold=False)
    ew, eh = text_size(draw, CHANNEL_NAME_EN, en_font)
    draw.text((width - pad - ew, bar_y + bar_h * 0.62), CHANNEL_NAME_EN,
              font=en_font, fill=BRAND["gray"] + (220,))

    # ميدالية صغيرة يسار الشريط
    chip_font = get_font(bar_h * 0.30, bold=True)
    chip_text = "كورة على مدار الساعة"
    cw, ch = text_size(draw, chip_text, chip_font)
    chip_pad_x, chip_pad_y = int(width * 0.012), int(bar_h * 0.12)
    chip_x0 = pad
    chip_y0 = bar_y + (bar_h - (ch + chip_pad_y * 2)) / 2
    chip_rect = [(chip_x0, chip_y0), (chip_x0 + cw + chip_pad_x * 2, chip_y0 + ch + chip_pad_y * 2)]
    draw.rounded_rectangle(chip_rect, radius=(chip_rect[1][1] - chip_rect[0][1]) / 2,
                           outline=BRAND["gold"] + (255,), width=max(2, height // 400))
    draw_rtl(draw, (chip_x0 + chip_pad_x, chip_y0 + chip_pad_y - ch * 0.1), chip_text,
             chip_font, BRAND["white"] + (235,))

    # شارة عاجل فوق الشريط
    if breaking:
        badge_font = get_font(int(height * 0.032), bold=True)
        badge_text = "عاجل"
        bw, bh = text_size(draw, badge_text, badge_font)
        bp_x, bp_y = int(width * 0.014), int(height * 0.010)
        b_w = bw + bp_x * 2
        b_h = bh + bp_y * 2
        bx0 = width - b_w - int(width * 0.02)
        by0 = bar_y - b_h - int(height * 0.015)
        draw.rounded_rectangle([(bx0, by0), (bx0 + b_w, by0 + b_h)], radius=b_h / 2,
                               fill=BRAND["red"] + (255,))
        draw_rtl(draw, (bx0 + bp_x, by0 + bp_y - bh * 0.1), badge_text, badge_font,
                 BRAND["white"] + (255,))

    # لوجو صغير أعلى اليمين (علامة مائية نصية)
    wm_font = get_font(int(height * 0.030), bold=True)
    wm_text = CHANNEL_NAME_AR
    ww, wh = text_size(draw, wm_text, wm_font)
    wx = width - ww - int(width * 0.02)
    wy = int(height * 0.025)
    box_pad = int(width * 0.008)
    draw.rounded_rectangle(
        [(wx - box_pad, wy - box_pad // 2), (wx + ww + box_pad, wy + wh + box_pad)],
        radius=(wh + box_pad) / 2, fill=BRAND["navy"] + (170,),
        outline=BRAND["gold"] + (220,), width=max(2, height // 450))
    draw_rtl(draw, (wx, wy - wh * 0.1), wm_text, wm_font, BRAND["gold"] + (255,))

    out_path = out_path or f"overlay_{width}x{height}.png"
    img.save(out_path)
    return out_path


def _bg_navy(width, height):
    """خلفية كحلية متدرجة بسيطة"""
    img = PIL.Image.new("RGB", (width, height), BRAND["navy"])
    top = PIL.Image.new("RGB", (width, height // 2), BRAND["navy_dark"])
    img.paste(top, (0, 0))
    img = img.filter(ImageFilter.GaussianBlur(radius=max(8, height // 40)))
    return img


def _gold_frame(draw, width, height):
    m = int(min(width, height) * 0.035)
    draw.rectangle([(m, m), (width - m, height - m)], outline=BRAND["gold"],
                   width=max(3, height // 300))


def create_intro_card(title, out_path="intro_card.png", width=1920, height=1080, date_str=""):
    """بطاقة افتتاحية: عنوان الخبر بخط كبير على هوية القناة"""
    ensure_fonts()
    img = _bg_navy(width, height)
    draw = ImageDraw.Draw(img)
    _gold_frame(draw, width, height)

    # ترويسة القناة
    head_font = get_font(int(height * 0.045), bold=True)
    hw, hh = text_size(draw, CHANNEL_NAME_AR, head_font)
    draw_rtl(draw, ((width - hw) / 2, int(height * 0.12)), CHANNEL_NAME_AR, head_font, BRAND["gold"])
    en_font = get_font(int(height * 0.022), bold=False)
    ew, _ = text_size(draw, CHANNEL_NAME_EN, en_font)
    draw.text(((width - ew) / 2, int(height * 0.12) + hh + int(height * 0.015)), CHANNEL_NAME_EN,
              font=en_font, fill=BRAND["gray"])

    # خط ذهبي فاصل
    line_y = int(height * 0.26)
    draw.rectangle([(int(width * 0.35), line_y), (int(width * 0.65), line_y + max(3, height // 300))],
                   fill=BRAND["gold"])

    # العنوان بأكبر خط يتسع في 3 سطور بدون اختصار
    size = int(height * 0.085)
    title_font = get_font(size, bold=True)
    lines, truncated = wrap_rtl(draw, title, title_font, int(width * 0.80), max_lines=3)
    while truncated and size > int(height * 0.038):
        size = int(size * 0.9)
        title_font = get_font(size, bold=True)
        lines, truncated = wrap_rtl(draw, title, title_font, int(width * 0.80), max_lines=3)

    total_h = 0
    sizes = []
    for ln in lines:
        lw, lh = text_size(draw, ln, title_font)
        sizes.append((lw, lh))
        total_h += lh + int(size * 0.35)
    y = int(height * 0.34) + (int(height * 0.40) - total_h) // 2
    for ln, (lw, lh) in zip(lines, sizes):
        # ظل خفيف ثم النص
        draw_rtl(draw, ((width - lw) / 2 + 3, y + 3), ln, title_font, (0, 0, 0))
        draw_rtl(draw, ((width - lw) / 2, y), ln, title_font, BRAND["white"])
        y += lh + int(size * 0.35)

    # التاريخ أسفل
    if date_str:
        d_font = get_font(int(height * 0.028), bold=False)
        dw, dh = text_size(draw, date_str, d_font)
        draw_rtl(draw, ((width - dw) / 2, int(height * 0.86)), date_str, d_font, BRAND["gold"])

    img.save(out_path)
    return out_path


def create_outro_card(out_path="outro_card.png", width=1920, height=1080):
    """بطاقة ختامية: دعوة للاشتراك"""
    ensure_fonts()
    img = _bg_navy(width, height)
    draw = ImageDraw.Draw(img)
    _gold_frame(draw, width, height)

    main_font = get_font(int(height * 0.085), bold=True)
    line1 = "اشترك في القناة"
    w1, h1 = text_size(draw, line1, main_font)
    draw_rtl(draw, ((width - w1) / 2, int(height * 0.32)), line1, main_font, BRAND["gold"])

    sub_font = get_font(int(height * 0.045), bold=False)
    line2 = "وفعل الجرس عشان يوصلك كل جديد أول بأول"
    w2, h2 = text_size(draw, line2, sub_font)
    draw_rtl(draw, ((width - w2) / 2, int(height * 0.32) + h1 + int(height * 0.05)), line2,
             sub_font, BRAND["white"])

    chip_font = get_font(int(height * 0.035), bold=True)
    cw, ch = text_size(draw, CHANNEL_NAME_AR, chip_font)
    cy = int(height * 0.72)
    draw.rounded_rectangle(
        [((width - cw) / 2 - int(width * 0.015), cy - int(height * 0.012)),
         ((width + cw) / 2 + int(width * 0.015), cy + ch + int(height * 0.018))],
        radius=(ch + int(height * 0.03)) / 2, outline=BRAND["gold"], width=max(3, height // 350))
    draw_rtl(draw, ((width - cw) / 2, cy - ch * 0.1), CHANNEL_NAME_AR, chip_font, BRAND["gold"])

    img.save(out_path)
    return out_path


def enhance_image(path):
    """تحسين بسيط لجودة صورة الخبر: ألوان + تباين + حدة"""
    try:
        img = PIL.Image.open(path).convert("RGB")
        img = ImageEnhance.Color(img).enhance(1.08)
        img = ImageEnhance.Contrast(img).enhance(1.06)
        img = ImageEnhance.Sharpness(img).enhance(1.15)
        img.save(path, "JPEG", quality=95)
        print("✨ تم تحسين الصورة")
    except Exception as e:
        print(f"⚠️ تخطي تحسين الصورة: {e}")


def draw_anchored(draw, xy, text, font, fill, anchor="la"):
    """رسم نص عربي بموضع دقيق: xy هو نقطة المرساة (l/m/r أفقياً، وأعلى الحبر رأسياً).
    يعتمد على قياس الحبر الفعلي textbbox فيعمل بشكل صحيح مع وبدون raqm."""
    t, kw = _ar(text)
    bbox = draw.textbbox((0, 0), t, font=font, **kw)
    x, y = xy
    if anchor.startswith('m'):
        x = x - (bbox[0] + bbox[2]) / 2
    elif anchor.startswith('r'):
        x = x - bbox[2]
    else:
        x = x - bbox[0]
    draw.text((x, y - bbox[1]), t, font=font, fill=fill, **kw)


# ====================== شرائح المحتوى (فيديو بدون أي صور خارجية) ======================
def _fit_font(draw, text, start_size, max_width, max_lines, min_size):
    """أكبر خط يجعل النص يتسع في max_lines بدون اختصار"""
    size = int(start_size)
    while size > min_size:
        font = get_font(size, bold=True)
        lines, truncated = wrap_rtl(draw, text, font, max_width, max_lines=max_lines)
        if not truncated:
            return font, lines
        size = int(size * 0.92)
    font = get_font(min_size, bold=True)
    lines, _ = wrap_rtl(draw, text, font, max_width, max_lines=max_lines)
    return font, lines


def _to_arabic_digits(n):
    return "".join("٠١٢٣٤٥٦٧٨٩"[int(d)] if d.isdigit() else d for d in str(n))


def create_content_slide(text, out_path, width, height, index=1, total=1, kicker=""):
    """
    شريحة محتوى أصلية بالهوية البصرية: خلفية كحلية متدرجة + إطار ذهبي
    + شارة القناة أعلى + النص بخط كبير في المنتصف + شريط تقدم ذهبي أسفل.
    تُستخدم بدلاً من صور المواقع (صفر محتوى محمي بحقوق ملكية).
    """
    ensure_fonts()
    img = _bg_navy(width, height)
    draw = ImageDraw.Draw(img)
    _gold_frame(draw, width, height)

    safe_bottom = int(height * 0.90)   # منطقة آمنة فوق الشريط السفلي

    # شارة القناة أعلى اليمين
    chip_font = get_font(int(height * 0.030), bold=True)
    cw, ch = text_size(draw, CHANNEL_NAME_AR, chip_font)
    pad_x, pad_y = int(width * 0.012), int(height * 0.010)
    cx1 = width - int(width * 0.045) - cw - pad_x * 2
    cy0 = int(height * 0.045)
    draw.rounded_rectangle(
        [(cx1, cy0), (cx1 + cw + pad_x * 2, cy0 + ch + pad_y * 2)],
        radius=(ch + pad_y * 2) / 2, fill=BRAND["navy_dark"],
        outline=BRAND["gold"], width=max(2, height // 450))
    draw_anchored(draw, (cx1 + cw + pad_x, cy0 + pad_y), CHANNEL_NAME_AR,
                  chip_font, BRAND["gold"], anchor="ra")

    # العداد أعلى اليسار
    if total > 1:
        # الرسم RTL يعكس ترتيب السلسلة: نبنيها معكوسة لتظهر "الحالي / الإجمالي"
        counter = f"{_to_arabic_digits(total)} / {_to_arabic_digits(index)}"
        cnt_font = get_font(int(height * 0.026), bold=False)
        draw_anchored(draw, (int(width * 0.05), cy0 + pad_y), counter, cnt_font,
                      BRAND["gray"], anchor="la")

    # سطر افتتاحي صغير (اختياري)
    top_y = int(height * 0.18)
    if kicker:
        k_font = get_font(int(height * 0.034), bold=True)
        kw, kh = text_size(draw, kicker, k_font)
        draw_anchored(draw, (width / 2, top_y), kicker, k_font, BRAND["gold"], anchor="ma")
        line_y = top_y + kh + int(height * 0.028)
        draw.rectangle([(int(width * 0.42), line_y), (int(width * 0.58), line_y + max(2, height // 350))],
                       fill=BRAND["gold"])
        top_y = line_y + int(height * 0.04)

    # النص الرئيسي: أكبر خط يتسع في 4 سطور داخل المنطقة الآمنة
    max_lines = 4 if height >= width else 5
    area_top = top_y + int(height * 0.03)
    area_bottom = safe_bottom - int(height * 0.06)
    font, lines = _fit_font(draw, text, int(height * 0.075), int(width * 0.82),
                            max_lines, int(height * 0.030))
    line_gap = int(font.size * 0.38)
    sizes = [text_size(draw, ln, font) for ln in lines]
    total_h = sum(lh for _, lh in sizes) + line_gap * (len(lines) - 1)
    y = area_top + max(0, (area_bottom - area_top - total_h) // 2)
    for ln, (lw, lh) in zip(lines, sizes):
        draw_anchored(draw, (width / 2 + 3, y + 3), ln, font, (0, 0, 0), anchor="ma")
        draw_anchored(draw, (width / 2, y), ln, font, BRAND["white"], anchor="ma")
        y += lh + line_gap

    # شريط التقدم الذهبي أسفل
    if total > 1:
        bar_w = int(width * 0.5)
        bar_x = (width - bar_w) // 2
        bar_y = safe_bottom - int(height * 0.012)
        draw.rounded_rectangle([(bar_x, bar_y), (bar_x + bar_w, bar_y + max(4, height // 220))],
                               radius=max(2, height // 440), fill=BRAND["navy_dark"],
                               outline=BRAND["gray"], width=1)
        fill_w = int(bar_w * index / total)
        if fill_w > 0:
            draw.rounded_rectangle([(bar_x, bar_y), (bar_x + fill_w, bar_y + max(4, height // 220))],
                                   radius=max(2, height // 440), fill=BRAND["gold"])

    img.save(out_path)
    return out_path


def create_thumbnail(title, out_path="thumbnail.png", width=1280, height=720, breaking=True):
    """
    صورة مصغرة أصلية بالهوية البصرية (١٢٨٠×٧٢٠):
    عنوان كبير بخط Cairo + شارة عاجل + شريط ذهبي + اسم القناة. لا صور خارجية.
    """
    ensure_fonts()
    img = _bg_navy(width, height)
    draw = ImageDraw.Draw(img)

    # شريط ذهبي سفلي عريض + كحلي غامق
    band_h = int(height * 0.16)
    draw.rectangle([(0, height - band_h), (width, height)], fill=BRAND["navy_dark"])
    draw.rectangle([(0, height - band_h), (width, height - band_h + max(6, height // 120))],
                   fill=BRAND["gold"])

    # اسم القناة داخل الشريط
    name_font = get_font(int(band_h * 0.40), bold=True)
    nw, nh = text_size(draw, CHANNEL_NAME_AR, name_font)
    draw_anchored(draw, (width / 2, height - band_h + (band_h - nh) / 2 - int(height * 0.006)),
                  CHANNEL_NAME_AR, name_font, BRAND["gold"], anchor="ma")

    # إطار ذهبي
    m = int(min(width, height) * 0.030)
    draw.rectangle([(m, m), (width - m, height - m)], outline=BRAND["gold"],
                   width=max(4, height // 220))

    # شارة عاجل
    top_area_bottom = height - band_h - m
    if breaking:
        badge_font = get_font(int(height * 0.075), bold=True)
        badge_text = "عاجل"
        bw, bh = text_size(draw, badge_text, badge_font)
        bp_x, bp_y = int(width * 0.022), int(height * 0.014)
        bx0 = width - bw - bp_x * 2 - int(width * 0.035)
        by0 = int(height * 0.045)
        draw.rounded_rectangle([(bx0, by0), (bx0 + bw + bp_x * 2, by0 + bh + bp_y * 2)],
                               radius=(bh + bp_y * 2) / 2, fill=BRAND["red"])
        draw_anchored(draw, (bx0 + bw + bp_x, by0 + bp_y), badge_text, badge_font,
                      BRAND["white"], anchor="ra")

    # العنوان: أكبر خط يتسع في 3 سطور
    font, lines = _fit_font(draw, title, int(height * 0.115), int(width * 0.84), 3,
                            int(height * 0.055))
    line_gap = int(font.size * 0.30)
    sizes = [text_size(draw, ln, font) for ln in lines]
    total_h = sum(lh for _, lh in sizes) + line_gap * (len(lines) - 1)
    area_top = int(height * 0.16)
    y = area_top + max(0, (top_area_bottom - area_top - total_h) // 2)
    for ln, (lw, lh) in zip(lines, sizes):
        # ظل قوي للوضوح على الموبايل
        draw_anchored(draw, (width / 2 + 4, y + 4), ln, font, (0, 0, 0), anchor="ma")
        draw_anchored(draw, (width / 2, y), ln, font, BRAND["white"], anchor="ma")
        y += lh + line_gap

    img.save(out_path)
    return out_path


# =====================================================================
#  محرك الفيديو المتحرك — كل إطار يُرسم بالكود (بدون أي صورة خارجية)
#  خلفية كحلية حية + كروت تنزلق + نص يظهر سطراً سطراً + تايم لاين ذهبي
#  + عدّاد + انتقالات بشريط ضوئي. مناسب لـ 16:9 و 9:16.
# =====================================================================
import math
import random
import numpy as np


def _ease_out(x):
    x = min(max(x, 0.0), 1.0)
    return 1 - (1 - x) ** 3


def _ease_in(x):
    x = min(max(x, 0.0), 1.0)
    return x ** 3


def _ease_back(x):
    x = min(max(x, 0.0), 1.0)
    c1, c3 = 1.2, 2.2
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2


def _lut(f):
    f = min(max(f, 0.0), 1.0)
    return [int(i * f) for i in range(256)]


class _Layer:
    """طبقة RGBA جاهزة للّصق بشفافية متغيرة"""
    def __init__(self, rgba):
        self.w, self.h = rgba.size
        self.rgb = rgba.convert("RGB")
        self.alpha = rgba.getchannel("A")

    def put(self, frame, x, y, opacity=1.0):
        if opacity <= 0.01:
            return
        a = self.alpha if opacity >= 0.99 else self.alpha.point(_lut(opacity))
        frame.paste(self.rgb, (int(x), int(y)), a)


def _text_layer(text, font, fill, pad=14, shadow=True):
    tmp = PIL.Image.new("RGBA", (8, 8))
    d = ImageDraw.Draw(tmp)
    tw, th = text_size(d, text, font)
    w, h = tw + pad * 2 + 6, th + pad * 2 + 6
    img = PIL.Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if shadow:
        draw_anchored(d, (w / 2 + 3, pad + 3), text, font, (0, 0, 0, 170), anchor="ma")
    draw_anchored(d, (w / 2, pad), text, font, fill + (255,), anchor="ma")
    return _Layer(img)


def _glow_sprite(size, color, strength):
    yy, xx = np.mgrid[0:size, 0:size]
    r = np.sqrt((xx - size / 2) ** 2 + (yy - size / 2) ** 2) / (size / 2)
    a = np.clip(1 - r, 0, 1) ** 2 * strength
    rgba = np.zeros((size, size, 4), dtype=np.uint8)
    rgba[..., 0], rgba[..., 1], rgba[..., 2] = color
    rgba[..., 3] = (a * 255).astype(np.uint8)
    return _Layer(PIL.Image.fromarray(rgba, "RGBA"))


class AnimatedScene:
    """يبني فيديو كامل: (مقدمة) + شرائح متحركة + (خاتمة) كدالة زمن → إطار"""

    def __init__(self, slide_texts, durations, width, height, is_shorts,
                 title="", kicker="", date_str="", intro=0.0, outro=0.0):
        ensure_fonts()
        self.W, self.H = width, height
        self.is_shorts = is_shorts
        self.title, self.kicker, self.date_str = title, kicker, date_str
        self.intro, self.outro = intro, outro
        self.texts = list(slide_texts)
        self.n = len(self.texts)
        self.durs = list(durations)
        self.starts = []
        t = intro
        for d in self.durs:
            self.starts.append(t)
            t += d
        self.content_end = t
        self.total = t + outro
        self.rng = random.Random(7)
        base = _bg_navy(width, height)
        # تدرج رأسي خفيف يعطي عمق
        arr = np.asarray(base).astype(np.float32)
        grad = np.linspace(1.12, 0.78, height, dtype=np.float32)[:, None, None]
        self.bg = PIL.Image.fromarray(np.clip(arr * grad, 0, 255).astype(np.uint8))
        s = int(max(width, height) * 0.75)
        self.glow_gold = _glow_sprite(s, BRAND["gold"], 0.20)
        self.glow_blue = _glow_sprite(s, (40, 90, 170), 0.32)
        self._build_stripes()
        self.particles = [(self.rng.random(), self.rng.random(),
                           self.rng.uniform(0.02, 0.07), self.rng.uniform(2, 5),
                           self.rng.random() * 6.28) for _ in range(26 if not is_shorts else 20)]
        self.chip = None
        self._cache = {}
        self.u = height / 1080.0 if not is_shorts else width / 1080.0

    def _build_stripes(self):
        W, H = self.W, self.H
        self.period = int(max(W, H) * 0.16)
        img = PIL.Image.new("RGBA", (W + self.period, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        for x in range(-H, W + self.period, self.period):
            d.line([(x, H), (x + H * 0.6, 0)], fill=BRAND["gold"] + (22,), width=max(2, H // 400))
        self.stripes = _Layer(img)

    # ---------- مكونات ----------
    def _draw_background(self, frame, t):
        W, H = self.W, self.H
        a = t * 0.35
        self.glow_blue.put(frame, W * (0.2 + 0.15 * math.sin(a)) - self.glow_blue.w / 2,
                           H * (0.25 + 0.12 * math.cos(a * 1.3)) - self.glow_blue.h / 2)
        self.glow_gold.put(frame, W * (0.82 + 0.1 * math.cos(a * 0.9)) - self.glow_gold.w / 2,
                           H * (0.78 + 0.1 * math.sin(a * 1.1)) - self.glow_gold.h / 2)
        self.stripes.put(frame, -((t * 22) % self.period), 0, 1.0)
        d = ImageDraw.Draw(frame)
        for px, py, sp, r, ph in self.particles:
            y = (py - t * sp) % 1.0
            x = px + 0.015 * math.sin(t * 0.8 + ph)
            tw = 0.5 + 0.5 * math.sin(t * 2 + ph)
            rr = r * self.u * (0.8 + 0.4 * tw)
            c = int(90 + 120 * tw)
            d.ellipse([x * W - rr, y * H - rr, x * W + rr, y * H + rr],
                      fill=(min(255, c + 100), min(255, c + 60), 70))

    def _frame_chrome(self, frame, t):
        """شارة القناة + إطار ذهبي نابض"""
        W, H = self.W, self.H
        d = ImageDraw.Draw(frame)
        _gold_frame(d, W, H)
        if self.chip is None:
            f = get_font(int(H * 0.030 if not self.is_shorts else W * 0.034), bold=True)
            tmp = PIL.Image.new("RGBA", (8, 8))
            cw, ch = text_size(ImageDraw.Draw(tmp), CHANNEL_NAME_AR, f)
            px, py = int(W * 0.014), int(H * 0.008)
            w, h = cw + px * 2 + 8, ch + py * 2 + 8
            img = PIL.Image.new("RGBA", (w, h), (0, 0, 0, 0))
            dd = ImageDraw.Draw(img)
            dd.rounded_rectangle([(1, 1), (w - 2, h - 2)], radius=h // 2,
                                 fill=BRAND["navy_dark"] + (255,), outline=BRAND["gold"],
                                 width=max(2, H // 450))
            draw_anchored(dd, (w - px - 4, py + 4), CHANNEL_NAME_AR, f, BRAND["gold"], anchor="ra")
            self.chip = _Layer(img)
        self.chip.put(frame, W - int(W * 0.045) - self.chip.w, int(H * 0.045))

    def _timeline(self, frame, t):
        W, H = self.W, self.H
        d = ImageDraw.Draw(frame)
        y = int(H * 0.925)
        x_r, x_l = W * 0.88, W * 0.12            # يمين ← يسار (اتجاه القراءة العربي)
        lw = max(4, H // 200)
        d.rounded_rectangle([x_l, y - lw / 2, x_r, y + lw / 2], radius=lw / 2,
                            fill=(35, 55, 90))
        span = max(self.content_end - self.intro, 0.1)
        prog = min(max((t - self.intro) / span, 0), 1)
        xp = x_r - (x_r - x_l) * prog
        d.rounded_rectangle([xp, y - lw / 2, x_r, y + lw / 2], radius=lw / 2, fill=BRAND["gold"])
        r0 = max(5, int(H * 0.0075))
        for i, st in enumerate(self.starts):
            fx = x_r - (x_r - x_l) * ((st - self.intro) / span)
            done = t >= st
            cur = st <= t < st + self.durs[i]
            r = r0 * (1.6 + 0.35 * math.sin(t * 6)) if cur else r0
            d.ellipse([fx - r, y - r, fx + r, y + r],
                      fill=BRAND["gold"] if done else (35, 55, 90),
                      outline=BRAND["white"] if cur else BRAND["gold"], width=2)
        # العدّاد
        total = self.n
        idx = max(1, min(self.n, 1 + sum(1 for s in self.starts if s <= t) - 1)) if self.n else 1
        counter = f"{_to_arabic_digits(idx)} / {_to_arabic_digits(total)}"
        f = get_font(int(H * 0.026 if not self.is_shorts else W * 0.032), bold=True)
        draw_anchored(d, (int(W * 0.06), int(H * 0.052)), counter, f, BRAND["gray"], anchor="la")

    def _slide_layers(self, i):
        if i in self._cache:
            return self._cache[i]
        W, H = self.W, self.H
        text = self.texts[i]
        tmp = PIL.Image.new("RGBA", (8, 8))
        d = ImageDraw.Draw(tmp)
        card_w = int(W * (0.86 if not self.is_shorts else 0.88))
        card_h = int(H * (0.56 if not self.is_shorts else 0.50))
        start = int((H if not self.is_shorts else W * 1.4) * 0.07)
        while True:
            font, lines = _fit_font(d, text, start, int(card_w * 0.84),
                                    5 if not self.is_shorts else 8, int(H * 0.026))
            lh = [text_size(d, ln, font)[1] + 34 for ln in lines]
            need = sum(lh) + int(font.size * 0.22) * (len(lines) - 1)
            if need <= card_h * 0.86 or start <= int(H * 0.028):
                break
            start = int(start * 0.9)
        # بطاقة زجاجية
        card = PIL.Image.new("RGBA", (card_w, card_h), (0, 0, 0, 0))
        cd = ImageDraw.Draw(card)
        cd.rounded_rectangle([(0, 0), (card_w - 1, card_h - 1)], radius=int(H * 0.025),
                             fill=(8, 22, 45, 215), outline=BRAND["gold"] + (255,),
                             width=max(3, H // 330))
        bar_w = max(8, int(card_w * 0.012))
        side = i % 3
        cd.rounded_rectangle([(card_w - bar_w - 18, 22), (card_w - 18, card_h - 22)],
                             radius=bar_w // 2, fill=BRAND["gold"] + (255,)) if side != 1 else \
            cd.rounded_rectangle([(18, 22), (18 + bar_w, card_h - 22)],
                                 radius=bar_w // 2, fill=BRAND["gold"] + (255,))
        line_layers = [_text_layer(ln, font, BRAND["white"]) for ln in lines]
        gap = int(font.size * 0.22)
        total_h = sum(l.h for l in line_layers) + gap * (len(line_layers) - 1)
        y = (card_h - total_h) // 2
        positions = []
        for l in line_layers:
            positions.append(((card_w - l.w) // 2, y))
            y += l.h + gap
        ghost_font = get_font(int(H * (0.55 if not self.is_shorts else 0.30)), bold=True)
        ghost = _text_layer(_to_arabic_digits(i + 1), ghost_font, BRAND["gold"], shadow=False)
        ghost.alpha = ghost.alpha.point(_lut(0.07))
        kf = get_font(int(H * 0.034 if not self.is_shorts else W * 0.04), bold=True)
        kick = _text_layer(self.kicker, kf, BRAND["gold"], shadow=False) if self.kicker else None
        out = dict(card=_Layer(card), lines=line_layers, pos=positions, ghost=ghost,
                   kick=kick, card_w=card_w, card_h=card_h)
        # حذف الشرائح القديمة لتوفير الذاكرة
        for k in [k for k in self._cache if isinstance(k, int) and k < i - 1]:
            del self._cache[k]
        self._cache[i] = out
        return out

    def _draw_slide(self, frame, i, t):
        W, H = self.W, self.H
        lt = t - self.starts[i]
        dur = self.durs[i]
        L = self._slide_layers(i)
        side = i % 3
        tin, tout = 0.65, 0.4
        pin = _ease_out(lt / tin)
        pout = _ease_in((lt - (dur - tout)) / tout)
        cx = (W - L["card_w"]) / 2
        cy = H * (0.50 if not self.is_shorts else 0.47) - L["card_h"] / 2
        travel = W * 0.35
        if side == 0:
            dx, dy = (1 - pin) * travel - pout * travel, 0
        elif side == 1:
            dx, dy = -(1 - pin) * travel + pout * travel, 0
        else:
            dx, dy = 0, (1 - _ease_back(lt / tin)) * H * 0.25 + pout * H * 0.15
        op = min(pin * 1.4, 1.0) * (1 - pout)
        # رقم شبحي كبير خلف الكارت
        gx = W * (0.5 if self.is_shorts else 0.14) - L["ghost"].w / 2 + (1 - pin) * 80 - pout * 80
        L["ghost"].put(frame, gx, H * 0.5 - L["ghost"].h / 2, op)
        L["card"].put(frame, cx + dx, cy + dy, op)
        for k, (ll, (lx, ly)) in enumerate(zip(L["lines"], L["pos"])):
            lp = _ease_out((lt - 0.25 - 0.14 * k) / 0.5)
            lo = lp * (1 - pout)
            ll.put(frame, cx + dx + lx, cy + dy + ly + (1 - lp) * H * 0.04, lo)
        # كيكر + خط ذهبي يتمدد
        if L["kick"] is not None:
            ky = cy - L["kick"].h - H * 0.035
            L["kick"].put(frame, (W - L["kick"].w) / 2, ky, op)
            d = ImageDraw.Draw(frame)
            wl = (W * 0.16) * _ease_out((lt - 0.2) / 0.6) * (1 - pout)
            d.rectangle([W / 2 - wl, ky + L["kick"].h + 2, W / 2 + wl,
                         ky + L["kick"].h + 2 + max(3, H // 330)], fill=BRAND["gold"])
        # شريط الانتقال الضوئي عند بداية كل شريحة
        if i > 0 and lt < 0.55:
            sx = W * (1.15 - 1.3 * (lt / 0.55))
            band = PIL.Image.new("RGB", (int(W * 0.10), H), BRAND["gold"])
            mask = PIL.Image.linear_gradient("L").rotate(90).resize((band.width, H))
            mask = mask.point(lambda v: int((255 - abs(v - 127) * 2) * 0.35))
            frame.paste(band, (int(sx), 0), mask)

    def _draw_intro(self, frame, t):
        W, H = self.W, self.H
        c = self._cache.get("intro")
        if c is None:
            d = ImageDraw.Draw(PIL.Image.new("RGBA", (8, 8)))
            hf = get_font(int(H * 0.075), bold=True)
            head = _text_layer(CHANNEL_NAME_AR, hf, BRAND["gold"])
            ef = get_font(int(H * 0.026), bold=False)
            en = _text_layer(CHANNEL_NAME_EN, ef, BRAND["gray"], shadow=False)
            font, lines = _fit_font(d, self.title, int(H * 0.085), int(W * 0.82), 3, int(H * 0.036))
            tl = [_text_layer(ln, font, BRAND["white"]) for ln in lines]
            df = get_font(int(H * 0.03), bold=False)
            date = _text_layer(self.date_str, df, BRAND["gold"], shadow=False) if self.date_str else None
            c = self._cache["intro"] = (head, en, tl, date)
        head, en, tl, date = c
        s = _ease_back(t / 0.7)
        head.put(frame, (W - head.w) / 2, H * 0.11 + (1 - s) * -H * 0.08, min(t / 0.5, 1))
        en.put(frame, (W - en.w) / 2, H * 0.11 + head.h + 4, min(max(t - 0.3, 0) / 0.5, 1))
        d = ImageDraw.Draw(frame)
        ly = H * 0.30
        wl = W * 0.17 * _ease_out((t - 0.3) / 0.8)
        d.rectangle([W / 2 - wl, ly, W / 2 + wl, ly + max(3, H // 300)], fill=BRAND["gold"])
        total_h = sum(l.h for l in tl)
        y = H * 0.38 + (H * 0.38 - total_h) / 2
        for k, l in enumerate(tl):
            p = _ease_out((t - 0.6 - 0.25 * k) / 0.6)
            l.put(frame, (W - l.w) / 2 + (1 - p) * W * 0.12, y, p)
            y += l.h
        if date is not None:
            date.put(frame, (W - date.w) / 2, H * 0.86, min(max(t - 1.4, 0) / 0.6, 1))

    def _draw_outro(self, frame, t):
        W, H = self.W, self.H
        c = self._cache.get("outro")
        if c is None:
            f1 = get_font(int(H * 0.085), bold=True)
            f2 = get_font(int(H * 0.042), bold=False)
            c = self._cache["outro"] = (
                _text_layer("اشترك في القناة", f1, BRAND["gold"]),
                _text_layer("وفعل الجرس عشان يوصلك كل جديد أول بأول", f2, BRAND["white"]),
                _text_layer(CHANNEL_NAME_AR, get_font(int(H * 0.05), bold=True), BRAND["gold"]))
        a, b, ch = c
        p1 = _ease_back(t / 0.7)
        a.put(frame, (W - a.w) / 2, H * 0.30 + (1 - p1) * H * 0.12, min(t / 0.4, 1))
        b.put(frame, (W - b.w) / 2, H * 0.30 + a.h + H * 0.03, min(max(t - 0.4, 0) / 0.6, 1))
        pulse = 1 + 0.04 * math.sin(t * 5)
        d = ImageDraw.Draw(frame)
        cx, cy = W / 2, H * 0.72
        rw, rh = ch.w * 0.62 * pulse, ch.h * 0.75 * pulse
        d.rounded_rectangle([cx - rw, cy - rh, cx + rw, cy + rh], radius=int(rh),
                            outline=BRAND["gold"], width=max(3, H // 350))
        ch.put(frame, cx - ch.w / 2, cy - ch.h / 2, min(max(t - 0.7, 0) / 0.5, 1))

    # ---------- الإطار ----------
    def frame_at(self, t):
        t = min(max(t, 0.0), self.total - 1e-3)
        frame = self.bg.copy()
        self._draw_background(frame, t)
        if t < self.intro:
            self._draw_intro(frame, t)
        elif t >= self.content_end:
            self._draw_outro(frame, t - self.content_end)
        else:
            i = max(k for k, s in enumerate(self.starts) if s <= t)
            self._draw_slide(frame, i, t)
            self._timeline(frame, t)
        self._frame_chrome(frame, t)
        return np.asarray(frame)


def build_animated_clip(slide_texts, durations, width, height, is_shorts,
                        title="", kicker="", date_str="", intro=0.0, outro=0.0):
    """يرجع (VideoClip, المدة الكلية)"""
    from moviepy.editor import VideoClip
    scene = AnimatedScene(slide_texts, durations, width, height, is_shorts,
                          title=title, kicker=kicker, date_str=date_str,
                          intro=intro, outro=outro)
    return VideoClip(scene.frame_at, duration=scene.total), scene.total
