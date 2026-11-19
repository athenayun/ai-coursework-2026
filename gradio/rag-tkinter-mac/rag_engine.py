"""Low-memory RAG: local quantized ONNX multilingual embeddings, Groq chat."""
import csv, io, math, os, re, threading
from collections import Counter
from docx import Document
from groq import Groq
from pypdf import PdfReader
import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer
from huggingface_hub import hf_hub_download
from functools import lru_cache

STRATEGIES = ['semantic','tfidf','hybrid','rerank','multi_query','compress','parent_child','hyde']
MODEL = 'Xenova/paraphrase-multilingual-MiniLM-L12-v2'

@lru_cache(maxsize=1)
def local_embedder():
    """Load one shared quantized ONNX model for the whole process, on demand."""
    model_file = None
    for candidate in ('onnx/model_quantized.onnx', 'onnx/model_qint8_avx2.onnx', 'onnx/model.onnx'):
        try:
            model_file = hf_hub_download(MODEL, candidate)
            break
        except Exception:
            continue
    if model_file is None:
        raise RuntimeError('Cannot download ONNX model. Check Hugging Face availability.')
    tokenizer_file = hf_hub_download(MODEL, 'tokenizer.json')
    tokenizer = Tokenizer.from_file(tokenizer_file)
    tokenizer.enable_truncation(max_length=256)
    tokenizer.enable_padding(pad_id=0, pad_token='[PAD]')
    options = ort.SessionOptions()
    options.intra_op_num_threads = 1
    options.inter_op_num_threads = 1
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_BASIC
    session = ort.InferenceSession(model_file, sess_options=options, providers=['CPUExecutionProvider'])
    return tokenizer, session

def local_embed(texts):
    tokenizer, session = local_embedder()
    result=[]
    for start in range(0,len(texts),8):
        batch=tokenizer.encode_batch(texts[start:start+8])
        ids=np.asarray([x.ids for x in batch],dtype=np.int64)
        mask=np.asarray([x.attention_mask for x in batch],dtype=np.int64)
        types=np.asarray([x.type_ids for x in batch],dtype=np.int64)
        inputs={}
        for item in session.get_inputs():
            if item.name=='input_ids': inputs[item.name]=ids
            elif item.name=='attention_mask': inputs[item.name]=mask
            elif item.name=='token_type_ids': inputs[item.name]=types
        outputs=session.run(None,inputs)
        hidden=outputs[0]
        if hidden.ndim==2: pooled=hidden
        else:
            weights=mask[:,:,None].astype(np.float32)
            pooled=(hidden*weights).sum(axis=1)/np.maximum(weights.sum(axis=1),1)
        pooled=pooled/np.maximum(np.linalg.norm(pooled,axis=1,keepdims=True),1e-12)
        result.extend(pooled.astype(np.float32).tolist())
    return result


