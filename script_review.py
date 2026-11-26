# -*- coding: utf-8 -*-
"""
script_review.py - مراجعة ثانية بـ Gemini قبل الصوت
يصحح: اللهجة (مصري قاهري فقط)، النحو، المصطلحات الكروية، وكتابة الأسماء، من غير ما يضيف أي معلومة.
لو GEMINI_API_KEY مش موجود أو فشل الاتصال: يرجّع النص زي ما هو (والفحص الصارم في pronunciation.script_problems بيكمل).
"""
import os

REVIEW_MODEL = os.environ.get("GEMINI_REVIEW_MODEL", "gemini-2.5-flash")

REVIEW_SYSTEM = (
 "أنت مدقق لغوي ومعلق كروي مصري قاهري خبير. هتاخد تعليق صوتي لفيديو كرة قدم ومعاه نص الخبر الأصلي. "
 "صحح التعليق بالقواعد دي بالترتيب:\n"
 "1) اللهجة: عامية مصرية قاهرية بس. أي كلمة فصحى أو خليجية أو شامية تتبدل بمرادفها المصري الطبيعي "
 "(مثلاً: الآن=دلوقتي، لماذا=ليه، كيف=إزاي، الذي/التي=اللي، هذا/هذه=ده/دي، كثيراً=أوي، سوف=هـ).\n"
 "2) المصطلحات الكروية بالمصري: هدف=جون، ركلة جزاء=ضربة جزاء، تسلل=أوفسايد، شوط أول/تاني، كارت أصفر/أحمر، حارس المرمى.\n"
 "3) النحو والإملاء وعلامات الترقيم، وجمل قصيرة طبيعية تتقال بالصوت.\n"
 "4) الأسماء: اكتبها بنفس الشكل في كل النص وبالنطق الشائع في مصر، ومتغيرش اسم يطابق النص الأصلي إلا لو اتكتب غلط واضح.\n"
 "5) ممنوع تضيف أي معلومة أو اسم أو رقم مش في التعليق، وممنوع تشيل معلومة صح، وممنوع تغير نتيجة أو رقم.\n"
 "6) الأرقام تفضل بالكلمات. مفيش كلمات إنجليزي. مفيش ذكر لذكاء اصطناعي أو مصدر.\n"
 "رجّع التعليق المصحح بس، نص واحد، بدون شرح ولا عناوين ولا علامات اقتباس."
)


def gemini_review(script, source_text, label=""):
    key = os.environ.get("GEMINI_API_KEY")
    if not key or not script:
        print("ℹ️ مراجعة Gemini متخطية (مفيش GEMINI_API_KEY)")
        return script
    try:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=key)
        resp = client.models.generate_content(
            model=REVIEW_MODEL,
            contents="النص الأصلي للخبر (مرجع للحقائق والأسماء):\n" + source_text[:3000] + "\n\nالتعليق المطلوب تصحيحه:\n" + script,
            config=types.GenerateContentConfig(system_instruction=REVIEW_SYSTEM, temperature=0.2, max_output_tokens=6000),
        )
        out = (resp.text or "").strip()
        if len(out) < 0.7 * len(script) or len(out) > 1.4 * len(script):
            print(f"⚠️ مراجعة Gemini {label}: الناتج غير منطقي الطول، هتجاهله")
            return script
        print(f"✅ مراجعة Gemini {label}: تمت")
        return out
    except Exception as e:
        print(f"⚠️ فشلت مراجعة Gemini {label}: {str(e)[:150]}")
        return script
