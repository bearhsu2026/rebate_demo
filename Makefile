# Mac / Linux 用。Windows 請參考 README 的對應指令。
.PHONY: install dev pipeline test docker-up docker-down

install:
	python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt

dev:
	uvicorn app.main:app --reload

pipeline:
	python -m app.cli ingest 2330 --start 2024-01-01

test:
	pytest -q

docker-up:
	docker compose up -d --build

docker-down:
	docker compose down
