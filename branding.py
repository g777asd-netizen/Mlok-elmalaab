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
        counter = f"{_to_arabic_digits(index)} / {_to_arabic_digits(total)}"
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
