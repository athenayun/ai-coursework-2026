# Google Sheets Multi-Channel Reporting Desktop (V6)

Run `python -m pip install -r requirements.txt` then `python app.py` in a Python 3.10+ environment with Tk support.

Paste a publicly accessible Google Sheets URL, load, select columns, optionally filter by keyword across all columns, choose 1–100 rows and run query. CSV, Excel, Word and TXT exports use the saved query snapshot. Query timestamp, filtering duration and sheet loading duration are retained. Private sheets require authentication not implemented here.

## Delivery tabs
- Telegram: bot token, numeric chat ID, report title and optional note. Start the bot first. HTML preformatted tables are split into pages; long cells are shortened.
- LINE: channel access token, Push (recipient user/group/room ID) or Broadcast (all eligible followers), report title and optional note. Push is default. LINE uses readable record lists rather than relying on monospace alignment. Long messages are split. Broadcast may consume quota.
- Email: Resend API key, sender, recipient, subject, multiline body and CSV/Word/Both attachments. Default testing sender onboarding@resend.dev generally only permits the account email; verify a domain for other recipients.

Switch tabs or click Refresh message preview after editing fields. Send always uses the latest saved query snapshot and current channel settings; confirmation is required. No credentials are persisted. API acceptance is not proof of delivery; partial delivery is possible. CSV/Excel protect against formula injection. No new dependencies beyond V5. GUI and live APIs require local testing.
