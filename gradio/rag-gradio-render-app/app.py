"""Render Free RAG: local ONNX embeddings, no torch / transformers / chromadb."""
import os, tempfile, threading, time, uuid
from pathlib import Path
import gradio as gr
from rag_engine import RAGSession, STRATEGIES, export_csv, export_docx

SESSIONS={}; LOCK=threading.RLock(); TTL=1800

def session(token):
    with LOCK:
        now=time.time()
        for sid,v in list(SESSIONS.items()):
            if now-v['last']>TTL: del SESSIONS[sid]
        if not token or token not in SESSIONS:
            token=uuid.uuid4().hex
            SESSIONS[token]={'rag':RAGSession(),'records':[],'last':now}
        SESSIONS[token]['last']=now
        return token,SESSIONS[token]

def connect(token,groq_key):
    token,e=session(token);r=e['rag']
    r.groq_key=(groq_key or os.getenv('GROQ_API_KEY','')).strip()
    try:
        models=r.models()
        if not models: raise ValueError('No chat models returned by Groq')
        r.model=next((x for x in ('openai/gpt-oss-20b','openai/gpt-oss-120b') if x in models),models[0])
        return token,gr.update(choices=models,value=r.model),f'Connected. Chat model: {r.model}; embeddings: local ONNX.'
    except Exception as ex:return token,gr.update(choices=[],value=None),f'Connection failed: {ex}'

def load(token,file):
    token,e=session(token)
    if not file:return token,'Select PDF/DOCX first',[],''
    path=Path(file)
    if path.suffix.lower() not in ('.pdf','.docx'):return token,'PDF/DOCX only',[],''
    if path.stat().st_size>3*1024*1024:return token,'Demo file limit: 3 MB',[],''
    try:
        msg=e['rag'].load(str(path),path.name);e['records']=[]
        return token,msg,[],''
    except Exception as ex:return token,f'Indexing failed: {type(ex).__name__}: {ex}',[],''

def ask(token,question,chat,strategy,k,model):
    token,e=session(token);chat=chat or []
    if not question.strip():return token,chat,question,'Enter a question'
    try:
        if model:e['rag'].model=model
        answer,sources=e['rag'].answer(question,strategy,k,e['records'])
        e['records'].append(dict(question=question,answer=answer,strategy=strategy,model=e['rag'].model,sources=sources))
        chat=chat+[{'role':'user','content':question},{'role':'assistant','content':answer}]
        return token,chat,'','\n\n'.join(f"[{s['id']}] {s['location']}\n{s['text']}" for s in sources)
    except Exception as ex:return token,chat,question,f'Error: {type(ex).__name__}: {ex}'

def download(token,fmt):
    _,e=session(token)
    if not e['records']:raise gr.Error('Ask a question first')
    data=export_csv(e['records']) if fmt=='csv' else export_docx(e['records'])
    fd,path=tempfile.mkstemp(prefix='rag_export_',suffix='.'+fmt)
    with os.fdopen(fd,'wb') as f:f.write(data)
    return path

def clear(token):
    token,e=session(token);e['records']=[];return token,[],''

with gr.Blocks(title='Multi-Strategy RAG — Render Free') as demo:
    token=gr.State('')
    gr.Markdown('# Multi-Strategy Document RAG\n**Render Free edition** · Local ONNX embeddings · Groq LLM · Eight retrieval strategies · PDF/DOCX · CSV/DOCX export')
    with gr.Row():
        with gr.Column(scale=1):
            groq=gr.Textbox(label='Groq API key',type='password',placeholder='gsk_...')
            connect_btn=gr.Button('Connect & list chat models')
            model=gr.Dropdown(choices=[],label='Groq chat model')
            connection=gr.Textbox(label='Connection',interactive=False)
            upload=gr.File(label='Upload PDF/DOCX (max 3 MB)',file_types=['.pdf','.docx'],type='filepath')
            load_btn=gr.Button('Index document')
            status=gr.Textbox(label='Document status',interactive=False)
            strategy=gr.Dropdown(choices=STRATEGIES,value='semantic',label='Retrieval strategy')
            k=gr.Slider(1,6,value=3,step=1,label='Top-K')
            gr.Markdown('**Privacy:** API keys and document content are held in server memory for a temporary session. Do not upload confidential files to an unauthenticated public demo. Document embeddings are generated locally; Groq receives retrieved excerpts for answering.')
        with gr.Column(scale=2):
            chat=gr.Chatbot(type='messages',label='Document Q&A',height=440)
            question=gr.Textbox(label='Question')
            send=gr.Button('Ask',variant='primary')
            with gr.Accordion('Retrieved evidence',open=False):evidence=gr.Textbox(lines=8,interactive=False)
            with gr.Row():
                csv_btn=gr.Button('Export CSV');docx_btn=gr.Button('Export DOCX');clear_btn=gr.Button('Clear chat')
            exported=gr.File(label='Download')
    connect_btn.click(connect,[token,groq],[token,model,connection])
    load_btn.click(load,[token,upload],[token,status,chat,evidence])
    send.click(ask,[token,question,chat,strategy,k,model],[token,chat,question,evidence])
    question.submit(ask,[token,question,chat,strategy,k,model],[token,chat,question,evidence])
    csv_btn.click(lambda t:download(t,'csv'),[token],[exported]);docx_btn.click(lambda t:download(t,'docx'),[token],[exported])
    clear_btn.click(clear,[token],[token,chat,evidence])

if __name__=='__main__':
    demo.queue(default_concurrency_limit=1).launch(server_name='0.0.0.0',server_port=int(os.getenv('PORT','7860')),share=False,max_file_size='3mb',allowed_paths=[tempfile.gettempdir()])
