.PHONY: help migrations migrate

help:
	@echo "Comandos disponíveis:"
	@echo "  make migrations    # Gera uma nova migration Alembic"
	@echo "  make migrate       # Aplica todas as migrations pendentes"

migrations:
	poetry run alembic revision --autogenerate -m "$(msg)"

migrate:
	poetry run alembic upgrade head