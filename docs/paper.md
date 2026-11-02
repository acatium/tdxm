# One Vocabulary for Agentic Work

*A working draft of an open standard for governed work by people and agents, and a demonstration of what
follows from it.*

## Summary

*Premise: [Lessons from the Factory Floor](lessons-from-the-factory-floor.md) (22 October 2026). This paper is
the test of its argument.*

Agents now act across systems that were each built to govern their own slice: tickets, identities, assets,
data. The closest thing an enterprise has to a record of the work itself (what was asked, who did each step
and on whose authority, and how it turned out) is its ServiceNow instance. That record is the starting point,
but it has two limits: agents increasingly act outside it, and it is written in one vendor's data model,
reshaped by each customer's customisation. Manufacturing faced the same problem between planning and the plant
floor, and solved it with a shared definition of the information that passes between levels (ISA-95) rather
than with one system.

This repository argues that the same move works for agentic work, and that it has a consequence worth more
than the standard itself: **with one vocabulary for work, every change to how work runs can be earned on
evidence.** That covers how the work is defined, the rules it runs under, and who may act unattended. The
language that says how work should run also says where it doesn't. So the platform can find what should
change, propose the change in the same terms, prove it against the customer's own record, and apply it once a
person approves. The argument is tested on a real ServiceNow instance:

1. **The standard comes first.** A small vocabulary of work, written in LinkML, from which every other format
   is generated or mapped. **One LinkML source produces the formats the other standards own**: an OpenTelemetry
   attribute registry, OCSF events and an Apache Ossie semantic model, each accepted by that community's own
   validator.
2. **Products join through it, not to each other.** ServiceNow, Veza, Armis and Moveworks each map to the
   vocabulary once, in a mapping set that is data. The record is read through those mappings, so adding a
   product means adding one mapping set, not one integration per product already joined.
3. **The platform finds what should change.** A gap is a record that fails the vocabulary, and its remedy
   is a change to the model, written in the same terms.
4. **Definitions are repaired, with history as the proof.** An agent translates legacy customisation into the
   model, and two years of requests are replayed against the result. A repair that would change any past
   decision is held for a person.
5. **Rules become declared policy, compiled into existing controls.** Approvals that history shows are a
   formality become policy, enforced by the systems customers already run. The method is measured out of
   sample: derived from one year, tested on the next.
6. **Agents earn autonomy.** They start at the bottom, are promoted on measured outcomes once a person
   confirms, and are demoted at once on a breach.
7. **Nothing is locked in.** Off-the-shelf tools and an unrelated agent read the exported record correctly.

Every claim is a command in this repository with evidence in [`results/`](../results/README.md).

## 1. The problem

Enterprise agents mostly fail where work crosses systems. Each system records its own part (a ticket, a
grant, a device, a span), and the joins are written by hand, pairwise, per customer.

One system already holds the record of the work. A ServiceNow instance carries years of requests, tasks,
approvals and outcomes: who asked for what, who decided, and how it turned out. That is the starting point for
everything here. It has two limits:

- **Agents act outside it.** An agent that calls a system directly leaves a span or a grant, not a task. In
  the demonstration, the first gap found is 65 agent actions with no request behind them, and the second is
  grants that no ticket explains.
- **It is not a shared language.** The record is written in one vendor's data model, and each customer has
  reshaped it with years of customisation: duplicate catalogue items, business rules nobody can explain,
  fields that shadow standard ones. Other systems cannot read or join it, agents trip on it, and it blocks
  upgrades. It is also the reason customers stay.

Opening the record's language as a standard addresses both: other systems and agents can write to it and read
it, and customisation can be moved into the customer's own layer of the model, safely.

Two public statements in October 2026 framed the problem as one of control rather than capability:

- Satya Nadella argued that models should be treated as insider risks: "We need to separate the supply of
  intelligence from the authority over it," with meaningful actions leaving "tamper-proof human readable
  evidence" [1].
- A fortnight later he said: "I used to always think that alignment will just fall out. I no longer believe
  that," and that agents "more capable and yet less aligned" need "a trust system that you can rely on" [2].

If alignment does not come with scale, the controls around models are permanent infrastructure, and permanent
infrastructure needs a standard. On ServiceNow's Q3 2026 earnings call, its chief executive Bill McDermott
said "we are the execution layer for the entire AI economy" [3]. An execution layer needs a shared definition of the work
it executes.

