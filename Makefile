.PHONY: help build up down logs restart test-daily test-weekly status

help:
	@echo "k8s-news-bot — управление"
	@echo ""
	@echo "  make build        — сборка Docker образа news-bot"
	@echo "  make up           — запустить все сервисы"
	@echo "  make down         — остановить"
	@echo "  make logs         — показать логи (Ctrl+C для выхода)"
	@echo "  make restart      — пересобрать и перезапустить news-bot"
	@echo "  make test-daily   — запустить daily digest прямо сейчас"
	@echo "  make test-weekly  — запустить weekly report прямо сейчас"
	@echo "  make status       — статус контейнеров"

build:
	docker compose build news-bot

up:
	docker compose up -d
	@echo "Запущено. Логи: make logs"

down:
	docker compose down

logs:
	docker compose logs -f

restart:
	docker compose build news-bot
	docker compose up -d --force-recreate news-bot

test-daily:
	docker compose run --rm -e RUN_DAILY_NOW=1 news-bot

test-weekly:
	docker compose run --rm -e RUN_WEEKLY_NOW=1 news-bot

status:
	docker compose ps
	@echo ""
	@echo "=== Health ==="
	docker inspect k8s-news-bot-gptr-1 --format '{{.State.Health.Status}}' 2>/dev/null || true
