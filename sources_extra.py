# -*- coding: utf-8 -*-
"""
sources_extra.py — مصادر ترند إضافية + تشغيل يدوي بالرابط / الكلمة المفتاحية
===========================================================================
- مصادر ترند إضافية: Google News RSS (رياضة/كرة مصر والسعودية)، Bing News RSS،
  وترند يوتيوب الرسمي (YouTube Data API: mostPopular، تصنيف الرياضة) لو فيه YOUTUBE_API_KEY.
- extract_from_url: أي رابط (مقال / يوتيوب / بوست سوشيال / رابط مختصر) -> نص + عنوان.
  بياخد الكلام والمعلومات بس. لا لقطات ولا صور ولا تحميل فيديو.
- search_keyword: كلمة مفتاحية -> أحدث خبر جديد غير مكرر + نص المقال.
كل الدوال بتفشل بهدوء ولها رسالة واضحة في اللوج.
"""

import os
import re
import json
import html
import time
from urllib.parse import quote, urlparse, parse_qs
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

import requests
from bs4 import BeautifulSoup

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'ar,en;q=0.8',
}

MIN_ARTICLE_CHARS = 500     # للأخبار التلقائية
MIN_MANUAL_ARTICLE = 300    # لمقال بعته المستخدم بنفسه
MIN_SOCIAL_CHARS = 40       # بوست قصير (كابشن/تغريدة)


class ExtractError(Exception):
    """فشل استخراج محتوى من رابط — الرسالة بتتعرض للمستخدم في اللوج"""


# ---------------------------------------------------------------- أدوات عامة
def _localname(tag):
    return tag.split('}')[-1]


def _clean_html(s):
    return re.sub(r'\s+', ' ', BeautifulSoup(html.unescape(s or ''), 'html.parser').get_text(' ')).strip()


def _decode_gnews(url):
    """روابط Google News بتكون وسيطة؛ بنحاول نفك الرابط الأصلي"""
    if 'news.google.com' not in url:
        return url
    try:
        from googlenewsdecoder import gnewsdecoder
        res = gnewsdecoder(url, interval=1)
        if res.get('status') and res.get('decoded_url'):
            return res['decoded_url']
    except Exception:
        pass
    return None


def fetch_text(url, min_chars=MIN_ARTICLE_CHARS, timeout=12):
    """نص مقال فقط (فقرات <p>) — بلا صور. يرجع (title, text) أو (None, None)"""
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        if r.status_code >= 400:
            return None, None
        soup = BeautifulSoup(r.content, 'html.parser')
        title = ''
        og = soup.find('meta', property='og:title')
        if og and og.get('content'):
            title = og['content'].strip()
        elif soup.title and soup.title.string:
            title = soup.title.string.strip()
        h1 = soup.find('h1')
        if h1 and h1.get_text().strip():
            title = h1.get_text().strip()
        paras = [p.get_text().strip() for p in soup.find_all('p')]
        text = " ".join(p for p in paras if len(p) > 30)
        if len(text) < min_chars:
            return title, None
        return title, text
    except Exception:
        return None, None


# ---------------------------------------------------------------- RSS أخبار
def _parse_news_rss(xml_bytes, default_source):
    items = []
    root = ET.fromstring(xml_bytes)
    for it in root.iter():
        if _localname(it.tag) != 'item':
            continue
        d = {'title': '', 'url': '', 'source': default_source, 'date': None, 'desc': ''}
        for c in it:
            n = _localname(c.tag)
            if n == 'title':
                d['title'] = (c.text or '').strip()
            elif n == 'link':
                d['url'] = (c.text or '').strip()
            elif n == 'source':
                d['source'] = (c.text or '').strip() or default_source
            elif n == 'description':
                d['desc'] = _clean_html(c.text)
            elif n == 'pubDate' and c.text:
                try:
                    d['date'] = parsedate_to_datetime(c.text).timestamp()
                except Exception:
                    pass
        # عناوين Google News بتنتهي بـ " - اسم الموقع"
        if ' - ' in d['title'] and d['source'] != default_source:
            d['title'] = d['title'].rsplit(' - ', 1)[0].strip()
        if d['title'] and d['url']:
            items.append(d)
    return items