Removing customisation safely, without losing what it encodes, is the precondition for running agents on the
platform.

## 2. Lessons from the factory

Manufacturing learned five lessons the expensive way. Each is a constraint on the design.

1. **Standardise the information that passes between levels, not the systems at either end.** ISA-95 defined
   the information exchanged between planning and operations and left implementations alone [4].
   *Constraint:* the vocabulary describes the work. It does not dictate how any platform stores or runs it.
2. **Keep the recipe separate from the equipment.** Under ISA-88 a procedure moves to new equipment without
   being rewritten [5].
   *Constraint:* work definitions never mention a model. Swapping a model changes capability evidence, not
   the work.
3. **Keep one record per unit of work.** A pharmaceutical batch record shows every significant step and who
   performed or checked it [6].
   *Constraint:* every task, from any actor on any platform, produces one joined record.
4. **Keep authority separate from the work model.** Plants govern who may act through ISA/IEC 62443, not
   through ISA-95.
   *Constraint:* policy is declared next to the work but enforced by the systems built to enforce it.
5. **Earn automation on results.**
   *Constraint:* autonomy is a measured, reversible state per actor and step, never a configuration switch.

## 3. The design

### 3.1 One source, many readers

```
                         model/  (LinkML: the vocabulary of work)
                                       │
        ┌──────────────┬───────────────┼────────────────┬─────────────────┐
        ▼              ▼               ▼                ▼                 ▼
  OpenTelemetry      OCSF          Apache Ossie     JSON Schema,      Compiled policy
  work.* registry   findings      semantic model   OWL, SQL,         Immuta, Veza
  (operations)     (security)    (analytics, agents) Pydantic        (enforcement)

        ▲              ▲               ▲                ▲
        └──────────────┴──── mappings/ (SSSOM) ─────────┘
           ServiceNow tables · Veza OAA · Armis assets · Moveworks intake
```

