from __future__ import annotations

import re
import sys
from datetime import (
    date,
    datetime,
    time
)
from decimal import Decimal
from enum import Enum
from typing import (
    Any,
    ClassVar,
    Literal,
    Optional,
    Union
)

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    RootModel,
    SerializationInfo,
    SerializerFunctionWrapHandler,
    field_validator,
    model_serializer
)


metamodel_version = "1.12.0"
version = "0.1.0"


class ConfiguredBaseModel(BaseModel):
    model_config = ConfigDict(
        serialize_by_alias = True,
        validate_by_name = True,
        validate_assignment = True,
        validate_default = True,
        extra = "forbid",
        arbitrary_types_allowed = True,
        use_enum_values = True,
        strict = False,
    )





class LinkMLMeta(RootModel):
    root: dict[str, Any] = {}
    model_config = ConfigDict(frozen=True)

    def __getattr__(self, key:str):
        return getattr(self.root, key)

    def __getitem__(self, key:str):
        return self.root[key]

    def __setitem__(self, key:str, value):
        self.root[key] = value

    def __contains__(self, key:str) -> bool:
        return key in self.root


linkml_meta = LinkMLMeta({'default_prefix': 'org',
     'default_range': 'string',
     'description': "The customer's specifics, in the customer's namespace. Each "
                    'class here extends a profile class; nothing here edits the '
                    'core or the profile. Customisations that carry business '
                    'meaning are declared here instead of living as scripts on the '
                    'platform.',
     'id': 'https://example.org/contoso',
     'imports': ['linkml:types', 'access'],
     'license': 'Apache-2.0',
     'name': 'contoso',
     'prefixes': {'access': {'prefix_prefix': 'access',
                             'prefix_reference': 'https://example.org/work/access/'},
                  'linkml': {'prefix_prefix': 'linkml',
                             'prefix_reference': 'https://w3id.org/linkml/'},
                  'org': {'prefix_prefix': 'org',
                          'prefix_reference': 'https://example.org/contoso/'},
                  'work': {'prefix_prefix': 'work',
                           'prefix_reference': 'https://example.org/work/'}},
     'source_file': 'model/contoso.yaml',
     'title': "Contoso Capital's own model"} )

class WorkMetric(str, Enum):
    """
    The measures of work performance (ISA-95 production performance; ISO 22400 in spirit). Each value carries its definition as SQL over the record's tables, so every consumer computes it the same way.
    """
    first_pass_yield = "first_pass_yield"
    """
    Share of completed tasks accepted without being reversed, reopened or reassigned.
    """
    reversal_rate = "reversal_rate"
    """
    Share of completed tasks reversed within their window.
    """
    agent_share = "agent_share"
    """
    Share of tasks performed by agents rather than people.
    """
    orphan_actions = "orphan_actions"
    """
    Number of observed actions with no request.
    """
    stops = "stops"
    """
    Number of steps halted by an authority outside the performer.
    """


class ActorKind(str, Enum):
    person = "person"
    agent = "agent"
    service_account = "service_account"
    system = "system"


