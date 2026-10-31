import asyncio
import os
import re
import requests
import edge_tts

GROQ_KEY = os.environ["GROQ_API_KEY"]
TG_URL = f"https://api.telegram.org/bot{os.environ['TG_TOKEN']}"

STT_MODEL = os.environ.get("STT_MODEL", "whisper-large-v3")
STT_LANGUAGE = os.environ.get("STT_LANGUAGE", "uk")          # "auto" для автовизначення
TTS_VOICE = os.environ.get("TTS_VOICE", "uk-UA-PolinaNeural")  # чоловічий: uk-UA-OstapNeural
TTS_MAX_CHARS = int(os.environ.get("TTS_MAX_CHARS", "1500"))   # скільки тексту озвучувати


def transcribe(audio_bytes, filename):
    data = {"model": STT_MODEL, "response_format": "json", "temperature": "0"}
    if STT_LANGUAGE and STT_LANGUAGE.lower() != "auto":
        data["language"] = STT_LANGUAGE
    r = requests.post(
        "https://api.groq.com/openai/v1/audio/transcriptions",
        headers={"Authorization": f"Bearer {GROQ_KEY}"},
        data=data,
        files={"file": (filename, audio_bytes)},
        timeout=120,
    )
    if r.status_code != 200:
        raise Exception(f"Groq {r.status_code}: {r.text[:300]}")
    return (r.json().get("text") or "").strip()


def clean_for_speech(text):
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"[`*_#>|~]", "", text)
    text = re.sub(r"[\U00010000-\U0010ffff\u2600-\u27bf\ufe0f•]", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()


def synthesize(text):
    async def run():
        audio = b""
        async for chunk in edge_tts.Communicate(text, TTS_VOICE).stream():
            if chunk["type"] == "audio":
                audio += chunk["data"]
        return audio

    return asyncio.run(run())


def send_voice(chat_id, text):
    clean = clean_for_speech(text)
    if len(clean) > TTS_MAX_CHARS:
        cut = clean[:TTS_MAX_CHARS]
        idx = max(cut.rfind(". "), cut.rfind("\n"))
        clean = cut[: idx + 1] if idx > TTS_MAX_CHARS * 0.5 else cut
    if len(clean) < 2:
        return
    audio = synthesize(clean)
    if not audio:
        raise Exception("TTS повернув порожній звук")
    r = requests.post(
        f"{TG_URL}/sendVoice",
        data={"chat_id": chat_id},
        files={"voice": ("answer.mp3", audio, "audio/mpeg")},
        timeout=60,
    )
    if not r.json().get("ok"):
        print("sendVoice failed:", r.text[:200], flush=True)
        requests.post(
            f"{TG_URL}/sendAudio",
            data={"chat_id": chat_id},
            files={"audio": ("answer.mp3", audio, "audio/mpeg")},
            timeout=60,
        )
