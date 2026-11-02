"""OpenTelemetry: the `work.*` attribute registry, generated from the vocabulary, and spans projected from tasks.

The registry is checked by OpenTelemetry's own Weaver (`weaver registry check`), and projected spans by
`weaver registry live-check`.
"""

from shopfloor.vocab import namespace, view

PROJECTED = ["WorkRequest", "TaskRecord", "WorkEvent"]
SKIP_RANGES = {"datetime"}
SKIP_SLOTS = {"prev_hash", "hash"}


def _attr_id(owner_ns: str, slot, sv) -> str:
    rng = slot.range or sv.schema.default_range
    if rng in sv.all_classes():
        target_ns = namespace(rng, sv)
        # A reference whose slot is named for its target is the shared join key, e.g. work.request.id.
        if slot.name == target_ns or slot.name == rng.lower():
            return f"work.{target_ns}.id"
        return f"work.{owner_ns}.{slot.name}.id"
    if slot.identifier:
        return f"work.{owner_ns}.id"
    return f"work.{owner_ns}.{slot.name}"


def _attributes(cls: str, sv, seen: dict) -> None:
    ns = namespace(cls, sv)
    for s in sv.class_induced_slots(cls):
        rng = s.range or sv.schema.default_range
        if rng in SKIP_RANGES or s.name in SKIP_SLOTS or s.multivalued:
            continue
        if rng in sv.all_classes() and s.inlined and not any(x.identifier for x in sv.class_induced_slots(rng)):
            _attributes(rng, sv, seen)
            continue
        aid = _attr_id(ns, s, sv)
        if aid in seen:
            continue
        attr = {"id": aid, "stability": "development",
                "brief": (s.description or f"The {s.name.replace('_', ' ')}.").strip()}
        if rng in sv.all_enums():
            enum = sv.get_enum(rng)
            attr["type"] = {"members": [
                {"id": k, "value": k, "stability": "development",
                 "brief": (v.description or k.replace("_", " ")).strip()}
                for k, v in enum.permissible_values.items()]}
        elif rng == "integer":
            attr["type"] = "int"
        elif rng == "float":
            attr["type"] = "double"
        elif rng == "boolean":
            attr["type"] = "boolean"
        else:
            attr["type"] = "string"
            attr["examples"] = [f"{aid.split('.')[1]}-1" if aid.endswith(".id") else "example"]
        seen[aid] = attr


def registry() -> dict:
    sv = view()
    seen: dict = {}
    for cls in PROJECTED:
        _attributes(cls, sv, seen)
    return {"groups": [{
        "id": "registry.work",
        "type": "attribute_group",
        "display_name": "Work attributes",
        "brief": "Attributes of governed work, generated from the work vocabulary. Do not edit by hand.",
        "attributes": sorted(seen.values(), key=lambda a: a["id"]),
    }]}


def span_attributes(cls: str, obj: dict) -> list[dict]:
    """Project one record object into span attributes, using the same naming rules as the registry."""
    sv = view()
    ns = namespace(cls, sv)
    out = []

    def add(owner_cls, owner_ns, data):
        for s in sv.class_induced_slots(owner_cls):
            rng = s.range or sv.schema.default_range
            if s.name not in data or rng in SKIP_RANGES or s.name in SKIP_SLOTS or s.multivalued:
                continue
            v = data[s.name]
            if rng in sv.all_classes() and isinstance(v, dict):
                add(rng, namespace(rng, sv), v)
                continue
            kind = {"integer": "int", "float": "double", "boolean": "boolean"}.get(rng, "string")
            out.append({"name": _attr_id(owner_ns, s, sv), "type": kind, "value": v})

    add(cls, ns, obj)
    return out


def span(task: dict, name: str | None = None) -> dict:
    """A task as a span sample in Weaver's live-check JSON format."""
    return {"span": {"name": name or f"work {task.get('step', 'task')}", "kind": "internal",
                     "attributes": span_attributes("TaskRecord", task)}}
