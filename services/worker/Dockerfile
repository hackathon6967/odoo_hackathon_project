FROM python:3.11-slim

# Install WeasyPrint system deps + xlsxwriter deps (libxslt, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 libcairo2 libgdk-pixbuf-2.0-0 libffi8 \
    shared-mime-info fonts-liberation && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /worker
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Mount api app code for model imports
ENV PYTHONPATH=/api_app

COPY worker.py runner.py ./
CMD ["python", "runner.py"]