class RiskClass(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class AutonomyLevel(str, Enum):
    """
    The earned autonomy ladder. Promotion follows evidence; demotion is immediate.
    """
    assist = "assist"
    """
    Proposes; a person acts.
    """
    act_with_checkpoint = "act_with_checkpoint"
    """
    Acts after a person approves.
    """
    act = "act"
    """
    Acts; a person can review.
    """
    act_and_report = "act_and_report"
    """
    Acts and reports in aggregate.
    """


class DecisionEffect(str, Enum):
    allow = "allow"
    deny = "deny"
    checkpoint = "checkpoint"


class OutcomeStatus(str, Enum):
    accepted = "accepted"
    reversed = "reversed"
    """
    Undone within the reversal window.
    """
    reopened = "reopened"
    reassigned = "reassigned"
    failed = "failed"
    abandoned = "abandoned"


class WorkEventKind(str, Enum):
    requested = "requested"
    decided = "decided"
    started = "started"
    stopped = "stopped"
    """
    Halted by an authority outside the performer, e.g. security.
    """
    approved = "approved"
    rejected = "rejected"
    overridden = "overridden"
    completed = "completed"
    reversed = "reversed"
    promoted = "promoted"
    demoted = "demoted"


class ChangeKind(str, Enum):
    """
    The three things whose change is earned on evidence.
    """
    repair = "repair"
    """
    How the work is defined. Proved by replaying history.
    """
    declared_policy = "declared_policy"
    """
    The rules the work runs under. Proved by approval history, out of sample.
    """
    autonomy = "autonomy"
    """
    Who may act unattended. Proved by outcomes.
    """


class Verdict(str, Enum):
    approve = "approve"
    reject = "reject"


class GapKind(str, Enum):
    orphan_action = "orphan_action"
    """
    An action with no request.
    """
    idle_privilege = "idle_privilege"
    """
    A grant no governed task has used.
    """
    unregistered_actor = "unregistered_actor"
    """
    An actor acting that the registry does not know.
    """
    policy_candidate = "policy_candidate"
    """
    An approval that history shows is a formality: a candidate for declared policy.
    """
    duplicate_definition = "duplicate_definition"
    """
    Several definitions of the same work.
    """
    dead_customisation = "dead_customisation"
    """
    A customisation that never runs.
    """
    drift = "drift"
    """
    Grants in an authority system that no request explains.
    """
    vocabulary = "vocabulary"
    """
    Something observed that the vocabulary cannot express; a gap in the standard.
    """


class Classification(str, Enum):
    """
    Ordered from least to most sensitive.
    """
    public = "public"
    internal = "internal"
    confidential = "confidential"
    restricted = "restricted"


class Privilege(str, Enum):
    read = "read"
    write = "write"
    admin = "admin"


class ApproverKind(str, Enum):
    dataset_owner = "dataset_owner"
    """
    The owner of the dataset requested.
    """
    role = "role"
    """
    Anyone holding approver_role.
    """


class CustomisationKind(str, Enum):
    catalogue_item = "catalogue_item"
    business_rule = "business_rule"
    client_script = "client_script"
    custom_field = "custom_field"
    approval_rule = "approval_rule"


class CleanupPlan(str, Enum):
    retire = "retire"
    """
    Never runs; remove.
    """
    revert_to_base = "revert_to_base"
    """
    Duplicates the platform's own behaviour.
    """
    declare = "declare"
    """
    Carries business meaning; declare it in the customer's model.
    """
    replace_with_adapter = "replace_with_adapter"
    """
    Integration glue; replace with an adapter behind the compiler.
    """
    keep = "keep"
    """
    No equivalent in the vocabulary yet; the residue feeds the standard.
    """



class WorkDefinition(ConfiguredBaseModel):
    """
    A kind of work the organisation does, as a sequence of steps.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'annotations': {'namespace': {'tag': 'namespace', 'value': 'work_definition'}},
         'from_schema': 'https://example.org/work'})

    id: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['WorkDefinition',
                       'StepDefinition',
                       'AcceptanceCriterion',
                       'Actor',
                       'Capability',
                       'WorkRequest',
                       'TaskRecord',
                       'Action',
                       'WorkEvent',
                       'AutonomyChange',
                       'Gap',
                       'Confirmation',
                       'Dataset',
                       'Role',
                       'Grant',
                       'AccessPolicy',
                       'ApprovalRule',
                       'Customisation']} })
    name: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['WorkDefinition',
                       'StepDefinition',
                       'Actor',
                       'Dataset',
                       'Role',
                       'Customisation'],
         'slot_uri': 'schema:name'} })
    description: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['WorkDefinition',
                       'StepDefinition',
                       'AcceptanceCriterion',
                       'AccessPolicy',
                       'ApprovalRule'],
         'slot_uri': 'schema:description'} })
    steps: Optional[list[StepDefinition]] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['WorkDefinition']} })
    owner: Optional[str] = Field(default=None, description="""The actor accountable.""", json_schema_extra = { "linkml_meta": {'domain_of': ['WorkDefinition', 'Actor', 'Dataset']} })


class StepDefinition(ConfiguredBaseModel):
    """
    One step of a kind of work. Autonomy is earned per step, not per agent.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'annotations': {'namespace': {'tag': 'namespace', 'value': 'step'}},
         'from_schema': 'https://example.org/work'})

    id: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['WorkDefinition',
                       'StepDefinition',
                       'AcceptanceCriterion',
                       'Actor',
                       'Capability',
                       'WorkRequest',
                       'TaskRecord',
                       'Action',
                       'WorkEvent',
                       'AutonomyChange',
                       'Gap',
                       'Confirmation',
                       'Dataset',
                       'Role',
                       'Grant',
                       'AccessPolicy',
                       'ApprovalRule',
                       'Customisation']} })
    name: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['WorkDefinition',
                       'StepDefinition',
                       'Actor',
                       'Dataset',
                       'Role',
                       'Customisation'],
         'slot_uri': 'schema:name'} })
    description: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['WorkDefinition',
                       'StepDefinition',
                       'AcceptanceCriterion',
                       'AccessPolicy',
                       'ApprovalRule'],
         'slot_uri': 'schema:description'} })
    risk_class: Optional[RiskClass] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['StepDefinition']} })
    requires_approval: Optional[bool] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['StepDefinition', 'AccessPolicy']} })
    acceptance: Optional[list[AcceptanceCriterion]] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['StepDefinition']} })


class AcceptanceCriterion(ConfiguredBaseModel):
    """
    How an outcome of a step is judged right. Judged after the reversal window closes.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://example.org/work'})

    id: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['WorkDefinition',
                       'StepDefinition',
                       'AcceptanceCriterion',
                       'Actor',
                       'Capability',
                       'WorkRequest',
                       'TaskRecord',
                       'Action',
                       'WorkEvent',
                       'AutonomyChange',
                       'Gap',
                       'Confirmation',
                       'Dataset',
                       'Role',
                       'Grant',
                       'AccessPolicy',
                       'ApprovalRule',
                       'Customisation']} })
    description: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['WorkDefinition',
                       'StepDefinition',
                       'AcceptanceCriterion',
                       'AccessPolicy',
                       'ApprovalRule'],
         'slot_uri': 'schema:description'} })
    reversal_window_days: Optional[int] = Field(default=None, ge=0, json_schema_extra = { "linkml_meta": {'domain_of': ['AcceptanceCriterion']} })


class Actor(ConfiguredBaseModel):
    """
    A person, agent, service account or system that can take part in work.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'annotations': {'namespace': {'tag': 'namespace', 'value': 'actor'}},
         'class_uri': 'prov:Agent',
         'from_schema': 'https://example.org/work'})

    id: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['WorkDefinition',
                       'StepDefinition',
                       'AcceptanceCriterion',
                       'Actor',
                       'Capability',
                       'WorkRequest',
                       'TaskRecord',
                       'Action',
                       'WorkEvent',
                       'AutonomyChange',
                       'Gap',
                       'Confirmation',
                       'Dataset',
                       'Role',
                       'Grant',
                       'AccessPolicy',
                       'ApprovalRule',
                       'Customisation']} })
    name: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['WorkDefinition',
                       'StepDefinition',
                       'Actor',
                       'Dataset',
                       'Role',
                       'Customisation'],
         'slot_uri': 'schema:name'} })
    actor_kind: ActorKind = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['Actor']} })
    registered: Optional[bool] = Field(default=None, description="""Whether the actor is known to the registry of agents and identities.""", json_schema_extra = { "linkml_meta": {'domain_of': ['Actor']} })
    owner: Optional[str] = Field(default=None, description="""The actor accountable.""", json_schema_extra = { "linkml_meta": {'domain_of': ['WorkDefinition', 'Actor', 'Dataset']} })
    title: Optional[str] = Field(default=None, description="""The actor's job title, as the directory holds it. Policy is written over roles derived from it.""", json_schema_extra = { "linkml_meta": {'domain_of': ['Actor']} })


