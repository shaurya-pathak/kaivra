.PHONY: install install-voice-local test doctor smoke

install:
	uv sync --extra dev

install-voice-local: install
	.venv/bin/python -m pip install -e "./packages/kaivra-voice[local]"

test:
	.venv/bin/pytest tests packages/kaivra-voice/tests

doctor:
	.venv/bin/kaivra doctor

smoke:
	.venv/bin/kaivra doctor
	.venv/bin/kaivra quick-render examples/algorithms/bubble_sort.json
