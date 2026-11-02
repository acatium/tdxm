"""Compute the vocabulary's metrics over the record, the way any Ossie consumer would: from the generated
semantic model's metric expressions and relationships, not from hand-written SQL."""

import re

import duckdb
import sqlglot

from shopfloor import ossie


def _sql(metric: dict, model: dict, base: str) -> str:
    expr = metric["expression"]["dialects"][0]["expression"]
    used = set(re.findall(r"\b([a-z_]+)\.[a-z_]+", expr)) - {base}
    joins = []
    for t in sorted(used):
        rels = [r for r in model["relationships"] if r["from"] == base and r["to"] == t]
        # Several columns may refer to the same table (actor, on_behalf_of); the one named for it is the join.
        rels.sort(key=lambda r: r["from_columns"][0] != t.rstrip("s"))
        if rels:
            joins.append((t, rels[0]["from_columns"][0], rels[0]["to_columns"][0]))
    used -= {j[0] for j in joins}
    if used:
        raise ValueError(f"metric {metric['name']}: no relationship from {base} to {sorted(used)}")
    sql = f"SELECT {expr} FROM {base}" + "".join(
        f" LEFT JOIN {t} ON {base}.{fc} = {t}.{tc}" for t, fc, tc in joins)
    return sqlglot.transpile(sql, read=None, write="duckdb")[0]


def compute(con: duckdb.DuckDBPyConnection) -> dict[str, float | None]:
    from shopfloor.vocab import metrics as defs
    model = ossie.semantic_model()
    tables = {d["name"]: d["table"] for d in defs()}
    out = {}
    for m in model["metrics"]:
        out[m["name"]] = con.execute(_sql(m, model, tables[m["name"]])).fetchone()[0]
    return out