class Capability(ConfiguredBaseModel):
    """
    An actor's standing to perform a step: the autonomy level it holds now and the evidence behind it. Permission comes from the authority systems; proven ability comes from outcomes in the record.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'annotations': {'namespace': {'tag': 'namespace', 'value': 'capability'}},
         'from_schema': 'https://example.org/work'})

    id: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['WorkDefinition',
                       'StepDefinition',
                       'AcceptanceCriterion',
                       'Actor',
                       'Capability',
                       'WorkRequest',
                       'TaskRecord',
                       'Action',
                       'WorkEvent',
                       'AutonomyChange',
                       'Gap',
                       'Confirmation',
                       'Dataset',
                       'Role',
                       'Grant',
                       'AccessPolicy',
                       'ApprovalRule',
                       'Customisation']} })
    actor: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Capability', 'TaskRecord', 'Action', 'WorkEvent', 'Grant'],
         'slot_uri': 'prov:wasAssociatedWith'} })
    step: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Capability', 'TaskRecord']} })
    autonomy_level: Optional[AutonomyLevel] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Capability', 'TaskRecord']} })
    evidence_count: Optional[int] = Field(default=None, ge=0, json_schema_extra = { "linkml_meta": {'domain_of': ['Capability']} })
    accepted_count: Optional[int] = Field(default=None, ge=0, json_schema_extra = { "linkml_meta": {'domain_of': ['Capability']} })
    lower_bound: Optional[float] = Field(default=None, description="""Wilson lower bound of the acceptance rate. Promotion compares this, not the raw rate.""", ge=0, le=1, json_schema_extra = { "linkml_meta": {'domain_of': ['Capability']} })


class WorkRequest(ConfiguredBaseModel):
    """
    A request for a kind of work, from a person or an agent, on someone's behalf.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'annotations': {'namespace': {'tag': 'namespace', 'value': 'request'}},
         'from_schema': 'https://example.org/work'})

    id: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['WorkDefinition',
                       'StepDefinition',
                       'AcceptanceCriterion',
                       'Actor',
                       'Capability',
                       'WorkRequest',
                       'TaskRecord',
                       'Action',
                       'WorkEvent',
                       'AutonomyChange',
                       'Gap',
                       'Confirmation',
                       'Dataset',
                       'Role',
                       'Grant',
                       'AccessPolicy',
                       'ApprovalRule',
                       'Customisation']} })
    work_definition: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['WorkRequest']} })
    requested_by: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['WorkRequest']} })
    on_behalf_of: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['WorkRequest', 'TaskRecord'], 'slot_uri': 'prov:actedOnBehalfOf'} })
    requested_at: Optional[datetime ] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['WorkRequest']} })
    channel: Optional[str] = Field(default=None, description="""Where the request came in, e.g. a chat assistant or a portal.""", json_schema_extra = { "linkml_meta": {'domain_of': ['WorkRequest']} })
    external_ref: Optional[str] = Field(default=None, description="""The record's identifier in the system that holds it, e.g. a ticket number.""", json_schema_extra = { "linkml_meta": {'domain_of': ['WorkRequest', 'TaskRecord']} })


class TaskRecord(ConfiguredBaseModel):
    """
    One step performed under a request. A task with no request is not a task: it is an orphan action, and fails validation by construction.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'annotations': {'namespace': {'tag': 'namespace', 'value': 'task'}},
         'class_uri': 'prov:Activity',
         'from_schema': 'https://example.org/work',
         'slot_usage': {'actor': {'name': 'actor', 'required': True},
                        'request': {'name': 'request', 'required': True},
                        'step': {'name': 'step', 'required': True}}})

    id: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['WorkDefinition',
                       'StepDefinition',
                       'AcceptanceCriterion',
                       'Actor',
                       'Capability',
                       'WorkRequest',
                       'TaskRecord',
                       'Action',
                       'WorkEvent',
                       'AutonomyChange',
                       'Gap',
                       'Confirmation',
                       'Dataset',
                       'Role',
                       'Grant',
                       'AccessPolicy',
                       'ApprovalRule',
                       'Customisation']} })
    request: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['TaskRecord', 'Action', 'WorkEvent', 'Grant']} })
    step: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['Capability', 'TaskRecord']} })
    actor: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['Capability', 'TaskRecord', 'Action', 'WorkEvent', 'Grant'],
         'slot_uri': 'prov:wasAssociatedWith'} })
    on_behalf_of: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['WorkRequest', 'TaskRecord'], 'slot_uri': 'prov:actedOnBehalfOf'} })
    autonomy_level: Optional[AutonomyLevel] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Capability', 'TaskRecord']} })
    started_at: Optional[datetime ] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['TaskRecord'], 'slot_uri': 'prov:startedAtTime'} })
    ended_at: Optional[datetime ] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['TaskRecord'], 'slot_uri': 'prov:endedAtTime'} })
    decision: Optional[Decision] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['TaskRecord']} })
    outcome: Optional[Outcome] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['TaskRecord']} })
    external_ref: Optional[str] = Field(default=None, description="""The record's identifier in the system that holds it, e.g. a ticket number.""", json_schema_extra = { "linkml_meta": {'domain_of': ['WorkRequest', 'TaskRecord']} })


