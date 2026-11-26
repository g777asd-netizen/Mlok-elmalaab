# -*- coding: utf-8 -*-
"""
yt_transcript.py - يتحط في جذر الريبو.
بيجيب نص الكلام الحقيقي من فيديو يوتيوب. لو مقدرش بيرمي TranscriptError برسالة عربي واضحة (والتشغيلة بتقف).
الترتيب (بيكمل للي بعده لو فشل):
  1) yt-dlp ترجمة الفيديو (مع كوكيز اختيارية YT_COOKIES لو يوتيوب حاجب GitHub)
  2) youtube-transcript-api (مع بروكسي اختياري YT_PROXY)
  3) Gemini بيقرا رابط الفيديو بنفسه من سيرفرات جوجل (مش بيتحجب زي GitHub) وبيفرّغ الكلام بس
"""
import os, re, json, tempfile
from urllib.parse import urlparse, parse_qs
import requests

MIN_TRANSCRIPT_CHARS = 600
MAX_CHARS = 14000


class TranscriptError(Exception):
    pass


def video_id(url):
    u = urlparse(url)
    h = (u.hostname or "").lower()
    if h.endswith("youtu.be"):
        return u.path.strip("/").split("/")[0]
    if u.path.startswith(("/shorts/", "/live/", "/embed/")):
        return u.path.split("/")[2]
    return (parse_qs(u.query).get("v") or [""])[0]


def _clean(txt):
    return re.sub(r"\s+", " ", txt or "").strip()


def _cookiefile():
    c = (os.environ.get("YT_COOKIES") or "").strip()
    if not c:
        return None
    f = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False)
    f.write(c)
    f.close()
    return f.name


def via_ytdlp(url):
    import yt_dlp
    opts = {"quiet": True, "no_warnings": True, "skip_download": True, "noplaylist": True,
            "socket_timeout": 20, "extractor_retries": 2,
            "extractor_args": {"youtube": {"player_client": ["tv", "web_safari", "android"]}}}
    cf = _cookiefile()
    if cf:
        opts["cookiefile"] = cf
    if os.environ.get("YT_PROXY"):
        opts["proxy"] = os.environ["YT_PROXY"]
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
    out = {"title": info.get("title") or "", "duration": info.get("duration") or 0,
           "description": info.get("description") or "", "text": ""}
    for bucket in ("subtitles", "automatic_captions"):
        caps = info.get(bucket) or {}
        for lang in ("ar", "ar-orig", "en", "en-orig"):
            fm = caps.get(lang)
            if not fm:
                continue
            pick = next((f for f in fm if f.get("ext") == "json3"), None) or next((f for f in fm if f.get("ext") == "vtt"), None)
            if not pick:
                continue
            raw = requests.get(pick["url"], timeout=20).text
            try:
                segs = [s.get("utf8", "") for ev in json.loads(raw).get("events", []) for s in (ev.get("segs") or [])]
                t = "".join(segs)
            except Exception:
                t = re.sub(r"WEBVTT.*?\n\n|\d+:\d+:\d+[\.,]\d+ --> .*|<[^>]+>", " ", raw, flags=re.S)
            t = _clean(t)
            if len(t) > len(out["text"]):
                out["text"] = t
        if len(out["text"]) >= MIN_TRANSCRIPT_CHARS:
            break
    return out


def via_transcript_api(url):
    vid = video_id(url)
    from youtube_transcript_api import YouTubeTranscriptApi
    kw = {}
    if os.environ.get("YT_PROXY"):
        from youtube_transcript_api.proxies import GenericProxyConfig
        kw["proxy_config"] = GenericProxyConfig(http_url=os.environ["YT_PROXY"], https_url=os.environ["YT_PROXY"])
    api = YouTubeTranscriptApi(**kw)
    tr = api.fetch(vid, languages=["ar", "en"])
    return {"text": _clean(" ".join(s.text for s in tr))}


GEMINI_ASK = (
    "فرّغ الكلام المنطوق في الفيديو ده بالترتيب كنص متصل، بنفس لغة المتكلم، من غير أوقات. "
    "اكتب اللي اتقال فعلاً بس. ممنوع تضيف أو تخمن أو تلخص من عندك. لو جزء مش مسموع اكتب [غير واضح]. "
    "لو الفيديو مفيهوش كلام اكتب بس: NO_SPEECH."
)


def via_gemini(url):
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise TranscriptError("no GEMINI_API_KEY")
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=key)
    models = [m.strip() for m in (os.environ.get("GEMINI_VIDEO_MODELS") or "gemini-2.5-flash,gemini-2.5-flash-lite").split(",") if m.strip()]
    last = None
    for m in models:
        try:
            cfg = types.GenerateContentConfig(temperature=0.0, max_output_tokens=16000,
                                              media_resolution="MEDIA_RESOLUTION_LOW")
            r = client.models.generate_content(
                model=m, config=cfg,
                contents=types.Content(parts=[types.Part(file_data=types.FileData(file_uri=url)),
                                              types.Part(text=GEMINI_ASK)]))
            t = _clean(r.text or "")
            if t and "NO_SPEECH" not in t[:40]:
                return {"text": t}
            last = "no speech"
        except Exception as e:
            last = str(e)[:150]
            print(f"   ⚠️ Gemini {m} مقدرش يقرا الفيديو: {last}")
    raise TranscriptError(last or "gemini failed")


def get_youtube_text(url, oembed_title=""):
    """يرجع dict(title, text, method, duration) أو يرمي TranscriptError."""
    title, duration, desc = oembed_title, 0, ""
    text, method = "", ""
    for name, fn in (("yt-dlp", via_ytdlp), ("transcript-api", via_transcript_api), ("gemini-video", via_gemini)):
        try:
            r = fn(url)
        except Exception as e:
            print(f"   ⚠️ {name}: {str(e)[:140]}")
            continue
        title = r.get("title") or title
        duration = r.get("duration") or duration
        desc = r.get("description") or desc
        if len(r.get("text", "")) >= MIN_TRANSCRIPT_CHARS:
            text, method = r["text"], name
            print(f"   🗒️ اتجاب نص الكلام بطريقة {name}: {len(text)} حرف")
            break
    if not text:
        raise TranscriptError(
            "مقدرتش أجيب نص الكلام الحقيقي للفيديو ده (يوتيوب حاجب GitHub وجوجل مقدرش يقراه). "
            "مش هكتب سكريبت من العنوان بس عشان ميتألفش كلام. الحلول: ضيف سر YT_COOKIES أو YT_PROXY في GitHub، "
            "أو جرب فيديو عليه ترجمة، أو استخدم رابط مقال عن نفس الموضوع.")
    return {"title": title, "text": text[:MAX_CHARS], "method": method, "duration": duration, "description": desc[:1500]}
