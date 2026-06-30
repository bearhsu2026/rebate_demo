# 給 Synology DS425+（x86 / Intel Celeron J4125）使用的映像。
# pandas/numpy 的官方 wheel 為通用 x86-64，不需 AVX，可在 J4125 正常執行。
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# 資料寫到 /app/data，對應 docker-compose 掛載的 NAS volume
ENV DATA_DIR=/app/data \
    TZ=Asia/Taipei \
    PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
