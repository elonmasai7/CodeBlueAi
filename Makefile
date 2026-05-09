.PHONY: help install dev prod test lint clean logs status

help:
	@echo "Code Blue AI - Make Commands"
	@echo "==========================="
	@echo "  install    - Install dependencies"
	@echo "  dev        - Start development environment"
	@echo "  prod        - Start production environment"
	@echo "  test        - Run all tests"
	@echo "  lint        - Run linting"
	@echo "  clean       - Clean containers and volumes"
	@echo "  logs        - View logs"
	@echo "  status      - Check service status"
	@echo "  seed        - Seed FHIR data"
	@echo "  demo        - Start demo mode"

install:
	@echo "Installing Python dependencies..."
	pip install -r backend/requirements.txt
	@echo "Dependencies installed."

dev:
	@echo "Starting development environment..."
	docker-compose up -d
	@sleep 5
	docker-compose ps

prod:
	@echo "Building and starting production..."
	docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

test:
	@echo "Running tests..."
	pytest tests/ -v --tb=short

lint:
	@echo "Running linting..."
	ruff check backend/ agents/ mcp_server/ a2a_bus/

clean:
	@echo "Cleaning containers and volumes..."
	docker-compose down -v --remove-orphans
	docker system prune -f

logs:
	docker-compose logs -f

status:
	docker-compose ps

seed:
	@echo "Seeding FHIR data..."
	python -m fhir.seed_data

demo:
	@echo "Starting demo mode..."
	docker-compose up -d
	@sleep 10
	curl -X POST http://localhost:8000/api/v1/demo/trigger

init-db:
	@echo "Initializing database..."
	python -m backend.db.init

stop:
	docker-compose down

restart: stop dev

openapi-docs:
	@echo "OpenAPI docs at http://localhost:8000/docs"
