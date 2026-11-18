"""Session-scoped document RAG engine; no user documents written to disk."""
import csv
import io
import re
import threading
import uuid
from dataclasses import dataclass, field
from typing import Any

import chromadb
import numpy as np
from docx import Document
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table
from docx.text.paragraph import Paragraph
from groq import Groq
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer
from sklearn.feature_extraction.text import TfidfVectorizer

EMBED_MODEL = 'intfloat/multilingual-e5-small'
STRATEGIES = ['semantic', 'tfidf', 'hybrid', 'rerank', 'multi_query', 'compress', 'parent_child', 'hyde']
EXCLUDED_MODEL_TERMS = ('whisper', 'orpheus', 'guard', 'tts', 'transcribe', 'safeguard')
DEFAULT_MODELS = ['openai/gpt-oss-20b', 'openai/gpt-oss-120b']


def split_text(text: str, size=500, overlap=100) -> list[str]:
    """Sentence-aware chunking, with hard splits for oversized sentences."""
    if not 0 <= overlap < size:
        raise ValueError('overlap must be smaller than chunk size')
    units = [x.strip() for x in re.split(r'(?<=[。！？!?；;.!?])\s*|\n+', text) if x.strip()]
    pieces = []
    for unit in units:
        while len(unit) > size:
            pieces.append(unit[:size])
            unit = unit[size:]
        if unit:
            pieces.append(unit)
    out, buf = [], ''
    for part in pieces:
        if buf and len(buf) + len(part) + 1 > size:
            out.append(buf)
            buf = (buf[-overlap:] + ' ' + part).strip() if overlap else part
            if len(buf) > size:
                buf = buf[-size:]
        else:
            buf = (buf + ' ' + part).strip()
    if buf:
        out.append(buf)
    return out


def extract_document(path: str) -> list[tuple[str, str]]:
    """Return (source label, text), retaining page or document block provenance."""
    if path.lower().endswith('.pdf'):
        reader = PdfReader(path)
        return [(f'PDF page {i}', t) for i, page in enumerate(reader.pages, 1)
                if (t := (page.extract_text() or '').strip())]
    if path.lower().endswith('.docx'):
        doc = Document(path)
        result = []
        for i, block in enumerate(doc.element.body.iterchildren(), 1):
            if isinstance(block, CT_P):
                text = Paragraph(block, doc).text.strip()
            elif isinstance(block, CT_Tbl):
                table = Table(block, doc)
                text = '\n'.join(' | '.join(cell.text.strip() for cell in row.cells)
                                 for row in table.rows)
            else:
                continue
            if text:
                result.append((f'DOCX block {i}', text))
        return result
    raise ValueError('Only PDF and DOCX are supported')


def rrf(rankings: list[list[int]], k: int, constant: int = 60) -> list[int]:
    scores: dict[int, float] = {}
    for ranking in rankings:
        for rank, index in enumerate(dict.fromkeys(ranking), 1):
            scores[index] = scores.get(index, 0) + 1 / (constant + rank)
    return sorted(scores, key=lambda i: scores[i], reverse=True)[:k]


def truncate_tokens(text: str, max_tokens: int) -> str:
    """Conservative token estimate, including CJK; avoids hard tokenizer dependency."""
    if max_tokens <= 0:
        return ''
    # Approximation: each CJK character counts as 2, other characters as 1/3 token.
    budget = 0
    for i, ch in enumerate(text):
        budget += 2 if ord(ch) > 0x2E80 else 1 / 3
        if budget > max_tokens:
            return text[:i]
    return text


