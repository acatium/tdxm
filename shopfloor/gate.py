"""decide(): the authority gate, outside the model that proposed the action. Fails closed.

Authority comes from what the model compiles (access policy, approval rules), the actor's capability on the
step, and stops raised by security. The gate never asks the agent whether it may act.
"""

from datetime import datetime

from shopfloor.policy import covers
from shopfloor.cleanup import required_approvers


def decide(step: str, request: dict, dataset: dict, actor: dict, *, role: str | None, policies: list[dict],
           approval_rules: list[dict], capability: dict | None, stops: list[dict], approvals: set[str]) -> dict:
    try:
        if not actor.get("registered"):
            return {"effect": "deny", "rule": "registry", "decided_by": "gate",
                    "reason": f"{actor['id']} is not a registered actor."}
        for s in stops:
            if s.get("request") == request["id"] and not s.get("cleared"):
                return {"effect": "deny", "rule": s["rule"], "decided_by": s["decided_by"], "reason": s["reason"]}
        if step == "st-approve":
            opened = datetime.fromisoformat(request["requested_at"].replace("Z", "+00:00"))
            # A rule that acts only in a window (the year-end close) was never part of the evidence for a declared
            # policy, so where it applies, the policy does not.
            windowed = [r for r in approval_rules
                        if r.get("year_end_close_days") and required_approvers([r], dataset, opened)]
            if not windowed and any(covers(p, role, dataset, request.get("privilege")) for p in policies):
                return {"effect": "allow", "rule": "declared_policy", "decided_by": "gate",
                        "reason": "Covered by declared access policy; no approval needed."}
            needed = required_approvers(approval_rules, dataset, opened)
            missing = sorted(needed - approvals)
            if missing:
                return {"effect": "checkpoint", "rule": "approval_rules", "decided_by": "gate",
                        "reason": f"Waiting for approval from: {', '.join(missing)}."}
            return {"effect": "allow", "rule": "approval_rules", "decided_by": "gate",
                    "reason": "All required approvals given."}
        if step == "st-provision":
            if capability is None:
                return {"effect": "deny", "rule": "capability", "decided_by": "gate",
                        "reason": f"{actor['id']} has no capability for {step}."}
            if capability["autonomy_level"] == "assist":
                return {"effect": "checkpoint", "rule": "autonomy", "decided_by": "gate",
                        "reason": "Autonomy is assist: a person acts."}
            if capability["autonomy_level"] == "act_with_checkpoint":
                return {"effect": "checkpoint", "rule": "autonomy", "decided_by": "gate",
                        "reason": "Autonomy is act with checkpoint: a person approves first."}
            return {"effect": "allow", "rule": "autonomy", "decided_by": "gate",
                    "reason": f"Autonomy is {capability['autonomy_level']}."}
        return {"effect": "deny", "rule": "unknown_step", "decided_by": "gate", "reason": f"Unknown step {step}."}
    except Exception as e:  # fail closed
        return {"effect": "deny", "rule": "gate_error", "decided_by": "gate", "reason": f"Gate error: {e}"}
