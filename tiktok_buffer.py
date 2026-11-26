"""نشر الشورتس على تيكتوك عن طريق Buffer.
- بيرفع الفيديو على فرع media في الريبو (رابط عام مباشر)
- وبعدين بيبعت الرابط لـ Buffer API عشان ينشره تلقائي
أي فشل هنا بيتطبع بس ومبيوقفش البوت."""
import os
import re
import shutil
import subprocess
import tempfile
import time
import requests

BUFFER_API = "https://api.buffer.com"
MEDIA_BRANCH = "media"


def _gql(key, query, variables=None):
    r = requests.post(
        BUFFER_API,
        json={"query": query, "variables": variables or {}},
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        timeout=60,
    )
    try:
        data = r.json()
    except Exception:
        raise RuntimeError(f"Buffer HTTP {r.status_code}: {r.text[:300]}")
    if data.get("errors"):
        raise RuntimeError(f"Buffer errors: {str(data['errors'])[:400]}")
    return data.get("data") or {}


def find_tiktok_channel(key):
    cid = (os.environ.get("BUFFER_CHANNEL_ID") or "").strip()
    if cid:
        return cid
    orgs = _gql(key, "query { account { organizations { id name } } }")["account"]["organizations"]
    for org in orgs:
        chans = _gql(
            key,
            "query($i: ChannelsInput!) { channels(input: $i) { id name service } }",
            {"i": {"organizationId": org["id"]}},
        )["channels"]
        for c in chans:
            if str(c.get("service", "")).lower() == "tiktok":
                print(f"   قناة تيكتوك في Buffer: {c.get('name')} ({c['id']})")
                return c["id"]
    raise RuntimeError("مفيش قناة تيكتوك مربوطة في Buffer")


def shrink_for_hosting(video_path, max_mb=60):
    """فيديو ٣ دقايق بجودة عالية ممكن يعدي ١٠٠ ميجا (حد جيت هب). بنعمل نسخة أخف لتيكتوك بس، والأصلي ما بيتغيرش."""
    if os.path.getsize(video_path) <= max_mb * 1024 * 1024:
        return video_path
    out = video_path + ".tt.mp4"
    subprocess.run(["ffmpeg", "-y", "-i", video_path, "-c:v", "libx264", "-b:v", "2200k", "-maxrate", "2800k",
                    "-bufsize", "5000k", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k",
                    "-movflags", "+faststart", out], check=True, capture_output=True, timeout=600)
    print(f"   اتعملت نسخة أخف لتيكتوك: {os.path.getsize(out)/1048576:.0f} ميجا")
    return out


def host_video(video_path):
    """يرفع الملف على فرع media ويرجع رابط raw عام."""
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not token or not repo:
        raise RuntimeError("GH_TOKEN / GITHUB_REPOSITORY مش موجودين")
    name = f"short_{int(time.time())}.mp4"
    tmp = tempfile.mkdtemp()
    try:
        shutil.copy(video_path, os.path.join(tmp, name))
        env = dict(os.environ, GIT_TERMINAL_PROMPT="0")

        def git(*args):
            subprocess.run(["git", *args], cwd=tmp, check=True, env=env,
                           capture_output=True, text=True, timeout=300)

        git("init", "-q")
        git("checkout", "-q", "-b", MEDIA_BRANCH)
        git("config", "user.name", "Arabic Football Bot")
        git("config", "user.email", "bot@github.com")
        git("add", name)
        git("commit", "-q", "-m", "media for TikTok [skip ci]")
        git("remote", "add", "origin", f"https://x-access-token:{token}@github.com/{repo}.git")
        git("push", "-q", "--force", "origin", MEDIA_BRANCH)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    url = f"https://raw.githubusercontent.com/{repo}/{MEDIA_BRANCH}/{name}"
    for _ in range(18):
        try:
            h = requests.get(url, headers={"Range": "bytes=0-1023"}, timeout=20)
            if h.status_code in (200, 206):
                print(f"   الرابط العام شغال: {url}")
                return url
        except Exception:
            pass
        time.sleep(5)
    raise RuntimeError("الرابط العام ماظهرش بعد ٩٠ ثانية")


CREATE = """
mutation($i: CreatePostInput!) {
  createPost(input: $i) {
    ... on PostActionSuccess { post { id status } }
    ... on MutationError { message }
  }
}
"""


def post_short_to_tiktok(video_path, title, hashtags):
    key = (os.environ.get("BUFFER_API_KEY") or "").strip()
    if not key:
        print("⚠️ تيكتوك غير مفعل - مفيش BUFFER_API_KEY")
        return False
    try:
        print("🎵 نشر الشورتس على تيكتوك عن طريق Buffer...")
        channel = find_tiktok_channel(key)
        url = host_video(shrink_for_hosting(video_path))
        tags = " ".join(h if h.startswith("#") else "#" + h for h in (hashtags or [])[:6])
        text = re.sub(r"\s+", " ", f"{title} {tags}").strip()[:2000]
        last = ""
        for mode in ("shareNow", "addToQueue"):
            inp = {
                "text": text,
                "channelId": channel,
                "schedulingType": "automatic",
                "mode": mode,
                "assets": [{"video": {"url": url}}],
                "metadata": {"tiktok": {"isAiGenerated": True}},
            }
            try:
                res = _gql(key, CREATE, {"i": inp})["createPost"]
            except Exception as e:
                last = str(e)
                continue
            if res.get("post"):
                print(f"✅ تيكتوك: Buffer استلم الفيديو ({mode}) id={res['post']['id']}")
                return True
            last = res.get("message", str(res))
        print(f"❌ تيكتوك فشل: {last}")
        return False
    except Exception as e:
        print(f"❌ تيكتوك فشل: {e}")
        return False