def google_news_rss(query, hl='ar', gl='EG', days=2, topic=None):
    ceid = f"{gl}:{hl}"
    if topic:
        url = f"https://news.google.com/rss/headlines/section/topic/{topic}?hl={hl}&gl={gl}&ceid={ceid}"
    else:
        q = quote(f"{query} when:{days}d")
        url = f"https://news.google.com/rss/search?q={q}&hl={hl}&gl={gl}&ceid={ceid}"
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.raise_for_status()
    return _parse_news_rss(r.content, 'Google News')


def bing_news_rss(query, mkt='ar-EG'):
    url = f"https://www.bing.com/news/search?q={quote(query)}&format=rss&mkt={mkt}"
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.raise_for_status()
    items = _parse_news_rss(r.content, 'Bing News')
    for it in items:   # روابط بينج بتكون apiclick فيها الرابط الأصلي في url=
        q = parse_qs(urlparse(it['url']).query)
        if q.get('url'):
            it['url'] = q['url'][0]
    return items


def _safe(fn, label, *a, **kw):
    try:
        res = fn(*a, **kw)
        print(f"   ✅ {label}: {len(res)} عنصر")
        return res
    except Exception as e:
        print(f"   ⚠️ {label} فشل: {e}")
        return []


# ---------------------------------------------------------------- ترند إضافي
def youtube_trending_titles(api_key=None, service=None, region='EG', category='17'):
    """ترند يوتيوب الرسمي (mostPopular) لتصنيف الرياضة. مفتاح API أو OAuth لو صلاحياته تسمح."""
    params = {'part': 'snippet,statistics', 'chart': 'mostPopular',
              'regionCode': region, 'videoCategoryId': category, 'maxResults': 25}
    data = None
    if api_key:
        r = requests.get('https://www.googleapis.com/youtube/v3/videos',
                         params={**params, 'key': api_key}, timeout=15)
        if r.status_code == 200:
            data = r.json()
        else:
            print(f"   ⚠️ YouTube API ({r.status_code}): {r.text[:150]}")
    if data is None and service is not None:
        try:
            data = service.videos().list(**params).execute()
        except Exception as e:
            print(f"   ⚠️ ترند يوتيوب عبر OAuth مش متاح (غالباً الصلاحيات): {str(e)[:120]}")
    if not data:
        print("   ℹ️ ترند يوتيوب متخطي (ضيف سر YOUTUBE_API_KEY لتفعيله)")
        return []
    out = []
    for v in data.get('items', []):
        sn = v.get('snippet', {})
        out.append({'title': sn.get('title', ''), 'channel': sn.get('channelTitle', ''),
                    'views': v.get('statistics', {}).get('viewCount', '')})
    return out


def _news_for_title(title, limit=4):
    news = []
    for it in _safe(google_news_rss, 'أخبار عن عنوان ترند', title, 'ar', 'EG', 3):
        news.append(it)
    return news[:limit]


def extra_trend_sets(get_service=None):
    """
    يرجع قائمة (label, [trend]) بنفس شكل تريند جوجل:
    trend = {topic, traffic, news:[{title,url,source}]}
    """
    sets = []
    api_key = os.environ.get('YOUTUBE_API_KEY')

    print("📈 مصدر: ترند يوتيوب الرسمي (رياضة - مصر)...")
    svc = None
    if not api_key and get_service:
        try:
            svc = get_service()
        except Exception:
            svc = None
    yt = youtube_trending_titles(api_key=api_key, service=svc)
    yt_trends = []
    for v in yt:
        news = _news_for_title(v['title'])
        yt_trends.append({'topic': v['title'], 'traffic': f"{v['views']} مشاهدة",
                          'news': [{'title': n['title'], 'url': n['url'], 'source': n['source']} for n in news]})
    if yt_trends:
        sets.append(('ترند يوتيوب مصر', yt_trends))

    print("📈 مصدر: Google News (رياضة مصر)...")
    for label, q, gl in (("أخبار جوجل مصر", "كرة القدم", "EG"), ("أخبار جوجل السعودية", "كرة القدم", "SA")):
        items = _safe(google_news_rss, label, q, 'ar', gl, 1)
        sets.append((label, [{'topic': i['title'], 'traffic': '',
                              'news': [{'title': i['title'], 'url': i['url'], 'source': i['source']}]}
                             for i in items]))

    print("📈 مصدر: Bing News...")
    items = _safe(bing_news_rss, 'أخبار بينج', 'كرة القدم مصر')
    sets.append(("أخبار بينج", [{'topic': i['title'], 'traffic': '',
                                 'news': [{'title': i['title'], 'url': i['url'], 'source': i['source']}]}
                                for i in items]))
    return sets


