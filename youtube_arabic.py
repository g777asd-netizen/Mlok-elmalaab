import os
import asyncio
import requests
import json
import base64
import re
import random
import sys
import time
import pickle
import logging
from datetime import datetime
from bs4 import BeautifulSoup
import PIL.Image
from PIL import ImageOps, ImageFilter, ImageDraw, ImageFont
import numpy as np

# ====================== إعدادات تقليل اللوج (Clean Logs) ======================
logging.basicConfig(level=logging.CRITICAL)
logging.getLogger('googleapiclient').setLevel(logging.CRITICAL)
logging.getLogger('urllib3').setLevel(logging.CRITICAL)
logging.getLogger('moviepy').setLevel(logging.CRITICAL)

# ====================== إصلاح توافق Pillow مع MoviePy ======================
if not hasattr(PIL.Image, 'Resampling'):
    PIL.Image.Resampling = PIL.Image
try:
    PIL.Image.ANTIALIAS = PIL.Image.Resampling.LANCZOS
except AttributeError:
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from moviepy.editor import (AudioFileClip, ImageClip,
                            CompositeVideoClip, CompositeAudioClip,
                            concatenate_videoclips)
from groq import Groq
from branding import (create_thumbnail, ensure_fonts, build_animated_clip)
from gemini_voice import generate_voice
from script_prompt import SYSTEM_MSG, build_prompt, polish_script, clean_script_keep_tashkeel
from pronunciation import script_problems, numbers_to_words, egyptianize
from script_review import gemini_review
from visuals import validate_visuals
from trending import find_trending_topic, trend_slug
import sources_extra
from music_bed import render_music_bed

# ====================== المتغيرات البيئة والإعدادات ======================
GROQ_API_KEY = os.environ.get('GROQ_API_KEY')
YOUTUBE_TOKEN_B64 = os.environ.get('YOUTUBE_TOKEN')
FACEBOOK_ACCESS_TOKEN = os.environ.get('FACEBOOK_ACCESS_TOKEN')
FACEBOOK_PAGE_ID = os.environ.get('FACEBOOK_PAGE_ID')

VIDEO_WIDTH = 1920
VIDEO_HEIGHT = 1080
SHORTS_WIDTH = 1080
SHORTS_HEIGHT = 1920
FPS = 30
HISTORY_FILE = "history.json"
SOURCE_INDEX_FILE = "source_index.json"
FAILED_LINKS_FILE = "failed_links.json"
ROTATION_FILE = "rotation_state.json"
CHANNEL_NAME_AR = "ملوك الملعب"
CHANNEL_NAME_EN = "Kings of the Stadium"

# إعدادات الشرائح والموسيقى
CROSSFADE_SEC = 0.5
INTRO_DURATION = 3.0
OUTRO_DURATION = 3.5
MAX_LONG_SLIDES = 40
MAX_SHORT_SLIDES = 12
MUSIC_VOLUME = 0.16       # مستوى الموسيقى تحت التعليق الصوتي

# ====================== موديلات Groq المدعومة فقط (محدث سبتمبر 2026) ======================
# llama-3.3-70b-versatile و llama-3.1-8b-instant بقوا Enterprise فقط ومش متاحين لحسابات المطورين العادية
# mixtral-8x7b-32768 و gemma2-9b-it و llama3-8b-8192 اتلغوا (decommissioned)
GROQ_MODELS = [
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "qwen/qwen3.6-27b",
    "openai/gpt-oss-safeguard-20b"
]

# ====================== المصادر مرقمة بالترتيب ======================
SOURCES = [
    {"id": 1, "name": "Btolat", "url": "https://www.btolat.com/news"},
    {"id": 2, "name": "Arriyadiyah", "url": "https://www.arriyadiyah.com/"},
    {"id": 3, "name": "So3ody", "url": "https://www.so3ody.com/"},
    {"id": 4, "name": "TalkSport", "url": "https://talksport.com/football/"},
    {"id": 5, "name": "London Football", "url": "https://www.football.london/"},
    {"id": 6, "name": "Yardbarker", "url": "https://www.yardbarker.com/soccer"},
    {"id": 7, "name": "FourFourTwo", "url": "https://www.fourfourtwo.com/news"},
    {"id": 8, "name": "TeamTalk", "url": "https://www.teamtalk.com/"},
    {"id": 9, "name": "Man Evening News", "url": "https://www.manchestereveningnews.co.uk/sport/football/"}
]

# ====================== الكلمات المفتاحية ======================
KEYWORDS_ARABIC = [
    "كرة القدم",
    "مباراة",
    "هدف",
    "أهداف",
    "ملخص",
    "الدوري",
    "الكأس",
    "البطولة",
    "انتقالات",
    "ميركاتو",
    "صفقة",
    "عاجل",
    "رسميا",
    "تشكيل",
    "مدرب",
    "ركلة جزاء",
    "تسلل",
    "طرد",
    "إنذار",
    "حكم",
    "فار",
    "VAR",
    "إصابة",
    "تصفيات",
    "نهائي",
    "نصف نهائي",
    "دوري أبطال",
    "الكونفدرالية",
    "الدوري الإنجليزي",
    "الدوري الإسباني",
    "الدوري السعودي",
    "دوري روشن",
    "كأس العالم",
    "كأس الأمم",
    "يورو",
    "السوبر",
    "الأهلي",
    "الزمالك",
    "بيراميدز",
    "المصري",
    "الإسماعيلي",
    "الهلال",
    "النصر",
    "الاتحاد",
    "الأهلي السعودي",
    "الشباب",
    "ريال مدريد",
    "برشلونة",
    "ليفربول",
    "مانشستر سيتي",
    "مانشستر يونايتد",
    "أرسنال",
    "تشيلسي",
    "بايرن ميونخ",
    "باريس سان جيرمان",
    "محمد صلاح",
    "صلاح",
    "كريستيانو رونالدو",
    "رونالدو",
    "ميسي",
    "نيمار",
    "بنزيما"
]

