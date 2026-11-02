"""The record store: DuckDB tables derived from the vocabulary. The Ossie model describes these tables."""

import json
from pathlib import Path

import duckdb
import yaml
from linkml.validator import validate

from shopfloor.vocab import CUSTOMER, RECORD_CLASS, ROOT, tables

DEFAULT_DB = ROOT / "var" / "record.duckdb"


def ddl() -> str:
    out = []
    for t in tables():
        cols = ",\n  ".join(f'"{c.name}" {c.sql_type}' + (" PRIMARY KEY" if c.name == "id" else "") for c in t.columns)
        out.append(f'CREATE TABLE IF NOT EXISTS "{t.name}" (\n  {cols}\n);')
    return "\n\n".join(out) + "\n"


def connect(path: Path | str = DEFAULT_DB, fresh: bool = False) -> duckdb.DuckDBPyConnection:
    path = Path(path) if path != ":memory:" else path
    if path != ":memory:":
        path.parent.mkdir(parents=True, exist_ok=True)
        if fresh and path.exists():
            path.unlink()
    con = duckdb.connect(str(path))
    con.execute(ddl())
    return con


def check(record: dict) -> list[str]:
    """Validate a record against the customer's model. Returns the error messages."""
    report = validate(record, str(CUSTOMER), RECORD_CLASS)
    return [r.message for r in report.results if r.severity.name == "ERROR"]


def _row(obj: dict, columns) -> list:
    row = []
    for c in columns:
        parts = c.name.split("_")
        v = obj.get(c.name)
        if v is None and c.name not in obj:
            # flattened inlined value object, e.g. decision_effect -> obj["decision"]["effect"]
            for i in range(1, len(parts)):
                head, tail = "_".join(parts[:i]), "_".join(parts[i:])
                if isinstance(obj.get(head), dict):
                    v = obj[head].get(tail)
                    break
        if c.sql_type == "JSON" and v is not None:
            v = json.dumps(v)
        row.append(v)
    return row


def load(con: duckdb.DuckDBPyConnection, record: dict, validate_first: bool = True) -> dict[str, int]:
    if validate_first:
        errors = check(record)
        if errors:
            raise ValueError("record does not conform:\n" + "\n".join(errors[:20]))
    counts = {}
    for t in tables():
        rows = [_row(o, t.columns) for o in record.get(t.name, [])]
        if rows:
            marks = ", ".join("?" for _ in t.columns)
            names = ", ".join(f'"{c.name}"' for c in t.columns)
            con.executemany(f'INSERT OR REPLACE INTO "{t.name}" ({names}) VALUES ({marks})', rows)
        counts[t.name] = len(rows)
    return counts


def read_yaml(path: Path | str) -> dict:
    return yaml.safe_load(Path(path).read_text())