class Action(ConfiguredBaseModel):
    """
    Something an actor did to a system, as observed in telemetry. Governed actions belong to a request; an action without one is the first kind of gap.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'annotations': {'namespace': {'tag': 'namespace', 'value': 'action'}},
         'class_uri': 'prov:Activity',
         'from_schema': 'https://example.org/work',
         'slot_usage': {'request': {'name': 'request', 'required': True}}})

    id: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['WorkDefinition',
                       'StepDefinition',
                       'AcceptanceCriterion',
                       'Actor',
                       'Capability',
                       'WorkRequest',
                       'TaskRecord',
                       'Action',
                       'WorkEvent',
                       'AutonomyChange',
                       'Gap',
                       'Confirmation',
                       'Dataset',
                       'Role',
                       'Grant',
                       'AccessPolicy',
                       'ApprovalRule',
                       'Customisation']} })
    actor: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Capability', 'TaskRecord', 'Action', 'WorkEvent', 'Grant'],
         'slot_uri': 'prov:wasAssociatedWith'} })
    target_system: Optional[str] = Field(default=None, description="""The system acted on.""", json_schema_extra = { "linkml_meta": {'domain_of': ['Action']} })
    operation: Optional[str] = Field(default=None, description="""What was done, in the target system's terms.""", json_schema_extra = { "linkml_meta": {'domain_of': ['Action']} })
    resource: Optional[str] = Field(default=None, description="""The thing acted on, in the target system's terms.""", json_schema_extra = { "linkml_meta": {'domain_of': ['Action']} })
    at: Optional[datetime ] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Action', 'WorkEvent', 'AutonomyChange']} })
    request: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['TaskRecord', 'Action', 'WorkEvent', 'Grant']} })
    source: Optional[str] = Field(default=None, description="""The system that reported this.""", json_schema_extra = { "linkml_meta": {'domain_of': ['Action', 'WorkEvent']} })


class Decision(ConfiguredBaseModel):
    """
    An authority decision on a step, taken outside the model that proposed the action.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'annotations': {'namespace': {'tag': 'namespace', 'value': 'decision'}},
         'from_schema': 'https://example.org/work'})

    effect: DecisionEffect = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['Decision', 'AccessPolicy']} })
    rule: Optional[str] = Field(default=None, description="""The rule that decided.""", json_schema_extra = { "linkml_meta": {'domain_of': ['Decision']} })
    decided_by: Optional[str] = Field(default=None, description="""The system or person that decided.""", json_schema_extra = { "linkml_meta": {'domain_of': ['Decision', 'Outcome', 'Confirmation']} })
    reason: Optional[str] = Field(default=None, description="""Why, in words an operator can read.""", json_schema_extra = { "linkml_meta": {'domain_of': ['Decision', 'WorkEvent', 'AutonomyChange', 'Confirmation']} })


class Outcome(ConfiguredBaseModel):
    """
    How a step turned out, judged against its acceptance criteria.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'annotations': {'namespace': {'tag': 'namespace', 'value': 'outcome'}},
         'from_schema': 'https://example.org/work'})

    status: OutcomeStatus = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['Outcome']} })
    decided_at: Optional[datetime ] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Outcome', 'Confirmation']} })
    decided_by: Optional[str] = Field(default=None, description="""The system or person that decided.""", json_schema_extra = { "linkml_meta": {'domain_of': ['Decision', 'Outcome', 'Confirmation']} })


class WorkEvent(ConfiguredBaseModel):
    """
    Something that happened to a request or a task. The one record every lens projects from: security (OCSF), operations (OpenTelemetry), analytics and agents (Ossie), and chat. Events are hash-chained.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'annotations': {'namespace': {'tag': 'namespace', 'value': 'event'}},
         'from_schema': 'https://example.org/work'})

    id: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['WorkDefinition',
                       'StepDefinition',
                       'AcceptanceCriterion',
                       'Actor',
                       'Capability',
                       'WorkRequest',
                       'TaskRecord',
                       'Action',
                       'WorkEvent',
                       'AutonomyChange',
                       'Gap',
                       'Confirmation',
                       'Dataset',
                       'Role',
                       'Grant',
                       'AccessPolicy',
                       'ApprovalRule',
                       'Customisation']} })
    kind: WorkEventKind = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['WorkEvent']} })
    at: Optional[datetime ] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Action', 'WorkEvent', 'AutonomyChange']} })
    request: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['TaskRecord', 'Action', 'WorkEvent', 'Grant']} })
    task: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['WorkEvent']} })
    actor: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Capability', 'TaskRecord', 'Action', 'WorkEvent', 'Grant'],
         'slot_uri': 'prov:wasAssociatedWith'} })
    reason: Optional[str] = Field(default=None, description="""Why, in words an operator can read.""", json_schema_extra = { "linkml_meta": {'domain_of': ['Decision', 'WorkEvent', 'AutonomyChange', 'Confirmation']} })
    source: Optional[str] = Field(default=None, description="""The system that reported this.""", json_schema_extra = { "linkml_meta": {'domain_of': ['Action', 'WorkEvent']} })
    via: Optional[str] = Field(default=None, description="""The surface an action was taken through, e.g. a chat card.""", json_schema_extra = { "linkml_meta": {'domain_of': ['WorkEvent']} })
    prev_hash: Optional[str] = Field(default=None, description="""Hash of the previous event in the chain.""", json_schema_extra = { "linkml_meta": {'domain_of': ['WorkEvent']} })
    hash: Optional[str] = Field(default=None, description="""Hash of this event and the previous hash.""", json_schema_extra = { "linkml_meta": {'domain_of': ['WorkEvent']} })


class AutonomyChange(ConfiguredBaseModel):
    """
    A promotion or demotion of a capability, with the evidence that justified it.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'annotations': {'namespace': {'tag': 'namespace', 'value': 'autonomy_change'}},
         'from_schema': 'https://example.org/work'})

    id: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['WorkDefinition',
                       'StepDefinition',
                       'AcceptanceCriterion',
                       'Actor',
                       'Capability',
                       'WorkRequest',
                       'TaskRecord',
                       'Action',
                       'WorkEvent',
                       'AutonomyChange',
                       'Gap',
                       'Confirmation',
                       'Dataset',
                       'Role',
                       'Grant',
                       'AccessPolicy',
                       'ApprovalRule',
                       'Customisation']} })
    capability: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['AutonomyChange']} })
    from_level: Optional[AutonomyLevel] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['AutonomyChange']} })
    to_level: Optional[AutonomyLevel] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['AutonomyChange']} })
    at: Optional[datetime ] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Action', 'WorkEvent', 'AutonomyChange']} })
    reason: Optional[str] = Field(default=None, description="""Why, in words an operator can read.""", json_schema_extra = { "linkml_meta": {'domain_of': ['Decision', 'WorkEvent', 'AutonomyChange', 'Confirmation']} })
    evidence: Optional[list[str]] = Field(default=None, description="""Identifiers of the records that justify this.""", json_schema_extra = { "linkml_meta": {'domain_of': ['AutonomyChange', 'Gap']} })
    confirmation: Optional[str] = Field(default=None, description="""The person's confirmation a promotion rests on. A demotion has none.""", json_schema_extra = { "linkml_meta": {'domain_of': ['AutonomyChange']} })


