# Multi-Strategy RAG Tkinter + LINE Broadcast

This is the existing local ONNX RAG desktop application with a **broadcast** button instead of the individual-user push button. It keeps the scrollable sidebar, indexing progress log, eight retrieval strategies, PDF/DOCX import, chat history, and CSV/DOCX export.

## Install on macOS

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python app_tk.py
```

If you already installed the previous version, simply replace `app_tk.py` and `line_messaging.py` and restart the application. The dependencies have not changed.

## Use

1. Enter a Groq API key and click **Connect / Fetch Models**.
2. Choose and index a PDF or DOCX, then ask a question.
3. Enter the **LINE Messaging API channel access token** (not the channel secret).
4. Click **Broadcast Last Answer to LINE**.
5. Read the confirmation and approve only if you intend to send the answer to **all eligible followers**.

No recipient ID or webhook is needed. This **does not reply privately to the user who last messaged the bot**. Broadcasting can count against LINE Official Account message quotas. The application truncates answers longer than 500 characters and preserves the full answer in Tkinter and exports.

The app sends the LINE token directly to LINE's API and does not write it to a file. Do not commit tokens to GitHub. Use a test Official Account for development. A successful API response means LINE accepted the broadcast request, not that every follower received it.

The RAG embedding model runs locally using ONNX; Groq receives selected document evidence for answer generation. No Cohere token is required.
