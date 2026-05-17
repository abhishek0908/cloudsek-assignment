.PHONY: install test test-unit test-integration lint

VENV = ./venv/bin
PYTHON = $(VENV)/python
PIP = $(VENV)/pip

install:
	$(PIP) install -r requirements.txt

test: test-unit test-integration

test-unit:
	$(PYTHON) -m pytest tests/unit/ -v --tb=short

test-integration:
	$(PYTHON) -m pytest tests/integration/ -v --tb=short

test-all:
	$(PYTHON) -m pytest tests/ -v --tb=short

clean:
	rm -rf .pytest_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