class Gap(ConfiguredBaseModel):
    """
    Something observed that does not fit the vocabulary, or fits with a required part missing. A gap is written in the same terms as its remedy.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'annotations': {'namespace': {'tag': 'namespace', 'value': 'gap'}},
         'from_schema': 'https://example.org/work'})

    id: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['WorkDefinition',
                       'StepDefinition',
                       'AcceptanceCriterion',
                       'Actor',
                       'Capability',
                       'WorkRequest',
                       'TaskRecord',
                       'Action',
                       'WorkEvent',
                       'AutonomyChange',
                       'Gap',
                       'Confirmation',
                       'Dataset',
                       'Role',
                       'Grant',
                       'AccessPolicy',
                       'ApprovalRule',
                       'Customisation']} })
    gap_kind: GapKind = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['Gap']} })
    subject: Optional[str] = Field(default=None, description="""Identifier of the thing the gap is about.""", json_schema_extra = { "linkml_meta": {'domain_of': ['Gap']} })
    evidence: Optional[list[str]] = Field(default=None, description="""Identifiers of the records that justify this.""", json_schema_extra = { "linkml_meta": {'domain_of': ['AutonomyChange', 'Gap']} })
    proposes: Optional[str] = Field(default=None, description="""The remedy, in the vocabulary's terms.""", json_schema_extra = { "linkml_meta": {'domain_of': ['Gap']} })


class Confirmation(ConfiguredBaseModel):
    """
    A person's decision on a proposed change: a repair, a declared policy or an autonomy promotion. Nothing proposed is applied without one. Bound to the proposal's content by a digest in its id, so a changed proposal needs a new confirmation. In a deployment, written by a person; a demo may write labelled stand-ins.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'annotations': {'namespace': {'tag': 'namespace', 'value': 'confirmation'}},
         'from_schema': 'https://example.org/work',
         'slot_usage': {'decided_at': {'name': 'decided_at', 'required': True},
                        'decided_by': {'name': 'decided_by', 'required': True}}})

    id: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['WorkDefinition',
                       'StepDefinition',
                       'AcceptanceCriterion',
                       'Actor',
                       'Capability',
                       'WorkRequest',
                       'TaskRecord',
                       'Action',
                       'WorkEvent',
                       'AutonomyChange',
                       'Gap',
                       'Confirmation',
                       'Dataset',
                       'Role',
                       'Grant',
                       'AccessPolicy',
                       'ApprovalRule',
                       'Customisation']} })
    change_kind: ChangeKind = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['Confirmation']} })
    verdict: Verdict = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['Confirmation']} })
    decided_by: str = Field(default=..., description="""The system or person that decided.""", json_schema_extra = { "linkml_meta": {'domain_of': ['Decision', 'Outcome', 'Confirmation']} })
    decided_at: datetime  = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['Outcome', 'Confirmation']} })
    reason: Optional[str] = Field(default=None, description="""Why, in words an operator can read.""", json_schema_extra = { "linkml_meta": {'domain_of': ['Decision', 'WorkEvent', 'AutonomyChange', 'Confirmation']} })


class Record(ConfiguredBaseModel):
    """
    A container for exchanging the record.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://example.org/work', 'tree_root': True})

    work_definitions: Optional[list[WorkDefinition]] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Record']} })
    actors: Optional[list[Actor]] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Record']} })
    capabilities: Optional[list[Capability]] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Record']} })
    requests: Optional[list[WorkRequest]] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Record']} })
    tasks: Optional[list[TaskRecord]] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Record']} })
    actions: Optional[list[Action]] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Record']} })
    events: Optional[list[WorkEvent]] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Record']} })
    changes: Optional[list[AutonomyChange]] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Record']} })
    gaps: Optional[list[Gap]] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Record']} })
    confirmations: Optional[list[Confirmation]] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Record']} })


class Dataset(ConfiguredBaseModel):
    """
    Data that people and agents ask to use.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://example.org/work/access'})

    id: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['WorkDefinition',
                       'StepDefinition',
                       'AcceptanceCriterion',
                       'Actor',
                       'Capability',
                       'WorkRequest',
                       'TaskRecord',
                       'Action',
                       'WorkEvent',
                       'AutonomyChange',
                       'Gap',
                       'Confirmation',
                       'Dataset',
                       'Role',
                       'Grant',
                       'AccessPolicy',
                       'ApprovalRule',
                       'Customisation']} })
    name: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['WorkDefinition',
                       'StepDefinition',
                       'Actor',
                       'Dataset',
                       'Role',
                       'Customisation'],
         'slot_uri': 'schema:name'} })
    platform: Optional[str] = Field(default=None, description="""The data platform holding the dataset.""", json_schema_extra = { "linkml_meta": {'domain_of': ['Dataset']} })
    classification: Classification = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['Dataset']} })
    domain: Optional[str] = Field(default=None, description="""The business domain accountable for the data.""", json_schema_extra = { "linkml_meta": {'domain_of': ['Dataset', 'AccessPolicy', 'ApprovalRule']} })
    owner: Optional[str] = Field(default=None, description="""The actor accountable.""", json_schema_extra = { "linkml_meta": {'domain_of': ['WorkDefinition', 'Actor', 'Dataset']} })


class Role(ConfiguredBaseModel):
    """
    A kind of person or agent, by job. Policy is written over roles, never over individuals.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://example.org/work/access'})

    id: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['WorkDefinition',
                       'StepDefinition',
                       'AcceptanceCriterion',
                       'Actor',
                       'Capability',
                       'WorkRequest',
                       'TaskRecord',
                       'Action',
                       'WorkEvent',
                       'AutonomyChange',
                       'Gap',
                       'Confirmation',
                       'Dataset',
                       'Role',
                       'Grant',
                       'AccessPolicy',
                       'ApprovalRule',
                       'Customisation']} })
    name: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['WorkDefinition',
                       'StepDefinition',
                       'Actor',
                       'Dataset',
                       'Role',
                       'Customisation'],
         'slot_uri': 'schema:name'} })
    department: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Role']} })


