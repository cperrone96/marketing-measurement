.PHONY: test lint typecheck notebooks figures notebook-smoke verify-checksums release-gate ingest api dashboard

PYTHON ?= .venv/bin/python
NOTEBOOK_OUTPUT_DIR ?= .artifacts/notebook-smoke

test:
	$(PYTHON) -m pytest -q

lint:
	$(PYTHON) -m ruff check .

typecheck:
	$(PYTHON) -m mypy src api

# Re-execute both notebooks in place with this environment's kernel, so the committed
# notebooks render on GitHub with outputs, then redraw the README figure.
notebooks:
	PATH="$(abspath $(dir $(PYTHON))):$$PATH" $(PYTHON) -m nbconvert --to notebook --execute --inplace --ExecutePreprocessor.record_timing=False \
		notebooks/01_public_data_findings.ipynb notebooks/02_conversion_model.ipynb

figures:
	$(PYTHON) scripts/make_figures.py

notebook-smoke:
	$(PYTHON) scripts/smoke_notebooks.py --root . --output-dir $(NOTEBOOK_OUTPUT_DIR)

verify-checksums:
	shasum -a 256 -c docs/release-checksums.sha256

release-gate: verify-checksums lint typecheck test notebook-smoke

ingest:
	$(PYTHON) scripts/validate_local_fixture.py

api:
	$(PYTHON) -m uvicorn api.main:app --host 127.0.0.1 --port 8000

dashboard:
	$(PYTHON) -m dashboard.app
