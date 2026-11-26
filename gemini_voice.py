# -*- coding: utf-8 -*-
"""
gemini_voice.py — صوت التعليق المصري الطبيعي عبر Gemini TTS
===========================================================
- نفس أسلوب الصوت الطبيعي (نبرة معلق كروي مصري) بدل الصوت الآلي
- الصوت الافتراضي: Charon على موديل gemini-2.5-flash-preview-tts
- النص يتقسم لمقاطع قصيرة وتتولد بالتتابع (احترام حدود المعدل في الخطة المجانية)
- أسماء اللاعبين والأندية الأجنبية تُعاد كتابتها بالنطق المصري قبل التوليد
- لو Gemini غير متاح أو فشل: يرجع تلقائياً لـ edge-tts (شاكر) فلا يتوقف البوت أبداً

التشغيل يحتاج Secret باسم GEMINI_API_KEY (مفتاح مجاني من Google AI Studio).
متغيرات اختيارية: GEMINI_TTS_MODEL و GEMINI_TTS_VOICE
"""

import os
import re
import time
import wave
import asyncio
import subprocess

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GEMINI_TTS_MODEL = os.environ.get("GEMINI_TTS_MODEL", "gemini-2.5-flash-preview-tts")
GEMINI_TTS_VOICE = os.environ.get("GEMINI_TTS_VOICE", "Charon")

# توجيه الأداء: مفتاح النبرة المصرية الطبيعية
EGYPTIAN_DIRECTIVE = (
    "اقرأ النص التالي بصوت رجل مصري في الخمسين من عمره، عاشق لكرة القدم ومعلق رياضي شعبي، "
    "بنبرة حماسية دافئة وطبيعية، وعامية مصرية أصيلة، مع وقفات طبيعية بين الجمل، "
    "وانطق أسماء اللاعبين والأندية الأجنبية بالنطق المصري المتداول: "
)

# إعادة تهجئة الأسماء الشائعة بالنطق المصري قبل إرسالها لمحرك الصوت
NAME_RESPELLINGS = {
    "بيلينغهام": "بيلينجهام",
    "بيلينجهام": "بيلينجهام",
    "غولر": "جولر",
    "آردا غولر": "آردا جولر",
    "بيريسيتش": "بيريسيتش",
    "فالفيردي": "فالفيردي",
    "فيدي فالفيردي": "فيدي فالفيردي",
    "تشواميني": "تشواميني",
    "مبابي": "مبابي",
    "كيليان مبابي": "كيليان مبابي",
    "فينيسيوس": "فينيسيوس",
    "آيندهوفن": "آيندهوفن",
    "سانتياغو برنابيو": "البرنابيو",
    "سانتياجو برنابيو": "البرنابيو",
    "هالاند": "هالاند",
    "جوارديولا": "جوارديولا",
    "غوارديولا": "جوارديولا",
    "تشابي ألونسو": "تشابي ألونسو",
    "ليفاندوفسكي": "ليفاندوفسكي",
    "دي بروين": "دي بروينه",
    "فيني": "فيني",
}

MAX_SEGMENT_CHARS = 550
SEGMENT_DELAY_SECONDS = 2     # فاصل بين الطلبات احتراماً لحد RPM
MAX_RETRIES = 3


def respell_names(text):
    """استبدال الأسماء بصيغتها المنطوقة مصرية"""
    for src, dst in NAME_RESPELLINGS.items():
        text = text.replace(src, dst)
    return text


def split_script(text, max_chars=MAX_SEGMENT_CHARS):
    """تقسيم السكريبت لمقاطع على حدود الجمل"""
    sentences = re.split(r"(?<=[\.!\?؟،\n])\s+", text.strip())
    segments, current = [], ""
    for s in sentences:
        if not s:
            continue
        if len(current) + len(s) + 1 > max_chars and current:
            segments.append(current.strip())
            current = s
        else:
            current = (current + " " + s).strip()
    if current:
        segments.append(current.strip())
    # لو جملة واحدة أطول من الحد: قسمها قسماً صلباً
    final = []
    for seg in segments:
        while len(seg) > max_chars:
            cut = seg.rfind(" ", 0, max_chars)
            cut = cut if cut > 0 else max_chars
            final.append(seg[:cut])
            seg = seg[cut:]
        if seg:
            final.append(seg)
    return [s for s in final if s]