def resolve_news_url(url):
    """يفك روابط جوجل نيوز الوسيطة؛ يرجع None لو مقدرش"""
    return _decode_gnews(url)


# ---------------------------------------------------------------- كلمة مفتاحية
def search_keyword(keyword, history, slug_fn, max_articles=2):
    """
    يدور على أحدث خبر عن الكلمة، غير موجود في الهيستوري.
    يرجع dict: title, text, url, source_name, slug_key, sources  أو None
    """
    kw = keyword.strip()
    print(f"🔎 بحث عن خبر بالكلمة: {kw}")
    items = []
    for hl, gl, mkt in (('ar', 'EG', 'ar-EG'), ('en', 'US', 'en-US')):
        items += _safe(google_news_rss, f'Google News ({hl})', kw, hl, gl, 7)
        items += _safe(bing_news_rss, f'Bing News ({hl})', kw, mkt)
        if items:
            break
    # ترتيب: الأحدث أولاً
    items.sort(key=lambda i: i['date'] or 0, reverse=True)

    seen, candidates = set(), []
    for it in items:
        s = slug_fn(it['title'])
        if s in seen or ("trend:" + s) in history or ("kw:" + s) in history or it['url'] in history:
            continue
        seen.add(s)
        candidates.append(it)
    print(f"   {len(candidates)} خبر جديد غير مكرر من {len(items)}")

    start = time.time()
    arts = []
    first = None
    for it in candidates:
        if time.time() - start > 120 or len(arts) >= max_articles:
            break
        real = resolve_news_url(it['url'])
        if not real:
            continue
        title, text = fetch_text(real, MIN_MANUAL_ARTICLE)
        if not text:
            continue
        if any(text[:200] == a['text'][:200] for a in arts):
            continue
        if real in history:
            continue
        if kw.lower() not in (it['title'] + ' ' + (title or '') + ' ' + text[:3000]).lower():
            continue   # مقال مش عن الكلمة فعلاً
        arts.append({'title': title or it['title'], 'url': real, 'source': it['source'], 'text': text})
        first = first or it
    if not arts:
        # حل أخير: عنوان + وصف RSS (قصير) لو متاح
        for it in candidates:
            if len(it['desc']) >= 80:
                print("   ℹ️ مفيش مقال كامل اتقرا، هستخدم ملخص الخبر من الـRSS (معلومات أقل)")
                return {'title': it['title'], 'text': it['title'] + ". " + it['desc'], 'url': it['url'],
                        'source_name': it['source'], 'slug_key': "kw:" + slug_fn(it['title']),
                        'sources': [{'source': it['source'], 'url': it['url']}]}
        return None
    text = "\n\n".join(f"مقال بعنوان ({a['title']}):\n{a['text'][:1600]}" for a in arts)
    return {'title': arts[0]['title'], 'text': text, 'url': arts[0]['url'],
            'source_name': arts[0]['source'], 'slug_key': "kw:" + slug_fn(first['title']),
            'sources': [{'source': a['source'], 'url': a['url']} for a in arts]}


# ---------------------------------------------------------------- رابط يدوي
URL_RE = re.compile(r'https?://[^\s<>"\'\)\]]+|(?:www\.)?(?:[a-z0-9-]+\.)+[a-z]{2,}/[^\s<>"\']*', re.I)
YT_HOSTS = ('youtube.com', 'youtu.be', 'youtube-nocookie.com')
SOCIAL_HOSTS = ('tiktok.com', 'instagram.com', 'facebook.com', 'fb.watch', 'fb.com', 'x.com', 'twitter.com',
                't.co', 'threads.net', 'reddit.com', 'redd.it', 't.me', 'snapchat.com', 'linkedin.com',
                'vm.tiktok.com', 'vt.tiktok.com')


def _host(url):
    h = (urlparse(url).hostname or '').lower()
    return h[4:] if h.startswith('www.') else h


def _is(url, hosts):
    h = _host(url)
    return any(h == x or h.endswith('.' + x) for x in hosts)


def normalize_url(raw):
    """بيطلع أول رابط من النص (حتى لو معاه كلام) ويكمله https لو ناقص"""
    m = URL_RE.search((raw or '').strip())
    if not m:
        raise ExtractError("مفيش رابط واضح في المدخل")
    u = m.group(0).rstrip('.,،؛;')
    if not u.lower().startswith('http'):
        u = 'https://' + u
    return u


