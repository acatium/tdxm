"""The vocabulary, loaded once. Every generator and projection reads the schema through here."""

from dataclasses import dataclass
from functools import cache
from pathlib import Path

from linkml_runtime.utils.schemaview import SchemaView

ROOT = Path(__file__).resolve().parent.parent
MODEL = ROOT / "model"
CORE = MODEL / "work.yaml"
CUSTOMER = MODEL / "contoso.yaml"
RECORD_CLASS = "ContosoRecord"

SQL_TYPES = {"datetime": "TIMESTAMP", "integer": "BIGINT", "float": "DOUBLE", "boolean": "BOOLEAN"}


@cache
def view(path: Path = CUSTOMER) -> SchemaView:
    return SchemaView(str(path))


def namespace(cls: str, sv: SchemaView | None = None) -> str | None:
    sv = sv or view()
    for c in [cls, *sv.class_ancestors(cls)]:
        ann = sv.get_class(c).annotations.get("namespace")
        if ann:
            return ann.value
    return None


@dataclass(frozen=True)
class Column:
    name: str
    sql_type: str
    slot: str  # the slot path in the vocabulary, e.g. decision.effect
    reference: str | None = None  # the class a column refers to, if any
    enum: str | None = None
    description: str = ""


@dataclass(frozen=True)
class Table:
    name: str
    cls: str
    columns: tuple[Column, ...]

    @property
    def key(self) -> str:
        return "id"


def _columns(sv: SchemaView, cls: str, prefix: str = "") -> list[Column]:
    cols = []
    for s in sv.class_induced_slots(cls):
        rng = s.range or sv.schema.default_range
        name = f"{prefix}{s.name}"
        if rng in sv.all_classes():
            target = sv.get_class(rng)
            has_id = any(x.identifier for x in sv.class_induced_slots(rng))
            if s.inlined and not has_id and not s.multivalued:
                cols += _columns(sv, rng, prefix=f"{name}_")
                continue
            if s.multivalued:
                cols.append(Column(name, "JSON", name.replace("_", ".", 1) if prefix else s.name,
                                   description=s.description or ""))
                continue
            cols.append(Column(name, "VARCHAR", s.name, reference=target.name, description=s.description or ""))
        elif s.multivalued:
            cols.append(Column(name, "VARCHAR[]", s.name, description=s.description or ""))
        elif rng in sv.all_enums():
            cols.append(Column(name, "VARCHAR", s.name, enum=rng, description=s.description or ""))
        else:
            cols.append(Column(name, SQL_TYPES.get(rng, "VARCHAR"), s.name, description=s.description or ""))
    return cols


@cache
def tables() -> tuple[Table, ...]:
    """One table per list in the record container, with inlined value objects flattened."""
    sv = view()
    out = []
    for s in sv.class_induced_slots(RECORD_CLASS):
        if s.multivalued and s.range in sv.all_classes():
            out.append(Table(s.name, s.range, tuple(_columns(sv, s.range))))
    return tuple(out)


def table_for(cls: str) -> Table | None:
    sv = view()
    for t in tables():
        if t.cls == cls or cls in sv.class_ancestors(t.cls) or t.cls in sv.class_ancestors(cls):
            return t
    return None


def metrics() -> list[dict]:
    sv = view()
    out = []
    for name, pv in sv.get_enum("WorkMetric").permissible_values.items():
        out.append({"name": name, "description": pv.description,
                    "expression": pv.annotations["expression"].value, "table": pv.annotations["table"].value})
    return out
