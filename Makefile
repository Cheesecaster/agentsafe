.PHONY: test install install-dev clean

test:
	python -m pytest tests/ -v --tb=short

install:
	pip install -e ".[dev,mcp,api]"

install-dev:
	pip install -e ".[dev]"

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache build dist *.egg-info