Generated artefacts live in [`gen/`](../gen) and are never edited by hand; a test fails if they drift from the
model. Mappings to each product are [SSSOM](https://mapping-commons.github.io/sssom/) files in
[`mappings/`](../mappings), so the joins are data that can be reviewed, versioned and counted.

LinkML is the source rather than a rival to the other standards. OCSF, OpenTelemetry and Ossie remain the
native formats of their communities; the vocabulary supplies the meaning that joins them. The tools, and why each was chosen, are in [`stack.md`](stack.md).

### 3.2 Three layers, so no one party owns all of it

| Layer | File | Owned by | Contents |
|---|---|---|---|
| Core | [`model/work.yaml`](../model/work.yaml) | An open body | `WorkDefinition`, `StepDefinition`, `AcceptanceCriterion`, `Actor`, `Capability`, `WorkRequest`, `TaskRecord`, `Action`, `Decision`, `Outcome`, `WorkEvent`, `AutonomyChange`, `Gap`; the autonomy ladder; metrics |
| Profile | [`model/access.yaml`](../model/access.yaml) | A domain community | Access to data: `Dataset`, `Role`, `Grant`, `AccessRequest`, `AccessPolicy`, `ApprovalRule`, `Customisation` |
| Customer | [`model/contoso.yaml`](../model/contoso.yaml) | The customer | One firm's specifics, such as cost centres and a year-end approval window. Extends the profile; never edits the core |

The core classes follow ISA-95's four categories of information:

| ISA-95 | Vocabulary | ServiceNow |
|---|---|---|
| Product definition | `WorkDefinition`, `StepDefinition`, `AcceptanceCriterion` | Catalogue item, flow |
| Production capability | `Capability`, `AutonomyLevel` | Agent and user records |
| Production schedule | `WorkRequest`, `TaskRecord` | `sc_req_item`, `sc_task`, `sysapproval_approver` |
| Production performance | `Action`, `Decision`, `Outcome`, `WorkEvent` | The ticket and its history |
| (outside ISA-95, as 62443 is) | `AccessPolicy`, `ApprovalRule` | Compiled into Veza, Immuta |

### 3.3 A gap is a statement in the vocabulary

Each kind of gap (`GapKind` in the core) is a statement in the vocabulary, and each proposes its remedy in the
same terms: a change to the customer's layer, a registration, a revocation, a declared policy. Some gaps are
plain schema failures: an `Action` must name the `WorkRequest` it serves, so an agent acting with no ticket
behind it fails validation, and stock LinkML tools find it with no code of ours. Others are queries over the
record in the vocabulary's terms (a grant no request explains, a grant unused for 90 days), or an agent's
reading of a script, which a person confirms. Telemetry the vocabulary cannot express is itself a gap, in the
standard rather than in the customer.

Because the gap and the fix share a language, findings are comparable across teams and products, and a fix
can be tested before it is applied.

### 3.4 One loop: every change is earned on evidence

Nothing about how work runs changes because someone configured it. Every change goes through the same loop:
**find** it in the record, **propose** it in the vocabulary, **prove** it against evidence, have a person
**approve** it, **apply** it, and **reverse** it if the evidence turns. The loop applies to three things:

| What changes | Called | Proved by | In the demonstration |
|---|---|---|---|
| How the work is defined | **Repair** | Replaying history: the declared model must reproduce every past decision, and no change may alter one | Legacy customisation becomes model, compiled back into the platform; the catalogue goes from 14 items to 1 |
| The rules it runs under | **Declared policy** | Approval history, out of sample: every approver approved almost every time | Approvals that were a formality become policy, compiled into Immuta and Veza |
| Who may act unattended | **Autonomy** | Outcomes: the lower bound of the acceptance rate | An agent starts at assist, is promoted on its record, and is demoted at once on a breach |

The approve step is a record, not a convention. Every change is first a proposal whose id carries a digest of
its content; a person writes a `Confirmation` of that id, and only then is it applied. A changed proposal
needs a new confirmation. Only steps down are automatic, because failing closed is cheap and failing open is
not. The proof fails closed too: if the declared model does not reproduce history, nothing is proposed.

### 3.5 Authority is compiled; the gate sits outside the model

Policy is declared once, as `AccessPolicy` and `ApprovalRule` in the customer's layer, and compiled into each
enforcing system's native form: access policy into Immuta subscription policies and Veza roles, approval rules
back into the platform that holds the requests. The execution layer does not become another policy engine, and
enforcement does not depend on it: an order through the platform's catalogue, or a request inserted directly,
still gets the approvals the model requires. A declared policy is never written over a domain that a rule with a
time window touches, because the grants Immuta and Veza hold have no window.

At run time every step passes one decision ([`shopfloor/gate.py`](../shopfloor/gate.py)). It reads compiled
policy, the actor's earned autonomy and any open security stop. It never asks the agent whether it may act, and
any error denies.

### 3.6 Autonomy is earned per step, on evidence

Each actor holds an autonomy level per step: `assist`, `act_with_checkpoint`, `act`, `act_and_report`. Every
actor starts at `assist`. The ledger ([`shopfloor/ledger.py`](../shopfloor/ledger.py)) proposes one rung up
when the Wilson lower bound of the acceptance rate reaches 0.95, the same bar declared policy uses; a person
confirms it before it applies, and the evidence starts again: each rung is earned by outcomes at the rung
below. A breach demotes one rung at once. Each change carries a receipt naming its
evidence and its confirmation. In the demonstration the agent's evidence is the provisioning it did under the
old configuration, before any ladder existed, and the seed plants that record so that it clears the bar: the
demonstration shows the mechanism that reads a record, not that this agent earned anything.

Every event is hash-chained, and the head of the chain is anchored in a second system, the request's work
notes on the platform. A chain alone only catches an editor who does not rebuild the hashes; the anchor
catches one who does, as long as the two systems do not share an administrator.

People are the source of that evidence: their approvals, corrections and reversals are the labels outcomes are
judged against. The metrics measure the work and the agents, never individual people.

## 4. The demonstration

**Domain:** requests for access to data at Contoso Capital, a fictional financial firm. Data access is the most
common request type, the most audited control, and where agents touch regulated data.

**Live:** a ServiceNow Personal Developer Instance (Brazil release). **Simulated from published
documentation, and labelled as such:** Veza, Armis, Moveworks, Immuta, agent telemetry and a security stop
event.

The instance is seeded with two years of history and 29 customisations, each planted from an anti-pattern
named in ServiceNow's own best-practice documentation, plus one trap. An answer key records what a correct
diagnosis should find, so the diagnosis is scored rather than claimed.

| Step | What happens | Result |
|---|---|---|
| 1. The standard | Generate every format from the model; check each with its own community's validator | OTel Weaver: 0 violations. OCSF 1.9.0 validator: 0 errors. Ossie validator: passes |
| 1a. The joins | Read ServiceNow and Veza through their SSSOM mappings | In the mapping tests the record is identical to a hand-written reader's, table by table |
| 2. The aged instance | Seed from blank; seed again | Every seeded record is found on the instance (`results/run/seed.json`); a second run changes nothing |
| 3. Diagnose | Read the instance and simulated sources into one record; find the gaps | 8 kinds of gap, each at precision and recall 1.000 against the answer key |
| 4. Clean up | An agent translates scripts into the customer layer; history is replayed; seeded translation errors | 2,649 requests replayed, 0 differences; the trap is held; all 5 seeded errors hold the whole plan. Approval rules are compiled back into the platform |
| 5. Declared policy | Derive policy from one year of approvals; measure on the next; propose only what was measured | 2 policies. 32.1% of year-two approved requests needed no ticket; none granted beyond the answer key; 1 request a person rejected would have been covered |
| — Confirm | Every repair, policy and promotion waits for a confirmation of its exact content | Scenario stand-ins for the process owner; without them nothing is applied |
| 6. Run | Orders through the platform's catalogue and a direct insert; a live request through the gate; a planted breach | The platform asks for the owner's and security's approval with no gate involved; a malformed cost centre is refused; the agent is promoted, then demoted; the chain, anchored on the ticket, catches an edit even after the hashes are rebuilt |
| 7. No lock-in | Export; validate with stock tools; ask a separate agent | Stock `linkml-validate` finds exactly the 65 orphan actions. A separate agent, given the definition, lists exactly the diagnosis's policy candidates |

Three results matter more than the rest.

**History caught what usage missed, and the catch does not depend on the agent.** One planted rule had not
fired in 180 days, and usage data said retire it. The replay showed it still decides who approves during the
year-end close and would have changed 9 past decisions. It was held. When errors were seeded into the agent's
translation (a missing rule, a shortened window, a dropped condition, a wrong role), the replay no longer
reproduced history and nothing at all was proposed.

**Gaps appeared only across products.** An unregistered notebook agent was found only by joining agent
telemetry, Armis and the agent registry. A shared service account holding grants no ticket explains was found
only by joining Veza with the tickets.

**The policy result is smaller than it first looked, and stronger for it.** Measured on the same history it
was derived from, and counting only the owner's approval, the method claimed about half of all requests and
proposed a policy that would have granted restricted credit data without a request. Counting every approver
and testing on a year it had not seen, it removes 32.1% of approved requests and grants nothing the firm's
practice did not: about three-fifths of the 51.0% the answer key allows. It is not free of judgement: one
year-two request that a person rejected falls under the proposed policies, and the proposal says so. A policy
replaces approvals that were a formality, not the rare refusal, and the person confirming it should know that. The rest needs more evidence or a
person. Above confidential, a proposal needs a confirmation that names the data owner (the demo does not
verify who wrote it). Finance gets no declared policy at all: the year-end rule acts there, and Immuta and Veza
grants have no window.

The full evidence, with exit criteria per step, is in [`results/README.md`](../results/README.md).

## 5. What this does not show

- **It is not a customer estate.** The history is generated and the mess is planted. Every anti-pattern cites
  its source and the diagnosis is scored against an answer key, but the detector and the answer key share
  their definitions (a grant is idle after 90 days in both), so perfect precision on those kinds shows the
  pipeline works, not that the definitions are right for a real firm.
- **Only ServiceNow is live.** The other products are simulated from public documentation; their real payloads
  may differ. Moveworks and Armis mappings are checked but drive no join in the demo.
- **Declared policy removes its own evidence.** A request a policy covers creates no ticket, so nothing records
  an approval for it. The diagnosis reads a grant no request explains as drift, so once a policy applies, its
  grants would be reported as drift, and no approval evidence exists to reverse the policy. The loop's reverse
  step has no path for policy yet: a deployment needs a policy-covered grant to write a request record, or the
  diagnosis to read declared policy.
- **"Nothing beyond practice" is built into the seed.** Requests the answer key's policies cover are planted
  with a 0.5% rejection rate per approver, all others with 5% or more. At 5% a cell cannot reach a 0.95 lower
  bound, so 0 granted beyond the key shows the bar holds under the seed's rates, not that the method separates
  formality from review in a real estate.
- **The agent's answers are cached.** Each prompt and answer is kept (`data/classifications.json`,
  `data/declarations.json`) and reused while the prompt is unchanged, so a run is repeatable; the translation
  the archived run replayed was written on 2026-10-30 by claude-opus-5-5.
