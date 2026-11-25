# Multi-Strategy RAG — Multi-channel Reporting

Local CustomTkinter document Q&A with ONNX multilingual embeddings, Groq, eight retrieval strategies, PDF/DOCX ingestion, evidence and chat history. Delivery tabs: LINE, Telegram and Resend Email.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app_tk.py
```

Connect Groq, select and index a document, choose retrieval strategy and ask a question. Select a delivery tab, enter credentials and destination, customize the title/subject and introduction, choose whether to include the question and evidence, refresh preview and confirm sending. Only the latest answer is sent; local CSV/DOCX exports retain chat history. Query duration measures retrieval and answer generation, not indexing or delivery.

- LINE: Push requires user/group/room ID; Broadcast sends to all eligible followers and may consume quota. Long reports are split into batches.
- Telegram: enter bot token and numeric chat ID; start the bot first. Long reports are split.
- Email: enter Resend key, sender, recipient, subject and optional introduction; choose CSV, DOCX, both or no attachments. The default onboarding@resend.dev test sender is restricted to the account owner's address; verify a domain for other recipients. Attachments contain the latest customized report.

Credentials are not saved by the app. Optional environment variables: GROQ_API_KEY, LINE_CHANNEL_ACCESS_TOKEN, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, RESEND_API_KEY. Never commit secrets. Retrieved evidence is sent to Groq; delivery sends selected report content to the chosen provider. Review sensitive document content before sending. API acceptance is not guaranteed delivery. Partial sends may occur; check before retrying.

The original rag_engine.py is unchanged. Syntax checked; live GUI and API delivery not tested.