def resolve_redirects(url):
    """يتتبع الروابط المختصرة (bit.ly, youtu.be, vm.tiktok.com, t.co ...) للرابط النهائي"""
    try:
        r = requests.get(url, headers=HEADERS, timeout=12, allow_redirects=True, stream=True)
        final = r.url
        r.close()
        return final or url
    except Exception:
        return url


def _parse_captions(raw):
    """نص من ملف ترجمة (json3 / vtt / srv) بلا أوقات"""
    try:
        data = json.loads(raw)
        segs = []
        for ev in data.get('events', []):
            for s in ev.get('segs', []) or []:
                segs.append(s.get('utf8', ''))
        txt = ''.join(segs)
    except Exception:
        txt = re.sub(r'WEBVTT.*?\n\n', '', raw, flags=re.S)
        txt = re.sub(r'\d+:\d+:\d+[\.,]\d+ --> .*', ' ', txt)
        txt = re.sub(r'<[^>]+>', '', txt)
    return re.sub(r'\s+', ' ', txt.replace('\n', ' ')).strip()


def _ytdlp_info(url):
    """بيانات وصفية (عنوان/وصف/ترجمة) عبر yt-dlp بدون تحميل أي فيديو"""
    try:
        import yt_dlp
    except Exception:
        print("   ℹ️ yt-dlp مش متثبت")
        return None
    opts = {'quiet': True, 'no_warnings': True, 'skip_download': True, 'noplaylist': True,
            'socket_timeout': 15, 'extractor_retries': 1}
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as e:
        print(f"   ⚠️ yt-dlp: {str(e)[:160]}")
        return None
    if not info:
        return None
    transcript = ''
    for bucket in ('subtitles', 'automatic_captions'):
        caps = info.get(bucket) or {}
        for lang in ('ar', 'ar-orig', 'en', 'en-orig'):
            fmts = caps.get(lang)
            if not fmts:
                continue
            pick = next((f for f in fmts if f.get('ext') == 'json3'), None) or \
                   next((f for f in fmts if f.get('ext') == 'vtt'), None)
            if not pick or not pick.get('url'):
                continue
            try:
                rr = requests.get(pick['url'], headers=HEADERS, timeout=15)
                transcript = _parse_captions(rr.text)
                if len(transcript) > 100:
                    print(f"   🗒️ اتقرت ترجمة ({bucket}/{lang}): {len(transcript)} حرف")
                    break
            except Exception:
                continue
        if len(transcript) > 100:
            break
    return {'title': info.get('title') or '', 'description': info.get('description') or '',
            'uploader': info.get('uploader') or info.get('channel') or '',
            'tags': info.get('tags') or [], 'transcript': transcript}


def _oembed(url):
    eps = []
    if _is(url, YT_HOSTS):
        eps.append(f"https://www.youtube.com/oembed?format=json&url={quote(url, safe='')}")
    if _is(url, ('x.com', 'twitter.com')):
        eps.append(f"https://publish.twitter.com/oembed?omit_script=1&url={quote(url, safe='')}")
    if _is(url, ('tiktok.com',)):
        eps.append(f"https://www.tiktok.com/oembed?url={quote(url, safe='')}")
    if _is(url, ('reddit.com',)):
        eps.append(f"https://www.reddit.com/oembed?url={quote(url, safe='')}")
    for ep in eps:
        try:
            r = requests.get(ep, headers=HEADERS, timeout=10)
            if r.status_code == 200:
                d = r.json()
                text = _clean_html(d.get('html', '')) if 'twitter' in ep or 'x.com' in url else ''
                return {'title': d.get('title') or '', 'author': d.get('author_name') or '', 'text': text}
        except Exception:
            continue
    return None


def _og_meta(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=12)
        soup = BeautifulSoup(r.content, 'html.parser')
        def meta(*names):
            for n in names:
                t = soup.find('meta', property=n) or soup.find('meta', attrs={'name': n})
                if t and t.get('content'):
                    return t['content'].strip()
            return ''
        return {'title': meta('og:title', 'twitter:title') or (soup.title.string.strip() if soup.title and soup.title.string else ''),
                'description': meta('og:description', 'twitter:description', 'description')}
    except Exception:
        return {'title': '', 'description': ''}