class Grant(ConfiguredBaseModel):
    """
    Standing access to a dataset, as held in an authority system.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://example.org/work/access'})

    id: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['WorkDefinition',
                       'StepDefinition',
                       'AcceptanceCriterion',
                       'Actor',
                       'Capability',
                       'WorkRequest',
                       'TaskRecord',
                       'Action',
                       'WorkEvent',
                       'AutonomyChange',
                       'Gap',
                       'Confirmation',
                       'Dataset',
                       'Role',
                       'Grant',
                       'AccessPolicy',
                       'ApprovalRule',
                       'Customisation']} })
    actor: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Capability', 'TaskRecord', 'Action', 'WorkEvent', 'Grant'],
         'slot_uri': 'prov:wasAssociatedWith'} })
    dataset: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Grant', 'AccessRequest']} })
    privilege: Optional[Privilege] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Grant', 'AccessRequest', 'AccessPolicy']} })
    held_in: Optional[str] = Field(default=None, description="""The authority system holding the grant, e.g. Veza or Immuta.""", json_schema_extra = { "linkml_meta": {'domain_of': ['Grant']} })
    granted_at: Optional[datetime ] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Grant']} })
    request: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['TaskRecord', 'Action', 'WorkEvent', 'Grant']} })
    last_used_at: Optional[datetime ] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Grant']} })


class AccessRequest(WorkRequest):
    """
    A request to use a dataset.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://example.org/work/access'})

    dataset: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Grant', 'AccessRequest']} })
    privilege: Optional[Privilege] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Grant', 'AccessRequest', 'AccessPolicy']} })
    justification: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['AccessRequest']} })
    duration_days: Optional[int] = Field(default=None, ge=1, json_schema_extra = { "linkml_meta": {'domain_of': ['AccessRequest']} })
    id: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['WorkDefinition',
                       'StepDefinition',
                       'AcceptanceCriterion',
                       'Actor',
                       'Capability',
                       'WorkRequest',
                       'TaskRecord',
                       'Action',
                       'WorkEvent',
                       'AutonomyChange',
                       'Gap',
                       'Confirmation',
                       'Dataset',
                       'Role',
                       'Grant',
                       'AccessPolicy',
                       'ApprovalRule',
                       'Customisation']} })
    work_definition: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['WorkRequest']} })
    requested_by: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['WorkRequest']} })
    on_behalf_of: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['WorkRequest', 'TaskRecord'], 'slot_uri': 'prov:actedOnBehalfOf'} })
    requested_at: Optional[datetime ] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['WorkRequest']} })
    channel: Optional[str] = Field(default=None, description="""Where the request came in, e.g. a chat assistant or a portal.""", json_schema_extra = { "linkml_meta": {'domain_of': ['WorkRequest']} })
    external_ref: Optional[str] = Field(default=None, description="""The record's identifier in the system that holds it, e.g. a ticket number.""", json_schema_extra = { "linkml_meta": {'domain_of': ['WorkRequest', 'TaskRecord']} })


class AccessPolicy(ConfiguredBaseModel):
    """
    Access declared once, by role and classification, and compiled into the authority systems. When a declared policy covers a request, the request need not exist.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://example.org/work/access'})

    id: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['WorkDefinition',
                       'StepDefinition',
                       'AcceptanceCriterion',
                       'Actor',
                       'Capability',
                       'WorkRequest',
                       'TaskRecord',
                       'Action',
                       'WorkEvent',
                       'AutonomyChange',
                       'Gap',
                       'Confirmation',
                       'Dataset',
                       'Role',
                       'Grant',
                       'AccessPolicy',
                       'ApprovalRule',
                       'Customisation']} })
    description: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['WorkDefinition',
                       'StepDefinition',
                       'AcceptanceCriterion',
                       'AccessPolicy',
                       'ApprovalRule'],
         'slot_uri': 'schema:description'} })
    role: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['AccessPolicy']} })
    domain: Optional[str] = Field(default=None, description="""The business domain accountable for the data.""", json_schema_extra = { "linkml_meta": {'domain_of': ['Dataset', 'AccessPolicy', 'ApprovalRule']} })
    max_classification: Optional[Classification] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['AccessPolicy']} })
    privilege: Optional[Privilege] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Grant', 'AccessRequest', 'AccessPolicy']} })
    effect: DecisionEffect = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['Decision', 'AccessPolicy']} })
    requires_approval: Optional[bool] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['StepDefinition', 'AccessPolicy']} })


class ApprovalRule(ConfiguredBaseModel):
    """
    Who must approve a request, and when. Declared once, compiled into the platform that holds the requests, and checked by the replay against what the platform actually did.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://example.org/work/access'})

    id: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['WorkDefinition',
                       'StepDefinition',
                       'AcceptanceCriterion',
                       'Actor',
                       'Capability',
                       'WorkRequest',
                       'TaskRecord',
                       'Action',
                       'WorkEvent',
                       'AutonomyChange',
                       'Gap',
                       'Confirmation',
                       'Dataset',
                       'Role',
                       'Grant',
                       'AccessPolicy',
                       'ApprovalRule',
                       'Customisation']} })
    description: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['WorkDefinition',
                       'StepDefinition',
                       'AcceptanceCriterion',
                       'AccessPolicy',
                       'ApprovalRule'],
         'slot_uri': 'schema:description'} })
    approver_kind: ApproverKind = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['ApprovalRule']} })
    approver_role: Optional[str] = Field(default=None, description="""When approver_kind is role: which role approves.""", json_schema_extra = { "linkml_meta": {'domain_of': ['ApprovalRule']} })
    min_classification: Optional[Classification] = Field(default=None, description="""Applies to datasets at or above this classification.""", json_schema_extra = { "linkml_meta": {'domain_of': ['ApprovalRule']} })
    domain: Optional[str] = Field(default=None, description="""The business domain accountable for the data.""", json_schema_extra = { "linkml_meta": {'domain_of': ['Dataset', 'AccessPolicy', 'ApprovalRule']} })


