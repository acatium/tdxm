# Prior art: what already claims part of the vocabulary

The question: does an existing standard already supply "ISA-95 for agentic work", and if not, what should the
vocabulary reuse rather than reinvent? Survey as of October 2026.

Confidence marks:
- ✓ confirmed from a primary or official source.
- ~ secondary sources only.
- ? unverified.

## Finding in one paragraph

No existing standard defines the information that passes between systems about agentic work: what the work
is, who is permitted and proven to do it, how it was handed off, and how it turned out. A September 2026
review of 89 primary sources on authorising tool-using agents reached a similar conclusion about the
authority side [1].

The neighbourhood, though, is crowded. Every ISA-95 category already has a partial claimant, and the record
alone has three (OpenTelemetry, OCSF and W3C PROV). So the new standard should be **small**: a vocabulary of work, written in LinkML, *projected onto* existing standards rather than
competing with them.

That is also closer to how ISA-95 worked. ISA defined the models, a different body published the XML
implementation (B2MML), and a third published the OPC UA mapping [2], [3].

## By ISA-95 category

### Product definition: what the work is

| Standard | Body | What it covers | Why it isn't the answer | Reuse |
|---|---|---|---|---|
| **BPMN 2.0** (ISO/IEC 19510) ✓ | OMG | Executable process models: tasks, gateways, events | Standardises *how a process runs* inside one engine, not the information exchanged between levels. Vendors are now marketing it as "agentic orchestration" [4], [5] ~ | Our `WorkDefinition` should be able to *reference* a BPMN process as its implementation, not replace it |
| **CMMN** ✓ | OMG | Case work: discretionary tasks, sentries, human tasks | The closest fit to knowledge work and human checkpoints. Adoption is thin outside Flowable and Camunda [5] ~ | Sentry semantics (entry and exit criteria) are a tested model for `HandoffRule` and checkpoints |
| **DMN** ✓ | OMG | Decision tables and expressions (FEEL) | A decision language, not a work model | A candidate *expression language* for deterministic `AcceptanceCriterion` checks, instead of inventing one |
| **ITIL 4** ✓ | PeopleCert (Axelos) | Practices and vocabulary for service management | A framework of practices, with no machine-readable schema | The concepts (incident, request, change, approval). **It is not a schema we can start from** |
| **ServiceNow CSDM 5** ~ | ServiceNow | ServiceNow's data model across ITSM, ITOM, SPM and CSM. Published as a 63-page white paper in the Community, May 2025 [6] | Vendor-owned; no open licence found ? | The richest existing mapping of ITIL to data. If seeded from it, it must be donated, or the vocabulary repeats MAP's mistake |

**Seeding.** ITIL supplies concepts, not a schema. The machine-readable starting point is CSDM, which
ServiceNow owns, so seeding the vocabulary from it raises the governance question directly.

### Production capability: who is permitted and proven

| Standard | Body | What it covers | Gap | Reuse |
|---|---|---|---|---|
| **OASF** (Open Agentic Schema Framework) ~ | AGNTCY (reportedly Linux Foundation ?) | Agent records: skills, domains and modules, with a skill taxonomy. Inspired by OCSF [7] | Describes what an agent *claims* it can do, for discovery. No permission, no evidence | Use the OASF skill taxonomy for `StepType`, or map to it. Our `Capability` adds *permitted* and *proven* |
| **ISA-95 capability model** ✓ | ISA / IEC 62264-2 | Committed, available and unattainable capability for personnel, equipment and material [2] | Manufacturing-specific | Its committed/available/unattainable split is a useful idea for agent capacity planning |

Nothing found models **proven** capability: reliability evidence for each step type. That part is new.

### Production schedule: requests, assignments, handoffs

| Standard | Body | What it covers | Gap | Reuse |
|---|---|---|---|---|
| **A2A** ✓ | Google, then AAIF (reported Aug 2026 ?) | Agent-to-agent tasks with generic states (`input-required`, `rejected`) | No meaning for *who* a task waits on or *why* | Carry our states as a refinement of A2A states  |
| **MCP** ✓ | AAIF | Tool and context access | Transport, not work | Input schemas for tools generated from `StepDefinition` |
| **CloudEvents** ✓ | CNCF (graduated) | A neutral event envelope | Envelope only | Candidate envelope for handoff events between platforms |

