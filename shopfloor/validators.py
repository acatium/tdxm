"""The other communities' own validators, pinned. Nothing here is ours: we only fetch and run them.

- OpenTelemetry Weaver: `weaver registry check` and `weaver registry live-check`.
- Apache Ossie: `validation/validate.py` from apache/ossie.
- OCSF: the OCSF schema server's validation API (see shopfloor.ocsf.validate).
"""

import json
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

from shopfloor.vocab import ROOT

CACHE = ROOT / ".cache"
WEAVER_VERSION = "v0.28.0"
WEAVER_URL = (f"https://github.com/open-telemetry/weaver/releases/download/{WEAVER_VERSION}/"
              "weaver-x86_64-unknown-linux-gnu.tar.xz")
OSSIE_REPO = "https://github.com/apache/ossie"
OSSIE_COMMIT = "290ec2a"


def weaver() -> Path:
    exe = CACHE / f"weaver-{WEAVER_VERSION}" / "weaver-x86_64-unknown-linux-gnu" / "weaver"
    if not exe.exists():
        exe.parent.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(suffix=".tar.xz") as f:
            urllib.request.urlretrieve(WEAVER_URL, f.name)
            with tarfile.open(f.name) as tar:
                tar.extractall(exe.parent.parent, filter="data")
    return exe


def ossie() -> Path:
    repo = CACHE / f"ossie-{OSSIE_COMMIT}"
    if not repo.exists():
        subprocess.run(["git", "clone", "-q", OSSIE_REPO, str(repo)], check=True)
        subprocess.run(["git", "-C", str(repo), "checkout", "-q", OSSIE_COMMIT], check=True)
    return repo


def weaver_check(registry: Path) -> subprocess.CompletedProcess:
    return subprocess.run([str(weaver()), "registry", "check", "-r", str(registry), "--future"],
                          capture_output=True, text=True)


def weaver_live_check(registry: Path, samples: list[dict]) -> list[dict]:
    """Returns every piece of advice Weaver gives, as dicts with level and id."""
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(samples, f)
    out = subprocess.run([str(weaver()), "registry", "live-check", "-r", str(registry), "--input-source", f.name,
                          "--input-format", "json", "--format", "jsonl", "--no-stats"],
                         capture_output=True, text=True)
    advice = []

    def walk(o):
        if isinstance(o, dict):
            r = o.get("live_check_result")
            if r:
                advice.extend(r.get("all_advice", []))
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    for line in out.stdout.splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                walk(json.loads(line))
            except json.JSONDecodeError:
                pass
    return advice


def ossie_validate(path: Path, schema: str | None = None) -> subprocess.CompletedProcess:
    repo = ossie()
    cmd = [sys.executable, str(repo / "validation" / "validate.py")]
    if schema:
        cmd += ["--schema", str(repo / schema)]
    return subprocess.run(cmd + ["--", str(path)], capture_output=True, text=True, cwd=Path(path).parent)
