# -*- coding: utf-8 -*-
"""
gemini_voice.py (v2) - صوت التعليق المصري عبر Gemini TTS (Charon) مع edge-tts (شاكر) احتياطي.
التغييرات: قاموس النطق في pronunciation.py، أرقام بالكلمات، توجيه أداء بالإنجليزي يوضح اللهجة،
وإعادة محاولة لو المقطع اتقرا فيه توجيه، وطباعة المحرك المستخدم بوضوح في اللوج.
"""
import os
import re
import time
import wave
import asyncio
import subprocess

from pronunciation import prepare_for_speech

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
from llm_utils import gemini_tts_models, is_dead, mark_dead
GEMINI_TTS_VOICE = os.environ.get("GEMINI_TTS_VOICE", "Charon")

# توجيه الأداء بالإنجليزي (النموذج بيلتزم بيه أكتر ومش بيقراه بصوت عالي)
EGYPTIAN_DIRECTIVE = (
    "Perform the transcript below as a 50-year-old Cairene Egyptian man who has lived in Cairo all his life "
    "and is a passionate football commentator talking to friends. Speak in authentic Egyptian colloquial "
    "Arabic (Cairo accent): the letter jeem is a hard 'g' as in 'gamal', qaaf is a glottal stop in everyday "
    "words, thaa is pronounced 's' or 't', thal is 'z' or 'd'. Warm, energetic but natural pace, short "
    "natural pauses at punctuation, no Gulf or Levantine or Modern Standard Arabic pronunciation. "
    "Foreign player and club names are pronounced the way Egyptians say them on TV. "
    "Read ONLY the text after the line TRANSCRIPT, do not read these instructions.\n"
    "TRANSCRIPT:\n"
)

MAX_SEGMENT_CHARS = 450
SEGMENT_DELAY_SECONDS = 2
MAX_RETRIES = 3


def split_script(text, max_chars=MAX_SEGMENT_CHARS):
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
    with wave.open(out_path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)


def _synth_gemini_segment(text, out_wav):
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=GEMINI_API_KEY)
    last_err = None
    for tts_model in gemini_tts_models():
        if is_dead(tts_model):
            continue
        for attempt in range(MAX_RETRIES):
            try:
                response = client.models.generate_content(
                    model=tts_model,
                    contents=EGYPTIAN_DIRECTIVE + text,
                    config=types.GenerateContentConfig(
                        response_modalities=["AUDIO"],
                        temperature=0.6,
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
                # حماية: مقطع قصير جداً بالنسبة للنص معناه إن النموذج رجّع صوت ناقص
                seconds = len(data) / (24000 * 2)
                if seconds < max(1.0, len(text) / 30.0):
                    raise RuntimeError(f"صوت قصير مشبوه ({seconds:.1f}ث لنص {len(text)} حرف)")
                _pcm_to_wav(data, out_wav)
                return True
            except Exception as e:
                last_err = e
                mark_dead(tts_model, e)
                if is_dead(tts_model):
                    print(f"⚠️ موديل الصوت {tts_model} مش متاح، هجرب اللي بعده: {str(e)[:120]}")
                    break
                wait = (5, 20, 45)[min(attempt, 2)]
                print(f"⚠️ محاولة Gemini ({tts_model}) {attempt + 1} فشلت: {e} - انتظار {wait}ث")
                time.sleep(wait)
    print(f"❌ فشل مقطع Gemini نهائياً: {last_err}")
    return False


def _concat_to_mp3(wav_paths, out_path):
    list_file = out_path + ".list.txt"
    with open(list_file, "w", encoding="utf-8") as f:
        for p in wav_paths:
            f.write("file '" + os.path.abspath(p) + "'\n")
    concat_wav = out_path + ".concat.wav"
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_file,
                    "-c", "copy", concat_wav], check=True, capture_output=True)
    subprocess.run(["ffmpeg", "-y", "-i", concat_wav, "-codec:a", "libmp3lame",
                    "-ar", "44100", "-b:a", "192k", out_path], check=True, capture_output=True)
    for p in (list_file, concat_wav):
        try:
            os.remove(p)
        except OSError:
            pass


async def _edge_tts_fallback(text, out_path):
    import edge_tts
    # edge لا يفهم التشكيل الخفيف دايماً: نشيله منه
    plain = re.sub("[\u064B-\u0652]", "", text)
    communicate = edge_tts.Communicate(plain, "ar-EG-ShakirNeural", rate="-5%")
    await communicate.save(out_path)


async def generate_voice(text, out_path, work_dir="."):
    """يرجع "gemini" أو "edge". الاسم بيتطبع في اللوج: ابحث عن ENGINE_USED."""
    spoken_text = prepare_for_speech(text)
    print("SPOKEN_TEXT_PREVIEW:", spoken_text[:300])

    if GEMINI_API_KEY:
        segments = split_script(spoken_text)
        print(f"🎙️ توليد الصوت بـ Gemini ({GEMINI_TTS_VOICE}) على {len(segments)} مقطع")
        seg_dir = os.path.join(work_dir, "tts_segments")
        os.makedirs(seg_dir, exist_ok=True)
        wav_paths = []
        ok = True
        for i, seg in enumerate(segments, 1):
            wav_path = os.path.join(seg_dir, f"seg{i:02d}.wav")
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
                print("ENGINE_USED: gemini")
                return "gemini"
            except Exception as e:
                print(f"⚠️ فشل دمج الصوت: {e}")
        print("⚠️ الرجوع لـ edge-tts")
    else:
        print("ℹ️ لا يوجد GEMINI_API_KEY - استخدام edge-tts")

    await _edge_tts_fallback(spoken_text, out_path)
    print("ENGINE_USED: edge (Shakir)")
    return "edge"