- **The agent's record is planted.** Its acceptance rate under the old configuration is a seed parameter chosen
  to clear the bar, and the reversals in it are read from the authority system's grant history, which is also
  simulated. What is shown is that the ledger reads the record as planted, promotes only on a confirmation, and
  demotes on a breach.
- **The people are scripted.** Approvers in chat, security clearing the stop and the process owner's
  confirmations are stand-ins, labelled in the record. The demo shows the mechanism that waits for them.
- **ServiceNow's licensed AI features are not exercised.** AI Agents, AI Control Tower, Action Fabric and AI
  Passport are outside a developer instance. The gate here stands in for them.
- **The replay compares decisions, not every side effect, and roles, not people.** A retired script with no
  approval logic is retired on usage alone; the replay cannot test it, and a person's confirmation is all that
  stands behind it. The proposal names those scripts. Where an old script named one person (the security lead)
  and the model names a role (any security analyst), the replay sees no difference; the agent's translation
  note says so, and the proposal points to it.
- **The anchor is only as independent as its administrators.** Here the same account writes the ledger and the
  work notes. In a deployment the anchor belongs in a system the ledger's writer cannot edit.
- **The separate agent is the same model family** as the one that reads the scripts, and it could read beyond
  its directory. A different model family would make the no-lock-in result stronger.
