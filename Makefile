.PHONY: setup dev migrate check test

# Backend commands
setup:
	cd backend && poetry install

dev:
	cd backend && poetry run python manage.py runserver

migrate:
	cd backend && poetry run python manage.py migrate

check:
	cd backend && poetry run python manage.py check
