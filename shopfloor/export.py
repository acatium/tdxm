"""Step 7, no lock-in: the vocabulary, Contoso's model and the whole record, exported as open files, then
read by tools that are not ours.

- Off-the-shelf LinkML (`linkml-validate`, installed from PyPI into a fresh environment) validates the record
  against the exported model. No code from this repository is involved.
- An agent that is not ServiceNow's (headless Claude) is given a copy of the export in a fresh temporary
  directory outside this repository, with file reading and the system Python only, and asked which approvals
  are candidates for declared policy. The question states the definition of a candidate: the test is whether
  the exported files carry enough meaning to answer a defined question, not whether the agent can invent the
  method. Its answer is compared with the diagnosis.

Limits, stated: Python can still read outside the directory, and the agent is the same model family as the
classifier. A second model family would make the independence stronger.
"""

import csv
import json
import shutil
import subprocess
from pathlib import Path

import yaml

from shopfloor.diagnose import POLICY_BOUND, POLICY_MIN
from shopfloor.generate import GEN
from shopfloor.vocab import MODEL, ROOT

EXPORT = ROOT / "var" / "export"

QUESTION = """You have a directory with a governed-work record exported in open formats:
- model/: the LinkML vocabulary (work.yaml, access.yaml) and the customer's model (contoso.yaml);
- ossie/: an Apache Ossie semantic model, ontology and mapping describing the CSV tables;
- data/: the tables as CSV.

Using only these files (read them; you may run python3 with the standard library), answer: which approvals
are candidates for declared policy? Follow the semantic model's ai_context. The definition is given, as a
process owner would give it: a cell is (requester title, dataset domain, dataset classification, privilege) and
counts requests; a request counts as approved only if every approval on it was approved. A cell is a candidate
when it has at least {POLICY_MIN} requests and the Wilson lower bound (z = 1.96) of the share approved is at least
{POLICY_BOUND}.
List every candidate cell with its count and lower bound.""".replace("{POLICY_MIN}", str(POLICY_MIN)).replace("{POLICY_BOUND}", str(POLICY_BOUND))

SCHEMA = {"type": "object", "properties": {"candidates": {"type": "array", "items": {"type": "object", "properties": {
    "requester_title": {"type": "string"}, "domain": {"type": "string"}, "classification": {"type": "string"},
    "privilege": {"type": "string"}, "requests": {"type": "integer"}, "lower_bound": {"type": "number"}},
    "required": ["requester_title", "domain", "classification", "privilege", "requests", "lower_bound"]}},
    "method": {"type": "string"}}, "required": ["candidates", "method"]}


def write(rec: dict) -> Path:
    if EXPORT.exists():
        shutil.rmtree(EXPORT)
    (EXPORT / "model").mkdir(parents=True)
    for f in ["work.yaml", "access.yaml", "contoso.yaml"]:
        shutil.copy(MODEL / f, EXPORT / "model" / f)
    shutil.copytree(GEN / "ossie", EXPORT / "ossie")
    (EXPORT / "record.yaml").write_text(yaml.safe_dump(rec, sort_keys=False))
    data = EXPORT / "data"
    data.mkdir()
    sm = yaml.safe_load((GEN / "ossie" / "work.semantic_model.yaml").read_text())
    for ds in sm["datasets"]:
        rows = rec.get(ds["name"], [])
        cols = [f["name"] for f in ds["fields"]]
        with (data / f"{ds['name']}.csv").open("w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(cols)
            for r in rows:
                flat = []
                for c in cols:
                    v = r.get(c)
                    if v is None and "_" in c:
                        head, _, tail = c.partition("_")
                        if isinstance(r.get(head), dict):
                            v = r[head].get(tail)
                    flat.append(json.dumps(v) if isinstance(v, (list, dict)) else v)
                w.writerow(flat)
    return EXPORT


def stock_validate() -> subprocess.CompletedProcess:
    """linkml-validate from PyPI, in an isolated environment that has never seen this repository."""
    return subprocess.run([str(Path.home() / ".local" / "bin" / "uvx"), "--isolated", "--from", "linkml==1.12.0", "linkml-validate",
                           "-s", "model/contoso.yaml", "-C", "ContosoRecord", "record.yaml"],
                          cwd=EXPORT, capture_output=True, text=True)


def outside_agent() -> dict:
    import tempfile
    work = Path(tempfile.mkdtemp(prefix="shopfloor-export-"))
    shutil.copytree(EXPORT, work, dirs_exist_ok=True)
    out = subprocess.run(["claude", "-p", "--output-format", "json", "--no-session-persistence",
                          "--tools", "Read,Bash,Glob", "--allowedTools", "Read", "Glob", "Bash(python3:*)",
                          "Bash(ls:*)", "Bash(head:*)", "--json-schema", json.dumps(SCHEMA)],
                         input=QUESTION, capture_output=True, text=True, cwd=work, timeout=1800)
    shutil.rmtree(work, ignore_errors=True)
    reply = json.loads(out.stdout)
    return {"answer": reply.get("structured_output"), "cost_usd": reply.get("total_cost_usd"),
            "model": next(iter(reply.get("modelUsage", {})), None), "turns": reply.get("num_turns"),
            "question": QUESTION, "workdir": "a fresh temporary directory outside the repository"}
