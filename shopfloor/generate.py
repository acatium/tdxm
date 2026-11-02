"""Everything in gen/ comes from the vocabulary through here. No hand edits; a test checks gen/ is current."""

import subprocess
import sys
from pathlib import Path

import yaml

from shopfloor import ossie, otel, store
from shopfloor.vocab import CORE, CUSTOMER, MODEL, ROOT

GEN = ROOT / "gen"


def _dump(data) -> str:
    return yaml.safe_dump(data, sort_keys=False, width=110, allow_unicode=True)


def _linkml(tool: str, schema: Path, *args: str) -> str:
    # Relative to the repo root, so the output is the same in any checkout.
    exe = Path(sys.executable).parent / tool
    return subprocess.run([str(exe), *args, str(schema.relative_to(ROOT))], cwd=ROOT,
                          capture_output=True, text=True, check=True).stdout


def artefacts() -> dict[str, str]:
    """Path under gen/ -> content."""
    out = {
        "otel/work.yaml": _dump(otel.registry()),
        "ossie/work.semantic_model.yaml": _dump(ossie.semantic_model()),
        "ossie/work.ontology.yaml": _dump(ossie.ontology()),
        "ossie/work.mapping.yaml": _dump(ossie.mapping()),
        "sql/record.sql": store.ddl(),
    }
    for schema in [CORE, MODEL / "access.yaml", CUSTOMER]:
        out[f"jsonschema/{schema.stem}.schema.json"] = _linkml("gen-json-schema", schema)
    out["owl/work.owl.ttl"] = _linkml("gen-owl", CORE)
    out["pydantic/contoso.py"] = _linkml("gen-pydantic", CUSTOMER)
    return out


def stale(root: Path = GEN) -> list[str]:
    """Artefacts under root that differ from what the vocabulary generates now."""
    return [rel for rel, content in artefacts().items()
            if not (root / rel).exists() or (root / rel).read_text() != content]


def write(root: Path = GEN) -> list[Path]:
    written = []
    for rel, content in artefacts().items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        written.append(p)
    return written


if __name__ == "__main__":
    for p in write():
        print(p.relative_to(ROOT))
