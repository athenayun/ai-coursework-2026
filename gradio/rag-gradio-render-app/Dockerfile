FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HF_HOME=/app/.cache/huggingface PORT=7860
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py rag_engine.py ./
RUN useradd -m -u 10001 appuser && mkdir -p /app/.cache/huggingface && chown -R appuser:appuser /app
USER appuser
EXPOSE 7860
CMD ["python", "app.py"]
