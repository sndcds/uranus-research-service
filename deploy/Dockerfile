# Prepare wheelhouse with: uv run python scripts/build_wheelhouse.py
# All dependency versions/hashes originate from uv.lock. No model weights.
FROM python:3.13.15-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
COPY wheelhouse /wheels
RUN pip install --no-index --require-hashes --find-links=/wheels -r /wheels/requirements.txt \
    && pip install --no-index --no-deps /wheels/uranus_research_service-*.whl \
    && rm -rf /wheels \
    && useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin research
USER 10001:10001
EXPOSE 6338
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:6338/health', timeout=2).read()"]
CMD ["uranus-research-service"]
