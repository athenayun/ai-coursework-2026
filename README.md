# AI Coursework 2026

A collection of hands-on Python coursework and applied AI projects covering computer vision, data applications, desktop interfaces, retrieval-augmented generation (RAG), and external API integrations.

## Project categories

| Category | Focus |
| --- | --- |
| [Computer vision](computer-vision/) | Image processing and object detection |
| [Gradio](gradio/) | Interactive web applications and deployment |
| [Streamlit](streamlit/) | Data exploration and dashboards |
| [Tkinter](tkinter/) | Standalone desktop applications and web scraping |
| [RAG, API & messaging integrations](rag-api-messaging-integrations/) | Document Q&A, structured reporting and multi-channel delivery |

## Featured projects

| Project | Description |
| --- | --- |
| [RAG Reporting Desktop](rag-api-messaging-integrations/rag-reporting-desktop/) | Document Q&A with local ONNX embeddings, eight retrieval strategies, Groq and LINE/Telegram/email delivery |
| [Google Sheets Reporting Desktop](rag-api-messaging-integrations/gsheet-reporting-desktop/) | Spreadsheet queries, table previews, file exports and multi-channel reporting |
| [ESG Render Deployment](gradio/esg-render-deployment/) | ESG data exploration and web deployment |
| [E-commerce Price Comparison](streamlit/ecommerce-price-comparison/) | Interactive product price comparison |
| [Tainan Parking Dashboard](streamlit/tainan_parking_dashboard/) | Parking data visualization |

## Getting started

Each application is independent. Follow its own README and install its dependencies in a dedicated Python environment. For projects providing a requirements file:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Run the entry point specified in the project documentation. Some applications require API credentials or network access.

## Security and scope

Never commit API keys, access tokens, private documents or virtual environments. Review data before sending it to external providers. These are educational implementations and prototypes; live API delivery and deployment behavior should be verified before operational use.