def _pcm_to_wav(pcm_bytes, out_path, sample_rate=24000):
    """Gemini يرجع PCM خام (16-bit mono 24kHz) — نغلفه كـ WAV"""
    with wave.open(out_path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)


def _synth_gemini_segment(text, out_wav):
    """توليد مقطع واحد عبر Gemini TTS مع المحاولات"""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=GEMINI_API_KEY)
    last_err = None
    for attempt in range(MAX_RETRIES):
        try:
            response = client.models.generate_content(
                model=GEMINI_TTS_MODEL,
                contents=EGYPTIAN_DIRECTIVE + text,
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                voice_name=GEMINI_TTS_VOICE
                            )
                        )
                    ),
                ),
            )
            data = response.candidates[0].content.parts[0].inline_data.data
            _pcm_to_wav(data, out_wav)
            return True
        except Exception as e:
            last_err = e
            wait = (5, 20, 45)[min(attempt, 2)]
            print(f"⚠️ محاولة Gemini {attempt + 1} فشلت: {e} — انتظار {wait}ث")
            time.sleep(wait)
    print(f"❌ فشل مقطع Gemini نهائياً: {last_err}")
    return False


def _concat_to_mp3(wav_paths, out_path):
    """دمج مقاطع WAV وتحويلها لـ MP3 بالجودة المناسبة"""
    list_file = out_path + ".list.txt"
    with open(list_file, "w", encoding="utf-8") as f:
        for p in wav_paths:
            f.write(f"file '{os.path.abspath(p)}'\n")
    concat_wav = out_path + ".concat.wav"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_file,
         "-c", "copy", concat_wav],
        check=True, capture_output=True,
    )
    subprocess.run(
        ["ffmpeg", "-y", "-i", concat_wav, "-codec:a", "libmp3lame",
         "-ar", "44100", "-b:a", "192k", out_path],
        check=True, capture_output=True,
    )
    for p in (list_file, concat_wav):
        try:
            os.remove(p)
        except OSError:
            pass


async def _edge_tts_fallback(text, out_path):
    """الخطة البديلة: صوت شاكر المصري من edge-tts"""
    import edge_tts
    communicate = edge_tts.Communicate(text, "ar-EG-ShakirNeural", rate="-5%")
    await communicate.save(out_path)


async def generate_voice(text, out_path, work_dir="."):
    """
    توليد الصوت الكامل للسكريبت.
    يرجع اسم المحرك المستخدم: "gemini" أو "edge".
    """
    spoken_text = respell_names(text)

    if GEMINI_API_KEY:
        segments = split_script(spoken_text)
        print(f"🎙️ توليد الصوت بـ Gemini ({GEMINI_TTS_VOICE}) على {len(segments)} مقطع ...")
        seg_dir = os.path.join(work_dir, "tts_segments")
        os.makedirs(seg_dir, exist_ok=True)
        wav_paths = []
        ok = True
        for i, seg in enumerate(segments, 1):
            wav_path = os.path.join(seg_dir, f"seg{i:02d}.wav")
            print(f"   🎤 مقطع {i}/{len(segments)} ({len(seg)} حرف)")
            if not _synth_gemini_segment(seg, wav_path):
                ok = False
                break
            wav_paths.append(wav_path)
            if i < len(segments):
                time.sleep(SEGMENT_DELAY_SECONDS)
        if ok and wav_paths:
            try:
                _concat_to_mp3(wav_paths, out_path)
                for p in wav_paths:
                    try:
                        os.remove(p)
                    except OSError:
                        pass
                print(f"✅ صوت Gemini جاهز: {out_path}")
                return "gemini"
            except Exception as e:
                print(f"⚠️ فشل دمج الصوت: {e}")
        print("⚠️ الرجوع لـ edge-tts ...")
    else:
        print("ℹ️ لا يوجد GEMINI_API_KEY — استخدام edge-tts")

    await _edge_tts_fallback(spoken_text, out_path)
    print(f"✅ صوت edge-tts جاهز: {out_path}")
    return "edge"
