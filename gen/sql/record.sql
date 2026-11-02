CREATE TABLE IF NOT EXISTS "roles" (
  "id" VARCHAR PRIMARY KEY,
  "name" VARCHAR,
  "department" VARCHAR
);

CREATE TABLE IF NOT EXISTS "datasets" (
  "id" VARCHAR PRIMARY KEY,
  "name" VARCHAR,
  "platform" VARCHAR,
  "classification" VARCHAR,
  "domain" VARCHAR,
  "owner" VARCHAR
);

CREATE TABLE IF NOT EXISTS "grants" (
  "id" VARCHAR PRIMARY KEY,
  "actor" VARCHAR,
  "dataset" VARCHAR,
  "privilege" VARCHAR,
  "held_in" VARCHAR,
  "granted_at" TIMESTAMP,
  "request" VARCHAR,
  "last_used_at" TIMESTAMP
);

CREATE TABLE IF NOT EXISTS "policies" (
  "id" VARCHAR PRIMARY KEY,
  "description" VARCHAR,
  "role" VARCHAR,
  "domain" VARCHAR,
  "max_classification" VARCHAR,
  "privilege" VARCHAR,
  "effect" VARCHAR,
  "requires_approval" BOOLEAN
);

CREATE TABLE IF NOT EXISTS "approval_rules" (
  "year_end_close_days" BIGINT,
  "id" VARCHAR PRIMARY KEY,
  "description" VARCHAR,
  "approver_kind" VARCHAR,
  "approver_role" VARCHAR,
  "min_classification" VARCHAR,
  "domain" VARCHAR
);

CREATE TABLE IF NOT EXISTS "customisations" (
  "id" VARCHAR PRIMARY KEY,
  "name" VARCHAR,
  "customisation_kind" VARCHAR,
  "host_table" VARCHAR,
  "executions_180d" BIGINT,
  "last_executed_at" TIMESTAMP,
  "plan" VARCHAR,
  "plan_reason" VARCHAR
);

CREATE TABLE IF NOT EXISTS "work_definitions" (
  "id" VARCHAR PRIMARY KEY,
  "name" VARCHAR,
  "description" VARCHAR,
  "steps" JSON,
  "owner" VARCHAR
);

CREATE TABLE IF NOT EXISTS "actors" (
  "id" VARCHAR PRIMARY KEY,
  "name" VARCHAR,
  "actor_kind" VARCHAR,
  "registered" BOOLEAN,
  "owner" VARCHAR,
  "title" VARCHAR
);

CREATE TABLE IF NOT EXISTS "capabilities" (
  "id" VARCHAR PRIMARY KEY,
  "actor" VARCHAR,
  "step" VARCHAR,
  "autonomy_level" VARCHAR,
  "evidence_count" BIGINT,
  "accepted_count" BIGINT,
  "lower_bound" DOUBLE
);

CREATE TABLE IF NOT EXISTS "requests" (
  "cost_centre" VARCHAR,
  "dataset" VARCHAR,
  "privilege" VARCHAR,
  "justification" VARCHAR,
  "duration_days" BIGINT,
  "id" VARCHAR PRIMARY KEY,
  "work_definition" VARCHAR,
  "requested_by" VARCHAR,
  "on_behalf_of" VARCHAR,
  "requested_at" TIMESTAMP,
  "channel" VARCHAR,
  "external_ref" VARCHAR
);

CREATE TABLE IF NOT EXISTS "tasks" (
  "id" VARCHAR PRIMARY KEY,
  "request" VARCHAR,
  "step" VARCHAR,
  "actor" VARCHAR,
  "on_behalf_of" VARCHAR,
  "autonomy_level" VARCHAR,
  "started_at" TIMESTAMP,
  "ended_at" TIMESTAMP,
  "decision_effect" VARCHAR,
  "decision_rule" VARCHAR,
  "decision_decided_by" VARCHAR,
  "decision_reason" VARCHAR,
  "outcome_status" VARCHAR,
  "outcome_decided_at" TIMESTAMP,
  "outcome_decided_by" VARCHAR,
  "external_ref" VARCHAR
);

CREATE TABLE IF NOT EXISTS "actions" (
  "id" VARCHAR PRIMARY KEY,
  "actor" VARCHAR,
  "target_system" VARCHAR,
  "operation" VARCHAR,
  "resource" VARCHAR,
  "at" TIMESTAMP,
  "request" VARCHAR,
  "source" VARCHAR
);

CREATE TABLE IF NOT EXISTS "events" (
  "id" VARCHAR PRIMARY KEY,
  "kind" VARCHAR,
  "at" TIMESTAMP,
  "request" VARCHAR,
  "task" VARCHAR,
  "actor" VARCHAR,
  "reason" VARCHAR,
  "source" VARCHAR,
  "via" VARCHAR,
  "prev_hash" VARCHAR,
  "hash" VARCHAR
);

CREATE TABLE IF NOT EXISTS "changes" (
  "id" VARCHAR PRIMARY KEY,
  "capability" VARCHAR,
  "from_level" VARCHAR,
  "to_level" VARCHAR,
  "at" TIMESTAMP,
  "reason" VARCHAR,
  "evidence" VARCHAR[],
  "confirmation" VARCHAR
);

CREATE TABLE IF NOT EXISTS "gaps" (
  "id" VARCHAR PRIMARY KEY,
  "gap_kind" VARCHAR,
  "subject" VARCHAR,
  "evidence" VARCHAR[],
  "proposes" VARCHAR
);

CREATE TABLE IF NOT EXISTS "confirmations" (
  "id" VARCHAR PRIMARY KEY,
  "change_kind" VARCHAR,
  "verdict" VARCHAR,
  "decided_by" VARCHAR,
  "decided_at" TIMESTAMP,
  "reason" VARCHAR
);
