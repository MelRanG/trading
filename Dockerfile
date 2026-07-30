FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app/src
WORKDIR /app
RUN useradd --create-home --uid 10001 quant
COPY requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock
COPY --chown=quant:quant . .
RUN chmod +x scripts/docker_entrypoint.sh
USER quant
EXPOSE 8788
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8788/api/health', timeout=3).read()"
ENTRYPOINT ["./scripts/docker_entrypoint.sh"]
