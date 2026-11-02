# 0001: What the developer instance allows (step 0 spikes)

Date: 2026-10-30. Instance: Personal Developer Instance, Brazil release (patch 1 hotfix 1). Evidence: the run
on this date, recorded below. Spike records were deleted afterwards.

## 1. Can history be backdated?

**Yes, server-side.**

- Through the Table API: `opened_at` and `closed_at` can be set on insert. `sys_created_on` is silently
  ignored on both insert and update.
- Through a run-once scheduled job (`sysauto_script`, created through the Table API) running
  `autoSysFields(false)` and `setWorkflow(false)`: `sys_created_on` and `sys_updated_on` were set on a
  requested item and on an approval. The job ran within seconds.
- **Watch: timezone.** A value set through `GlideRecord` is read in the job user's timezone: 09:00 became
  17:00 UTC. The seeder must write UTC explicitly (`GlideDateTime.setValueUTC`).

**Decision:** history goes on the instance. Records are inserted through the Table API with business dates
(`opened_at`, `closed_at`), then a server-side job backdates system fields from a manifest. The seeding job is
tooling, tagged `[shopfloor-tool]`, and is excluded from the truth file and the diagnosis.

## 2. Is Instance Scan available?

**Yes.**

- Plugin `com.glide.instance_scan` is active, with 432 checks: 124 table checks, 301 script-only checks and
  7 column-type checks.
- The instance already holds scan results from provisioning: 10 results and 5,550 findings. That is the
  **baseline** the planted mess is measured against.
- Scans can be started without the UI: `new sn_instance_scan.ScanInstance()` exposes `triggerFullScan()`,
  `triggerPointScan(table, sysId)`, `triggerSuiteScan(sysId)` and `triggerAppScan(scopeId)`, run from a
  run-once job. Progress is in `sys_execution_tracker`.
- Full scan duration: **41 minutes** (20:13 to 20:54 UTC), 8,738 findings, 0 errors.
- **The installed checks don't cover customisation quality.** Of 431 checks, 362 are security configuration;
  none look at business-rule practice (`current.update()`, hard-coded sys_ids), unused rules or catalogue
  sprawl. Those checks ship as separate content.

**Decision:**
- The planted anti-patterns cite ServiceNow's published best-practice documentation, not Instance Scan checks.
- The diagnosis is our own: the vocabulary checked against the record, usage from the record, and
  agent-assisted reading of each script. It is scored against the answer key.
- The original criterion "Instance Scan findings drop after clean-up" is replaced by "the record's own checks
  drop to the residue", because the base checks would show no change either way. Saying so is part of the
  finding: the platform's own scanner does not see this kind of debt.

## 3. How fast can we seed?

| Method | Throughput |
|---|---|
| Table API, 1 worker | 4 inserts/s |
| Table API, 8 workers | 28 inserts/s |
| Table API, 16 workers | 55 inserts/s |
| Batch API (`/api/now/v1/batch`), 50 inserts per call, 1 worker | 12 inserts/s |

These are requested-item inserts with the base business rules running.

**Decision:** Table API, 16 workers. About 5,000 requests plus approvals and tasks (roughly 20,000 records) is
about 6 minutes, which is acceptable for `seed apply`. Throttling under sustained load is not yet measured.

## 4. Can compiled policy be validated against published schemas?

- **Veza: yes, through Veza's own SDK.** `oaaclient` (MIT licence, version 1.2.1) builds custom-application
  payloads offline from its templates and reports issues that don't conform. The template already has
  `local_agents` and `local_models` alongside users, groups and roles, so agent identities have a native
  place.
- **Immuta: partly.** The V2 API (`/api/v2/policy` with `dryRun`, JSON or YAML) is documented in prose and
  attribute tables. No public OpenAPI or JSON Schema was found.

**Decision:**
- Veza payloads are built with `oaaclient`.
- Immuta payloads are checked against a JSON Schema we write from the documentation pages, each field citing
  its page and labelled "derived from documentation". A tenant would replace this with the server's dry run.

## Sources

- Immuta V2 API documentation. https://documentation.immuta.com/SaaS/developer-guides/api-intro/immuta-v2-api
- Veza, OAA getting started. https://developer.veza.com/oaa/guide/getting-started
- `oaaclient` on PyPI. https://pypi.org/project/oaaclient
