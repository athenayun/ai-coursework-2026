# RAG, API & Messaging Integrations

Applications combining document question answering, structured data processing and external messaging APIs. The two reporting desktop projects share a tabbed delivery interface while using different processing engines.

## Projects

| Project | Processing | Delivery |
| --- | --- | --- |
| [rag-streamlit-line](rag-streamlit-line/) | Streamlit document Q&A | LINE |
| [rag-tk-line-broadcast](rag-tk-line-broadcast/) | Local ONNX RAG and Groq | LINE broadcast |
| [rag-reporting-desktop](rag-reporting-desktop/) | Multi-strategy RAG and Groq | LINE, Telegram, Resend |
| [gsheet-reporting-desktop](gsheet-reporting-desktop/) | Google Sheets and pandas | LINE, Telegram, Resend |

## Featured desktop applications

### RAG Reporting Desktop

- PDF/DOCX ingestion, multilingual ONNX embeddings and eight retrieval strategies.
- Groq answer generation, retrieved evidence and chat history.
- Query timestamps and retrieval/generation duration.
- Independent delivery tabs with customizable titles, subjects and introductions.
- Optional question and evidence inclusion; CSV/DOCX email attachments.

Entry point: `python app_tk.py`.

### Google Sheets Reporting Desktop

- Full Google Sheets URL parsing for publicly accessible worksheets.
- Dynamic column selection, keyword filtering and query result table (up to 100 rows).
- Query timestamps, filtering duration and sheet loading duration.
- CSV, Excel, Word and TXT exports from a consistent query snapshot.
- Telegram formatted tables, LINE record lists and Resend email attachments.

Entry point: `python app.py`. No LLM or GPU is required.

## Delivery configuration

| Channel | Required configuration |
| --- | --- |
| LINE | Channel access token; recipient ID for Push, or explicit Broadcast selection |
| Telegram | Bot token and numeric chat ID; start the bot before sending |
| Resend | API key, sender and recipient email; verified sender domain for general delivery |

The reporting applications support previews and confirmation before sending. LINE Push is the default; broadcast targets eligible followers and may consume message quota. Resend's default test sender is restricted to the account owner's address. API acceptance does not guarantee delivery.

## Setup and privacy

Install dependencies separately for each project using its `requirements.txt`. Follow the project README for exact setup instructions. Never commit credentials. RAG sends selected document evidence to Groq; messaging sends selected report content to the chosen provider. Review confidential content before delivery. Live GUI and API delivery of the latest reporting versions still require local testing.

[Back to repository overview](../README.md)
