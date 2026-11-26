# -*- coding: utf-8 -*-
"""
trending.py — رصد المواضيع الترندية في كرة القدم
==================================================
- يقرأ خلاصة Google Trends اللحظية (realtime RSS) لمصر أولاً ثم السعودية
- يفلتر المواضيع بالكلمات المفتاحية الكروية (تمرر من youtube_arabic)
- لكل موضوع ترندي يجلب المصادر الإخبارية المرتبطة به (عناوين + روابط)
- يجلب نص أفضل مقالين ليستخدمهما الـ LLM كأساس للسكريبت (نص فقط — لا صور إطلاقاً)
- منع التكرار: مفتاح trend:<slug> وروابط المقالات تتسجل في history.json
"""

import re
import time
import unicodedata
import requests
import xml.etree.ElementTree as ET

TREND_FEEDS = [
    ("مصر", "https://trends.google.com/trending/rss?geo=EG"),
    ("السعودية", "https://trends.google.com/trending/rss?geo=SA"),
]

MAX_TREND_SECONDS = 150      # حد أقصى لمرحلة رصد الترند كاملة
MAX_ARTICLES_PER_TREND = 2   # أقصى عدد مقالات يُعتمد عليها لكل موضوع
MIN_ARTICLE_CHARS = 500

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

AR_DIACRITICS = re.compile(r'[ً-ْٰ]')


def trend_slug(title):
    """تطبيع عنوان الترند لمفتاح منع التكرار"""
    t = unicodedata.normalize('NFKD', title or '')
    t = AR_DIACRITICS.sub('', t)
    t = t.replace('أ', 'ا').replace('إ', 'ا').replace('آ', 'ا').replace('ة', 'ه')
    t = re.sub(r'[^\w\s]', ' ', t, flags=re.UNICODE)
    t = re.sub(r'\s+', ' ', t).strip().lower()
    return t[:80]


def _localname(tag):
    return tag.split('}')[-1]


def _parse_feed(xml_bytes):
    """تحليل خلاصة الترند: قائمة مواضيع مع مصادرها الإخبارية"""
    root = ET.fromstring(xml_bytes)
    trends = []
    for item in root.iter():
        if _localname(item.tag) != 'item':
            continue
        title = ''
        traffic = ''
        news_items = []
        for child in item:
            name = _localname(child.tag)
            if name == 'title':
                title = (child.text or '').strip()
            elif name == 'approx_traffic':
                traffic = (child.text or '').strip()
            elif name == 'news_item':
                news = {}
                for nc in child:
                    nname = _localname(nc.tag)
                    if nname == 'news_item_title':
                        news['title'] = (nc.text or '').strip()
                    elif nname == 'news_item_url':
                        news['url'] = (nc.text or '').strip()
                    elif nname == 'news_item_source':
                        news['source'] = (nc.text or '').strip()
                if news.get('title') and news.get('url'):
                    news_items.append(news)
        if title:
            trends.append({
                'topic': title,
                'traffic': traffic,
                'news': news_items,
            })
    return trends


def _matches(text, keywords, blacklist):
    low = (text or '').lower()
    for bl in blacklist:
        if bl.lower() in low:
            return False
    for kw in keywords:
        if kw.lower() in low:
            return True
    return False


def fetch_article_text(url):
    """جلب نص مقال فقط (بلا أي صور) — لاستخدامه كمصدر معلومات"""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.content, 'html.parser')
        paragraphs = soup.find_all('p')
        text = " ".join(p.get_text().strip() for p in paragraphs if len(p.get_text().strip()) > 30)
        return text if len(text) >= MIN_ARTICLE_CHARS else None
    except Exception:
        return None


def find_trending_topic(history_links, keywords, blacklist):
    """
    يرصد أول موضوع كروي ترندي غير مكرر مع مقالات مصدر كافية.
    يرجع dict:
      topic, traffic, feed_label, slug_key (trend:<slug>),
      articles: [{title, url, source, text}]
    أو None لو لا يوجد موضوع صالح.
    """
    start = time.time()

    for feed_label, feed_url in TREND_FEEDS:
        if time.time() - start > MAX_TREND_SECONDS:
            print("⏱️ انتهى الوقت المخصص لرصد الترند")
            return None
        try:
            print(f"📈 جاري رصد الترند من جوجل ({feed_label})...")
            resp = requests.get(feed_url, headers=HEADERS, timeout=15)
            trends = _parse_feed(resp.content)
            print(f"   📊 {len(trends)} موضوع ترندي")
        except Exception as e:
            print(f"⚠️ فشل جلب خلاصة الترند ({feed_label}): {e}")
            continue

        for trend in trends:
            if time.time() - start > MAX_TREND_SECONDS:
                print("⏱️ انتهى الوقت المخصص لرصد الترند")
                return None

            topic = trend['topic']
            haystack = topic + " " + " ".join(n['title'] for n in trend['news'])
            if not _matches(haystack, keywords, blacklist):
                continue

            slug_key = "trend:" + trend_slug(topic)
            if slug_key in history_links:
                print(f"   ⏭️ موضوع مكرر (اتعمل عنه فيديو قبل كده): {topic}")
                continue

            print(f"🔥 موضوع كروي ترندي: {topic} ({trend['traffic']} بحث)")

            articles = []
            for news in trend['news']:
                if len(articles) >= MAX_ARTICLES_PER_TREND:
                    break
                if news['url'] in history_links:
                    continue
                text = fetch_article_text(news['url'])
                # استبعاد نفس المقال برابط مختلف (مثلاً bbc.com و bbc.co.uk)
                if text and any(text[:200] == a['text'][:200] for a in articles):
                    continue
                if text:
                    articles.append({
                        'title': news['title'],
                        'url': news['url'],
                        'source': news.get('source') or 'مصدر إخباري',
                        'text': text,
                    })

            if not articles:
                print(f"   😔 لا توجد مقالات مصدر صالحة للموضوع: {topic}")
                continue

            return {
                'topic': topic,
                'traffic': trend['traffic'],
                'feed_label': feed_label,
                'slug_key': slug_key,
                'articles': articles,
            }

    print("😴 لا يوجد موضوع كروي ترندي جديد حالياً")
    return None
