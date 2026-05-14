---
type: banned-vague-taxonomy
description: "Generic terms that cannot satisfy visual-spec specificity unless qualified by domain context."
version: 1.0
---

# Banned Vague Taxonomy

## Standalone entity terms (must be qualified)

- Item
- Thing
- Object
- Element
- Entry
- Record
- User
- Owner
- Person
- Member
- Agent
- Status
- State
- Condition
- Phase
- Stage
- Detail
- Summary
- Overview
- Info
- Data
- Priority
- Severity
- Importance
- Level
- Queue
- Lane
- List
- Stream
- Feed
- Event
- Action
- Update
- Activity
- Task
- Job
- Work
- Assignment
- Asset
- Resource
- Property
- Group
- Team
- Department
- Org
- Category
- Type
- Kind
- Class

## Allowed forms

- Banned standalone: "Alert" is too generic.
- Allowed qualified: "Detector-Generated Alert", "P0/P1/P2/P3 Severity Alert", and "EDR-CrowdStrike Alert".
- Banned standalone: "Queue" is too generic.
- Allowed qualified: "SOC Escalation Queue", "ACH Return Queue", and "Radiology Read Queue".
- Banned standalone: "Record" is too generic.
- Allowed qualified: "Stripe Dispute Record", "FHIR Encounter Record", and "Warehouse Lot Record".

## Allowed domain-natural terms

- Incident
- Promise to Pay
- Adverse Event
- Reconciliation Run
- Investor Briefing
- Onboarding Cohort
- Chargeback
- Prior Authorization
- Pull Request
- Deployment
- KYC Review
- Entitlement

These terms are allowed because they are intrinsically domain-specific in ordinary professional use. They still need source grounding from the brief when used as declared specificity items.

## Standalone workflow verbs (must be qualified)

- Edit
- Update
- Save
- Delete
- Remove
- View
- See
- Open
- Close
- Click
- Tap
- Select
- Choose
- Add
- Create
- New
- Make
- Submit
- Send
- Confirm
- OK
- Cancel

## Allowed workflow verbs

- Domain-specific: "Triage", "Escalate", "Suppress", "Dispute", "Sign-off", "Promote", "Materialize", "Reconcile", "Apportion", "Ingest", "Strike", and "Provision".
- Qualified generic: "Send dunning email", "Submit Form 10-K", "Save customer-segment definition", "Close P1 incident", and "Create Okta SCIM mapping".
- Workflow verbs are acceptable when the verb plus object names a real action a user performs in the project domain.

## Scoring impact

Each declared specificity item with a banned standalone term scores 0 on term-specificity unless explicitly qualified. Qualification must name a domain object, system, severity scale, regulatory form, workflow state, or audience-visible artifact that is grounded in the brief. A term does not become specific just because it is capitalized or placed in a product-sounding phrase.
