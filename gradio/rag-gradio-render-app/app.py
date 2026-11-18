"""Gradio web app for Render. Session tokens keep user state isolated."""
import os
import tempfile
import threading
import time
import uuid
from pathlib import Path

import gradio as gr
from sentence_transformers import SentenceTransformer
from rag_engine import RAGSession, STRATEGIES, export_csv, export_docx

EMBEDDER = SentenceTransformer(os.getenv('EMBED_MODEL', 'intfloat/multilingual-e5-small'), device='cpu')
SESSIONS = {}
LOCK = threading.RLock()
SESSION_TTL = 3600


def get_session(token):
    with LOCK:
        now = time.time()
        for sid, entry in list(SESSIONS.items()):
            if now - entry['last'] > SESSION_TTL:
                del SESSIONS[sid]
        if not token or token not in SESSIONS:
            token = uuid.uuid4().hex
            SESSIONS[token] = {'rag': RAGSession(EMBEDDER), 'last': now, 'records': []}
        SESSIONS[token]['last'] = now
        return token, SESSIONS[token]


def connect(token, key):
    token, entry = get_session(token)
    rag = entry['rag']
    rag.api_key = (key or os.getenv('GROQ_API_KEY', '')).strip()
    try:
        models = rag.models()
        if not models:
            raise ValueError('No compatible models found. Check your Groq account.')
        rag.model = next((m for m in ('openai/gpt-oss-20b', 'openai/gpt-oss-120b') if m in models), models[0])
        return token, gr.update(choices=models, value=rag.model), f'Connected. Selected: {rag.model}'
    except Exception as exc:
        return token, gr.update(choices=[], value=None), f'Connection failed: {exc}'


def load(token, file):
    token, entry = get_session(token)
    if not file:
        return token, 'Choose a PDF or DOCX first.', [], [], ''
    filename = Path(file).name
    if not filename.lower().endswith(('.pdf', '.docx')):
        return token, 'Only PDF/DOCX accepted.', [], [], ''
    if Path(file).stat().st_size > 12 * 1024 * 1024:
        return token, 'Maximum file size: 12 MB.', [], [], ''
    try:
        result = entry['rag'].load(file, filename)
        entry['records'] = []
        return token, result, [], [], ''
    except Exception as exc:
        return token, f'Load failed: {exc}', [], [], ''


def ask(token, question, history, strategy, k, model):
    token, entry = get_session(token)
    history = history or []
    if not (question or '').strip():
        return token, history, '', 'Enter a question.'
    rag = entry['rag']
    if model:
        rag.model = model
    try:
        answer, sources = rag.answer(question, strategy, int(k), entry['records'])
        entry['records'].append({'question': question, 'answer': answer, 'strategy': strategy,
                                 'model': rag.model, 'sources': sources})
        history = history + [{'role': 'user', 'content': question}, {'role': 'assistant', 'content': answer}]
        source_text = '\n\n'.join(f"[{s['id']}] {s['location']}\n{s['text']}" for s in sources)
        return token, history, '', source_text
    except Exception as exc:
        return token, history, question, f'Error: {type(exc).__name__}: {exc}'


def export(token, kind):
    token, entry = get_session(token)
    records = entry['records']
    if not records:
        raise gr.Error('Ask at least one question before exporting.')
    suffix = '.csv' if kind == 'csv' else '.docx'
    data = export_csv(records) if kind == 'csv' else export_docx(records)
    fd, path = tempfile.mkstemp(prefix='rag_export_', suffix=suffix)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(data)
    return path


def clear(token):
    token, entry = get_session(token)
    entry['records'] = []
    return token, [], ''


with gr.Blocks(title='Multi-Strategy Document RAG') as demo:
    token = gr.State(value='')
    gr.Markdown('# Multi-Strategy Document RAG\nPDF/DOCX document Q&A · 8 retrieval strategies · Groq + E5 + ChromaDB')
    with gr.Row():
        with gr.Column(scale=1):
            key = gr.Textbox(label='Groq API key', type='password', placeholder='gsk_...')
            connect_btn = gr.Button('Connect & list models')
            model = gr.Dropdown(choices=[], label='Chat model', interactive=True)
            connection = gr.Textbox(label='Connection', interactive=False)
            upload = gr.File(label='Upload PDF or DOCX', file_types=['.pdf', '.docx'], type='filepath')
            load_btn = gr.Button('Load document')
            status = gr.Textbox(label='Document status', interactive=False)
            strategy = gr.Dropdown(choices=STRATEGIES, value='semantic', label='Retrieval strategy')
            k = gr.Slider(1, 10, value=3, step=1, label='Top-K')
            gr.Markdown('**Privacy:** Documents and API keys stay in server memory during the session. Do not upload sensitive files to a public demo.')
        with gr.Column(scale=2):
            chat = gr.Chatbot(label='Document Q&A', type='messages', height=440)
            question = gr.Textbox(label='Question', placeholder='What does this document say about...?')
            send = gr.Button('Ask', variant='primary')
            with gr.Accordion('Retrieved evidence', open=False):
                evidence = gr.Textbox(lines=10, interactive=False)
            with gr.Row():
                csv_btn = gr.Button('Export CSV')
                docx_btn = gr.Button('Export DOCX')
                clear_btn = gr.Button('Clear conversation')
            download = gr.File(label='Download results')
    connect_btn.click(connect, [token, key], [token, model, connection])
    load_btn.click(load, [token, upload], [token, status, chat, question, evidence])
    send.click(ask, [token, question, chat, strategy, k, model], [token, chat, question, evidence])
    question.submit(ask, [token, question, chat, strategy, k, model], [token, chat, question, evidence])
    csv_btn.click(lambda t: export(t, 'csv'), [token], [download])
    docx_btn.click(lambda t: export(t, 'docx'), [token], [download])
    clear_btn.click(clear, [token], [token, chat, evidence])

if __name__ == '__main__':
    demo.launch(server_name='0.0.0.0', server_port=int(os.getenv('PORT', '7860')), share=False,
                max_file_size='12mb', allowed_paths=[tempfile.gettempdir()])
