"""Proof point 1: the vocabulary is the source. Each check is paired with a case that shows it failing."""

from pathlib import Path

import pytest

from shopfloor import store
from shopfloor.generate import artefacts, stale, write
from shopfloor.vocab import ROOT

EXAMPLES = ROOT / "data" / "examples"


def test_valid_examples_conform():
    for path in sorted((EXAMPLES / "valid").glob("*.yaml")):
        assert store.check(store.read_yaml(path)) == [], path.name


@pytest.mark.parametrize("path", sorted((EXAMPLES / "invalid").glob("*.yaml")), ids=lambda p: p.stem)
def test_invalid_examples_fail(path: Path):
    assert store.check(store.read_yaml(path)), f"{path.name} should not conform"


def test_task_without_request_is_rejected_with_the_reason():
    errors = store.check(store.read_yaml(EXAMPLES / "invalid" / "task-without-request.yaml"))
    assert any("'request' is a required property" in e for e in errors)


def test_generated_artefacts_are_current():
    assert stale() == [], "regenerate: python -m shopfloor.generate"


def test_currency_check_notices_a_hand_edit(tmp_path):
    write(tmp_path)
    (tmp_path / "otel" / "work.yaml").write_text((tmp_path / "otel" / "work.yaml").read_text() + "# hand edit\n")
    assert stale(tmp_path) == ["otel/work.yaml"]


def test_one_source_many_formats():
    out = artefacts()
    for expected in ["otel/work.yaml", "ossie/work.semantic_model.yaml", "ossie/work.ontology.yaml",
                     "ossie/work.mapping.yaml", "jsonschema/contoso.schema.json", "owl/work.owl.ttl",
                     "pydantic/contoso.py", "sql/record.sql"]:
        assert out[expected].strip(), expected
