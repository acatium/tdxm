"""Agent-assisted reading of each customisation: what it means in the vocabulary's terms, and how to tell
from the record whether it still does anything. The agent proposes; usage from the record and the replay
decide; a person confirms.

The agent is told the vocabulary and shown the customisation. It is not told usage, history or the answer
key. Answers are cached in data/classifications.json with the prompt, so a run is repeatable and auditable.
"""

import json
from pathlib import Path

import yaml

from shopfloor import agent
from shopfloor.ingest import Estate
from shopfloor.vocab import MODEL, ROOT

CACHE = ROOT / "data" / "classifications.json"

SCHEMA = {
    "type": "object",
    "properties": {"items": {"type": "array", "items": {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "meaning": {"type": "string", "enum": [
                "defines_the_work", "business_meaning", "duplicates_platform", "integration_glue", "no_effect",
                "outside_vocabulary"]},
            "proposed_plan": {"type": "string", "enum": ["retire", "revert_to_base", "declare",
                                                         "replace_with_adapter", "keep"]},
            "target_term": {"type": ["string", "null"],
                            "description": "The vocabulary term it becomes, e.g. org:ContosoAccessRequest.cost_centre"},
            "translation": {"type": ["string", "null"],
                            "description": "For declare: the LinkML YAML to add to Contoso's model, or the policy instance"},
            "effect_table": {"type": ["string", "null"]},
            "effect_query": {"type": ["string", "null"],
                             "description": "ServiceNow encoded query matching records that show this rule's effect"},
            "reason": {"type": "string"},
        },
        "required": ["id", "meaning", "proposed_plan", "target_term", "translation", "effect_table", "effect_query",
                     "reason"]}}},
    "required": ["items"],
}

PROMPT = """You are reviewing customisations on a ServiceNow instance at Contoso Capital, a financial firm,
to move them into an open vocabulary for governed work. The vocabulary is LinkML; Contoso's own model extends
it. Here are the classes and slots that matter (core work:, profile access:, customer org:):

{vocabulary}

For each customisation below, decide:
- meaning: what it is, in these terms.
  - defines_the_work: a catalogue item that is a definition of the data-access work.
  - business_meaning: a rule or field that carries Contoso policy the vocabulary can express (declare it).
  - duplicates_platform: re-implements what the platform already does (revert to base).
  - integration_glue: pushes changes to another system; the compiler's adapters do this (replace).
  - no_effect: as written it can never do anything (retire).
  - outside_vocabulary: real Contoso practice the vocabulary cannot express yet (keep, and say what is missing).
- proposed_plan: retire | revert_to_base | declare | replace_with_adapter | keep.
- target_term: the vocabulary term it becomes (null if none).
- translation: for declare, the LinkML YAML or policy instance that expresses it (null otherwise). Be exact
  about conditions: dates, datasets, roles, patterns.
- effect_table and effect_query: for business rules only, a ServiceNow encoded query on the table where the
  rule's effect would be visible in history (e.g. approval rows it creates, field values it sets), matching
  only records this rule would have produced. Use field names exactly as they appear. Null for items and fields.
- reason: one or two sentences.

Do not assume anything about how often a customisation is used; you are not told.

Customisations:
{customisations}
"""


def _vocabulary() -> str:
    parts = []
    for f in ["work.yaml", "access.yaml", "contoso.yaml"]:
        doc = yaml.safe_load((MODEL / f).read_text())
        for name, c in (doc.get("classes") or {}).items():
            slots = c.get("slots", []) + list((c.get("slot_usage") or {}).keys())
            parts.append(f"- {doc['default_prefix']}:{name}"
                         f"{' (is_a ' + c['is_a'] + ')' if c.get('is_a') else ''}: {' '.join(c.get('description', '').split())[:220]}"
                         f" Slots: {', '.join(dict.fromkeys(slots))}.")
        for name, e in (doc.get("enums") or {}).items():
            if name in ("CleanupPlan", "WorkMetric", "GapKind"):
                continue
            parts.append(f"- enum {name}: {', '.join(e.get('permissible_values', {}))}")
    return "\n".join(parts)


def customisations(estate: Estate) -> list[dict]:
    out = []
    for it in estate.items:
        out.append({"id": it["sys_id"], "kind": "catalogue_item", "name": it["name"],
                    "category": "Data Access", "short_description": it.get("short_description")})
    for f in estate.fields:
        out.append({"id": f["sys_id"], "kind": "custom_field", "name": f"sc_req_item.{f['element']}",
                    "label": f["column_label"], "type": f["internal_type"]})
    for r in estate.customer_rules():
        out.append({"id": r["sys_id"], "kind": "business_rule", "name": r["name"], "table": "sc_req_item",
                    "when": r["when"], "insert": r["action_insert"], "update": r["action_update"],
                    "script": r["script"]})
    return out


def _current(run: dict, vocabulary: str) -> bool:
    """A cached run counts only if its prompt is the one today's vocabulary would produce for its items."""
    items = run["prompt"].split("Customisations:\n", 1)[1] if "Customisations:\n" in run["prompt"] else ""
    return run["prompt"] == PROMPT.format(vocabulary=vocabulary, customisations=items.rstrip("\n"))


def classify(estate: Estate, refresh: bool = False) -> dict:
    """Classify every customisation the agent has not seen yet. Cached answers are kept with their prompts and
    reused only while the vocabulary still produces that prompt; an answer to an older vocabulary is asked again."""
    items = customisations(estate)
    vocabulary = _vocabulary()
    cached = json.loads(CACHE.read_text()) if CACHE.exists() and not refresh else {"runs": []}
    cached["runs"] = [r for r in cached["runs"] if _current(r, vocabulary)]
    known = {a["id"]: a for run in cached["runs"] for a in run["answer"]["items"]}
    new = [i for i in items if i["id"] not in known]
    if new:
        prompt = PROMPT.format(vocabulary=vocabulary, customisations=json.dumps(new, indent=1))
        result = agent.ask(prompt, SCHEMA)
        cached["runs"].append({"prompt": prompt, "model": result["model"], "cost_usd": result["cost_usd"],
                               "answer": result["answer"], "status": "proposed, awaiting confirmation by a person"})
        CACHE.write_text(json.dumps(cached, indent=1))
        known |= {a["id"]: a for a in result["answer"]["items"]}
    ids = {i["id"] for i in items}
    return {"answer": {"items": [a for k, a in known.items() if k in ids]},
            "model": cached["runs"][-1]["model"] if cached["runs"] else None,
            "status": "proposed, awaiting confirmation by a person"}
