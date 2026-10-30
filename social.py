import json
import os
import re
import time
import requests

BSKY_HANDLE = os.environ.get("BSKY_HANDLE", "")
BSKY_APP_PASSWORD = os.environ.get("BSKY_APP_PASSWORD", "")
X_BEARER = os.environ.get("X_BEARER_TOKEN", "")
THREADS_TOKEN = os.environ.get("THREADS_TOKEN", "")
X_MAX_POSTS = int(os.environ.get("X_MAX_POSTS", "20"))        # кожен допис в X платний
BSKY_MAX_POSTS = int(os.environ.get("BSKY_MAX_POSTS", "40"))  # безкоштовно, до 100

_bsky = {"jwt": None, "time": 0}


def connected():
    names = []
    if BSKY_HANDLE and BSKY_APP_PASSWORD:
        names.append("Bluesky")
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


# ---------- Пошукові фрази з довільного запиту ----------
def make_queries(groq, request_text):
    try:
        out = groq(
            [
                {
                    "role": "system",
                    "content": (
                        "Перетвори запит користувача на 1-3 короткі пошукові запити для "
                        "соцмереж (ключові слова, 1-4 слова, без пояснень). Використовуй "
                        "українську та/або англійську залежно від теми: для міжнародних "
                        "тем додай англійський варіант. Поверни ТІЛЬКИ JSON-масив рядків, "
                        'наприклад: ["apple політика", "apple policy"]'
                    ),
                },
                {"role": "user", "content": request_text},
            ],
            temperature=0,
        )
        m = re.search(r"\[.*\]", out, re.S)
        arr = json.loads(m.group(0))
        qs = [str(q).strip() for q in arr if str(q).strip()][:3]
        if qs:
            return qs
    except Exception as e:
        print("Query gen error:", e, flush=True)
    return [request_text[:100]]


def collect(groq, request_text):
    """Повертає (дописи за джерелами, пошукові фрази, примітки про помилки)."""
    queries = make_queries(groq, request_text)
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
    return posts, queries, notes
