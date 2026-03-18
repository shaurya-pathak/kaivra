.PHONY: install install-voice-local install-pre-commit format lint precommit-test test doctor smoke

install:
	uv sync --extra dev

install-voice-local: install
	uv pip install --python .venv/bin/python -e "./packages/kaivra-voice[local]"

install-pre-commit: install
	.venv/bin/pre-commit install

format:
	.venv/bin/python scripts/repo_hygiene.py .
	.venv/bin/ruff format .
	.venv/bin/ruff check --fix .

lint:
	.venv/bin/python scripts/repo_hygiene.py --check .
	.venv/bin/ruff format --check .
	.venv/bin/ruff check .

precommit-test:
	./scripts/run_containerized_tests.sh

test:
	.venv/bin/pytest tests packages/kaivra-voice/tests

doctor:
	.venv/bin/kaivra doctor

smoke:
	.venv/bin/kaivra doctor
	.venv/bin/kaivra quick-render examples/algorithms/bubble_sort.json
