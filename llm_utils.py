# -*- coding: utf-8 -*-
"""
llm_utils.py - طبقة موحدة للنماذج: Gemini (مع قائمة موديلات وتبديل تلقائي) وGroq (مع إعادة محاولة بدون response_format).
كل أسماء الموديلات تتغير من متغيرات البيئة (قائمة مفصولة بفاصلة) من غير تعديل كود.
"""
import os
import re
import json

# موديلات متاحة حسب توثيق جوجل وGroq (نوفمبر 2026). llama-3.x اتلغت على Groq، وqwen3.6 هيتلغي 14 سبتمبر.
DEFAULT_GEMINI_MODELS = "gemini-3.8-flash,gemini-3.6-flash,gemini-3.5-flash-lite,gemini-2.5-flash-lite"
DEFAULT_GEMINI_TTS_MODELS = "gemini-3.8-flash-tts,gemini-3.8-flash-lite-tts,gemini-2.5-flash-preview-tts"
DEFAULT_GROQ_MODELS = "openai/gpt-oss-120b,qwen/qwen3.8-27b,openai/gpt-oss-20b"


def env_list(name, default):
    raw = (os.environ.get(name) or "").strip() or default
    return [m.strip() for m in raw.split(",") if m.strip()]


def gemini_models():
    return env_list("GEMINI_MODELS", DEFAULT_GEMINI_MODELS)


def gemini_tts_models():
    # GEMINI_TTS_MODEL (قديم) لو اتحط يتجرب الأول
    first = (os.environ.get("GEMINI_TTS_MODEL") or "").strip()
    lst = env_list("GEMINI_TTS_MODELS", DEFAULT_GEMINI_TTS_MODELS)
    if first and first not in lst:
        lst.insert(0, first)
    return lst


def groq_models():
    return env_list("GROQ_MODELS", DEFAULT_GROQ_MODELS)


_DEAD = set()   # موديلات رجّعت 404/غير متاح في التشغيلة دي، منجربهاش تاني


def is_model_missing(err):
    s = str(err).lower()
    return ("404" in s or "not_found" in s or "no longer available" in s
            or "not found" in s or "does not exist" in s or "decommission" in s
            or "model_not_found" in s)


def mark_dead(model, err):
    if is_model_missing(err):
        _DEAD.add(model)


def is_dead(model):
    return model in _DEAD


def gemini_text(system, prompt, temperature=0.2, max_tokens=6000, label=""):
    """يجرب موديلات Gemini بالترتيب. يرجّع النص أو None لو كلهم فشلوا."""
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        return None
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=key)
    for m in gemini_models():
        if is_dead(m):
            continue
        try:
            resp = client.models.generate_content(
                model=m, contents=prompt,
                config=types.GenerateContentConfig(system_instruction=system, temperature=temperature,
                                                   max_output_tokens=max_tokens))
            out = (resp.text or "").strip()
            if out:
                return out
            print(f"⚠️ Gemini {m} رجّع رد فاضي {label}")
        except Exception as e:
            mark_dead(m, e)
            print(f"⚠️ Gemini {m} فشل {label}: {str(e)[:140]}")
    return None


def extract_json(text):
    """يطلّع JSON من رد النموذج حتى لو جواه ```json أو كلام قبله وبعده."""
    if not text:
        raise ValueError("رد فاضي")
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t, flags=re.S).strip()
    try:
        return json.loads(t)
    except Exception:
        pass
    a, b = t.find("{"), t.rfind("}")
    if a != -1 and b > a:
        return json.loads(t[a:b + 1])
    raise ValueError("مفيش JSON في الرد")


def groq_json(client, model, system, prompt, temperature=0.4, max_tokens=4000):
    """يجرب مع response_format وبعدين بدونه (gpt-oss بيرجّع json_validate_failed أحياناً) ويحلل الـJSON يدوي."""
    msgs = [{"role": "system", "content": system}, {"role": "user", "content": prompt}]
    last = None
    for use_rf in (True, False):
        try:
            kw = dict(model=model, messages=msgs, temperature=temperature, max_tokens=max_tokens)
            if use_rf:
                kw["response_format"] = {"type": "json_object"}
            comp = client.chat.completions.create(**kw)
            return extract_json(comp.choices[0].message.content)
        except Exception as e:
            last = e
            if is_model_missing(e):
                mark_dead(model, e)
                break
            if "rate_limit" in str(e).lower() or "429" in str(e) or "tokens per minute" in str(e).lower():
                break
    raise last


def gemini_json(system, prompt, model, temperature=0.4, max_tokens=8000):
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    last = None
    for use_mime in (True, False):
        try:
            cfg = dict(system_instruction=system, temperature=temperature, max_output_tokens=max_tokens)
            if use_mime:
                cfg["response_mime_type"] = "application/json"
            resp = client.models.generate_content(model=model, contents=prompt,
                                                  config=types.GenerateContentConfig(**cfg))
            return extract_json(resp.text)
        except Exception as e:
            last = e
            if is_model_missing(e):
                mark_dead(model, e)
                break
    raise last