### Production performance: the record

The record has three claimants, and each serves a different reader:

| Standard | Body | Reader | What it covers | Gap |
|---|---|---|---|---|
| **OpenTelemetry GenAI conventions** ✓ | CNCF | Operations | `invoke_agent` and `execute_tool` spans; Development status [8] | Calls, not work; no outcome |
| **OCSF**, with the AOS extension ~ | OCSF project; AOS ("Agent Observability Standard", `trustworthyagents/aos`) | Security (SIEM) | AOS maps agent events onto OCSF API Activity (6003) and to OTel, and emits an AgBOM in CycloneDX or SPDX [9]. Has `task_delegation` and tool-execution status | No approvals, no policy decisions, no acceptance |
| **W3C PROV / PROV-O** ✓ | W3C (Recommendation, 2013) | Audit and compliance | Entity, Activity, Agent; `wasAssociatedWith`, **`actedOnBehalfOf`** (delegation) | Generic. PROV-AGENT (ORNL, IEEE e-Science 2025) extends it for agents and MCP [10]. No OTel mapping is standardised ~ |
| **OpenLineage** ✓ | LF AI & Data (graduated 2023) | Data teams | Run, job and dataset lineage, extensible through facets [11] | No agent or work facet yet ~ |

**What this means.** The task record has three audiences, and each already has a standard:

- operations reads OpenTelemetry;
- security reads OCSF;
- audit reads PROV.

`TaskRecord` should be defined once in LinkML and **projected** onto all three. It also maps cleanly onto
PROV:

| `TaskRecord` | PROV |
|---|---|
| The task | `prov:Activity` |
| The actor | `prov:Agent` |
| `on_behalf_of` | `prov:actedOnBehalfOf` |
| Outputs | `prov:Entity` with `prov:wasGeneratedBy` |

LinkML supports this directly through `class_uri` and `slot_uri`. An OpenLineage run facet carrying
`work.request.id` ties the data a task touched to the task.

### Authority: outside ISA-95, as in plants

| Standard | Body | What it covers | Relevance |
|---|---|---|---|
| **OAuth 2.0 Token Exchange** (RFC 8693) ✓ | IETF | Delegation chains, including the `act` claim | Carries "agent acting for person" across hops |
| **Rich Authorization Requests** (RFC 9396) ✓ | IETF | Structured `authorization_details` instead of coarse scopes | **The natural wire carrier for task-scoped authority**: a typed object naming the work request, step type and policy |
| **Agent on-behalf-of drafts** ~ | IETF OAuth WG, WIMSE | `draft-oauth-ai-agents-on-behalf-of-user` (expired Feb 2026); WIMSE credential delegation (Jul 2026); Alibaba integration draft (Jul 2026) [12] | Active but unsettled. The OAuth WG was reportedly rechartered in Jun 2026 with agent work in scope ? |
| **OPA/Rego, Cedar** ✓ | CNCF; AWS (open source) | Policy *engines and languages* | Places to compile policy into, not a shared vocabulary |
| **SPIFFE/SPIRE** ✓ | CNCF | Workload identity | How agent processes prove who they are |

Task-scoped delegation is the piece these standards leave open, and it is the vocabulary seen from the
identity side:

- At compile time, authority goes to the enforcing systems (Veza, Immuta and so on).
- At run time, it travels as RAR `authorization_details` typed by the vocabulary, exchanged per hop with
  RFC 8693.

A downstream system can then check the task scope itself, without calling back to the gate.

### Data meaning

| Standard | Body | Notes |
|---|---|---|
| **Apache Ossie** ✓ | Apache Incubator (Jul 2026) | Semantic models with `ai_context`; converters for about 20 platforms, including an ontology converter [13] |

Ossie was built for BI semantic layers. Using it to measure the work is a stretch; this demonstration tests it, and Ossie's own validator accepts the result.
The metrics are ordinary aggregates over a fact table, which Ossie handles, but nothing in its ecosystem
assumes operational KPIs.

## Where would the vocabulary live?

There is no single home, and that is normal. ISA-95's models (ISA, then IEC 62264), its XML (B2MML, from the
World Batch Forum and later MESA) and its OPC UA mapping (OPC Foundation) each lived in a different body
[2], [3]. The candidates:

