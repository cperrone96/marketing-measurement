.PHONY: test lint typecheck ingest api dashboard

test:
	pytest tests/test_config.py -v

lint:
	ruff check .

typecheck:
	mypy src

ingest:
	@echo "ingest is not available until a later implementation stage." >&2
	@exit 1

api:
	@echo "api is not available until a later implementation stage." >&2
	@exit 1

dashboard:
	@echo "dashboard is not available until a later implementation stage." >&2
	@exit 1