def split_text(text, size=450, overlap=70):
    if not 0 <= overlap < size: raise ValueError('Invalid overlap')
    text = re.sub(r'\s+', ' ', text).strip()
    if not text: return []
    out=[]; start=0
    while start < len(text):
        end=min(len(text),start+size)
        if end < len(text):
            cut=max(text.rfind(x,start+size//2,end) for x in ('。','！','？','.','!','?',';','；'))
            if cut > start+size//2: end=cut+1
        out.append(text[start:end]);
        if end==len(text): break
        start=max(start+1,end-overlap)
    return out

def extract(path):
    if path.lower().endswith('.pdf'):
        r=PdfReader(path)
        return [(f'PDF page {i}',p.extract_text() or '') for i,p in enumerate(r.pages,1)]
    if path.lower().endswith('.docx'):
        d=Document(path)
        return [(f'DOCX paragraph {i}',p.text) for i,p in enumerate(d.paragraphs,1)] + [(f'DOCX table {i}', '\n'.join(' | '.join(c.text for c in row.cells) for row in t.rows)) for i,t in enumerate(d.tables,1)]
    raise ValueError('Only PDF and DOCX supported')

def grams(s):
    s=s.lower(); return [s[i:i+n] for n in (2,3) for i in range(max(0,len(s)-n+1))]

def rrf(rankings,k):
    scores={}
    for ranking in rankings:
        for rank,i in enumerate(dict.fromkeys(ranking),1): scores[i]=scores.get(i,0)+1/(60+rank)
    return sorted(scores,key=lambda i:scores[i],reverse=True)[:k]

def cosine(a,b):
    return sum(x*y for x,y in zip(a,b))/max(1e-12,math.sqrt(sum(x*x for x in a))*math.sqrt(sum(y*y for y in b)))

class RAGSession:
    def __init__(self):
        self.groq_key=''; self.model='openai/gpt-oss-20b'; self.lock=threading.RLock()
        self.chunks=[]; self.labels=[]; self.vectors=[]; self.child_vectors=[]; self.children=[]; self.child_parent=[]; self.keyword=[]; self.idf={}

    def models(self):
        if not self.groq_key: raise ValueError('Enter Groq API key')
        ids=[m.id for m in Groq(api_key=self.groq_key).models.list().data]
        return sorted(m for m in ids if not any(x in m.lower() for x in ('whisper','orpheus','guard','tts','transcribe','safeguard')))

    def llm(self,prompt,max_tokens=350):
        if not self.groq_key: raise ValueError('Groq API key required')
        r=Groq(api_key=self.groq_key).chat.completions.create(model=self.model,messages=[{'role':'system','content':'Answer accurately from supplied document evidence. Never invent sources.'},{'role':'user','content':prompt}],max_tokens=max_tokens,temperature=0.2)
        return (r.choices[0].message.content or '').strip()

    def embed(self,texts,input_type=None):
        return local_embed(texts)

    def load(self,path,filename):
        with self.lock:
            blocks=extract(path); chunks=[]; labels=[]
            for label,text in blocks:
                for part in split_text(text): chunks.append(part); labels.append(label)
            if not chunks: raise ValueError('No selectable text; scanned PDFs need OCR')
            if len(chunks)>120: raise ValueError('Free-tier demo limit: 120 chunks. Upload a shorter document.')
            children=[]; parents=[]
            for i,part in enumerate(chunks):
                for child in split_text(part,180,30): children.append(child); parents.append(i)
            if len(children)>400: raise ValueError('Too many child chunks for free demo')
            # Build all data locally, then atomically replace active document on success.
            vectors=self.embed(chunks,'search_document')
            child_vectors=self.embed(children,'search_document')
            tf=[Counter(grams(x)) for x in chunks]
            df=Counter(g for c in tf for g in c)
            idf={g:math.log((len(chunks)+1)/(n+1))+1 for g,n in df.items()}
            self.chunks,self.labels,self.vectors=chunks,labels,vectors
            self.children,self.child_parent,self.child_vectors=children,parents,child_vectors
            self.keyword,self.idf=tf,idf
            return f'Loaded {filename}: {len(chunks)} parent chunks, {len(children)} child chunks. Local ONNX embedding: {MODEL}.'

    def vec(self,q,k,child=False):
        v=self.embed([q],'search_query')[0]
        source=self.child_vectors if child else self.vectors
        return sorted(range(len(source)),key=lambda i:cosine(v,source[i]),reverse=True)[:k]

    def kw(self,q,k):
        qf=Counter(grams(q)); scores=[]
        for i,doc in enumerate(self.keyword):
            score=sum((1+math.log(doc[g]))*(1+math.log(freq))*self.idf.get(g,0)**2 for g,freq in qf.items() if doc[g])
            if score>0: scores.append((i,score))
        return [i for i,_ in sorted(scores,key=lambda t:t[1],reverse=True)[:k]]

    def retrieve(self,q,strategy,k):
        if strategy not in STRATEGIES: raise ValueError('Unknown strategy')
        k=max(1,min(int(k),6))
        if strategy=='tfidf': ids=self.kw(q,k)
        elif strategy in ('hybrid','compress'): ids=rrf([self.vec(q,k*3),self.kw(q,k*3)],k)
        elif strategy=='parent_child': ids=list(dict.fromkeys(self.child_parent[i] for i in self.vec(q,k*5,True)))[:k]
        elif strategy=='multi_query':
            variants=self.llm('Rewrite as 3 alternative search queries, one per line:\n'+q,160)
            queries=[q]+[x.strip(' -0123456789.') for x in variants.splitlines() if x.strip()][:3]
            ids=rrf([self.vec(x,k*3) for x in queries],k)
        elif strategy=='hyde':
            hypothetical=self.llm('Write a hypothetical short answer ONLY to improve document retrieval:\n'+q,180)
            ids=self.vec(hypothetical or q,k)
        elif strategy=='rerank':
            candidates=self.vec(q,k*3)
            lines='\n'.join(f'{i}: {self.chunks[i][:240]}' for i in candidates)
            response=self.llm(f'Question: {q}\nScore passages 0-10. Return ONLY lines ID:score.\n{lines}',200)
            scores={int(i):float(s) for i,s in re.findall(r'(?m)^\s*(\d+)\s*:\s*(\d+(?:\.\d+)?)',response)}
            ids=sorted(candidates,key=lambda i:scores.get(i,-1),reverse=True)[:k]
        else: ids=self.vec(q,k)
        if strategy=='compress':
            return [(i,self.llm(f'Extract only relevant factual sentences, do not invent. Question: {q}\nPassage: {self.chunks[i][:450]}',150)) for i in ids]
        return [(i,self.chunks[i]) for i in ids]

    def answer(self,question,strategy,k,history):
        with self.lock:
            if not self.chunks: raise ValueError('Upload and index a document first')
            recent='\n'.join('Q: '+r['question'][:180]+' A: '+r['answer'][:220] for r in history[-2:])
            hits=self.retrieve((recent+'\n'+question)[-650:],strategy,k)
            # Limit CJK-heavy context and leave space for completion.
            evidence=[]; remaining=1800
            for i,passage in hits:
                if remaining<100: break
                snippet=passage[:min(450,remaining)]
                evidence.append(f'[S{i+1} | {self.labels[i]}]\n{snippet}')
                remaining-=len(snippet)
            prompt=f'Use ONLY these document sources. Cite source IDs [S#]. If not found, say so. Reply in question language.\nRecent dialogue: {recent[:450]}\nSources:\n'+ '\n\n'.join(evidence)+f'\nQuestion: {question[:500]}'
            response=self.llm(prompt,500)
            return response,[{'id':f'S{i+1}','location':self.labels[i],'text':passage} for i,passage in hits]

def export_csv(records):
    f=io.StringIO(); w=csv.writer(f); w.writerow(['question','answer','strategy','model','sources'])
    for r in records:w.writerow([r['question'],r['answer'],r['strategy'],r['model'],'; '.join(s['id']+' '+s['location'] for s in r['sources'])])
    return f.getvalue().encode('utf-8-sig')

def export_docx(records):
    d=Document(); d.add_heading('RAG Document Q&A',0)
    for n,r in enumerate(records,1):
        d.add_heading(f'Question {n}',1);d.add_paragraph(r['question']);d.add_heading('Answer',2);d.add_paragraph(r['answer']);d.add_paragraph(f"Strategy: {r['strategy']} | Model: {r['model']}")
        for s in r['sources']:d.add_paragraph(f"[{s['id']}] {s['location']}: {s['text']}")
    f=io.BytesIO();d.save(f);return f.getvalue()
