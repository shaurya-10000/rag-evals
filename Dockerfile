FROM python:3.11-slim

WORKDIR /app

# Install CPU-only Torch FIRST to prevent Render from downloading 2.5GB of Nvidia drivers
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

COPY . .
RUN pip install --no-cache-dir -e "."

EXPOSE 8000
CMD ["uvicorn", "rag.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
