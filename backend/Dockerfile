FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
# Install the CPU torch wheel explicitly so the container does not pull CUDA runtimes.
RUN pip install --no-cache-dir --timeout 180 --retries 8 torch --index-url https://download.pytorch.org/whl/cpu \
 && pip install --no-cache-dir --timeout 180 --retries 8 -r requirements.txt

COPY . .

EXPOSE 8000

# One worker: the SSE hub is in-process. Migrate and seed are idempotent.
CMD ["sh", "-c", "python migrate.py && python seed.py && uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1"]