def _reddit_json(url):
    try:
        r = requests.get(url.split('?')[0].rstrip('/') + '.json', headers=HEADERS, timeout=12)
        d = r.json()[0]['data']['children'][0]['data']
        return {'title': d.get('title', ''), 'text': d.get('selftext', '')}
    except Exception:
        return None


def extract_from_url(raw):
    """
    أي رابط -> dict(title, text, url, source_name, slug_key, sources, kind)
    أو ExtractError برسالة واضحة. نص ومعلومات فقط، لا لقطات ولا صور.
    """
    url = normalize_url(raw)
    print(f"🔗 الرابط المدخل: {url}")
    final = resolve_redirects(url)
    if final != url:
        print(f"   ↪️ الرابط النهائي: {final}")
    url = final

    social = _is(url, SOCIAL_HOSTS)
    video = _is(url, YT_HOSTS)
    title, text, kind = '', '', 'article'

    if video:
        kind = 'video'
        print("   🎥 نوع الرابط: فيديو يوتيوب")
        import yt_transcript
        oe = _oembed(url)
        try:
            yt = yt_transcript.get_youtube_text(url, (oe or {}).get('title', ''))
        except yt_transcript.TranscriptError as e:
            raise ExtractError(str(e))
        title = yt['title']
        text = "نص الكلام في الفيديو (من الفيديو نفسه):\n" + yt['text']
        if yt['description'] and len(yt['description']) > 200:
            text += "\nوصف الفيديو: " + yt['description']
        kind = 'video'
    elif social:
        kind = 'social'
        print("   🎥 نوع الرابط: بوست/فيديو سوشيال")
        parts = []
        info = _ytdlp_info(url)
        if info:
            title = info['title']
            if info['transcript']:
                parts.append("نص الكلام في الفيديو (ترجمة): " + info['transcript'][:6000])
            if info['description']:
                parts.append("الوصف: " + info['description'][:2500])
        if not parts:
            oe = _oembed(url)
            if oe:
                title = title or oe['title']
                if oe['text']:
                    parts.append("البوست: " + oe['text'])
                elif oe['title']:
                    parts.append("العنوان: " + oe['title'])
        if not parts and _is(url, ('reddit.com',)):
            rj = _reddit_json(url)
            if rj and (rj['title'] or rj['text']):
                title = title or rj['title']
                parts.append(f"{rj['title']}. {rj['text']}")
        if not parts or sum(len(p) for p in parts) < MIN_SOCIAL_CHARS * 2:
            og = _og_meta(url)
            bad = re.search(r'404|not found|لم يتم العثور|غير موجود|log ?in|تسجيل الدخول|page isn', og['title'] + ' ' + og['description'], re.I)
            if not bad:
                title = title or og['title']
            if og['description'] and not bad:
                parts.append("وصف الصفحة: " + og['description'])
        text = "\n".join(parts).strip()
        if not title:
            title = text[:80]
        if len(text) < MIN_SOCIAL_CHARS:
            raise ExtractError(
                f"المنصة ({_host(url)}) حجبت القراءة الآلية أو الرابط ملوش نص/وصف أقدر أقراه. "
                "جرّب رابط مقال إخباري عن نفس الموضوع، أو استخدم تشغيل بكلمة مفتاحية.")
    else:
        print("   📰 نوع الرابط: مقال")
        t, tx = fetch_text(url, MIN_MANUAL_ARTICLE, timeout=15)
        if tx:
            title, text = t, tx[:6000]
        else:
            og = _og_meta(url)
            if len(og['description']) >= 80:
                title, text = og['title'], og['title'] + ". " + og['description']
                print("   ⚠️ النص الكامل مش متاح، هستخدم ملخص الصفحة (معلومات أقل)")
            else:
                raise ExtractError(
                    f"مقدرتش أقرا نص المقال من {_host(url)} (الموقع ممكن يكون حاجب القراءة الآلية أو محتاج اشتراك).")

    print(f"   ✅ اتقرا: «{title[:70]}» ({len(text)} حرف)")
    import hashlib
    slug = "url:" + hashlib.sha1(url.encode()).hexdigest()[:16]
    return {'title': title or 'موضوع', 'text': text, 'url': url, 'source_name': _host(url) or 'رابط يدوي',
            'slug_key': slug, 'sources': [{'source': _host(url), 'url': url}], 'kind': kind}
