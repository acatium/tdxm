"""The autonomy ledger and the event chain.

Autonomy is earned per step, never per agent overall. Every actor starts at assist. When the Wilson lower bound
of its acceptance rate clears the bar, the ledger proposes one rung up; a person confirms it, and only then does
it apply. The evidence then starts again: each rung is earned by outcomes at the rung below. A breach demotes one rung at once, with no confirmation: failing closed is cheap. Every change carries
a receipt naming its evidence and, for a promotion, its confirmation.

Events are hash-chained. A chain alone only shows an edit by someone who did not rebuild the hashes, so the head
hash is anchored in a second system (the ticket's work notes) and verified against it.
"""

import hashlib
import json
from dataclasses import dataclass, field

from shopfloor import confirm
from shopfloor.diagnose import POLICY_BOUND, wilson_lower

LADDER = ["assist", "act_with_checkpoint", "act", "act_and_report"]
PROMOTE_AT = POLICY_BOUND  # one bar for everything earned on evidence


@dataclass
class Capability:
    id: str
    actor: str
    step: str
    autonomy_level: str = "assist"  # everyone starts here
    evidence: list[str] = field(default_factory=list)
    accepted: int = 0

    @property
    def lower_bound(self) -> float:
        return wilson_lower(self.accepted, len(self.evidence))

    def as_record(self) -> dict:
        return {"id": self.id, "actor": self.actor, "step": self.step, "autonomy_level": self.autonomy_level,
                "evidence_count": len(self.evidence), "accepted_count": self.accepted,
                "lower_bound": round(self.lower_bound, 4)}


def observe(cap: Capability, outcome_id: str, accepted: bool) -> None:
    cap.evidence.append(outcome_id)
    cap.accepted += accepted


def propose(cap: Capability) -> dict | None:
    """One rung up, if the evidence clears the bar. A proposal, not a change."""
    i = LADDER.index(cap.autonomy_level)
    if i == len(LADDER) - 1 or cap.lower_bound < PROMOTE_AT:
        return None
    to = LADDER[i + 1]
    basis = {"capability": cap.id, "from_level": cap.autonomy_level, "to_level": to,
             "evidence_count": len(cap.evidence), "accepted_count": cap.accepted}
    reason = (f"{cap.accepted} of {len(cap.evidence)} accepted; lower bound {cap.lower_bound:.3f} >= {PROMOTE_AT}.")
    return {**confirm.proposal("autonomy", f"{cap.id}:{to}", basis,
                               f"Promote {cap.actor} on {cap.step} from {cap.autonomy_level} to {to}: {reason}",
                               cap.evidence[-20:]), **basis, "reason": reason}


def apply_confirmed(cap: Capability, confirmations: list[dict], at: str) -> dict | None:
    """Apply the next promotion only if a person confirmed exactly that proposal. Returns the receipt."""
    p = propose(cap)
    if not p or confirm.verdict(confirmations, p["id"]) != "approve":
        return None
    cap.autonomy_level = p["to_level"]
    # Each rung is earned at the rung below: the evidence that earned this one starts again.
    cap.evidence, cap.accepted = [], 0
    return {"id": f"chg-{cap.id}-{len(cap.evidence)}-{p['to_level']}", "capability": cap.id,
            "from_level": p["from_level"], "to_level": p["to_level"], "at": at, "reason": p["reason"],
            "evidence": p["evidence"], "confirmation": p["id"]}


def demote(cap: Capability, at: str, breach: str) -> dict | None:
    """One rung down at once on a breach; the evidence starts again."""
    i = LADDER.index(cap.autonomy_level)
    if i == 0:
        return None
    new = LADDER[i - 1]
    change = {"id": f"chg-{cap.id}-breach-{new}-{at}", "capability": cap.id, "from_level": cap.autonomy_level,
              "to_level": new, "at": at, "reason": f"Breach: {breach}. Demoted at once; evidence resets.",
              "evidence": [breach]}
    cap.autonomy_level, cap.evidence, cap.accepted = new, [], 0
    return change


def _digest(event: dict, prev: str) -> str:
    body = {k: v for k, v in event.items() if k not in ("hash", "prev_hash")}
    return hashlib.sha256((prev + json.dumps(body, sort_keys=True)).encode()).hexdigest()


def chain(events: list[dict]) -> list[dict]:
    prev = "0" * 64
    for e in events:
        e["prev_hash"] = prev
        e["hash"] = prev = _digest(e, prev)
    return events


def head(events: list[dict]) -> str:
    """The chain's head hash: what is anchored outside the ledger."""
    return events[-1]["hash"] if events else "0" * 64


def verify(events: list[dict], anchor: str | None = None) -> list[str]:
    """The ids of events whose hash does not match, and "anchor" if the head differs from the anchor held
    elsewhere. Empty means intact."""
    bad, prev = [], "0" * 64
    for e in events:
        if e.get("prev_hash") != prev or e.get("hash") != _digest(e, prev):
            bad.append(e["id"])
        prev = e.get("hash", "")
    if anchor is not None and head(events) != anchor:
        bad.append("anchor")
    return bad
