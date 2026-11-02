"""Proof point 1a: the acquisitions are joined through the vocabulary, one mapping set each.
Every mapping's subject exists in the vocabulary, and every object exists on the other side."""

import json
from pathlib import Path

import pytest
from oaaclient.templates import CustomApplication, OAAPermission

from shopfloor.mappings import read_metadata, read_sssom
from shopfloor.servicenow import from_env
from shopfloor.vocab import ROOT, view

MAPPINGS = sorted((ROOT / "mappings").glob("*.sssom.tsv"))


def _slot_exists(subject: str) -> bool:
    sv = view()
    prefix, _, local = subject.partition(":")
    cls, _, slot = local.partition(".")
    if cls not in sv.all_classes():
        return False
    return slot in {s.name for s in sv.class_induced_slots(cls)}


@pytest.mark.parametrize("path", MAPPINGS, ids=lambda p: p.stem)
def test_every_subject_is_in_the_vocabulary(path: Path):
    missing = [r["subject_id"] for r in read_sssom(path) if not _slot_exists(r["subject_id"])]
    assert missing == []


def test_subject_check_catches_a_term_not_in_the_vocabulary():
    assert not _slot_exists("work:TaskRecord.no_such_slot")
    assert not _slot_exists("work:NoSuchClass.id")


@pytest.mark.parametrize("path", MAPPINGS, ids=lambda p: p.stem)
def test_every_mapping_set_declares_its_prefixes_and_licence(path: Path):
    meta = read_metadata(path)
    assert meta.get("license") and meta.get("curie_map") and meta.get("mapping_set_id")
    for r in read_sssom(path):
        for curie in (r["subject_id"], r["object_id"], r["predicate_id"]):
            assert curie.split(":", 1)[0] in meta["curie_map"], curie


def test_servicenow_fields_exist_on_the_live_instance():
    sn = from_env()
    rows = read_sssom(ROOT / "mappings" / "servicenow.sssom.tsv") + read_sssom(ROOT / "mappings" / "contoso-servicenow.sssom.tsv")
    missing = []
    for r in rows:
        table, _, field = r["object_id"].removeprefix("snow:").partition(".")
        if sn.field_type(table, field) is None:
            missing.append(r["object_id"])
    assert missing == []


def test_servicenow_check_catches_a_field_that_does_not_exist():
    assert from_env().field_type("sc_req_item", "no_such_field") is None


def _veza_paths() -> set[str]:
    app = CustomApplication("lake", application_type="DataPlatform")
    app.add_custom_permission("read", [OAAPermission.DataRead])
    ds = app.add_resource("loan_book", resource_type="dataset")
    user = app.add_local_user("amaya", identities=["amaya@contoso.example"])
    user.add_permission("read", resources=[ds])
    agent = app.add_agent("Access agent", unique_id="a-access-agent", ai_platform="contoso")
    agent.add_owner("amaya@contoso.example", owner_type="AzureADUser")
    agent.add_permission("read", resources=[ds])
    payload = json.loads(json.dumps(app.get_payload()))
    paths = set()

    def walk(o, prefix):
        if isinstance(o, dict):
            for k, v in o.items():
                p = f"{prefix}.{k}" if prefix else k
                paths.add(p)
                walk(v, p)
        elif isinstance(o, list):
            for v in o:
                walk(v, prefix)

    walk(payload, "")
    return paths


def test_veza_paths_exist_in_a_payload_built_by_vezas_sdk():
    paths = _veza_paths()
    rows = read_sssom(ROOT / "mappings" / "veza.sssom.tsv")
    assert [r["object_id"] for r in rows if r["object_id"].removeprefix("veza:") not in paths] == []


def test_veza_check_catches_a_path_the_sdk_does_not_produce():
    assert "applications.local_agents.no_such_field" not in _veza_paths()


def test_moveworks_plugin_slots_are_vocabulary_slots():
    sv = view()
    slots = {s.name for s in sv.class_induced_slots("ContosoAccessRequest")}
    rows = read_sssom(ROOT / "mappings" / "moveworks.sssom.tsv")
    data = [r["object_id"].removeprefix("moveworks:data.") for r in rows if r["object_id"].startswith("moveworks:data.")]
    assert data and set(data) <= slots


def test_requests_are_read_through_the_mapping():
    """The ServiceNow row becomes a request by the mapping's rows and the vocabulary's ranges, not by code."""
    from shopfloor.ingest import through
    row = {"sys_id": "abc", "number": "RITM1", "opened_at": "2026-01-02 03:04:05", "requested_for": "u1",
           "opened_by": "u1", "cat_item": "item", "u_dataset": "loan_book", "u_privilege": "read",
           "u_cost_centre": "CC-4120", "description": "why"}
    refs = {"Actor": {"u1": "ann.lee"}, "WorkRequest": {}}
    got = through("sc_req_item", row, ("WorkRequest", "AccessRequest", "ContosoAccessRequest"), refs)
    assert got == {"id": "RITM1", "external_ref": "RITM1", "requested_at": "2026-01-02T03:04:05Z",
                   "requested_by": "ann.lee", "on_behalf_of": "ann.lee", "work_definition": "item",
                   "dataset": "loan_book", "privilege": "read", "cost_centre": "CC-4120", "justification": "why"}


def test_a_mapping_row_removed_is_a_slot_not_read():
    from shopfloor.ingest import SN, through
    row, classes = {"u_cost_centre": "CC-4120", "number": "R"}, ("ContosoAccessRequest", "WorkRequest")
    assert through("sc_req_item", row, classes, {})["cost_centre"] == "CC-4120"
    without = [m for m in SN if m["slot"] != "cost_centre"]
    assert "cost_centre" not in through("sc_req_item", row, classes, {}, without)


def test_grants_are_read_through_the_veza_mapping():
    from shopfloor.mappings import crosswalk, flatten
    paths = {m["slot"]: m["path"] for m in crosswalk("veza") if m["cls"] == "Grant"}
    payload = {"identity_to_permissions": [{"identity": "ann", "application_permissions": [
        {"permission": "read", "resources": ["a", "b"]}, {"permission": "admin", "apply_to_application": True}]}]}
    rows = [{s: r.get(p) for s, p in paths.items()} for r in flatten(payload, list(paths.values()))]
    assert {(r["actor"], r.get("dataset"), r["privilege"]) for r in rows} == {
        ("ann", "a", "read"), ("ann", "b", "read"), ("ann", None, "admin")}