class Customisation(ConfiguredBaseModel):
    """
    Something a customer added to the platform instead of to the model. Retired, reverted, declared into the customer's model, replaced by an adapter, or kept with a reason.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://example.org/work/access'})

    id: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['WorkDefinition',
                       'StepDefinition',
                       'AcceptanceCriterion',
                       'Actor',
                       'Capability',
                       'WorkRequest',
                       'TaskRecord',
                       'Action',
                       'WorkEvent',
                       'AutonomyChange',
                       'Gap',
                       'Confirmation',
                       'Dataset',
                       'Role',
                       'Grant',
                       'AccessPolicy',
                       'ApprovalRule',
                       'Customisation']} })
    name: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['WorkDefinition',
                       'StepDefinition',
                       'Actor',
                       'Dataset',
                       'Role',
                       'Customisation'],
         'slot_uri': 'schema:name'} })
    customisation_kind: CustomisationKind = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['Customisation']} })
    host_table: Optional[str] = Field(default=None, description="""The platform table the customisation acts on.""", json_schema_extra = { "linkml_meta": {'domain_of': ['Customisation']} })
    executions_180d: Optional[int] = Field(default=None, ge=0, json_schema_extra = { "linkml_meta": {'domain_of': ['Customisation']} })
    last_executed_at: Optional[datetime ] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Customisation']} })
    plan: Optional[CleanupPlan] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Customisation']} })
    plan_reason: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Customisation']} })


class AccessRecord(Record):
    """
    The record, with the access profile.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://example.org/work/access', 'tree_root': True})

    roles: Optional[list[Role]] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['AccessRecord']} })
    datasets: Optional[list[Dataset]] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['AccessRecord']} })
    grants: Optional[list[Grant]] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['AccessRecord']} })
    policies: Optional[list[AccessPolicy]] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['AccessRecord']} })
    approval_rules: Optional[list[ApprovalRule]] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['AccessRecord']} })
    customisations: Optional[list[Customisation]] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['AccessRecord']} })
    work_definitions: Optional[list[WorkDefinition]] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Record']} })
    actors: Optional[list[Actor]] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Record']} })
    capabilities: Optional[list[Capability]] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Record']} })
    requests: Optional[list[WorkRequest]] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Record']} })
    tasks: Optional[list[TaskRecord]] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Record']} })
    actions: Optional[list[Action]] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Record']} })
    events: Optional[list[WorkEvent]] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Record']} })
    changes: Optional[list[AutonomyChange]] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Record']} })
    gaps: Optional[list[Gap]] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Record']} })
    confirmations: Optional[list[Confirmation]] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Record']} })