- **ServiceNow's Instance Scan does not see this kind of debt.** Its installed checks are almost all security
  configuration ([decision 0001](decisions/0001-instance-spikes.md)), so the diagnosis is the vocabulary's own.

## 6. Open questions

- **Who governs the vocabulary?** Whoever writes the gap taxonomy defines the problem. Candidate homes include
  the Agentic AI Foundation, AGNTCY, CNCF (for the telemetry registry) and OMG ([`prior-art.md`](prior-art.md)).
  An open licence is not the same as neutral governance.
- **What seeds the core?** ITIL is practice guidance, not a schema. The richest machine-readable model of that
  practice is ServiceNow's CSDM and task model, which is vendor-owned. Seeding from it means donating it.
- **How fast can it be adopted?** ISA-95 took about fifteen years and spread through free implementations
  (B2MML) more than through the standard's text. A reference implementation matters more than the
  specification.
- **How are thresholds set and owned?** The autonomy bar and the policy bar are per step, set by the
  process owner. This demo fixes them; a deployment needs them versioned in the customer layer.

## References

1. S. Nadella, post on X, Oct 10, 2026, as reported in "Satya Nadella says companies should treat AI models as
   insider risks," TNW, Oct 12, 2026. https://x.com/satyanadella/status/2108931348857827686 ;
   https://thenextweb.com/news/nadella-ai-models-insider-risks-emergency-brake
2. "Satya Nadella says he was wrong to think AI alignment would come with scale," TNW, Oct 28, 2026 (20VC with
   H. Stebbings). https://thenextweb.com/news/satya-nadella-ai-alignment-20vc
3. "Earnings call transcript: ServiceNow Q3 2026," Investing.com, Oct 28, 2026.
   https://www.investing.com/news/transcripts/earnings-call-transcript-servicenow-q3-2026-revenue-beats-shares-sink-after-hours-93CH-4981127
4. International Society of Automation, ANSI/ISA-95.00.01-2000. https://www.isa.org/isa-95
5. Yokogawa, "Standardizing batch control."
   https://yokogawa.com/library/resources/media-publications/standardizing-batch-control
6. 21 C.F.R. § 211.188.
   https://www.ecfr.gov/current/title-21/chapter-I/subchapter-C/part-211/subpart-J/section-211.188
