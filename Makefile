.PHONY: build up down logs


build:
	docker compose build --no-cache


up:
	docker compose up --build -d


down:
	docker compose down -v


logs:
	docker compose logs -f
