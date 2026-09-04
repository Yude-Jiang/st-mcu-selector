FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/server \
    ST_MCU_DB=/data/cube-finder-db.db \
    ST_MCU_DATA_DIR=/data \
    ST_MCU_AUTO_UPDATE=if_missing \
    HOST=0.0.0.0

WORKDIR /app

COPY server/requirements.txt /app/server/requirements.txt
RUN pip install --no-cache-dir -r /app/server/requirements.txt

COPY server /app/server
COPY web /app/web

RUN mkdir -p /data
EXPOSE 8080

CMD ["python", "-m", "bootstrap"]
