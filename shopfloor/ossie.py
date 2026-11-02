"""Apache Ossie: the ontology, the semantic model over the record's tables, and the mapping between them,
all generated from the vocabulary.

Checked by Ossie's own validator (`validation/validate.py` in apache/ossie, pinned).
"""

from shopfloor.vocab import Table, metrics, tables, view

VERSION = "0.2.0.dev0"
CATALOG = "record.main"
DATATYPES = {"TIMESTAMP": "DateTimeTz", "BIGINT": "Integer", "DOUBLE": "Float", "BOOLEAN": "Boolean",
             "VARCHAR": "String", "JSON": "Opaque", "VARCHAR[]": "Opaque"}
BUILTIN = {"string": "String", "integer": "Integer", "float": "Float", "boolean": "Boolean",
           "datetime": "DateTime", "date": "Date"}
NAME = "Work record"
ONTOLOGY = "Work"


def _concept(cls: str) -> str:
    return cls


def _table_of(cls: str) -> Table | None:
    sv = view()
    for t in tables():
        if t.cls == cls or cls in sv.class_ancestors(t.cls):
            return t
    return None


def semantic_model() -> dict:
    sv = view()
    datasets, relationships = [], []
    for t in tables():
        c = sv.get_class(t.cls)
        fields = []
        for col in t.columns:
            f = {"name": col.name,
                 "expression": {"dialects": [{"dialect": "ANSI_SQL", "expression": col.name}]},
                 "datatype": DATATYPES[col.sql_type]}
            if col.description:
                f["description"] = col.description
            if col.enum:
                f["ai_context"] = {"synonyms": [], "instructions":
                                   "One of: " + ", ".join(sv.get_enum(col.enum).permissible_values)}
                f["ai_context"].pop("synonyms")
            fields.append(f)
            if col.reference:
                target = _table_of(col.reference)
                if target:
                    relationships.append({"name": f"{t.name}_{col.name}", "from": t.name, "to": target.name,
                                          "from_columns": [col.name], "to_columns": ["id"]})
        datasets.append({"name": t.name, "source": f"{CATALOG}.{t.name}", "primary_key": ["id"],
                         "description": " ".join((c.description or "").split()),
                         "ai_context": {"instructions": f"Rows are {t.cls} records of the work vocabulary."},
                         "fields": fields})
    return {
        "version": VERSION, "name": NAME,
        "description": "The record of governed work, generated from the work vocabulary. Do not edit by hand.",
        "ai_context": {"instructions": (
            "Every table joins on request (the work request id). Autonomy levels are a closed ladder: "
            "assist, act_with_checkpoint, act, act_and_report. A promotion compares lower_bound, never a raw rate.")},
        "datasets": datasets,
        "relationships": relationships,
        "metrics": [{"name": m["name"], "description": m["description"], "datatype": "Decimal",
                     "expression": {"dialects": [{"dialect": "ANSI_SQL", "expression": m["expression"]}]}}
                    for m in metrics()],
    }


def ontology() -> dict:
    sv = view()
    components = []
    for e in sorted(sv.all_enums()):
        if e == "WorkMetric":
            continue
        enum = sv.get_enum(e)
        values = list(enum.permissible_values)
        components.append({"concept": e, "type": "ValueType", "extends": ["String"],
                           "description": " ".join((enum.description or f"One of {', '.join(values)}.").split()),
                           "requires": [" OR ".join(f"{e} == '{v}'" for v in values)]})
    for t in tables():
        for cls in [t.cls, *[a for a in sv.class_ancestors(t.cls) if a != t.cls]]:
            if any(c["concept"] == cls for c in components):
                continue
            c = sv.get_class(cls)
            comp = {"concept": cls, "type": "EntityType",
                    "description": " ".join((c.description or "").split())}
            if c.is_a:
                comp["extends"] = [c.is_a]
            own = [s for s in sv.class_induced_slots(cls)
                   if not c.is_a or s.name not in {x.name for x in sv.class_induced_slots(c.is_a)}]
            if not c.is_a:
                comp["identify_by"] = ["id"]
            rels = []
            for s in own:
                rng = s.range or sv.schema.default_range
                if s.multivalued or (rng in sv.all_classes() and not _table_of(rng)):
                    continue
                target = BUILTIN.get(rng, rng)
                rel = {"name": s.name, "roles": [{"concept": target}],
                       "multiplicity": "OneToOne" if s.identifier else "ManyToOne",
                       "verbalizes": [f"{{{cls}}} has {s.name.replace('_', ' ')}- {{{target}}}"
                                      if not s.identifier else f"{{{cls}}} is identified by {{{target}}}"]}
                rels.append(rel)
            if rels:
                comp["relationships"] = rels
            components.append(comp)
    return {"version": VERSION, "name": ONTOLOGY,
            "description": "Concepts of the work vocabulary, generated from LinkML. Do not edit by hand.",
            "prefixes": {"work": "https://example.org/work/", "access": "https://example.org/work/access/",
                         "org": "https://example.org/contoso/"},
            "ontology": components}


def mapping(ontology_iri: str = "./work.ontology.yaml", model_iri: str = "./work.semantic_model.yaml") -> dict:
    """Maps each concept onto its dataset: identity by id, other relationships by their column."""
    sv = view()
    onto = {c["concept"]: c for c in ontology()["ontology"]}
    concept_mappings = []
    for t in tables():
        cls = t.cls
        cols = {c.name for c in t.columns}
        ident = {"referent_mappings": [{"relationship": "id", "expression": f"{t.name}.id"}]}
        chain = [cls, *[a for a in sv.class_ancestors(cls) if a != cls]]
        children = []
        for concept in chain:
            for rel in onto.get(concept, {}).get("relationships", []):
                if rel["name"] == "id" or rel["name"] not in cols:
                    continue
                target = rel["roles"][0]["concept"]
                if target in onto and onto[target]["type"] == "EntityType":
                    om = {"referent_mappings": [{"relationship": "id",
                                                 "expression": f"{t.name}.{rel['name']}"}]}
                    om["concept"] = target
                else:
                    om = {"concept": target, "expression": f"{t.name}.{rel['name']}"}
                children.append({"object_mapping": om, "relationship": rel["name"]})
        cm = {"concept": cls, "object_mappings": [ident]}
        if children:
            cm["link_mappings"] = [{"object_mapping": ident, "children": children}]
        concept_mappings.append(cm)
    return {"version": VERSION, "name": "work_mapping",
            "description": "Maps the Work ontology onto the work record's semantic model. Generated.",
            "ontology_ref": {"name": ONTOLOGY, "iri": ontology_iri},
            "semantic_model_ref": {"name": NAME, "iri": model_iri},
            "concept_mappings": concept_mappings}

