# A ten-minute walkthrough

For someone who knows ServiceNow and its security portfolio well. Show the live instance and the files, not
slides. Every number below comes from [`results/run/`](../results/run/), from one run of `make demo`,
`make scenario` and `make apply` on a blank instance.

## 1. The premise (1 minute)

ServiceNow already holds the closest thing an enterprise has to a record of its work: who asked, who decided,
how it turned out. That record has two limits. Agents act outside it, and it is written in one vendor's data
model, reshaped by every customer's customisation. The proposal is the one manufacturing made with ISA-95:
standardise the meaning of the information, not the systems at either end.

Show: [`model/work.yaml`](../model/work.yaml), then `make check`. One LinkML source generates the OpenTelemetry
registry, OCSF events and an Ossie semantic model, and each passes its own community's validator.

## 2. What the record says is wrong (2 minutes)

Show: the seeded instance (14 catalogue items for one kind of work, 29 customisations), then
`results/run/diagnosis.json`.

- An agent nobody registered, found only by joining agent telemetry, Armis and the agent registry.
- A shared service account holding grants no ticket explains, found only by joining Veza and the tickets.
- ServiceNow's own Instance Scan sees none of this: its installed checks are security configuration.

## 3. Repair, with history as the proof (2 minutes)

Show: `results/run/cleanup.json`, `results/run/perturb.json`, `results/run/enforcement.json`.

- An agent translated the approval scripts into Contoso's model. Replaying 2,649 past requests: 0 differences.
- One rule had not fired in 180 days. Usage said retire it; the replay showed it still decides who approves
  at the year-end close. It was held.
- The point that matters: the proof does not trust the agent. Five kinds of error seeded into its
  translation each held the whole clean-up.
- After the clean-up, the platform enforces the model on its own: an order through the one generated catalogue
  item, or a request inserted directly, gets the owner's and security's approval, and a malformed cost centre
  is refused. None of that goes through this code.
- The proposal a person confirms names what the replay cannot vouch for: four scripts with no approval logic
  (one of them replaced by the compiled request-fields rule),
  and the translation notes, such as the one saying the security approver widens from a named lead to any
  security analyst.

## 4. Declared policy, measured honestly (2 minutes)

Show: `results/run/policy.json`.

- Approvals that history shows are a formality become declared policy, compiled into Immuta and Veza.
- Derived from one year, tested on the next: 32.1% of approved requests needed no ticket, and nothing was
  granted that the firm's practice did not allow. The answer key's ceiling is 51.0%. The two policies measured
  are the two proposed. One year-two request a person had rejected falls under them; the proposal says so.
- No policy is declared over finance: the year-end rule acts there, and the grants Immuta and Veza hold have no
  window.
- An earlier version of this method claimed about half, measured on its own training data, and proposed a
  policy that would have granted restricted credit data without a request. Counting every approver, not only
  the data owner, removed it.

## 5. Autonomy and the record of it (1 minute)

Show: `results/run/live.json`.

- The access agent starts at assist. Its record under the old configuration (1,086 of 1,113 accepted, planted
  to clear the bar) supports one rung; it applies only once a person confirms it, and the next rung needs fresh
  evidence. A breach demotes it at once.
- Every event is hash-chained and the head is written to the ticket's work notes. Editing an event and
  rebuilding the chain is caught against that anchor.

## 6. Where it breaks (1 minute)

- The history is generated and the mess is planted. Only ServiceNow is live; Veza, Armis, Moveworks and Immuta
  are simulated from their documentation.
- The people are scripted: the approvers, the security analyst and the process owner's confirmations. A
  confirmation names who decided; the demo does not verify it.
- The replay compares roles, not people, and cannot test scripts with no approval logic.
- The anchor shares an administrator with the ledger. The separate agent is the same model family.

## 7. What would make it real (1 minute)

One real estate, read only: the same diagnosis and replay on a customer's own history, a real Veza tenant
instead of fixtures, and a second model family for the independent reading. The open question that matters
most is governance: who should hold a vocabulary that defines what counts as a gap
([`paper.md`](paper.md) §6).