class RAGSession:
    def __init__(self, embedder: SentenceTransformer):
        self.embedder = embedder
        self.api_key = ''
        self.model = ''
        self.source_name = ''
        self.chunks: list[str] = []
        self.labels: list[str] = []
        self.child_parent: list[int] = []
        self.tfidf = None
        self.tfidf_matrix = None
        self.db = chromadb.EphemeralClient()
        self.parent_collection = self.db.create_collection('p_' + uuid.uuid4().hex, metadata={'hnsw:space': 'cosine'})
        self.child_collection = self.db.create_collection('c_' + uuid.uuid4().hex, metadata={'hnsw:space': 'cosine'})
        self.lock = threading.RLock()

    def client(self):
        if not self.api_key:
            raise ValueError('Enter your Groq API key first.')
        return Groq(api_key=self.api_key)

    def models(self):
        available = self.client().models.list().data
        return sorted(m.id for m in available if not any(term in m.id.lower() for term in EXCLUDED_MODEL_TERMS))

    def llm(self, prompt: str, max_tokens=400, temperature=0.2, system='You are a careful document analysis assistant.') -> str:
        if not self.model:
            raise ValueError('Choose a Groq chat model.')
        result = self.client().chat.completions.create(
            model=self.model,
            messages=[{'role': 'system', 'content': system}, {'role': 'user', 'content': prompt}],
            max_tokens=max_tokens, temperature=temperature,
        )
        return (result.choices[0].message.content or '').strip()

    def enc(self, texts: list[str], query=False):
        prefix = 'query: ' if query else 'passage: '
        return self.embedder.encode([prefix + t for t in texts], normalize_embeddings=True,
                                    show_progress_bar=False).astype('float32').tolist()

    def load(self, path: str, filename: str):
        with self.lock:
            blocks = extract_document(path)
            chunks, labels = [], []
            for label, text in blocks:
                for piece in split_text(text):
                    chunks.append(piece)
                    labels.append(label)
            if not chunks:
                raise ValueError('No extractable text found. Scanned PDFs need OCR.')
            if len(chunks) > 3000:
                raise ValueError('Document too large for this demo (max 3000 chunks).')
            # Create fresh indexes on every upload; no cross-document leakage.
            self.db = chromadb.EphemeralClient()
            self.parent_collection = self.db.create_collection('p_' + uuid.uuid4().hex, metadata={'hnsw:space': 'cosine'})
            self.child_collection = self.db.create_collection('c_' + uuid.uuid4().hex, metadata={'hnsw:space': 'cosine'})
            self.chunks, self.labels = chunks, labels
            self.source_name = filename
            for start in range(0, len(chunks), 100):
                batch = chunks[start:start + 100]
                self.parent_collection.add(ids=[str(i) for i in range(start, start + len(batch))],
                                           documents=batch, embeddings=self.enc(batch))
            children, parents = [], []
            for i, chunk in enumerate(chunks):
                for child in split_text(chunk, 200, 40):
                    children.append(child)
                    parents.append(i)
            self.child_parent = parents
            for start in range(0, len(children), 100):
                batch = children[start:start + 100]
                self.child_collection.add(ids=[str(i) for i in range(start, start + len(batch))],
                                          documents=batch, embeddings=self.enc(batch))
            self.tfidf = TfidfVectorizer(analyzer='char', ngram_range=(2, 4), max_features=10000)
            self.tfidf_matrix = self.tfidf.fit_transform(chunks)
            return f'Loaded {filename}: {len(chunks)} parent chunks, {len(children)} child chunks.'

    def vec(self, q, k=5, child=False):
        col = self.child_collection if child else self.parent_collection
        count = len(self.child_parent) if child else len(self.chunks)
        if not count:
            return []
        result = col.query(query_embeddings=self.enc([q], query=True), n_results=min(k, count))
        return [int(x) for x in result['ids'][0]]

    def kw(self, q, k=5):
        if self.tfidf is None:
            return []
        v = self.tfidf.transform([q])
        scores = (self.tfidf_matrix @ v.T).toarray().ravel()
        return [int(i) for i in np.argsort(-scores)[:k] if scores[i] > 0]

    def retrieve(self, q, strategy, k):
        if strategy not in STRATEGIES:
            raise ValueError('Unknown strategy')
        k = max(1, min(int(k), 10))
        if strategy == 'tfidf':
            ids = self.kw(q, k)
        elif strategy in ('hybrid', 'compress'):
            ids = rrf([self.vec(q, k * 3), self.kw(q, k * 3)], k)
        elif strategy == 'parent_child':
            ids = list(dict.fromkeys(self.child_parent[i] for i in self.vec(q, k * 5, child=True)))[:k]
        elif strategy == 'multi_query':
            variants = self.llm('Rewrite the following question in 3 different ways. One per line, no numbering:\n' + q, max_tokens=160)
            queries = [q] + [x.strip(' -0123456789.') for x in variants.splitlines() if x.strip()][:3]
            ids = rrf([self.vec(x, k * 3) for x in queries], k)
        elif strategy == 'hyde':
            hypo = self.llm('Write a short hypothetical answer for retrieval, not a factual conclusion:\n' + q, max_tokens=200)
            ids = self.vec(hypo or q, k)
        elif strategy == 'rerank':
            candidates = self.vec(q, k * 3)
            descriptions = '\n'.join(f'{i}: {truncate_tokens(self.chunks[i], 130)}' for i in candidates)
            raw = self.llm(f'Question: {q}\nScore each passage relevance 0-10. Return ONLY lines ID:score.\n{descriptions}', max_tokens=180)
            scores = {int(i): float(s) for i, s in re.findall(r'(?m)^\s*(\d+)\s*:\s*(\d+(?:\.\d+)?)', raw)}
            ids = sorted(candidates, key=lambda i: scores.get(i, -1), reverse=True)[:k]
        else:
            ids = self.vec(q, k)
        if strategy == 'compress':
            return [(i, self.llm('Extract only statements relevant to the question. Do not invent facts.\nQuestion: '
                                 + q + '\nPassage:\n' + truncate_tokens(self.chunks[i], 350), max_tokens=180)) for i in ids]
        return [(i, self.chunks[i]) for i in ids]

    def answer(self, question: str, strategy: str, top_k: int, history: list[dict[str, str]]):
        with self.lock:
            if not self.chunks:
                raise ValueError('Upload a PDF or DOCX first.')
            # Include recent user turns to resolve references like "what about that?".
            recent = '\n'.join('User: ' + h['question'] + '\nAssistant: ' + truncate_tokens(h['answer'], 120)
                               for h in history[-2:])
            retrieval_query = (truncate_tokens(recent, 250) + '\n' + question) if recent else question
            hits = self.retrieve(retrieval_query, strategy, top_k)
            # Conservative input budget; configurable via environment if needed.
            blocks, used = [], 0
            for i, passage in hits:
                available = 1800 - used
                if available < 100:
                    break
                block = f'[S{i + 1} | {self.labels[i]}]\n' + truncate_tokens(passage, min(550, available - 40))
                blocks.append(block)
                used += len(block) // 3 + sum(2 for ch in block if ord(ch) > 0x2E80)
            context = '\n\n'.join(blocks)
            prompt = (f'Answer based ONLY on the following document excerpts. If unsupported, say so. '
                      f'Cite sources using [S#] identifiers. Reply in the language of the question.\n'
                      f'Recent dialogue:\n{truncate_tokens(recent, 250)}\n\nSources:\n{context}\n\nQuestion: {question}')
            response = self.llm(prompt, max_tokens=500)
            return response, [{'id': f'S{i+1}', 'location': self.labels[i], 'text': text} for i, text in hits]


def export_csv(records: list[dict]) -> bytes:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['question', 'answer', 'strategy', 'model', 'sources'])
    for r in records:
        writer.writerow([r['question'], r['answer'], r['strategy'], r['model'],
                         '; '.join(s['id'] + ' ' + s['location'] for s in r['sources'])])
    return output.getvalue().encode('utf-8-sig')


def export_docx(records: list[dict]) -> bytes:
    doc = Document()
    doc.add_heading('Document Q&A Session', 0)
    for n, r in enumerate(records, 1):
        doc.add_heading(f'Question {n}', level=1)
        doc.add_paragraph(r['question'])
        doc.add_heading('Answer', level=2)
        doc.add_paragraph(r['answer'])
        doc.add_paragraph(f"Strategy: {r['strategy']} | Model: {r['model']}")
        doc.add_heading('Retrieved sources', level=2)
        for s in r['sources']:
            doc.add_paragraph(f"[{s['id']}] {s['location']}: {s['text']}")
    stream = io.BytesIO()
    doc.save(stream)
    return stream.getvalue()
