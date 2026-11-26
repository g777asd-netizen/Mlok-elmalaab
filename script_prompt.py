# -*- coding: utf-8 -*-
"""
script_prompt.py - يتحط في جذر الريبو. بيحل محل بلوك الـprompt والـsystem في generate_ai_content
الاستخدام داخل youtube_arabic.py:

  from script_prompt import SYSTEM_MSG, build_prompt, polish_script
  from pronunciation import script_problems
  ...
  prompt = build_prompt(article['title'], article_text)       # بدل f-string القديمة
  messages=[{"role":"system","content":SYSTEM_MSG},{"role":"user","content":prompt}]
  temperature=0.4                                              # كان 0.7: ده سبب اختراع الأسماء
  بعد json.loads:
      for k in ("video_script","shorts_script"):
          content[k] = polish_script(client, model, content[k], article_text)
      if script_problems(content["video_script"], article_text): continue   # جرّب الموديل التالي
  وبدل clean_text_strict على السكريبتات استخدم clean_script_keep_tashkeel (تحت).
"""
import re, json

SYSTEM_MSG = (
 "You output strictly valid JSON. You write voice-over scripts in natural Egyptian colloquial Arabic "
 "(Cairo street dialect), the way a lifelong Cairene football commentator talks to friends. "
 "Facts, names, scores, ages and dates come ONLY from the provided source text. "
 "If a detail is not in the source, leave it out. Never translate English idioms literally."
)

STYLE_RULES = """
قواعد الأسلوب (إلزامية):
- عامية مصرية قاهرية حقيقية: دلوقتي، كده، ده/دي، إزاي، ليه، عشان، لسه، برضو، أوي، يعني، بقى، مش، اللي، إحنا.
  ممنوع الفصحى الثقيلة وممنوع ألفاظ خليجية أو شامية (مثل: هلق، شلون، وايد، كثير).
- جمل قصيرة (٨ إلى ١٥ كلمة). ممنوع جملة فيها أكتر من فكرة.
- ممنوع ترجمة حرفية لتعبيرات إنجليزية. لو الخبر فيه تعبير مش مصري، اشرح معناه بكلمات مصرية بسيطة.
- كل الأرقام بالحروف بالنطق المصري (أربعة صفر، واحد وعشرين سنة، تلتمية مليون). ممنوع أي رقم بالأرقام.
- النتيجة تتقال "أربعة صفر" أو "أربعة لصفر" مش "أربعة لايف".
- ممنوع تذكر اسم لاعب أو مدرب أو نادي أو رقم مش موجود حرفياً في النص الأصلي. لو الاسم مش واضح قول "اللاعب" أو "المدرب".
- ممنوع تحدد دور أي شخص (مدرب/لاعب/محلل) إلا لو النص قاله صراحة.
- الأسماء الأجنبية بالعربي بالنطق الشائع في مصر، وكل اسم يتكتب بنفس الشكل طول النص.
- حط تشكيل خفيف (فتحة وضمة وكسرة وشدة) على الأسماء الأجنبية والكلمات اللي ممكن تتقرا غلط بس، مش على كل النص.
- علامات الترقيم مهمة للأداء: نقطة آخر كل جملة، فاصلة للوقفة، علامة تعجب مرة كل كام جملة.
- متكررش نفس الجملة أو نفس الكلمة (مثل: لو لو). مفيش حشو.
- افتتاحية Hook من جملة واحدة وبعدها الخبر مباشرة، والختام دعوة قصيرة للاشتراك.
"""

def build_prompt(title, article_text, words="700-900"):
    return f"""أنت معلق كروي مصري قاهري في الخمسين، عايش في مصر طول عمره، وبتحكي لصحابك على القهوة.
اكتب محتوى بالعامية المصرية عن الخبر ده بس.

العنوان: {title}
المحتوى: {article_text}

{STYLE_RULES}
- طول سكريبت الفيديو الطويل {words} كلمة، لو النص الأصلي قصير اكتب أقل بدل ما تخترع.
- العنوان ٥٠-٦٠ حرف بالفصحى المبسطة للسيو، الوصف حوالي ١٢٠ كلمة، ١٥ هاشتاج عربي، شورتس ٣٠-٤٥ ثانية بدون هاشتاجات.

المطلوب JSON فقط بالمفاتيح:
video_title, video_script, video_description, shorts_title, shorts_script, hashtags (قائمة ١٥), facebook_post
"""

# ---- مراجعة نطق وأسلوب بنداء ثاني للنموذج (بتصلح الجُمل المش مصرية) ----
POLISH_SYSTEM = (
 "أنت مدقق لغوي مصري. بتاخد نص تعليق صوتي بالعامية المصرية وبترجعه بعد تصحيح: "
 "1) أي كلمة فصحى ثقيلة أو غير مصرية تتبدل بمرادفها المصري. "
 "2) أي جملة مترجمة حرفياً أو معناها غريب تتعدل أو تتشال. "
 "3) تشكيل خفيف على الأسماء الأجنبية والكلمات الملتبسة بس. "
 "4) متضيفش معلومة ولا اسم ولا رقم جديد، ومتشيلش معلومة صح. "
 "5) أي رقم بالأرقام يتحول لكلمات مصرية. "
 "رجّع النص المصحح بس بدون أي شرح."
)

def polish_script(client, model, script, source_text):
    try:
        r = client.chat.completions.create(
            model=model, temperature=0.2, max_tokens=4000,
            messages=[{"role": "system", "content": POLISH_SYSTEM},
                      {"role": "user", "content": "النص الأصلي للخبر (مرجع للأسماء فقط):\n" + source_text[:2500] + "\n\nالتعليق:\n" + script}])
        out = (r.choices[0].message.content or "").strip()
        return out if len(out) > 0.7 * len(script) else script
    except Exception as e:
        print("⚠️ فشل تدقيق السكريبت:", e)
        return script


def clean_script_keep_tashkeel(text):
    """زي clean_text_strict لكن بيحافظ على التشكيل وعلامات الترقيم."""
    if not text:
        return ""
    text = re.sub(r"[a-zA-Z]", "", text)
    text = re.sub(r"[^\u0600-\u06FF0-9\s\.\,\!\?\:\(\)\-]", "", text)
    return re.sub(r"\s+", " ", text).strip()
