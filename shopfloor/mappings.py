"""SSSOM mapping sets: the crosswalks between the vocabulary and every other system's terms."""

import csv
import io
from pathlib import Path

import yaml


def read_sssom(path: Path) -> list[dict]:
    lines = Path(path).read_text().splitlines()
    body = [line for line in lines if not line.startswith("#")]
    return [row for row in csv.DictReader(io.StringIO("\n".join(body)), delimiter="\t")]


def read_metadata(path: Path) -> dict:
    head = [line[2:] if line.startswith("# ") else line[1:] for line in Path(path).read_text().splitlines()
            if line.startswith("#")]
    return yaml.safe_load("\n".join(head)) or {}


MAPPINGS = Path(__file__).resolve().parent.parent / "mappings"


def crosswalk(*names: str) -> list[dict]:
    """The exact matches of one or more mapping sets, as (class, slot, table, field) rows. ServiceNow object ids
    are table.field; payload object ids are dotted paths, with table set to the path's first part."""
    out = []
    for name in names:
        for r in read_sssom(MAPPINGS / f"{name}.sssom.tsv"):
            if r["predicate_id"] != "skos:exactMatch":
                continue
            cls, _, slot = r["subject_id"].split(":", 1)[1].partition(".")
            obj = r["object_id"].split(":", 1)[1]
            table, _, field = obj.partition(".")
            out.append({"cls": cls, "slot": slot, "table": table, "field": field, "path": obj})
    return out


def fields(walk: list[dict], table: str) -> list[str]:
    return sorted({m["field"] for m in walk if m["table"] == table})


def flatten(obj, paths: list[str]) -> list[dict]:
    """Rows from nested JSON: one per combination of list items along the paths, each {path: value}. Paths that
    share a prefix share the walk, so siblings stay together (an identity with each of its permissions)."""
    def walk(node, prefix: str, rest: list[list[str]]) -> list[dict]:
        if isinstance(node, list):
            return [row for item in node for row in walk(item, prefix, rest)]
        heads = {p[0] for p in rest if p}
        if not heads:
            return [{prefix: node}]
        rows = [{}]
        for h in sorted(heads):
            sub = [p[1:] for p in rest if p and p[0] == h]
            value = node.get(h) if isinstance(node, dict) else None
            # Missing: the row carries no value for it. An empty list: nothing to join, so no rows.
            child = [{}] if value is None else walk(value, f"{prefix}.{h}".lstrip("."), sub)
            rows = [a | b for a in rows for b in child]
        return rows
    return walk(obj, "", [p.split(".") for p in paths])
