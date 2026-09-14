.PHONY: test lint typecheck notebook-smoke verify-checksums release-gate api dashboard

PYTHON ?= .venv/bin/python
NOTEBOOK_OUTPUT_DIR ?= .artifacts/notebook-smoke

test:
	$(PYTHON) -m pytest -q

lint:
	$(PYTHON) -m ruff check .

typecheck:
	$(PYTHON) -m mypy src api

notebook-smoke:
	$(PYTHON) scripts/smoke_notebooks.py --root . --output-dir $(NOTEBOOK_OUTPUT_DIR)

verify-checksums:
	shasum -a 256 -c docs/release-checksums.sha256

release-gate: verify-checksums lint typecheck test notebook-smoke

api:
	$(PYTHON) -m uvicorn api.main:app --host 127.0.0.1 --port 8000

dashboard:
	$(PYTHON) -m dashboard.app
