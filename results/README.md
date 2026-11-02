# Results: the demo, run from a blank instance

Run: `make demo`, `make scenario` and `make apply` on 2026-11-02 (UTC), from the code in this repository (only prose changed
after the run), on a ServiceNow
Personal Developer Instance (Brazil, patch 1 hotfix 1). About 45 minutes end to end: reset 30 minutes, seed
4, the rest under 15. `make check` passes on the same code. The run's files are in [`run/`](run/); rows 1, 1a and 2 rest on
`make check`, and the timings on the run's logs, which are not archived.

- **Live:** the ServiceNow instance, with two years of history, 29 customisations, the clean-up, the orders
  through the catalogue and the live request.
- **Simulated, from published documentation:** Veza, Armis, Moveworks, Immuta, agent telemetry and the
  security stop.
- **Scripted, and labelled in the record:** the people. Approvers in chat, the security analyst clearing the
  stop, and the process owner's confirmations ([`run/confirmations.yaml`](run/confirmations.yaml), written by
  `make scenario`; the working copy is not in the repository).
- **Planted:** the history, the customisations and the answer key, including the access agent's record, whose
  acceptance rate is a seed parameter set to clear the autonomy bar.

## Exit criteria

| #   | Proof point         | Criterion                                                                                                     | Result                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| --- | ------------------- | ------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | **The standard**    | One LinkML source produces the formats the others own, each checked by its own community's tooling            | **Met.** The OTel registry and spans pass Weaver 0.28. Gaps and stops pass OCSF 1.9.0's validator with 0 errors. The Ossie ontology, semantic model and mapping pass Ossie's validator                                                                                                                                                                                                                                                                                                                                                                                       |
| 1a  | Products joined     | ServiceNow and Veza records are read through their mappings                                                   | **Met.** In the mapping tests the record built through the SSSOM mappings is identical, table by table, to a hand-written reader's. Moveworks and Armis mappings are checked, not used ([`run/integration.json`](run/integration.json))                                                                                                                                                                                                                                                                                                                                    |
| 2   | Aged instance       | Rebuilds from blank; same result twice; counts match the answer key                                           | **Met.** 8,593 seeded records expected, 8,593 found, table by table ([`run/seed.json`](run/seed.json)); the world is deterministic (`tests/test_seed_and_score.py`)                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| 3   | **Diagnose**        | Precision and recall ≥ 0.9 for each kind of gap                                                               | **Met.** 8 kinds of gap, each at precision and recall 1.000; 6 policy candidates found, 6 in the key ([`run/diagnosis.json`](run/diagnosis.json))                                                                                                                                                                                                                                                                                                                                                                                                                            |
| 3   |                     | Gaps visible only by joining products                                                                         | **Met.** The unregistered notebook agent (telemetry, Armis and the registry). The shared service account's unexplained grants (Veza and the tickets)                                                                                                                                                                                                                                                                                                                                                                                                                         |
| 4   | **Repair**          | The declared model reproduces history; the trap is held, and nothing else                                     | **Met.** 2,649 requests replayed, 0 differences. The year-end rule would change 9 past decisions and is **held**. A rule whose usage cannot be measured is held too. Plan: 13 retired, 12 declared, 2 kept, 2 held; 20 customisations deactivated ([`run/cleanup.json`](run/cleanup.json))                                                                                                                                                                                                                                                                                   |
| 4   |                     | Seeded translation errors hold the whole plan                                                                 | **Met.** Five errors (drop the window, shorten it, drop a classification, wrong role, miss a rule): each makes 9 to 1,885 past decisions differ, and every one holds everything ([`run/perturb.json`](run/perturb.json))                                                                                                                                                                                                                                                                                                                                                     |
| 4   |                     | Enforcement survives without this code                                                                        | **Met.** Two business rules compiled from the model. An order through the generated catalogue item and a request inserted directly each get the owner's and security's approval; an order with a malformed cost centre is refused by the platform, with the old cost-centre script switched off ([`run/enforcement.json`](run/enforcement.json))                                                                                                                                                                                                                             |
| 4   |                     | Catalogue goes from 14 items to 1                                                                             | **Met.** One item, generated from the vocabulary. Retired fields are hidden, not dropped; dropping waits for a retention window                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| 5   | **Declared policy** | Measured out of sample; nothing beyond practice; what is proposed is what was measured                        | **Met.** 2 policies derived from year one, tested on year two: **32.1%** of the 1,248 approved requests needed no ticket, 0 granted beyond the answer key (its ceiling: 51.0%), and 1 request a person rejected is covered; the proposal counts it. The same 2 are proposed and compiled: 5 Immuta payloads pass the schema derived from Immuta's documentation; 3 Veza roles are built by its SDK ([`run/policy.json`](run/policy.json))                                                                                                                                  |
| —   | **Confirm**         | Nothing proposed is applied without a confirmation of its exact content                                       | **Met.** 4 proposals (the repair, 2 policies, 1 promotion), each confirmed by a labelled scenario stand-in ([`run/confirmations.yaml`](run/confirmations.yaml); `run/proposals.yaml` is written again after the promotion applied, so it lists the three open then). Phase 1 applied nothing; a changed proposal gets a new id; any rejection wins                                                                                                                                                                                                                                                                                                                                                                                    |
| 6   | **Run**             | Platform and gate agree; promotion only on confirmation; demotion on breach; the chain catches a rebuilt edit | **Met.** The live request was ordered through the catalogue; the platform asked for the same approvers the gate named. The agent went from assist to act with checkpoint on a confirmed promotion (1,086 of 1,113 planted outcomes accepted, lower bound 0.965), with no further rung open, and back to assist on a breach. 18 chained events; the head is anchored in the ticket's work notes; an edit with the chain rebuilt passes the chain check and fails against the anchor. Spans: 0 Weaver violations; the run's record conforms ([`run/live.json`](run/live.json)) |
| 7   | **No lock-in**      | Stock tools validate the export; a separate agent answers from it                                             | **Met.** Stock `linkml-validate` (from PyPI, isolated) finds exactly the 65 orphan actions and nothing else. A separate Claude session, in a temporary directory outside the repository and given the definition, listed exactly the diagnosis's policy candidates (13 turns, $1.61) ([`run/close.json`](run/close.json))                                                                                                                                                                                                                                                    |
| 8   | Package             | From blank, timed                                                                                             | **Met** (about 45 minutes)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |

## What the run found

- **The proof does not trust the agent.** The agent's translation of the approval scripts was exact, and the
  replay confirmed it. That alone would only show that this agent was right this time. Seeding errors into
  its translation shows the method fails closed: when the declared model does not reproduce history, nothing
  is proposed, and no policy is derived under that model's rules either.
- **The trap still works, and so does the defence.** Usage said "retire". The replay said "this still decides
  who approves at year end". No declared policy is written over finance, because the grants Immuta and Veza
  hold have no window and would skip the rule all year. The gate also refuses a policy where a windowed rule
  applies (`tests/test_authority.py`; the live run is not in March).
- **What the replay cannot vouch for is named.** The clean-up proposal lists the four scripts with no approval
  logic, which it cannot test, and points to the agent's three translation notes. One says the security
  approval widens from a named lead to any security analyst. The replay compares roles, so it cannot see
  that; a person has to. One of the four, the cost-centre script, is replaced by the compiled request-fields
  rule, which enforces the slot's requiredness and pattern from the model; the enforcement check shows the
  platform refusing a malformed cost centre with that script switched off.
- **The confirmation covers what is installed.** The repair proposal's id digests the compiled business
  rules and the generated catalogue item as text, not only the list of changes, so a change to a dataset's
  owner or a role's name changes the proposal.
- **The policy number is smaller and honest.** An earlier version of this method counted only the owner's
  approval and measured on its own training data. It claimed about half of all requests and proposed a policy
  that would have granted restricted credit data without a request. Counting every approver and testing on a
  year it had not seen: 32.1%, with nothing granted beyond practice, and the one rejected request the policies
  would cover is counted in the proposal. The minimum cell is 73 requests, the smallest that can clear the
  0.95 lower bound even if every request was approved; the answer key uses the same minimum, so engineers'
  internal markets data (66 requests, all approved, lower bound 0.945) is a candidate in neither.
- **The agent's record is planted, and read as planted.** The seed records every grant's history, revoked
  grants included, and the ingest reads a task's outcome from that history rather than from the grant a
  person holds today (`tests/test_ingest.py`). The planted acceptance rate clears the bar; that is a seed
  parameter, not a finding.
- **Enforcement belongs to the platform.** The repair is compiled back into ServiceNow as rules generated from
  the model, so the platform enforces it without this code running, through its own catalogue. The compiled
  JavaScript is also run locally under node against the Python replay engine on the same cases
  (`tests/test_compiled.py`).
- **ServiceNow behaviours worth knowing.**
  - An encoded query with an unknown field silently matches every row. The diagnosis checks fields first.
  - `^NQ` groups each need their own time window.
  - Task-family tables delete row by row, so a reset takes 25 to 30 minutes.
  - A catalogue variable's "map to field" applies to record producers, not to catalogue items. Business rules
    read the variables instead, before and after insert.
  - The installed Instance Scan checks are almost all security configuration and do not see this kind of
    debt ([decision 0001](../docs/decisions/0001-instance-spikes.md)).
  - Scenario confirmations belong to one run: a stale file pre-confirms the next run's identical proposals,
    so `make reset` removes it.

## Limits

- The history is generated and the mess is planted. The detector and the answer key share their definitions,
  so perfect precision on those kinds shows the pipeline works, not that the definitions suit a real firm.
- The agent's acceptance rate is a seed parameter chosen to clear the autonomy bar.
- "Nothing beyond the answer key" is a property of the seed: requests its policies cover are planted with a
  0.5% rejection rate per approver, all others with 5% or more, and at 5% a cell cannot reach the 0.95 bound.
- The agent's answers are cached with their prompts (`data/classifications.json`, `data/declarations.json`)
  and were reused by this run; the translation was written on 2026-10-30 by claude-opus-5-5. `--refresh`
  asks again.
- A request a declared policy covers leaves no ticket, so the next diagnosis would read its grant as drift
  ([`docs/paper.md`](../docs/paper.md) §5).
- Simulated sources are only as right as the public documentation. Armis's mapping is the weakest.
- The replay compares decisions (who approves), not every side effect, and roles, not people. Scripts with no
  approval logic are retired on usage and a person's confirmation alone, or replaced by the compiled
  request-fields rule where their target is a slot it enforces.
- A confirmation names who decided; the demo does not verify it. Above confidential it must name the data owner.
- The anchor shares an administrator with the ledger in the demo.
- The separate agent is the same model family as the one that reads the scripts, and could read beyond its
  directory.
- The live run's instance timestamps are real. The history's "now" is fixed at 2026-10-30 so a rerun is
  repeatable.
