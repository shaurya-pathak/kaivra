.PHONY: install install-voice-local install-pre-commit format lint precommit-test test doctor smoke

install:
	uv sync --extra dev

install-voice-local: install
	bash scripts/run_in_repo_venv.sh python -m pip install -e "./packages/kaivra-voice[local]"

install-pre-commit: install
	bash scripts/run_in_repo_venv.sh pre-commit install

format:
	bash scripts/run_in_repo_venv.sh python scripts/repo_hygiene.py .
	bash scripts/run_in_repo_venv.sh ruff format .
	bash scripts/run_in_repo_venv.sh ruff check --fix .

lint:
	bash scripts/run_in_repo_venv.sh python scripts/repo_hygiene.py --check .
	bash scripts/run_in_repo_venv.sh ruff format --check .
	bash scripts/run_in_repo_venv.sh ruff check .

precommit-test:
	./scripts/run_containerized_tests.sh

test:
	bash scripts/run_in_repo_venv.sh pytest tests packages/kaivra-voice/tests

doctor:
	bash scripts/run_in_repo_venv.sh kaivra doctor

smoke:
	bash scripts/run_in_repo_venv.sh kaivra doctor
	bash scripts/run_in_repo_venv.sh kaivra quick-render examples/algorithms/bubble_sort.json
