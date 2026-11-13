FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    FASTEMBED_CACHE_PATH=/app/.fastembed_cache

WORKDIR /app

COPY . .
RUN pip install -e "."

# Bake the reranker model into the image so the first request doesn't download it
RUN python -c "from fastembed.rerank.cross_encoder import TextCrossEncoder; TextCrossEncoder(model_name='Xenova/ms-marco-MiniLM-L-6-v2', cache_dir='/app/.fastembed_cache')"

CMD ["sh", "-c", "uvicorn rag.api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]