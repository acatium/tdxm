"""The agent's cached answers are kept with the prompt that produced them, and used only while that prompt is
the prompt the vocabulary would produce today."""

import json

from shopfloor import classify


def _estate_with(items):
    class E:
        pass
    e = E()
    e.items, e.fields = items, []
    e.customer_rules = lambda: []
    return e


def test_a_cached_answer_is_reused_only_for_the_vocabulary_that_produced_it(tmp_path, monkeypatch):
    monkeypatch.setattr(classify, "CACHE", tmp_path / "classifications.json")
    calls = []

    def ask(prompt, schema):
        calls.append(prompt)
        return {"model": "test", "cost_usd": 0.0, "answer": {"items": [
            {"id": "i1", "meaning": "defines_the_work", "proposed_plan": "retire", "target_term": None,
             "translation": None, "effect_table": None, "effect_query": None, "reason": "x"}]}}
    monkeypatch.setattr(classify.agent, "ask", ask)
    estate = _estate_with([{"sys_id": "i1", "name": "Old item", "short_description": "Old item"}])
    classify.classify(estate)
    classify.classify(estate)
    assert len(calls) == 1, "the second run reuses the cached answer"
    cached = json.loads(classify.CACHE.read_text())
    cached["runs"][0]["prompt"] = cached["runs"][0]["prompt"].replace("Slots:", "Fields:", 1)  # an older vocabulary
    classify.CACHE.write_text(json.dumps(cached))
    classify.classify(estate)
    assert len(calls) == 2, "an answer to a prompt the vocabulary no longer produces is asked again"
