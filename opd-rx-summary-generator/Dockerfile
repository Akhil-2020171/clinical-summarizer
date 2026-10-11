FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /srv

# Install dependencies first so this layer is cached between code changes.
COPY requirements.txt .
RUN pip install -r requirements.txt

# Run as a non-root user.
RUN useradd --create-home --uid 10001 appuser
COPY --chown=appuser:appuser app ./app
USER appuser

# Where the llama.cpp server lives (overridden by docker-compose).
ENV LLAMA_SERVER_URL=http://llama:8080 \
    ENABLE_QWEN_SUMMARIZER=true

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
