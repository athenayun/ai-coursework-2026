FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 TOKENIZERS_PARALLELISM=false
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Cache ONNX weights and tokenizer in the image, avoiding runtime download latency.
RUN python - <<'PYBUILD'
from huggingface_hub import hf_hub_download
repo='Xenova/paraphrase-multilingual-MiniLM-L12-v2'
for file in ('tokenizer.json',):
    hf_hub_download(repo,file)
for file in ('onnx/model_quantized.onnx','onnx/model_qint8_avx2.onnx','onnx/model.onnx'):
    try:
        hf_hub_download(repo,file)
        print('Cached',file)
        break
    except Exception as exc:
        print('Unavailable:',file, str(exc)[:120])
else:
    raise RuntimeError('No ONNX weights found')
PYBUILD
COPY app.py rag_engine.py ./
EXPOSE 10000
CMD ["python", "app.py"]
