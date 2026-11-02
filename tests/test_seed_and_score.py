"""The aged instance's world, its fixtures and the scorer, without the instance."""

import copy
import json

import yaml

from shopfloor import score
from shopfloor.seed import fixtures
from shopfloor.seed.world import build
from shopfloor.vocab import ROOT


def test_the_world_is_deterministic():
    a, b = build(), build()
    assert a.truth == b.truth
    assert [r["sys_id"] for r in a.requests] == [r["sys_id"] for r in b.requests]


def test_committed_fixtures_and_answer_key_are_current(tmp_path, monkeypatch):
    monkeypatch.setattr(fixtures, "OUT", tmp_path / "fixtures")
    monkeypatch.setattr(fixtures, "ROOT", tmp_path)
    (tmp_path / "data").mkdir()
    fixtures.write()
    for p in (tmp_path / "fixtures").rglob("*.json"):
        committed = ROOT / "data" / "fixtures" / p.relative_to(tmp_path / "fixtures")
        assert committed.read_text() == p.read_text(), committed
    assert (ROOT / "data" / "truth.yaml").read_text() == (tmp_path / "data" / "truth.yaml").read_text()


def test_every_simulated_fixture_says_so():
    for p in (ROOT / "data" / "fixtures").rglob("*.json"):
        assert json.loads(p.read_text())["_label"]["simulated"] is True, p


def test_every_planted_customisation_cites_why_it_is_an_anti_pattern():
    for c in build().customisations:
        assert c["truth"]["cite"].startswith("ServiceNow,"), c["name"]


def test_the_trap_acts_but_not_in_the_last_180_days():
    w = build()
    trap = [c for c in w.customisations if c["truth"].get("trap")]
    assert len(trap) == 1 and trap[0]["truth"]["dead_by_usage"] and trap[0]["truth"]["plan"] == "declare"
    year_end = [a for a in w.approvals if a["why"] == "controller"]
    assert year_end and max(a["sys_created_on"] for a in year_end) < "2026-05-03"


TRUTH = yaml.safe_load((ROOT / "data" / "truth.yaml").read_text())
PERFECT = [{"gap_kind": g["kind"], "subject": g["subject"]} for g in TRUTH["gaps"]]


def test_a_perfect_diagnosis_scores_one():
    assert all(s["precision"] == 1.0 and s["recall"] == 1.0 for s in score.score(PERFECT, TRUTH).values())


def test_the_score_drops_when_a_planted_problem_is_removed_from_the_answer_key():
    truth = copy.deepcopy(TRUTH)
    removed = next(g for g in truth["gaps"] if g["kind"] == "drift")
    truth["gaps"].remove(removed)
    assert score.score(PERFECT, truth)["drift"]["precision"] < 1.0


def test_the_score_drops_when_a_gap_is_missed():
    missed = [g for g in PERFECT if g["gap_kind"] != "unregistered_actor"]
    assert score.score(missed, TRUTH)["unregistered_actor"]["recall"] == 0.0
