"""LINE Messaging API broadcast (no recipient ID and no webhook)."""
import requests

LINE_BROADCAST_URL = "https://api.line.me/v2/bot/message/broadcast"
MAX_MESSAGE_LENGTH = 500


def prepare_message(message):
    """Prepare a LINE text message with at most 500 Python characters."""
    if not isinstance(message, str) or not message.strip():
        raise ValueError("Cannot broadcast an empty answer.")
    message = message.strip()
    if len(message) > MAX_MESSAGE_LENGTH:
        message = message[:MAX_MESSAGE_LENGTH - 1] + "…"
    return message


def send_line_message(MESSAGE, channel_access_token):
    """Broadcast MESSAGE to all eligible followers. No user ID is required."""
    if not isinstance(channel_access_token, str) or not channel_access_token.strip():
        raise ValueError("LINE channel access token is required.")
    message = prepare_message(MESSAGE)
    try:
        response = requests.post(
            LINE_BROADCAST_URL,
            headers={
                "Authorization": "Bearer " + channel_access_token.strip(),
                "Content-Type": "application/json",
            },
            json={"messages": [{"type": "text", "text": message}]},
            timeout=20,
        )
        response.raise_for_status()
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "unknown"
        details = (exc.response.text[:250] if exc.response is not None else "")
        raise RuntimeError(f"LINE broadcast rejected (HTTP {status}): {details}") from exc
    except requests.RequestException as exc:
        raise RuntimeError(f"LINE network error: {exc}") from exc
    return f"LINE accepted broadcast request ({len(message)} characters). Delivery is not guaranteed."
