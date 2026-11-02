"""An outside agent: headless Claude Code (`claude -p`), with no tools, answering in a JSON Schema.

Used where the demo says "agent-assisted": reading customisations, and the no-lock-in close. Every call's
prompt and answer are kept with the results so a reader can see exactly what the agent was told.
"""

import json
import subprocess


def ask(prompt: str, schema: dict, model: str | None = None, timeout: int = 900) -> dict:
    cmd = ["claude", "-p", "--output-format", "json", "--no-session-persistence", "--tools", "",
           "--json-schema", json.dumps(schema)]
    if model:
        cmd += ["--model", model]
    out = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=timeout)
    if out.returncode != 0:
        raise RuntimeError(f"claude -p failed: {out.stderr[-500:]}")
    reply = json.loads(out.stdout)
    if reply.get("is_error") or reply.get("structured_output") is None:
        raise RuntimeError(f"claude -p gave no structured answer: {str(reply.get('result'))[:500]}")
    return {"answer": reply["structured_output"], "model": next(iter(reply.get("modelUsage", {})), None),
            "cost_usd": reply.get("total_cost_usd")}