KEYWORDS_ENGLISH = [
    "football",
    "soccer",
    "goal",
    "match",
    "league",
    "cup",
    "transfer",
    "premier league",
    "laliga",
    "serie a",
    "bundesliga",
    "champions league",
    "world cup",
    "euro",
    "real madrid",
    "barcelona",
    "liverpool",
    "man city",
    "arsenal",
    "al ahly",
    "zamalek",
    "al hilal",
    "al nassr",
    "salah",
    "messi",
    "ronaldo",
    "mbappe",
    "haaland",
    "benzema"
]

STRICT_KEYWORDS = KEYWORDS_ARABIC + KEYWORDS_ENGLISH

BLACKLIST_KEYWORDS = [
    "basketball",
    "tennis",
    "nba",
    "f1",
    "politics",
    "economy",
    "art",
    "cinema",
    "weather",
    "crime",
    "election",
    "كرة سلة",
    "تنس",
    "سياسة",
    "اقتصاد",
    "فن",
    "سينما",
    "طقس",
    "جريمة"
]


# ====================== نظام التناوب (ترندي / مصدر) ======================
def get_next_video_type():
    """نوع الفيديو المطلوب في التشغيلة دي: trending أو source"""
    if os.path.exists(ROTATION_FILE):
        try:
            with open(ROTATION_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if data.get('next_type') in ('trending', 'source'):
                    return data['next_type']
        except Exception as e:
            print(f"⚠️ خطأ في قراءة ملف التناوب: {e}")
    return "trending"


def save_next_video_type(next_type):
    """حفظ نوع الفيديو للتشغيلة القادمة"""
    data = {
        'next_type': next_type,
        'updated_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    with open(ROTATION_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    print(f"🔁 التشغيلة القادمة: {'موضوع ترندي' if next_type == 'trending' else 'خبر من مصدر'}")


# ====================== نظام ترتيب المصادر (محسن) ======================
def get_current_source_index():
    """الحصول على رقم المصدر الحالي من الملف"""
    if os.path.exists(SOURCE_INDEX_FILE):
        try:
            with open(SOURCE_INDEX_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('current_index', 0)
        except Exception as e:
            print(f"⚠️ خطأ في قراءة ملف المصادر: {e}")
            return 0
    return 0


def save_next_source_index(current_index):
    """حفظ رقم المصدر التالي للتشغيل القادم"""
    next_index = (current_index + 1) % len(SOURCES)

    data = {
        'current_index': next_index,
        'last_used_index': current_index,
        'last_used_source': SOURCES[current_index]['name'],
        'updated_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'total_sources': len(SOURCES)
    }

    with open(SOURCE_INDEX_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

    print(f"📝 تم حفظ المصدر التالي: [{next_index + 1}/{len(SOURCES)}] {SOURCES[next_index]['name']}")


def get_current_source():
    """الحصول على المصدر الحالي للاستخدام"""
    current_index = get_current_source_index()
    source = SOURCES[current_index]

    print(f"")
    print(f"📌 ═══════════════════════════════════════════════")
    print(f"📌 المصدر الحالي: [{source['id']}/{len(SOURCES)}] {source['name']}")
    print(f"📌 الرابط: {source['url']}")
    print(f"📌 ═══════════════════════════════════════════════")
    print(f"")

    return current_index, source


# ====================== دوال الهيستوري ======================
def load_history():
    """تحميل كل الروابط من الهيستوري"""
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list) and len(data) > 0:
                    if isinstance(data[0], dict):
                        return {item['link'] for item in data if 'link' in item}
                    else:
                        return set(data)
        except Exception as e:
            print(f"⚠️ خطأ في قراءة الهيستوري: {e}")
            return set()
    return set()


def save_history(link, source_name):
    """حفظ الرابط الجديد في الهيستوري مع كل الروابط السابقة"""
    data = []
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if not isinstance(data, list):
                    data = []
        except Exception as e:
            print(f"⚠️ خطأ في قراءة الهيستوري للحفظ: {e}")
            data = []

    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_entry = {
        "link": link,
        "source": source_name,
        "added_at": current_time
    }

    data.append(new_entry)

    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

    print(f"✅ تم حفظ الرابط في الهيستوري (إجمالي: {len(data)} رابط)")


# ====================== دوال الروابط الفاشلة ======================
def save_failed_link(link, source_name, reason):
    """حفظ رابط فشل مع سبب الفشل في ملف منفصل عشان نراجعهم"""
    data = []
    if os.path.exists(FAILED_LINKS_FILE):
        try:
            with open(FAILED_LINKS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if not isinstance(data, list):
                    data = []
        except Exception as e:
            print(f"⚠️ خطأ في قراءة ملف الروابط الفاشلة: {e}")
            data = []

    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_entry = {
        "link": link,
        "source": source_name,
        "reason": reason,
        "failed_at": current_time
    }

    data.append(new_entry)

    with open(FAILED_LINKS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

    print(f"📝 تم تسجيل رابط فاشل ({reason}): {link}")


# ====================== دوال التنظيف ======================
def clean_text_strict(text):
    """تنظيف النص من الحروف الإنجليزية والرموز الغريبة"""
    if not text:
        return ""
    text = re.sub(r'[a-zA-Z]', '', text)
    text = re.sub(r'[^؀-ۿ0-9\s\.\,\!\?\(\)\-\#\_]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


_META_PAT = re.compile(
    r"(ذكاء\s*اصطناعي|الذكاء\s*الاصطناعي|نقلا\s*عن|نقلاً\s*عن|وفقا\s*ل|وفقاً\s*ل|"
    r"بحسب\s*(موقع|صحيفة|تقرير)|حسب\s*(موقع|صحيفة|تقرير)|المصدر|المصادر|مصدر\s*الخبر|"
    r"جوجل\s*ترند|Google|Trends|\bAI\b|ChatGPT|Groq|Gemini)", re.I)

def strip_meta_mentions(text):
    """يشيل أي جملة بتذكر الذكاء الاصطناعي أو مصدر الخبر من الوصف/البوست."""
    if not text:
        return ""
    parts = re.split(r"(?<=[\.\!\?؟\n])\s+", text)
    kept = [p for p in parts if not _META_PAT.search(p)]
    return re.sub(r"\s+", " ", " ".join(kept)).strip()


# ====================== استخراج المحتوى (نص فقط — بلا صور) ======================
def get_article_content(url):
    """استخراج عنوان ومحتوى المقال من الرابط — لا يتم تحميل أي صور"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=8)
        soup = BeautifulSoup(response.content, 'html.parser')

        title = ""
        if soup.title:
            title = soup.title.string
        h1 = soup.find('h1')
        if h1:
            title = h1.get_text().strip()

        paragraphs = soup.find_all('p')
        text_content = " ".join([p.get_text().strip() for p in paragraphs if len(p.get_text().strip()) > 30])

        if len(text_content) < 500:
            return None

        return {
            'title': title,
            'text': text_content,
            'url': url
        }
    except Exception as e:
        return None


# ====================== البحث عن الأخبار (بالترتيب) ======================
MAX_SEARCH_SECONDS = 240  # 4 دقائق كحد أقصى لمرحلة البحث كلها عبر كل المصادر

def find_best_news():
    """البحث عن أفضل خبر بالترتيب - بتجرب كل المصادر في نفس التشغيلة قبل ما توقف، مع حد زمني أقصى"""
    history = load_history()

    total_sources = len(SOURCES)
    attempts = 0
    start_time = time.time()

    while attempts < total_sources:
        elapsed = time.time() - start_time
        if elapsed > MAX_SEARCH_SECONDS:
            print(f"⏱️ تم تجاوز الحد الأقصى لوقت البحث ({MAX_SEARCH_SECONDS}s) - إيقاف البحث والاكتفاء بالمحاولات اللي تمت")
            break

        attempts += 1
        current_index, source = get_current_source()
        save_next_source_index(current_index)

        try:
            print(f"🔎 جاري البحث في: {source['name']}...")
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            resp = requests.get(source['url'], headers=headers, timeout=8)
            soup = BeautifulSoup(resp.content, 'html.parser')

            links = soup.find_all('a', href=True)
            valid_links = []

            for a in links:
                href = a['href']
                if not href.startswith('http'):
                    base = "/".join(source['url'].split('/')[:3])
                    if href.startswith('/'):
                        href = base + href
                    else:
                        href = base + '/' + href

                if href in history:
                    continue

                check_str = (href + " " + a.get_text()).lower()

                is_sports = False
                for kw in STRICT_KEYWORDS:
                    if kw.lower() in check_str:
                        is_sports = True
                        break

                if not is_sports:
                    continue

                is_blacklisted = False
                for bl in BLACKLIST_KEYWORDS:
                    if bl.lower() in check_str:
                        is_blacklisted = True
                        break

                if is_blacklisted:
                    continue

                if len(a.get_text().strip()) > 15:
                    valid_links.append(href)

            print(f"📋 تم العثور على {len(valid_links)} رابط محتمل")

            if valid_links:
                random.shuffle(valid_links)
                for chosen_link in valid_links[:5]:
                    if time.time() - start_time > MAX_SEARCH_SECONDS:
                        print(f"⏱️ تم تجاوز الحد الأقصى لوقت البحث أثناء تجربة الروابط - إيقاف")
                        break
                    data = get_article_content(chosen_link)

                    if data and len(data['text']) > 800:
                        title_check = data['title'].lower()
                        has_keyword = False
                        for kw in STRICT_KEYWORDS:
                            if kw.lower() in title_check:
                                has_keyword = True
                                break

                        if has_keyword:
                            print(f"🎯 تم العثور على خبر مناسب!")
                            data['source_name'] = source['name']
                            data['source_id'] = source['id']
                            return data
                        else:
                            save_failed_link(chosen_link, source['name'], "العنوان لا يحتوي على كلمات مفتاحية رياضية")
                    else:
                        save_failed_link(chosen_link, source['name'], "فشل استخراج المحتوى / المحتوى قصير")

            print(f"😔 لم يتم العثور على خبر مناسب في {source['name']}")

        except Exception as e:
            print(f"❌ خطأ في المصدر {source['name']}: {e}")

        if attempts < total_sources:
            print(f"➡️ جاري الانتقال للمصدر التالي في نفس التشغيلة...")

    print(f"😴 تم تجربة كل المصادر ({total_sources}) في هذه التشغيلة ولم يتم العثور على خبر مناسب")
    return None


# ====================== الذكاء الاصطناعي (محتوى طويل) ======================
def generate_ai_content(article):
    """توليد المحتوى باستخدام الذكاء الاصطناعي"""
    client = Groq(api_key=GROQ_API_KEY)

    # تقصير نص المقال عشان مايتجاوزش حد التوكنز بالدقيقة (TPM) في الخطة المجانية
    MAX_ARTICLE_CHARS = 3000
    article_text = article['text']
    if len(article_text) > MAX_ARTICLE_CHARS:
        article_text = article_text[:MAX_ARTICLE_CHARS]

    n = len(article_text)
    words = "700-900" if n >= 1500 else ("400-550" if n >= 700 else "200-300")
    prompt = build_prompt(article['title'], article_text, words=words)

    for model in GROQ_MODELS:
        try:
            print(f"🤖 جاري التجربة مع موديل: {model}")

            completion = client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": SYSTEM_MSG
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.4,
                max_tokens=4000,
                response_format={"type": "json_object"}
            )

            content = json.loads(completion.choices[0].message.content)

            content['video_title'] = clean_text_strict(content.get('video_title', ''))
            # تدقيق مصري + أرقام بالكلمات + فحص المشاكل قبل التنظيف
            for _k in ("video_script", "shorts_script"):
                _raw = content.get(_k, '') or ''
                _raw = polish_script(client, model, numbers_to_words(_raw), article_text)   # مراجعة ١ (Groq)
                _raw = gemini_review(_raw, article_text, label=_k)                          # مراجعة ٢ (Gemini)
                content[_k] = numbers_to_words(egyptianize(_raw))
            _probs = script_problems(content["video_script"], article_text) + \
                     script_problems(content["shorts_script"], article_text)
            if _probs:
                print(f"⚠️ مشاكل في سكريبت {model}: {_probs} - تجربة الموديل التالي")
                continue
            content['visuals'] = validate_visuals(content.get('visuals'), article_text)
            print(f"🎨 بيانات الرسومات المقبولة: {list(content['visuals'].keys()) or 'مفيش (هتستخدم مشاهد عامة)'}")
            content['video_script'] = clean_script_keep_tashkeel(content['video_script'])
            content['video_description'] = strip_meta_mentions(clean_text_strict(content.get('video_description', '')))
            content['shorts_title'] = clean_text_strict(content.get('shorts_title', ''))
            content['shorts_script'] = clean_script_keep_tashkeel(content.get('shorts_script', ''))
            content['facebook_post'] = strip_meta_mentions(clean_text_strict(content.get('facebook_post', '')))

            tags = []
            for t in content.get('hashtags', []):
                ct = clean_text_strict(t).replace(' ', '_')
                if ct and not ct.startswith('#'):
                    ct = '#' + ct
                if len(ct) > 2:
                    tags.append(ct)

            defaults = [
                "#كرة_القدم",
                "#الرياضة",
                "#أخبار_رياضية",
                "#الدوري_الانجليزي",
                "#دوري_ابطال_اوروبا",
                "#الأهلي",
                "#الزمالك",
                "#ليفربول",
                "#ريال_مدريد",
                "#محمد_صلاح",
                "#الهلال",
                "#النصر",
                "#الدوري_السعودي",
                "#مانشستر_سيتي",
                "#برشلونة",
                "#بايرن_ميونخ",
                "#ميسي",
                "#رونالدو",
                "#نيمار",
                "#عاجل"
            ]

            while len(tags) < 15:
                for d in defaults:
                    if d not in tags:
                        tags.append(d)
                    if len(tags) >= 15:
                        break

            content['hashtags'] = tags[:15]

            if len(content['video_title']) > 60:
                content['video_title'] = content['video_title'][:57] + "..."

            if len(content['shorts_title']) > 40:
                content['shorts_title'] = content['shorts_title'][:37] + "..."

            print(f"✅ تم توليد المحتوى بنجاح باستخدام: {model}")
            return content

        except Exception as e:
            print(f"⚠️ فشل الموديل {model}: {e}")
            continue

    print("❌ فشلت جميع الموديلات")
    return None


# ====================== توليد الصوت ======================
async def generate_audio(text, output_file):
    """توليد الصوت: Gemini TTS بأسلوب التعليق المصري الطبيعي (صوت Charon)،
    ومع edge-tts (شاكر) كخطة بديلة تلقائية لو المفتاح غير موجود أو فشل التوليد"""
    engine = await generate_voice(text, output_file)
    print(f"✅ تم توليد الصوت [{engine}]: {output_file}")
    return output_file


# ====================== ضمان حد الشورتس (أقل من ٦٠ ثانية) ======================
SHORTS_MAX_SECONDS = 58.0

def enforce_shorts_duration(audio_path):
    """لو صوت الشورتس عدّى الحد، يتسرّع قليلاً (atempo) ليدخل في حدود يوتيوب شورتس"""
    try:
        import subprocess
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", audio_path],
            capture_output=True, text=True, timeout=30)
        duration = float(probe.stdout.strip())
        if duration <= SHORTS_MAX_SECONDS:
            return
        factor = duration / SHORTS_MAX_SECONDS
        print(f"⏱️ صوت الشورتس {duration:.1f}ث — تسريع ×{factor:.2f} ليدخل في حد {SHORTS_MAX_SECONDS:.0f}ث")
        tmp = audio_path + ".fast.mp3"
        subprocess.run(
            ["ffmpeg", "-y", "-i", audio_path, "-filter:a", f"atempo={factor:.4f}",
             "-codec:a", "libmp3lame", "-b:a", "192k", tmp],
            check=True, capture_output=True, timeout=120)
        os.replace(tmp, audio_path)
    except Exception as e:
        print(f"⚠️ تعذر ضبط مدة الشورتس: {e}")


# ====================== الشرائح من السكريبت ======================
def derive_slide_lines(script, max_slides, max_chars=170):
    """اشتقاق أسطر الشرائح من جُمل السكريبت نفسه (تطابق تام مع التعليق الصوتي)"""
    sentences = [s.strip() for s in re.split(r'(?<=[\.!\?؟])\s+', script.replace('\n', ' '))
                 if len(s.strip()) > 2]
    if not sentences:
        sentences = [script.strip()[:max_chars] or CHANNEL_NAME_AR]

    # الجُمل الطويلة جداً تتقسم على حدود الكلمات
    pieces = []
    for s in sentences:
        while len(s) > max_chars:
            cut = s.rfind(' ', 0, max_chars)
            cut = cut if cut > 40 else max_chars
            pieces.append(s[:cut])
            s = s[cut:].strip()
        if s:
            pieces.append(s)

    # دمج أقصر جملتين متتاليتين حتى نصل للعدد المطلوب
    slides = pieces
    while len(slides) > max_slides:
        lengths = [len(a) + len(b) for a, b in zip(slides, slides[1:])]
        i = lengths.index(min(lengths))
        slides = slides[:i] + [slides[i] + " " + slides[i + 1]] + slides[i + 2:]

    return slides


def _slide_durations(slide_texts, total_seconds):
    """توزيع مدة الشرائح بالتناسب مع طول نص كل شريحة"""
    weights = [max(len(t), 20) for t in slide_texts]
    total_w = sum(weights)
    durations = [total_seconds * w / total_w for w in weights]
    durations = [max(2.5, d) for d in durations]
    scale = total_seconds / sum(durations)
    return [d * scale for d in durations]


# ====================== إنشاء الفيديو بالشرائح + الموسيقى ======================
def create_slideshow_video(slide_texts, audio_path, output_path, width, height,
                           is_shorts, title=None, kicker="", visuals=None):
    """
    فيديو من شرائح أصلية التصميم (بدون أي صورة خارجية):
    بطاقة افتتاحية + شرائح المحتوى بحركة زوم هادئة وانتقالات ناعمة + بطاقة ختامية،
    مع تعليق صوتي وموسيقى خلفية أصلية مولدة بالكود.
    """
    slide_files = []
    music_path = None
    try:
        video_type = "شورتس" if is_shorts else "فيديو"
        print(f"🎬 جاري المونتاج بالشرائح ({video_type})...")

        voice = AudioFileClip(audio_path)
        content_dur = voice.duration
        print(f"⏱️ مدة التعليق: {content_dur:.1f} ثانية ({content_dur/60:.2f} دقيقة)")

        durations = _slide_durations(slide_texts, content_dur)
        intro_d = 0.0 if is_shorts else INTRO_DURATION
        outro_d = 0.0 if is_shorts else OUTRO_DURATION
        date_str = datetime.now().strftime("%Y/%m/%d")
        final, total_dur = build_animated_clip(
            slide_texts, durations, width, height, is_shorts,
            title=title or CHANNEL_NAME_AR, kicker=kicker, date_str=date_str,
            intro=intro_d, outro=outro_d, visuals=visuals)
        print(f"🎞️ {len(slide_texts)} مشهد متحرك — المدة الكلية: {total_dur:.1f} ثانية")

        # موسيقى خلفية أصلية بطول الفيديو بالظبط
        music_path = "music_bed.wav"
        render_music_bed(music_path, total_dur)
        music = AudioFileClip(music_path).volumex(MUSIC_VOLUME)

        voice_start = (INTRO_DURATION) if not is_shorts else 0.0
        audio_mix = CompositeAudioClip([music, voice.set_start(voice_start)])
        audio_mix = audio_mix.set_duration(total_dur)
        final = final.set_audio(audio_mix)

        final.write_videofile(
            output_path,
            fps=FPS,
            codec="libx264",
            audio_codec="aac",
            audio_bitrate="192k",
            bitrate="6000k",
            preset="veryfast",
            threads=4,
            ffmpeg_params=["-pix_fmt", "yuv420p", "-movflags", "+faststart"],
            verbose=False,
            logger=None
        )

        print(f"✅ تم إنشاء {video_type}: {output_path}")
        return True

    except Exception as e:
        print(f"❌ Video Error: {e}")
        return False

    finally:
        for tmp in slide_files:
            if tmp and os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except OSError:
                    pass
        if music_path and os.path.exists(music_path):
            try:
                os.remove(music_path)
            except OSError:
                pass


# ====================== الرفع لليوتيوب ======================
def get_youtube_service():
    """الحصول على خدمة يوتيوب"""
    try:
        raw_token = ''.join((YOUTUBE_TOKEN_B64 or '').split()).strip('"\'')
        raw_token += '=' * (-len(raw_token) % 4)
        token_data = base64.b64decode(raw_token)

        try:
            creds = pickle.loads(token_data)
        except Exception as e:
            creds_data = json.loads(token_data.decode('utf-8'))
            creds = Credentials.from_authorized_user_info(creds_data)

        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())

        return build('youtube', 'v3', credentials=creds)

    except Exception as e:
        print(f"❌ Youtube Auth Error: {e}")
        return None


def upload_to_youtube(video_path, title, description, tags, is_shorts, thumbnail_path=None):
    """رفع الفيديو لليوتيوب مع الصورة المصغرة المخصصة"""
    youtube = get_youtube_service()
    if not youtube:
        return False

    video_type = "شورتس" if is_shorts else "فيديو"
    print(f"🚀 جاري رفع {video_type} لليوتيوب...")

    final_title = title
    if is_shorts:
        final_title = title + " #Shorts"

    hashtags_str = " ".join(tags)
    full_description = f"{description}\n\n{hashtags_str}"

    clean_tags = []
    for t in tags:
        clean_tag = t.replace("#", "").replace("_", " ")
        if clean_tag:
            clean_tags.append(clean_tag)

    body = {
        'snippet': {
            'title': final_title,
            'description': full_description,
            'tags': clean_tags,
            'categoryId': '17'
        },
        'status': {
            'privacyStatus': 'public',
            'selfDeclaredMadeForKids': False
        }
    }

    try:
        media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
        req = youtube.videos().insert(
            part=','.join(body.keys()),
            body=body,
            media_body=media
        )

        res = None
        while res is None:
            status, res = req.next_chunk()
            if status:
                print(f"   📤 تقدم الرفع: {int(status.progress() * 100)}%")

        video_id = res.get('id')
        print(f"✅ يوتيوب ({video_type}) تم الرفع: https://youtu.be/{video_id}")

        # رفع الصورة المصغرة المخصصة
        if thumbnail_path and os.path.exists(thumbnail_path) and video_id:
            try:
                youtube.thumbnails().set(
                    videoId=video_id,
                    media_body=MediaFileUpload(thumbnail_path, mimetype='image/png')
                ).execute()
                print(f"🖼️ تم رفع الصورة المصغرة للفيديو {video_id}")
            except Exception as e:
                print(f"⚠️ فشل رفع الصورة المصغرة: {e}")

        return True

    except Exception as e:
        print(f"❌ Youtube Upload Failed: {e}")
        return False


# ====================== الرفع لفيسبوك ======================
def upload_to_facebook(video_path, message_body, hashtags_list):
    """رفع الفيديو لفيسبوك"""
    if not FACEBOOK_ACCESS_TOKEN or not FACEBOOK_PAGE_ID:
        print("⚠️ فيسبوك غير مفعل - لا يوجد توكن أو Page ID")
        return False

    print("🚀 جاري رفع الفيديو لفيسبوك...")

    hashtags_str = " ".join(hashtags_list)
    full_message = f"{message_body}\n\n{hashtags_str}"

    url = f"https://graph-video.facebook.com/v18.0/{FACEBOOK_PAGE_ID}/videos"

    try:
        file_size = os.path.getsize(video_path)

        start_response = requests.post(
            url,
            params={
                'access_token': FACEBOOK_ACCESS_TOKEN,
                'upload_phase': 'start',
                'file_size': file_size
            }
        ).json()

        session_id = start_response.get('upload_session_id')
        if not session_id:
            print(f"❌ فشل بدء رفع فيسبوك: {start_response}")
            return False

        with open(video_path, 'rb') as f:
            transfer_response = requests.post(
                url,
                data={
                    'access_token': FACEBOOK_ACCESS_TOKEN,
                    'upload_phase': 'transfer',
                    'start_offset': 0,
                    'upload_session_id': session_id
                },
                files={
                    'video_file_chunk': (os.path.basename(video_path), f, 'video/mp4')
                }
            )

        finish_response = requests.post(
            url,
            data={
                'access_token': FACEBOOK_ACCESS_TOKEN,
                'upload_phase': 'finish',
                'upload_session_id': session_id,
                'description': full_message
            }
        ).json()

        if finish_response.get('success'):
            print("✅ فيسبوك تم الرفع بنجاح")
            return True
        else:
            print(f"❌ فيسبوك فشل: {finish_response}")
            return False

    except Exception as e:
        print(f"❌ Facebook Failed: {e}")
        return False


# ====================== اختيار المحتوى حسب التناوب ======================
def pick_manual_content():
    """
    تشغيل يدوي: رابط (أي صيغة) أو كلمة مفتاحية. مفيش رجوع للتناوب التلقائي.
    لو الاتنين اتحطوا، الرابط له الأولوية. يرجع (payload, ai, 'manual') أو يوقف التشغيلة برسالة واضحة.
    """
    url_in = (os.environ.get('MANUAL_URL') or '').strip()
    kw_in = (os.environ.get('MANUAL_KEYWORD') or '').strip()
    if url_in and kw_in:
        print("ℹ️ اتحط رابط وكلمة مفتاحية معاً، هستخدم الرابط وأتجاهل الكلمة.")

    if url_in:
        print(f"\n🎯 تشغيل يدوي بالرابط")
        try:
            payload = sources_extra.extract_from_url(url_in)
        except sources_extra.ExtractError as e:
            print(f"❌ {e}")
            sys.exit(1)
        except Exception as e:
            print(f"❌ خطأ غير متوقع في قراءة الرابط: {e}")
            sys.exit(1)
        if payload['slug_key'] in load_history():
            print("ℹ️ الرابط ده اتعمل عنه فيديو قبل كده، بس هكمل لأنك طلبته بنفسك.")
    else:
        print(f"\n🎯 تشغيل يدوي بالكلمة المفتاحية: {kw_in}")
        payload = sources_extra.search_keyword(kw_in, load_history(), trend_slug)
        if not payload:
            print("❌ ملقتش خبر جديد مناسب بالكلمة دي (أو كلها اتعمل عنها فيديو قبل كده أو المواقع حاجبة القراءة). جرب كلمة تانية.")
            sys.exit(1)

    payload['mode'] = 'manual'
    ai = generate_ai_content(payload)
    if not ai:
        print("❌ فشل توليد السكريبت من المحتوى ده (غالباً المحتوى قليل أو الموديلات رفضت النص).")
        sys.exit(1)
    return payload, ai, 'manual'


def pick_content():
    """
    يختار محتوى التشغيلة حسب نظام التناوب:
    فيديو عن موضوع ترندي (مع مصادره) ثم فيديو من خبر مصدر، بالتناوب.
    لو النوع المطلوب فشل، يحاول النوع الآخر في نفس التشغيلة.
    يرجع (payload, used_mode) أو (None, None)
    """
    next_type = get_next_video_type()
    order = [next_type, 'source' if next_type == 'trending' else 'trending']
    history = load_history()

    for mode in order:
        print(f"\n🎯 نوع التشغيلة: {'موضوع ترندي' if mode == 'trending' else 'خبر من مصدر'}")

        if mode == 'trending':
            topic = find_trending_topic(history, STRICT_KEYWORDS, BLACKLIST_KEYWORDS, get_service=get_youtube_service)
            if topic:
                combined_parts = [f"الموضوع الترندي: {topic['topic']}"]
                for art in topic['articles']:
                    combined_parts.append(
                        f"مقال بعنوان ({art['title']}):\n{art['text'][:1600]}"
                    )
                payload = {
                    'title': topic['topic'],
                    'text': "\n\n".join(combined_parts),
                    'url': topic['articles'][0]['url'],
                    'source_name': topic['feed_label'],
                    'source_id': 0,
                    'mode': 'trending',
                    'slug_key': topic['slug_key'],
                    'sources': [{'source': a['source'], 'url': a['url']}
                                for a in topic['articles']],
                }
                ai = generate_ai_content(payload)
                if ai:
                    return payload, ai, mode
                print("⚠️ فشل توليد المحتوى للموضوع الترندي — تجربة النوع الآخر")
        else:
            article = find_best_news()
            if article:
                article['mode'] = 'source'
                article['sources'] = [{'source': article['source_name'], 'url': article['url']}]
                ai = generate_ai_content(article)
                if ai:
                    return article, ai, mode
                print("⚠️ فشل توليد المحتوى للخبر — تجربة النوع الآخر")

    return None, None, None


# ====================== التنفيذ الرئيسي ======================
async def main():
    """الدالة الرئيسية للتنفيذ"""
    print("=" * 60)
    print("⚽ بدء تشغيل بوت ملوك الملعب ⚽")
    print("=" * 60)
    print(f"🕐 الوقت: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📊 عدد المصادر: {len(SOURCES)}")
    print("=" * 60)

    ensure_fonts()

    if (os.environ.get('MANUAL_URL') or '').strip() or (os.environ.get('MANUAL_KEYWORD') or '').strip():
        payload, ai, used_mode = pick_manual_content()
    else:
        payload, ai, used_mode = pick_content()
    if not payload:
        print("😴 لا يوجد محتوى مناسب في هذه التشغيلة (لا ترند ولا أخبار جديدة).")
        return

    print(f"\n📰 المحتوى المختار ({ {'trending':'ترندي','manual':'يدوي'}.get(used_mode,'من مصدر') }):")
    print(f"   المصدر: {payload['source_name']}")
    print(f"   العنوان: {payload['title'][:80]}")
    # ملحوظة: المصادر تُستخدم كأساس للمعلومات فقط ولا تُذكر في الوصف (طلب صاحب القناة)

    print(f"\n✍️ المحتوى المُنشأ:")
    print(f"   عنوان الفيديو: {ai['video_title']}")
    print(f"   عنوان الشورتس: {ai['shorts_title']}")
    print(f"   طول سكريبت الفيديو: {len(ai['video_script'])} حرف")
    print(f"   طول سكريبت الشورتس: {len(ai['shorts_script'])} حرف")
    print(f"   عدد الهاشتاقات: {len(ai['hashtags'])}")

    video_audio = "video_audio.mp3"
    shorts_audio = "shorts_audio.mp3"
    video_file = "video.mp4"
    shorts_file = "shorts.mp4"
    thumbnail_file = "thumbnail.png"

    # الصورة المصغرة المخصصة بالهوية البصرية
    print("\n🖼️ تصميم الصورة المصغرة...")
    try:
        create_thumbnail(ai['video_title'], thumbnail_file)
    except Exception as e:
        print(f"⚠️ فشل تصميم الصورة المصغرة: {e}")
        thumbnail_file = None

    print("\n🎙️ توليد الصوت للفيديو الطويل...")
    await generate_audio(ai['video_script'], video_audio)

    print("\n🎙️ توليد الصوت للشورتس...")
    await generate_audio(ai['shorts_script'], shorts_audio)
    enforce_shorts_duration(shorts_audio)

    kicker = "الأكثر بحثاً الآن" if used_mode == 'trending' else "آخر الأخبار"

    long_slides = derive_slide_lines(ai['video_script'], MAX_LONG_SLIDES, max_chars=120)
    short_slides = derive_slide_lines(ai['shorts_script'], MAX_SHORT_SLIDES, max_chars=90)
    print(f"\n🖼️ الشرائح: {len(long_slides)} للفيديو الطويل، {len(short_slides)} للشورتس")

    print("\n🎬 إنتاج الفيديو الطويل...")
    video_success = create_slideshow_video(
        long_slides,
        video_audio,
        video_file,
        VIDEO_WIDTH,
        VIDEO_HEIGHT,
        is_shorts=False,
        title=ai['video_title'],
        kicker=kicker,
        visuals=ai.get('visuals')
    )

    print("\n🎬 إنتاج الشورتس...")
    shorts_success = create_slideshow_video(
        short_slides,
        shorts_audio,
        shorts_file,
        SHORTS_WIDTH,
        SHORTS_HEIGHT,
        is_shorts=True,
        title=ai['shorts_title'],
        kicker=kicker,
        visuals=ai.get('visuals')
    )

    something_uploaded = False

    if video_success:
        print("\n📤 رفع الفيديو الطويل...")
        yt_ok = upload_to_youtube(
            video_file,
            ai['video_title'],
            ai['video_description'],
            ai['hashtags'],
            is_shorts=False,
            thumbnail_path=thumbnail_file
        )
        something_uploaded = something_uploaded or yt_ok
        if not yt_ok:
            save_failed_link(payload['url'], payload['source_name'], "فشل رفع الفيديو الطويل لليوتيوب")
        fb_ok = upload_to_facebook(video_file, ai['facebook_post'], ai['hashtags'])
        something_uploaded = something_uploaded or fb_ok
        if not fb_ok:
            save_failed_link(payload['url'], payload['source_name'], "فشل رفع الفيديو لفيسبوك")

    if shorts_success:
        print("\n📤 رفع الشورتس...")
        shorts_description = ai['shorts_script']
        shorts_ok = upload_to_youtube(
            shorts_file,
            ai['shorts_title'],
            shorts_description,
            ai['hashtags'],
            is_shorts=True,
            thumbnail_path=thumbnail_file
        )
        something_uploaded = something_uploaded or shorts_ok
        if not shorts_ok:
            save_failed_link(payload['url'], payload['source_name'], "فشل رفع الشورتس لليوتيوب")

    if video_success or shorts_success:
        print("\n💾 حفظ الموضوع في الهيستوري (منع التكرار)...")
        if used_mode in ('trending', 'manual'):
            save_history(payload['slug_key'], payload['source_name'])
            for s in payload['sources']:
                if s['url'] != payload['slug_key']:
                    save_history(s['url'], s['source'])
        else:
            save_history(payload['url'], payload['source_name'])

        # قلب التناوب للتشغيلة القادمة — التشغيل اليدوي ميغيّرش التناوب
        if used_mode == 'manual':
            print("🔁 تشغيل يدوي: التناوب التلقائي ما اتغيرش")
        else:
            save_next_video_type('source' if used_mode == 'trending' else 'trending')
    else:
        print("⚠️ فشل إنتاج الفيديوهات — لن يتم حفظ الهيستوري ولا تغيير التناوب")

    print("\n🧹 تنظيف الملفات المؤقتة...")
    files_to_remove = [video_audio, shorts_audio, video_file, shorts_file]
    if thumbnail_file:
        files_to_remove.append(thumbnail_file)
    for f in files_to_remove:
        if os.path.exists(f):
            os.remove(f)
            print(f"   ✓ تم حذف: {f}")

    print("\n" + "=" * 60)
    print("✅ اكتمل التنفيذ بنجاح")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
