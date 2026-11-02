# Task Data Exchange Model (TDXM)

Accelerating enterprise automation requires a shared data model for task data that spans many systems and
actors, including humans and agentic workflows. The Task Data Exchange Model (TDXM) demonstrates how
organizations can use a common data model to exchange this data between the systems, people and agents in a
process, in a machine and human-readable format. This approach lowers the cost of integration and improves
end-to-end visibility of work while maintaining function and tool-specific data formats.

In this demo we unify the task data on its ServiceNow record, giving operators a single picture of task
performance, accuracy and efficiency. This intelligence is crucial to safely adopting agentic solutions that
accelerate workflow velocity across complex tasks. The demo shows three things the model makes possible:
removing years of customisation safely, turning rubber-stamp approvals into policy, and rolling out faster,
more automated processes step by step, each step governed by the results of the last.

The argument it tests is [`docs/lessons-from-the-factory-floor.md`](docs/lessons-from-the-factory-floor.md):
enterprise AI has protocols for connecting agents but nothing like ISA-95, an agreed meaning for the work
that passes between systems. The model replaces no one's format: from it the repository generates
OpenTelemetry's registry, OCSF's events and Ossie's model, and each passes that community's own validator.

```
  ServiceNow        Veza          Armis        Moveworks      Agent telemetry
  tickets,          grants        hosts        chat intake    OpenTelemetry spans
  approvals, tasks    │             │             │                 │
      └───────────────┴──── one mapping each (SSSOM) ───────────────┘
                                    ▼
                  THE RECORD, in the task data model (LinkML, model/)
          ┌─────────────────────────┼──────────────────────────┐
          ▼                         ▼                          ▼
      DIAGNOSE                   REPAIR                     POLICY · AUTONOMY
  what fails the model    scripts → rules; history     formality approvals →
                          replayed; held on any diff   policy; agents promoted on outcomes
          └─────────── a person confirms each proposal ────────┘
          ▼                         ▼                          ▼
   ServiceNow business rules     Immuta policies,          OTel · OCSF · Ossie
   and catalogue item            Veza roles                (each validated by its
   (generated)                   (compiled)                own community's tool)
```

Information flows back out the same way: rules and policy are compiled into the products that enforce them,
a chat request that policy covers is answered with no ticket, and each gap names its remedy in the product
that holds it. The stack, and why each piece, is in [`docs/stack.md`](docs/stack.md).

There is no agent framework or control layer in the architecture. The agent that reads the scripts is called
as a function with a schema for its answer and no tools, so it can propose but not act; what governs it is
the record it must write and the platform that enforces the rules derived from it. Any agent that writes
the record is governed the same way. The architecture assumes the language model is interchangeable: it
accelerates the work, the record and the platform govern it, so a better one drops in without changing
anything that governs.

## What the demo shows

We seed two years of a fictional bank's data-access requests onto a blank ServiceNow instance, with the mess
a real one collects: 14 catalogue items for the same request, six custom fields, and nine business rules
holding the approval policy as script. The ticket is the join key. Data access is the example, one profile
on a generic core. Then we use that history to prove three things.

**Customisation can be removed safely.** An AI agent rewrites each script as a rule in the model. A replay
engine checks every one of the 2,649 past requests: would the same people have been asked to approve? 0
differences. One script that had not run in six months still decides approvals every March, so the replay
held it. Five mistakes planted in the translation each failed the replay, and nothing was proposed. After
confirmation the rules are compiled back into ServiceNow, which enforces them itself.
[`cleanup.json`](results/run/cleanup.json) · [`perturb.json`](results/run/perturb.json) ·
[`enforcement.json`](results/run/enforcement.json)

**Rubber-stamp approvals become policy.** Where every approver approved nearly every request of one kind,
that access needs no ticket. Derived from year one and tested on year two: 32% of approved requests would
have needed no ticket, none beyond the planted ground truth, and the proposal counts the one request a
person rejected. Compiled into Immuta and Veza. [`policy.json`](results/run/policy.json)

**Faster processes roll out one governed step at a time.** The provisioning agent starts at "assist" and
moves up one step when its record clears the bar and a person confirms. A planted breach demotes it at once.
Every event is hash-chained and anchored on the ticket. [`live.json`](results/run/live.json)

Nothing is applied without a person confirming the proposal's exact content. A stock validator and a
separate AI session read the exported record and reach the same findings.
[`results/README.md`](results/README.md) lists every exit criterion and whether the last run met it.

## What is real

ServiceNow is live. Veza, Armis, Moveworks and Immuta are simulated from public documentation. The people
are scripted. The history, the mess and the answer key are planted, and the agent's acceptance rate is set to
clear the bar. The demo shows the mechanisms, not that the definitions suit a real firm. Limits:
[`docs/paper.md`](docs/paper.md) §5.

## Running it

Python 3.12, [uv](https://docs.astral.sh/uv/), node, [Claude Code](https://claude.com/claude-code) signed in
(the agent steps; a few dollars a run), network for the validators, and a ServiceNow Personal Developer
Instance with `SN_INSTANCE`, `SN_USER` and `SN_PASSWORD` in a local `.env`.

```
make check     # the tests
make demo      # blank instance → proposals (~35 minutes)
make scenario  # demo only: a labelled stand-in confirms every proposal
make apply     # apply, enforce, run, close, archive (~10 minutes)
```

## Where to look

[`docs/paper.md`](docs/paper.md): design, results, limits, open questions. [`docs/walkthrough.md`](docs/walkthrough.md):
ten minutes on the live instance. `model/` the model, `mappings/` the joins, `shopfloor/` the demo's code
(the demo is named for the paper), `tests/` the exit criteria, `results/` the evidence.

© 2026 Acatium, Inc. Licensed under [Apache-2.0](LICENSE).
