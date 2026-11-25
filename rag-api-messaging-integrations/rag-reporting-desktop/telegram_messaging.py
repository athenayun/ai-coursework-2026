"""Send RAG answers through Telegram Bot API without logging credentials."""
import re
import requests


def send_telegram_message(token, chat_id, text):
    if not re.fullmatch(r"[0-9]+:[A-Za-z0-9_-]+", token):
        raise ValueError("Invalid Telegram bot token format.")
    if not re.fullmatch(r"-?[0-9]+", chat_id):
        raise ValueError("Enter a numeric Telegram chat ID.")
    if not text.strip():
        raise ValueError("Empty answer.")
    # Conservative chunk size also accommodates supplementary Unicode characters.
    chunks = [text[i:i+2000] for i in range(0, len(text), 2000)]
    for i, chunk in enumerate(chunks, 1):
        try:
            response = requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": chunk}, timeout=30)
            result = response.json()
        except (requests.RequestException, ValueError):
            raise RuntimeError(f"Telegram request failed at part {i}; {i-1} parts accepted earlier. Check network and bot settings.") from None
        if not response.ok or not result.get("ok"):
            raise RuntimeError(f"Telegram rejected part {i} (HTTP {response.status_code}); {i-1} parts accepted earlier. Check token, chat ID and permissions.")
    return f"Telegram accepted {len(chunks)} message(s)."
