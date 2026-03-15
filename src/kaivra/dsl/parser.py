"""Parse and validate DSL files (JSON or YAML) into DocumentSpec."""

import json
from pathlib import Path

import yaml
from pydantic import ValidationError

from kaivra.dsl.schema import DocumentSpec


def parse_file(path: str | Path) -> DocumentSpec:
    """Load a JSON or YAML file and return a validated DocumentSpec."""
    path = Path(path)
    text = path.read_text(encoding="utf-8")

    if path.suffix in (".yaml", ".yml"):
        raw = yaml.safe_load(text)
    elif path.suffix == ".json":
        raw = json.loads(text)
    else:
        # Try JSON first, then YAML
        try:
            raw = json.loads(text)
        except json.JSONDecodeError:
            raw = yaml.safe_load(text)

    if not isinstance(raw, dict):
        raise ValueError(f"Expected a JSON/YAML object at top level, got {type(raw).__name__}")

    return _validate(raw, source=str(path))


def parse_string(text: str, *, format: str = "json") -> DocumentSpec:
    """Parse a DSL string and return a validated DocumentSpec."""
    if format == "json":
        raw = json.loads(text)
    elif format in ("yaml", "yml"):
        raw = yaml.safe_load(text)
    else:
        raise ValueError(f"Unknown format: {format!r}")

    return _validate(raw, source="<string>")


def _validate(raw: dict, source: str) -> DocumentSpec:
    """Validate raw dict against the schema, with LLM-friendly errors."""
    try:
        doc = DocumentSpec.model_validate(raw)
    except ValidationError as e:
        raise _format_validation_error(e, source) from e

    _assign_auto_ids(doc)
    return doc


def _assign_auto_ids(doc: DocumentSpec) -> None:
    """Auto-generate IDs for objects and scenes that don't have explicit ones."""
    for i, scene in enumerate(doc.scenes):
        if scene.id is None:
            scene.id = f"scene_{i}"

        _assign_object_ids(scene.objects, prefix=scene.id)


def _assign_object_ids(objects: list, prefix: str) -> None:
    """Recursively assign IDs to objects missing them."""
    for j, obj in enumerate(objects):
        if obj.id is None:
            obj.id = f"{prefix}_obj_{j}"
        if obj.children:
            _assign_object_ids(obj.children, prefix=obj.id)


def _format_validation_error(e: ValidationError, source: str) -> ValueError:
    """Format Pydantic errors into clear, actionable messages for LLMs."""
    lines = [f"Validation failed for {source}:"]
    for err in e.errors():
        loc = " -> ".join(str(x) for x in err["loc"])
        msg = err["msg"]
        lines.append(f"  [{loc}] {msg}")
        if err.get("ctx"):
            lines.append(f"    context: {err['ctx']}")
    return ValueError("\n".join(lines))
