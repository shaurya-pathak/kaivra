.PHONY: install install-voice-local install-pre-commit precommit-test test doctor smoke

install:
	uv sync --extra dev

install-voice-local: install
	uv pip install --python .venv/bin/python -e "./packages/kaivra-voice[local]"

install-pre-commit: install
	.venv/bin/pre-commit install

precommit-test:
	./scripts/run_containerized_tests.sh

test:
	.venv/bin/pytest tests packages/kaivra-voice/tests

doctor:
	.venv/bin/kaivra doctor

smoke:
	.venv/bin/kaivra doctor
	.venv/bin/kaivra quick-render examples/algorithms/bubble_sort.json
