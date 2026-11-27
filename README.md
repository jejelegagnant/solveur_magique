# Solveur Magique *(Working Codename)*

> **Swiss Shift-Scheduling Optimization SaaS — Requirement-Driven Development (RDD) Repository**
>
> *Note: **Solveur Magique** is a working engineering codename (`solveur_magique`); the final commercial brand name is TBD. Internal engineering and requirements documentation is maintained in English while preserving official Swiss legal and operational terminology (e.g., LTr, OLT 2, L-GAV, CCT, nLPD, pensum, pouliste, doublure). Commercial/marketing materials will be authored later in French (and German).*

---

## Executive Summary

**Solveur Magique** is a lightweight, 100% Swiss-hosted constraint-programming (CP-SAT) shift-scheduling companion for small and medium-sized teams (5–35 employees) in the Swiss care, social, hospitality, and service industries.

Rather than forcing establishments to replace legacy ERPs or payroll systems, V1.0.0 sits alongside existing grid-based ERPs: managers define shifts, staff contractual percentages (*pensums*), legal presets, hard absences, and soft preferences; the CP-SAT engine computes fair, legally compliant schedules with human-readable conflict diagnostics; and managers export ready-to-use **Excel (`.xlsx`), CSV, PDF, or iCal** outputs matching their ERP's shift codes.

---

## Requirement-Driven Development (RDD) Documentation Index

Every artifact in this repository follows strict forward and backward traceability:

```
Stakeholder Needs (NEED-XX)
   └──► Strategic Goals (GOAL-XX)
           └──► User Personas & Use Cases (UC-XX)
                   └──► System Overview & PlantUML Flows
                           └──► V1.0.0 Functional (FR-XXX) & Non-Functional (NFR-XXX) Requirements
                                   └──► System Architecture, Data Model & Tech Stack ADRs (ADR-XXX)
```

| # | Document | Purpose |
| :-: | :--- | :--- |
| 01 | [Needs Discovery & Domain Glossary](docs/01-needs-discovery.md) | Synthesized field interview findings (anonymized), Swiss market & legal viability analysis, domain glossary, and formal stakeholder needs (`NEED-01`–`NEED-16`). |
| 02 | [Project Vision & Goals](docs/02-vision-and-goals.md) | Product vision, measurable V1.0.0 commercial launch goals (`GOAL-01`–`GOAL-07`), target verticals, pricing tiers, and strict V1.0.0 vs. Post-V1 scope boundaries. |
| 03 | [Users, Personas & Use Cases](docs/03-users-and-use-cases.md) | Detailed user personas and full behavioral scenarios (`UC-01`–`UC-12`) including main, alternative, and error flows. |
| 04 | [System Overview](docs/04-system-overview.md) | System boundaries, external ERP/billing interfaces, end-to-end information flow, and nLPD-compliant acquisition lifecycle. |
| 05 | [V1.0.0 Functional & Non-Functional Requirements](docs/05-requirements-v1.md) | Complete commercial-launch requirements catalog (`FR-001`–`FR-048`, `NFR-001`–`NFR-025`), MoSCoW prioritization, acceptance criteria, and Requirements Traceability Matrix (RTM). |
| 06 | [System Architecture & Tech Stack](docs/06-architecture-and-tech-stack.md) | C4 container architecture, data model, solver pipeline, 100% Swiss sovereign deployment topology, scaling economics, and Architecture Decision Records (`ADR-001`–`ADR-007`). |

---

## PlantUML Diagrams

All system and architecture diagrams are stored as version-controlled PlantUML (`.puml`) files under [`docs/diagrams/`](docs/diagrams/):

| Diagram | Source File | Description |
| :--- | :--- | :--- |
| **Use Case Diagram** | [`docs/diagrams/use-case-diagram.puml`](docs/diagrams/use-case-diagram.puml) | Actors, V1.0.0 system boundary, `UC-01`–`UC-12`, and `<<include>>` / `<<extend>>` relationships. |
| **Information Flow** | [`docs/diagrams/information-flow.puml`](docs/diagrams/information-flow.puml) | End-to-end swimlane data flow from scheduling inputs through CP-SAT optimization, pinning, and ERP-mapped Excel export. |
| **Sandbox-to-B2B Funnel** | [`docs/diagrams/sandbox-to-b2b-flow.puml`](docs/diagrams/sandbox-to-b2b-flow.puml) | nLPD-compliant acquisition sequence from Zero-PII Anonymous Sandbox to *Pack Direction* and institutional activation. |
| **Container Architecture** | [`docs/diagrams/architecture-container.puml`](docs/diagrams/architecture-container.puml) | C4 Container view (React SPA, Caddy, FastAPI, Redis, OR-Tools CP-SAT workers, PostgreSQL 16, Swiss Backup S3). |
| **Solver Pipeline Sequence** | [`docs/diagrams/solver-pipeline-sequence.puml`](docs/diagrams/solver-pipeline-sequence.puml) | Asynchronous solve lifecycle, timeout enforcement, and `SufficientAssumptionsForInfeasibility` diagnostic loop. |
| **Domain Data Model (ERD)** | [`docs/diagrams/data-model.puml`](docs/diagrams/data-model.puml) | Multi-tenant relational schema with PostgreSQL Row-Level Security (RLS) boundaries. |
| **Swiss Cloud Deployment** | [`docs/diagrams/deployment-swiss-cloud.puml`](docs/diagrams/deployment-swiss-cloud.puml) | 100% Swiss sovereign Infomaniak Geneva/Zurich deployment and scale-out topology (10 → 100 → 1,000 teams). |

### Rendering PlantUML Locally

To render or preview `.puml` diagrams:
- **VS Code**: Install the `jebbs.plantuml` extension and press `Alt+D` on any `.puml` file.
- **CLI** (requires Java + PlantUML JAR or `plantuml` package):
  ```bash
  plantuml -tsvg docs/diagrams/*.puml
  ```

---

## Privacy & Anonymization Notice

All real-world scheduling insights referenced in `docs/01-needs-discovery.md` and `docs/03-users-and-use-cases.md` have been strictly anonymized prior to commit. Every institution name, team lead, and staff member referenced in the scenarios is fictional.