| Home | Hosts | Fit |
|---|---|---|
| **AAIF** (Linux Foundation, Dec 2025) ✓ | MCP, goose, AGENTS.md; reportedly agentgateway and A2A ? [14] | Strongest: the vocabulary refines A2A and MCP |
| **AGNTCY** ~ | OASF, agent directory | Fits capability; narrower |
| **CNCF** ✓ | OpenTelemetry, CloudEvents | For the `work.*` registry only, as a GenAI SIG contribution |
| **OMG** ✓ | BPMN, CMMN, DMN | Formal and slow; fits the definition side |

The likely shape:
- a vocabulary in AAIF or AGNTCY;
- the `work.*` registry contributed to OpenTelemetry;
- profiles for PROV and OCSF published with the vocabulary.

## How ISA-95 got adopted

- The SP95 committee formed in the mid-1990s. Part 1 was published in 2000, Part 2 in 2001 and Part 3 in
  2005 ?
- IEC 62264-1 and -2 internationalised Parts 1 and 2 ✓ [2].
- B2MML gave Parts 1 and 2 a royalty-free XML form. It was used courtesy of MESA, and covers the personnel,
  equipment, material, definition, capability, schedule and performance models ✓ [3].
- Even now the OPC UA companion specification covers only a *subset* of the object models ✓ [3].

**The lesson.** Uptake took about 15 years. It came through free implementations (B2MML), not the standard
text alone, and partial coverage was enough to be useful. The reference implementation matters more than the
specification.

## Sources

1. R. K. Surapani et al., "Authorization architectures for tool-using AI agents," arXiv:2609.15906, Sep 2026.
   https://arxiv.org/abs/2609.15906
2. OPC Foundation, ISA-95 companion specification (OPC 10030).
   https://reference.opcfoundation.org/specs/OPC-10030/full ; "ISA-95," Wikipedia.
   https://en.wikipedia.org/wiki/ISA-95
3. "XML delivers," Control Engineering. https://www.controleng.com/articles/xml-delivers ;
   https://reference.opcfoundation.org/ISA-95/docs/1
4. Camunda, "Why BPMN (still) matters, especially in the age of AI," Apr 2026.
   https://camunda.com/blog/2026/04/why-bpmn-still-matters-especially-in-the-age-of-ai/
5. Flowable, "AI orchestration." https://documentation.flowable.com/latest/ai/ai-orchestration ;
   "Towards modeling human-agentic collaborative workflows: a BPMN extension," arXiv:2412.05958.
   https://arxiv.org/pdf/2412.05958
6. "CSDM 5: get the white paper," ServiceNow Community, May 2025.
   https://www.servicenow.com/community/common-service-data-model/csdm-5-finally-get-the-csdm-5-white-paper-here/ta-p/3254967/page/2/show-comments/true ;
   ServiceNow docs, CSDM.
   https://www.servicenow.com/docs/bundle/yokohama-servicenow-platform/page/product/csdm-implementation/concept/csdm-landing-page.html
7. AGNTCY, "Open Agentic Schema Framework." https://docs.agntcy.org/oasf/open-agentic-schema-framework/
8. OpenTelemetry, "Semantic conventions for GenAI agent and framework spans."
   https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-agent-spans
9. AOS, "Extend OCSF." https://aos.owasp.org/spec/trace/extend_ocsf/
10. "PROV-AGENT: unified provenance for tracking AI agent interactions in agentic workflows,"
    arXiv:2508.02866. https://arxiv.org/abs/2508.02866
11. LF AI & Data, "OpenLineage." https://lfai.foundation/projects/openlineage ;
    https://github.com/OpenLineage/OpenLineage
12. https://datatracker.ietf.org/doc/html/draft-oauth-ai-agents-on-behalf-of-user-02 ;
    https://www.ietf.org/archive/id/draft-sweeney-wimse-credential-delegation-00.html ;
    https://datatracker.ietf.org/doc/draft-liu-ai-agent-authorization-integration/
13. Apache Ossie. https://ossie.apache.org/ ; https://github.com/apache/ossie-converters
14. "Linux Foundation launches Agentic AI Foundation," RCPmag, Dec 9, 2025.
    https://rcpmag.com/Articles/2025/12/09/Linux-Foundation-Unites-Major-Tech-Firms.aspx ;
    latent.space AAIF entry (unverified dates). https://latent.space/wiki/aaif/