class ContosoAccessRequest(AccessRequest):
    """
    An access request at Contoso, which carries the cost centre that pays for the platform usage.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://example.org/contoso',
         'slot_usage': {'cost_centre': {'name': 'cost_centre', 'required': True}}})

    cost_centre: str = Field(default=..., description="""Declared from the platform's custom field u_cost_centre.""", json_schema_extra = { "linkml_meta": {'domain_of': ['ContosoAccessRequest']} })
    dataset: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Grant', 'AccessRequest']} })
    privilege: Optional[Privilege] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Grant', 'AccessRequest', 'AccessPolicy']} })
    justification: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['AccessRequest']} })
    duration_days: Optional[int] = Field(default=None, ge=1, json_schema_extra = { "linkml_meta": {'domain_of': ['AccessRequest']} })
    id: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['WorkDefinition',
                       'StepDefinition',
                       'AcceptanceCriterion',
                       'Actor',
                       'Capability',
                       'WorkRequest',
                       'TaskRecord',
                       'Action',
                       'WorkEvent',
                       'AutonomyChange',
                       'Gap',
                       'Confirmation',
                       'Dataset',
                       'Role',
                       'Grant',
                       'AccessPolicy',
                       'ApprovalRule',
                       'Customisation']} })
    work_definition: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['WorkRequest']} })
    requested_by: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['WorkRequest']} })
    on_behalf_of: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['WorkRequest', 'TaskRecord'], 'slot_uri': 'prov:actedOnBehalfOf'} })
    requested_at: Optional[datetime ] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['WorkRequest']} })
    channel: Optional[str] = Field(default=None, description="""Where the request came in, e.g. a chat assistant or a portal.""", json_schema_extra = { "linkml_meta": {'domain_of': ['WorkRequest']} })
    external_ref: Optional[str] = Field(default=None, description="""The record's identifier in the system that holds it, e.g. a ticket number.""", json_schema_extra = { "linkml_meta": {'domain_of': ['WorkRequest', 'TaskRecord']} })

    @field_validator('cost_centre')
    def pattern_cost_centre(cls, v):
        pattern=re.compile(r"^CC-[0-9]{4}$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.search(element):
                    err_msg = f"Invalid cost_centre format: {element}"
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.search(v):
            err_msg = f"Invalid cost_centre format: {v}"
            raise ValueError(err_msg)
        return v


class ContosoAccessPolicy(AccessPolicy):
    """
    Contoso's access policy, as the profile defines it.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://example.org/contoso'})

    id: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['WorkDefinition',
                       'StepDefinition',
                       'AcceptanceCriterion',
                       'Actor',
                       'Capability',
                       'WorkRequest',
                       'TaskRecord',
                       'Action',
                       'WorkEvent',
                       'AutonomyChange',
                       'Gap',
                       'Confirmation',
                       'Dataset',
                       'Role',
                       'Grant',
                       'AccessPolicy',
                       'ApprovalRule',
                       'Customisation']} })
    description: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['WorkDefinition',
                       'StepDefinition',
                       'AcceptanceCriterion',
                       'AccessPolicy',
                       'ApprovalRule'],
         'slot_uri': 'schema:description'} })
    role: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['AccessPolicy']} })
    domain: Optional[str] = Field(default=None, description="""The business domain accountable for the data.""", json_schema_extra = { "linkml_meta": {'domain_of': ['Dataset', 'AccessPolicy', 'ApprovalRule']} })
    max_classification: Optional[Classification] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['AccessPolicy']} })
    privilege: Optional[Privilege] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Grant', 'AccessRequest', 'AccessPolicy']} })
    effect: DecisionEffect = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['Decision', 'AccessPolicy']} })
    requires_approval: Optional[bool] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['StepDefinition', 'AccessPolicy']} })


class ContosoApprovalRule(ApprovalRule):
    """
    Contoso's approval rule. Can be limited to the financial year-end close, when finance data needs a second approver. That rule used to live in a platform script and acts once a year, which is why usage data alone says it is dead.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://example.org/contoso'})

    year_end_close_days: Optional[int] = Field(default=None, description="""If set, the rule applies only this many days before the financial year end (31 March).""", ge=1, le=31, json_schema_extra = { "linkml_meta": {'domain_of': ['ContosoApprovalRule']} })
    id: str = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['WorkDefinition',
                       'StepDefinition',
                       'AcceptanceCriterion',
                       'Actor',
                       'Capability',
                       'WorkRequest',
                       'TaskRecord',
                       'Action',
                       'WorkEvent',
                       'AutonomyChange',
                       'Gap',
                       'Confirmation',
                       'Dataset',
                       'Role',
                       'Grant',
                       'AccessPolicy',
                       'ApprovalRule',
                       'Customisation']} })
    description: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['WorkDefinition',
                       'StepDefinition',
                       'AcceptanceCriterion',
                       'AccessPolicy',
                       'ApprovalRule'],
         'slot_uri': 'schema:description'} })
    approver_kind: ApproverKind = Field(default=..., json_schema_extra = { "linkml_meta": {'domain_of': ['ApprovalRule']} })
    approver_role: Optional[str] = Field(default=None, description="""When approver_kind is role: which role approves.""", json_schema_extra = { "linkml_meta": {'domain_of': ['ApprovalRule']} })
    min_classification: Optional[Classification] = Field(default=None, description="""Applies to datasets at or above this classification.""", json_schema_extra = { "linkml_meta": {'domain_of': ['ApprovalRule']} })
    domain: Optional[str] = Field(default=None, description="""The business domain accountable for the data.""", json_schema_extra = { "linkml_meta": {'domain_of': ['Dataset', 'AccessPolicy', 'ApprovalRule']} })


class ContosoRecord(AccessRecord):
    """
    Contoso's record. Requests and policies are Contoso's own extensions of the profile's classes.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://example.org/contoso',
         'slot_usage': {'approval_rules': {'name': 'approval_rules',
                                           'range': 'ContosoApprovalRule'},
                        'policies': {'name': 'policies',
                                     'range': 'ContosoAccessPolicy'},
                        'requests': {'name': 'requests',
                                     'range': 'ContosoAccessRequest'}},
         'tree_root': True})

    roles: Optional[list[Role]] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['AccessRecord']} })
    datasets: Optional[list[Dataset]] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['AccessRecord']} })
    grants: Optional[list[Grant]] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['AccessRecord']} })
    policies: Optional[list[ContosoAccessPolicy]] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['AccessRecord']} })
    approval_rules: Optional[list[ContosoApprovalRule]] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['AccessRecord']} })
    customisations: Optional[list[Customisation]] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['AccessRecord']} })
    work_definitions: Optional[list[WorkDefinition]] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Record']} })
    actors: Optional[list[Actor]] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Record']} })
    capabilities: Optional[list[Capability]] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Record']} })
    requests: Optional[list[ContosoAccessRequest]] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Record']} })
    tasks: Optional[list[TaskRecord]] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Record']} })
    actions: Optional[list[Action]] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Record']} })
    events: Optional[list[WorkEvent]] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Record']} })
    changes: Optional[list[AutonomyChange]] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Record']} })
    gaps: Optional[list[Gap]] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Record']} })
    confirmations: Optional[list[Confirmation]] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['Record']} })


# Model rebuild
# see https://pydantic-docs.helpmanual.io/usage/models/#rebuilding-a-model
WorkDefinition.model_rebuild()
StepDefinition.model_rebuild()
AcceptanceCriterion.model_rebuild()
Actor.model_rebuild()
Capability.model_rebuild()
WorkRequest.model_rebuild()
TaskRecord.model_rebuild()
Action.model_rebuild()
Decision.model_rebuild()
Outcome.model_rebuild()
WorkEvent.model_rebuild()
AutonomyChange.model_rebuild()
Gap.model_rebuild()
Confirmation.model_rebuild()
Record.model_rebuild()
Dataset.model_rebuild()
Role.model_rebuild()
Grant.model_rebuild()
AccessRequest.model_rebuild()
AccessPolicy.model_rebuild()
ApprovalRule.model_rebuild()
Customisation.model_rebuild()
AccessRecord.model_rebuild()
ContosoAccessRequest.model_rebuild()
ContosoAccessPolicy.model_rebuild()
ContosoApprovalRule.model_rebuild()
ContosoRecord.model_rebuild()
