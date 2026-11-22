FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    AIMO_DATA_DIR=/app/data \
    AIMO_UPLOAD_DIR=/app/uploads \
    AIMO_HOST=0.0.0.0 \
    AIMO_PORT=5000

RUN groupadd --gid 1000 aimo && \
    useradd --uid 1000 --gid 1000 --create-home --shell /bin/bash aimo && \
    mkdir -p /app/data /app/uploads && \
    chmod 0777 /app/data /app/uploads && \
    chown -R aimo:aimo /app

WORKDIR /app

COPY --chown=aimo:aimo requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --require-hashes -r /app/requirements.txt

COPY --chown=aimo:aimo . /app

USER 1000:1000

VOLUME ["/app/data", "/app/uploads"]

EXPOSE 5000

CMD ["python", "aimo_flask.py"]
