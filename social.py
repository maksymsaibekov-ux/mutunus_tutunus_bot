import html
import json
import os
import re
import time
from urllib.parse import quote
import requests

BSKY_HANDLE = os.environ.get("BSKY_HANDLE", "")
BSKY_APP_PASSWORD = os.environ.get("BSKY_APP_PASSWORD", "")
X_BEARER = os.environ.get("X_BEARER_TOKEN", "")
THREADS_TOKEN = os.environ.get("THREADS_TOKEN", "")
X_MAX_POSTS = int(os.environ.get("X_MAX_POSTS", "20"))        # кожен допис в X платний
BSKY_MAX_POSTS = int(os.environ.get("BSKY_MAX_POSTS", "40"))  # безкоштовно, до 100
MASTODON_ON = os.environ.get("MASTODON", "1") == "1"          # без ключів; вимкнути: MASTODON=0
MASTODON_INSTANCE = (
    os.environ.get("MASTODON_INSTANCE", "mastodon.social")
    .replace("https://", "").replace("http://", "").strip("/")
)

_bsky = {"jwt": None, "time": 0}


def connected():
    names = []
    if BSKY_HANDLE and BSKY_APP_PASSWORD:
        names.append("Bluesky")
    if MASTODON_ON:
        names.append("Mastodon")
    if X_BEARER:
        names.append("X")
    if THREADS_TOKEN:
        names.append("Threads")
    return names


# ---------- Bluesky ----------
def _bsky_login():
    r = requests.post(
        "https://bsky.social/xrpc/com.atproto.server.createSession",
        json={"identifier": BSKY_HANDLE, "password": BSKY_APP_PASSWORD},
        timeout=20,
    )
    if r.status_code != 200:
        raise Exception(f"Bluesky login {r.status_code}: {r.text[:150]}")
    _bsky["jwt"] = r.json()["accessJwt"]
    _bsky["time"] = time.time()


def fetch_bluesky(query):
    if not _bsky["jwt"] or time.time() - _bsky["time"] > 3000:
        _bsky_login()
    for attempt in (1, 2):
        r = requests.get(
            "https://bsky.social/xrpc/app.bsky.feed.searchPosts",
            headers={"Authorization": f"Bearer {_bsky['jwt']}"},
            params={"q": query, "limit": min(BSKY_MAX_POSTS, 100), "sort": "latest"},
            timeout=30,
        )
        if r.status_code == 401 and attempt == 1:
            _bsky_login()
            continue
        break
    if r.status_code != 200:
        raise Exception(f"Bluesky search {r.status_code}: {r.text[:150]}")
    out = []
    for p in r.json().get("posts", []):
        text = (p.get("record") or {}).get("text")
        if text:
            out.append(text)
    return out


# ---------- Mastodon (хештеги, без ключів) ----------
def fetch_mastodon(tag):
    r = requests.get(
        f"https://{MASTODON_INSTANCE}/api/v1/timelines/tag/{quote(tag)}",
        params={"limit": 40},
        timeout=30,
    )
    if r.status_code == 404:  # такого хештегу ще немає
        return []
    if r.status_code != 200:
        raise Exception(f"Mastodon {r.status_code}: {r.text[:150]}")
    out = []
    for s in r.json():
        if s.get("reblog"):
            continue
        text = re.sub(r"<[^>]+>", " ", s.get("content", ""))
        text = re.sub(r"\s+", " ", html.unescape(text)).strip()
        if text:
            out.append(text)
    return out


# ---------- X ----------
def fetch_x(query):
    n = max(10, min(X_MAX_POSTS, 100))
    r = requests.get(
        "https://api.x.com/2/tweets/search/recent",
        headers={"Authorization": f"Bearer {X_BEARER}"},
        params={"query": f"{query} -is:retweet", "max_results": n},
        timeout=30,
    )
    if r.status_code != 200:
        raise Exception(f"X {r.status_code}: {r.text[:150]}")
    return [t["text"] for t in r.json().get("data", [])]


# ---------- Threads ----------
def fetch_threads(query):
    r = requests.get(
        "https://graph.threads.net/v1.0/keyword_search",
        params={
            "q": query,
            "search_type": "TOP",
            "fields": "text,username,timestamp",
            "access_token": THREADS_TOKEN,
        },
        timeout=30,
    )
    if r.status_code != 200:
        raise Exception(f"Threads {r.status_code}: {r.text[:150]}")
    return [p["text"] for p in r.json().get("data", []) if p.get("text")]


# ---------- Пошукові фрази й хештеги з довільного запиту ----------
def _fallback_tags(queries):
    tags = [re.sub(r"\W+", "", q) for q in queries]
    return [t for t in tags if t][:3]


def make_queries(groq, request_text):
    try:
        out = groq(
            [
                {
                    "role": "system",
                    "content": (
                        "Перетвори запит користувача на пошукові терміни для соцмереж. "
                        "Поверни ТІЛЬКИ JSON-об'єкт без пояснень: "
                        '{"queries": [1-3 короткі пошукові фрази по 1-4 слова], '
                        '"hashtags": [1-3 хештеги, кожен одним словом без пробілів і без #]}. '
                        "Використовуй українську та/або англійську залежно від теми: для "
                        "міжнародних тем додай англійські варіанти. Приклад: "
                        '{"queries": ["apple політика", "apple policy"], "hashtags": ["apple", "ios"]}'
                    ),
                },
                {"role": "user", "content": request_text},
            ],
            temperature=0,
        )
        data = json.loads(re.search(r"\{.*\}", out, re.S).group(0))
        qs = [str(q).strip() for q in data.get("queries", []) if str(q).strip()][:3]
        tags = [re.sub(r"\W+", "", str(h)) for h in data.get("hashtags", [])]
        tags = [t for t in tags if t][:3]
        if qs:
            return qs, tags or _fallback_tags(qs)
    except Exception as e:
        print("Query gen error:", e, flush=True)
    qs = [request_text[:100]]
    return qs, _fallback_tags(qs)


def collect(groq, request_text):
    """Повертає (дописи за джерелами, пошукові запити, примітки про помилки)."""
    queries, tags = make_queries(groq, request_text)
    posts, notes = {}, []

    def add(src, items):
        bucket = posts.setdefault(src, [])
        for t in items:
            t = t.strip()
            if t and t not in bucket:
                bucket.append(t)

    if BSKY_HANDLE and BSKY_APP_PASSWORD:
        for q in queries:
            try:
                add("Bluesky", fetch_bluesky(q))
            except Exception as e:
                print("Bluesky error:", e, flush=True)
                notes.append("Bluesky зараз недоступний")
                break
    if MASTODON_ON:
        for t in tags:
            try:
                add("Mastodon", fetch_mastodon(t))
            except Exception as e:
                print("Mastodon error:", e, flush=True)
                notes.append("Mastodon зараз недоступний")
                break
    if X_BEARER:  # лише перша фраза, щоб не витрачати гроші
        try:
            add("X", fetch_x(queries[0]))
        except Exception as e:
            print("X error:", e, flush=True)
            notes.append("X недоступний (перевір ключ і баланс)")
    if THREADS_TOKEN:
        try:
            add("Threads", fetch_threads(queries[0]))
        except Exception as e:
            print("Threads error:", e, flush=True)
            notes.append("Threads недоступний (можливо, немає дозволу на пошук)")

    posts = {k: v for k, v in posts.items() if v}
    shown = queries + ([f"#{t}" for t in tags] if MASTODON_ON else [])
    return posts, shown, notes
