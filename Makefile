.PHONY: install run test lint

install:
	python -m pip install --upgrade pip
	pip install -r requirements.txt

run:
	python run.py

test:
	pytest -q

lint:
	ruff check .
	ruff format --check .

