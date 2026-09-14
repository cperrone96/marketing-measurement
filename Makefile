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
	mkdir -p $(NOTEBOOK_OUTPUT_DIR)
	PATH="$(CURDIR)/.venv/bin:$$PATH" $(PYTHON) -m nbconvert --to notebook --execute --output-dir $(NOTEBOOK_OUTPUT_DIR) notebooks/01_public_data_findings.ipynb
	PATH="$(CURDIR)/.venv/bin:$$PATH" $(PYTHON) -m nbconvert --to notebook --execute --output-dir $(NOTEBOOK_OUTPUT_DIR) notebooks/02_conversion_model.ipynb

verify-checksums:
	shasum -a 256 -c docs/release-checksums.sha256

release-gate: lint typecheck test notebook-smoke verify-checksums

api:
	$(PYTHON) -m uvicorn api.main:app --host 127.0.0.1 --port 8000

dashboard:
	$(PYTHON) -m dashboard.app
