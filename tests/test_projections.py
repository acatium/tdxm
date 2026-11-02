"""Proof point 1, in bold: one LinkML source produces the formats the other standards own, and each is
checked by that community's own tooling. Each check is shown failing once on a broken input."""

import copy

import yaml

from shopfloor import metrics, ocsf, ossie, otel, store, validators
from shopfloor.generate import GEN
from shopfloor.vocab import ROOT

RECORD = store.read_yaml(ROOT / "data" / "examples" / "valid" / "record.yaml")
STOP = {"id": "e-stop", "kind": "stopped", "at": "2026-10-30T09:03:00Z", "request": "req-1", "task": "t-2",
        "actor": "p-soc", "reason": "Destination host is not compliant", "source": "soc"}
STOP_DECISION = {"effect": "deny", "rule": "pol-device-posture", "decided_by": "soc"}


# --- OpenTelemetry, checked by Weaver ---

def test_otel_registry_passes_weaver():
    r = validators.weaver_check(GEN / "otel")
    assert r.returncode == 0, r.stdout + r.stderr


def test_weaver_rejects_a_broken_registry(tmp_path):
    reg = otel.registry()
    reg["groups"][0]["attributes"][0]["type"] = "not_a_type"
    (tmp_path / "work.yaml").write_text(yaml.safe_dump(reg))
    assert validators.weaver_check(tmp_path).returncode != 0


def _violations(advice):
    return [a for a in advice if a["level"] == "violation" or a["id"] == "undefined_enum_variant"]


def test_projected_spans_pass_weaver_live_check():
    advice = validators.weaver_live_check(GEN / "otel", [otel.span(t) for t in RECORD["tasks"]])
    assert advice, "live-check returned nothing; it did not run"
    assert _violations(advice) == []


def test_weaver_live_check_flags_a_bad_span():
    bad = otel.span(RECORD["tasks"][0])
    bad["span"]["attributes"] += [{"name": "work.made_up", "type": "string", "value": "x"},
                                  {"name": "work.task.autonomy_level", "type": "string", "value": "full_auto"}]
    ids = {a["id"] for a in _violations(validators.weaver_live_check(GEN / "otel", [bad]))}
    assert {"missing_attribute", "undefined_enum_variant"} <= ids


# --- OCSF, checked by the OCSF schema server ---

def test_gap_and_stop_pass_ocsf_validation():
    for event in [ocsf.project("Gap", RECORD["gaps"][0]), ocsf.project("WorkEvent", STOP, STOP_DECISION)]:
        result = ocsf.validate(event)
        assert result["error_count"] == 0, result["errors"]


def test_stop_carries_the_join_key_and_the_operators_words():
    event = ocsf.project("WorkEvent", STOP, STOP_DECISION)
    assert event["metadata"]["correlation_uid"] == "req-1"
    assert event["finding_info"]["desc"] == STOP["reason"]
    assert event["compliance"]["control"] == "pol-device-posture"
    assert event["unmapped"]["work.task.id"] == "t-2"


def test_ocsf_validator_rejects_a_broken_event():
    event = copy.deepcopy(ocsf.project("Gap", RECORD["gaps"][0]))
    del event["class_uid"]
    event["severity_id"] = 42
    assert ocsf.validate(event)["error_count"] > 0


# --- Apache Ossie, checked by Ossie's validator ---

def test_ossie_documents_pass_ossie_validation():
    for name, schema in [("work.semantic_model.yaml", None), ("work.ontology.yaml", "ontology/ontology.json"),
                         ("work.mapping.yaml", "ontology/mapping.json")]:
        r = validators.ossie_validate(GEN / "ossie" / name, schema)
        assert r.returncode == 0, r.stdout + r.stderr


def test_ossie_validator_rejects_a_broken_mapping(tmp_path):
    for name in ["work.semantic_model.yaml", "work.ontology.yaml"]:
        (tmp_path / name).write_text((GEN / "ossie" / name).read_text())
    m = ossie.mapping()
    m["concept_mappings"][0]["object_mappings"][0]["referent_mappings"][0]["expression"] = "roles.no_such_field"
    (tmp_path / "work.mapping.yaml").write_text(yaml.safe_dump(m, sort_keys=False))
    assert validators.ossie_validate(tmp_path / "work.mapping.yaml", "ontology/mapping.json").returncode != 0


# --- The metrics an agent reads from the Ossie model compute over the record ---

def test_metrics_compute_from_the_ossie_model():
    con = store.connect(":memory:")
    store.load(con, RECORD)
    m = metrics.compute(con)
    assert m["first_pass_yield"] == 1.0
    assert m["agent_share"] == 0.5
    assert m["orphan_actions"] == 0
