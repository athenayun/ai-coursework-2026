"""Offline retrieval evaluation on labeled queries; no Groq key required for basic strategies.

Input JSON example:
[
  {"query": "What is the policy?", "relevant_chunk_ids": [0, 2]},
  {"query": "Who approved it?", "relevant_chunk_ids": [4]}
]

Run: python evaluate.py path/to/document.pdf path/to/labels.json
"""
import json
import sys
import time
from pathlib import Path
from sentence_transformers import SentenceTransformer
from rag_engine import EMBED_MODEL, RAGSession


def evaluate(rag, labels, strategy, k=3):
    recall, reciprocal_rank, elapsed = [], [], []
    for example in labels:
        gold = set(example['relevant_chunk_ids'])
        if not gold:
            continue
        t0 = time.perf_counter()
        hits = [i for i, _ in rag.retrieve(example['query'], strategy, k)]
        elapsed.append(time.perf_counter() - t0)
        recall.append(len(gold.intersection(hits)) / len(gold))
        reciprocal_rank.append(next((1 / rank for rank, i in enumerate(hits, 1) if i in gold), 0))
    if not recall:
        raise ValueError('No labeled queries with relevant_chunk_ids')
    return {'strategy': strategy, 'recall_at_k': sum(recall) / len(recall),
            'mrr_at_k': sum(reciprocal_rank) / len(reciprocal_rank),
            'mean_latency_seconds': sum(elapsed) / len(elapsed)}


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit('Usage: python evaluate.py document.pdf labels.json')
    rag = RAGSession(SentenceTransformer(EMBED_MODEL, device='cpu'))
    rag.load(sys.argv[1], Path(sys.argv[1]).name)
    labels = json.loads(Path(sys.argv[2]).read_text(encoding='utf-8'))
    for strategy in ['semantic', 'tfidf', 'hybrid', 'parent_child']:
        print(json.dumps(evaluate(rag, labels, strategy), indent=2))
