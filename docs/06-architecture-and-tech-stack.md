# 06 — System Architecture & Tech Stack (V1.0.0)

> **Traceability**: Translates the V1.0.0 Functional (`FR-001`–`FR-048`) and Non-Functional (`NFR-001`–`NFR-025`) requirements in [`docs/05-requirements-v1.md`](05-requirements-v1.md) into a concrete, lean, 100% Swiss-hosted system architecture engineered for solo/small-team delivery and >90% unit gross margin.

---

## 1. Architectural Style & Guiding Principles

**Chosen Pattern**: **Modular Monolith API + Decoupled Asynchronous CP-SAT Worker Pool**.

Why this pattern fits V1.0.0:
- **Velocity without distributed-systems tax**: A single well-structured FastAPI backend with strict domain module boundaries (`auth`, `tenants`, `scheduling`, `legal_rules`, `exports`, `billing`) avoids microservice operational overhead while keeping code cleanly separable.
- **CPU isolation for NP-hard solves (`NFR-002`, `NFR-003`)**: Constraint programming is CPU-intensive. Offloading `solver_core` to dedicated Redis-backed background worker processes ensures interactive grid edits and web requests stay `< 200ms` (`NFR-004`) even during end-of-month burst spikes.
- **Pure-Python Solver Core (`NFR-020`)**: `solver_core` has zero dependency on FastAPI or SQLAlchemy—it accepts immutable Pydantic input models and returns deterministic schedule/conflict outputs, allowing standalone benchmarking, Hypothesis property testing (`NFR-019`), and independent horizontal scaling to dedicated compute nodes.
- **Sovereign Privacy by Construction (`NFR-006`–`NFR-009`)**: Every stateful component (API, workers, PostgreSQL, Redis, S3 backups, SMTP, GlitchTip) runs inside ISO 27001 Swiss infrastructure (Infomaniak Geneva/Zurich) outside the US CLOUD Act, reinforced by PostgreSQL Row-Level Security (RLS).

---

## 2. Architecture Diagrams (PlantUML)

| Diagram | Source | Scope |
| :--- | :--- | :--- |
| **Container Architecture** | [`docs/diagrams/architecture-container.puml`](diagrams/architecture-container.puml) | C4 Container view showing SPA, Caddy TLS proxy, FastAPI Modular Monolith, Redis, OR-Tools CP-SAT Worker Pool, PostgreSQL 16 (RLS), Infomaniak Swiss Backup S3, and external billing/mail/ERP boundaries. |
| **Solver Pipeline Sequence** | [`docs/diagrams/solver-pipeline-sequence.puml`](diagrams/solver-pipeline-sequence.puml) | Async job lifecycle, tier timeout enforcement, `SufficientAssumptionsForInfeasibility` diagnostic core extraction, SSE/polling status stream, and `.xlsx` export. |
| **Domain Data Model (ERD)** | [`docs/diagrams/data-model.puml`](diagrams/data-model.puml) | Multi-tenant relational schema (`Organization` → `Team` → `ShiftTemplate` / `Employee` / `SchedulePeriod` → `AvailabilityRequest` / `ShiftAssignment` / `SolverJob` / `ExportMappingProfile` / `AuditLog`). |
| **Swiss Cloud Deployment** | [`docs/diagrams/deployment-swiss-cloud.puml`](diagrams/deployment-swiss-cloud.puml) | Sovereign Infomaniak Geneva/Zurich Docker topology at launch (`~CHF 45.41/mo`) and clear scale-out stages (`100` teams and `1,000` teams). |

---

## 3. Recommended Tech Stack (V1.0.0)

| Layer | Technology Choice | Key Libraries / Components | Requirements Fulfilled |
| :--- | :--- | :--- | :--- |
| **Frontend SPA** | **React 19 + TypeScript + Vite** | Tailwind CSS, TanStack Query, TanStack Virtual (fast grid scrolling), `react-i18next` (`fr-CH`, `de-CH`, `en`), Lucide icons | `FR-034`–`FR-036`, `FR-048`, `NFR-004`, `NFR-014`, `NFR-015` |
| **Backend API** | **Python 3.12 + FastAPI** | Pydantic v2, SQLAlchemy 2.0 (async `psycopg3`), Alembic, Uvicorn/Gunicorn | `FR-001`–`FR-048`, `NFR-004`, `NFR-025` |
| **Constraint Solver** | **Google OR-Tools (`cp_model` / CP-SAT)** | Apache 2.0 C++ native solver via Python bindings, `SufficientAssumptionsForInfeasibility`, `holidays` (Swiss cantonal calendar) | `FR-006`, `FR-022`–`FR-031`, `NFR-001`, `NFR-002`, `NFR-019`, `NFR-020` |
| **Async Task Queue** | **Redis 7 + Dramatiq** *(or Celery)* | Dedicated solver queue (`solver_fast` for Free 5s, `solver_paid` for 15–30s), SSE/WebSocket progress pub-sub | `FR-027`, `NFR-002`, `NFR-003`, `NFR-018` |
| **Primary Database** | **PostgreSQL 16** | Row-Level Security (`RLS`), JSONB (shift segments, versioned legal rule snapshots, conflict payloads), `pg_dump`/WAL-G | `FR-004`, `FR-026`, `FR-047`, `NFR-007`, `NFR-017` |
| **Export & PDF Engine** | **Python Export Service** | `openpyxl` (formatted `.xlsx` with live formulas), `WeasyPrint` (printable schedule & 2-page *Pack Direction* PDFs), `icalendar` (`.ics` with `zoneinfo` `Europe/Zurich`), stdlib `csv` | `FR-039`–`FR-044`, `NFR-005`, `NFR-024` |
| **Authentication** | **Sovereign Self-Hosted Auth** | `argon2-cffi`, `PyJWT` / signed `HttpOnly` sessions, time-limited HMAC magic links for Pro Employee Wish Portal | `FR-001`–`FR-004`, `FR-021`, `NFR-006`, `NFR-008` |
| **Billing & Invoicing** | **Stripe Switzerland + `qrbill`** | Stripe SDK (CHF cards + TWINT + webhooks), Python `qrbill` (ISO 20022 Swiss QR-Invoice SVG/PDF) | `FR-005`, `FR-045`, `FR-046` |
| **Reverse Proxy & TLS** | **Caddy 2** | Automatic Let's Encrypt TLS 1.3, HSTS, strict CSP headers, rate limiting, static SPA serving | `NFR-008`, `NFR-012` |
| **Sovereign Hosting** | **Infomaniak VPS Cloud / Public Cloud (Geneva/Zurich)** | Docker Compose (launch), Infomaniak Swiss Backup S3 (encrypted WAL/snapshots), Infomaniak SMTP relay | `NFR-006`, `NFR-016`, `NFR-017`, `NFR-021`, `NFR-022` |
| **Testing, CI/CD & Observability** | **GitHub Actions + Pytest + Prometheus** | `pytest`, `hypothesis` (legal invariant fuzzing), `playwright` (E2E grid), `ruff` + `mypy` + `import-linter`, Prometheus/Grafana + self-hosted **GlitchTip** (zero-PII Sentry-compatible) | `NFR-012`, `NFR-019`, `NFR-020`, `NFR-023` |

---

## 4. Proposed Repository Code Layout (Future Implementation Reference)

```text
solveur_magique/
├── docs/                           # RDD specification & PlantUML diagrams (current)
├── backend/
│   ├── app/
│   │   ├── api/                    # FastAPI routers (sandbox, teams, schedules, exports, billing)
│   │   ├── core/                   # Config, sovereign auth, RLS session context, i18n
│   │   ├── models/                 # SQLAlchemy 2.0 ORM + Alembic migrations
│   │   ├── schemas/                # Pydantic v2 request/response DTOs
│   │   ├── services/               # Business services (pack_direction, exports, billing, rollover)
│   │   └── workers/                # Dramatiq/Celery task definitions & Redis pub-sub
│   ├── solver_core/                # PURE PYTHON CP-SAT engine (zero FastAPI/ORM imports)
│   │   ├── model_builder.py        # Binary variables, shifts, doublures, pouliste slack
│   │   ├── legal_presets.py        # LTr, OLT 2, L-GAV, CCT constraint encoders
│   │   ├── objective.py            # Soft wishes, rolling equity, hour-balance, stability
│   │   └── explainer.py            # SufficientAssumptionsForInfeasibility -> i18n conflict cards
│   └── tests/                      # Unit, Hypothesis legal-invariant, benchmark & API tests
├── frontend/
│   └── src/
│       ├── features/grid/          # ERP-familiar monthly matrix grid + cell pinning
│       ├── features/setup/         # Shift templates, coverage matrix, Swiss presets, staff
│       ├── features/portal/        # Pro-tier mobile Employee Wish Submission view
│       ├── features/billing/       # Pack Direction wizard, Stripe & Swiss QR-Bill checkout
│       └── i18n/                   # fr-CH, de-CH, en translation bundles
└── infra/
    ├── docker-compose.yml          # Single-node launch stack (Infomaniak VPS Cloud)
    ├── Caddyfile                   # TLS 1.3 + CSP + rate limiting
    └── backup/                     # Encrypted PostgreSQL WAL -> Infomaniak Swiss Backup S3
```

---

## 5. Architecture Decision Records (`ADR-001`–`ADR-007`)

### `ADR-001` — Google OR-Tools CP-SAT over Timefold Solver
- **Status**: Accepted
- **Context**: V1.0.0 needs an open-source, commercially permissive shift-scheduling solver capable of handling 5–60 staff with hard Swiss labor rules, soft fairness preferences, and infeasibility explanations under a CHF 50/mo launch server budget.
- **Decision**: Select **Google OR-Tools CP-SAT** (Apache 2.0).
- **Rationale**:
  - 100% free Apache 2.0 license with zero Enterprise paywalls (unlike Timefold's paid Enterprise features).
  - Native C++ core invoked directly from Python FastAPI workers with low idle RAM footprint (vs. Timefold's JVM overhead even via Python bindings).
  - Built-in `SufficientAssumptionsForInfeasibility` enables exact minimal conflict-core extraction (`FR-030`).
- **Trade-off**: Non-linear fairness penalties require piecewise linear approximation in CP-SAT, which is straightforward for discrete monthly preference counts.

### `ADR-002` — Predefined Discrete Shifts over Continuous Hour-by-Hour Granularity (V1.0.0)
- **Status**: Accepted
- **Context**: Allowing arbitrary hour-by-hour headcount demands without predefined shift templates was considered early on.
- **Decision**: Restrict V1.0.0 strictly to **predefined discrete shift templates** (including split shifts and custom `SDE` events).
- **Rationale**: Academic benchmarks (ICAPS 2026 CASP:ER) show continuous 30–60 minute formulations explode to ~180k variables and ~350k constraints with 36%–99% optimality gaps after 600s, whereas discrete shift models solve typical Swiss SME teams in `< 2s` (`NFR-001`). Continuous demand decomposition is deferred to V2.0 as a shift-candidate generator pre-pass.

### `ADR-003` — 100% Swiss Sovereign Hosting (Infomaniak) over Lean EU/US Managed Services
- **Status**: Accepted
- **Context**: Option A ("Lean EU": Hetzner DE + Supabase Pro EU ~CHF 30/mo) costs ~CHF 15/mo less at launch than Option B ("100% Swiss Sovereign": Infomaniak Geneva/Zurich ~CHF 45.41/mo).
- **Decision**: Host **100%** of compute, database, backups, auth, and error tracking on **Infomaniak (Geneva/Zurich)**, scaling PostgreSQL to **Exoscale Managed HA (CH)** at 1,000+ teams.
- **Rationale**: Supabase is a US-incorporated entity subject to the US CLOUD Act. Under Swiss `nLPD` (personal fines up to CHF 250k), guaranteeing *"100% Swiss ISO 27001 hosting, zero US CLOUD Act subprocessors"* is a decisive B2B sales moat that pays back the CHF 15/mo delta with the very first paying team.

### `ADR-004` — Modular Monolith + Async Worker Queue over Microservices
- **Status**: Accepted
- **Context**: A lean founder/small team needs rapid V1.0.0 iteration while isolating CPU-heavy optimization jobs from web latency.
- **Decision**: Build a single **FastAPI Modular Monolith** paired with **Redis + Dramatiq/Celery workers** running the decoupled `solver_core` package.
- **Rationale**: Keeps deployment to one Docker Compose file at launch (`NFR-021`, `NFR-022`) while enabling immediate horizontal scale-out by spinning up dedicated solver worker VPS nodes once team volume reaches 100+.

### `ADR-005` — Companion Excel/CSV Export Bridge over Direct ERP API Integration (V1.0.0)
- **Status**: Accepted
- **Context**: Target establishments use fragmented legacy ERPs (Polypoint PEP, Abacus AbaPlan, Lobos, Bexio, Crésus, raw Excel) whose APIs require costly partner certifications or institutional IT projects.
- **Decision**: Ship V1.0.0 with a rich, configurable **Excel (`.xlsx`) & CSV export bridge** (preserving exact ERP shift codes, formulas, flat import rows, and *pouliste* gap lists) rather than live ERP APIs.
- **Rationale**: Delivers immediate day-one value with zero IT gatekeepers (`GOAL-04`). Direct bidirectional ERP connectors can be prioritized in V2.0 based on actual paying-customer ERP distribution.

### `ADR-006` — Zero-PII Anonymous Sandbox + PostgreSQL RLS for `nLPD` Compliance
- **Status**: Accepted
- **Context**: Managers want to try the tool immediately, but inputting real employee names or medical absence notes without institutional approval exposes them personally under `nLPD`.
- **Decision**: Combine a **Zero-PII Anonymous Sandbox** (`FR-001`), schema-level omission of medical free-text (`FR-014`), and **PostgreSQL Row-Level Security (RLS)** (`NFR-007`) bound to `app.current_org_id` per transaction.
- **Rationale**: Eliminates legal friction at trial stage and provides defense-in-depth multi-tenant isolation at database engine level.

### `ADR-007` — Dual Swiss Payment Stack (Stripe CHF + Native Swiss QR-Bill)
- **Status**: Accepted
- **Context**: Independent SMEs prefer instant card/TWINT checkout, whereas Swiss care foundations and EMS institutions frequently refuse corporate credit cards and require invoice-based accounting.
- **Decision**: Integrate **Stripe Switzerland** (CHF cards/TWINT) alongside native **ISO 20022 Swiss QR-Bill** PDF generation (`qrbill`) for annual institutional plans.
- **Rationale**: Removes the #1 procurement blocker in Swiss social foundations while saving Stripe's `2.9% + CHF 0.30` transaction fee on annual B2B renewals.

---

## 6. Infrastructure Scaling & FinOps Roadmap

Aligned with Little's Law burst modeling (`NFR-003`) and launch cost ceilings (`NFR-022`):

| Scale Stage | Active Teams | Concurrent Peak Solves | Swiss Sovereign Topology | Est. Monthly Infra Cost | Unit Gross Margin (est.) |
| :--- | :---: | :---: | :--- | :---: | :---: |
| **Stage 1 — V1.0.0 Launch** | `10` teams (~80 staff) | `0.01` | **1× Infomaniak VPS Cloud** (2 vCPU / 6 GB RAM / 100 GB SSD, Geneva/Zurich) running Caddy + FastAPI + Worker + PostgreSQL 16 + Redis + Swiss Backup S3 + Infomaniak Mail/Domain | **CHF 45.41 / mo** *(CHF 300 Public Cloud launch credit available)* | **> 90%** *(Break-even at 1–2 paid teams)* |
| **Stage 2 — Growth** | `100` teams (~1,000 staff) | `0.12` | **2× Infomaniak VPS Cloud**: Node 1 (Caddy + FastAPI + PostgreSQL + Redis), Node 2 (Dedicated CP-SAT Worker Pool) + WAL-G to Swiss Backup S3 + GlitchTip/Prometheus | **~CHF 109 / mo** | **> 96%** |
| **Stage 3 — Scale** | `1,000` teams (~12,000 staff) | `1.25` *(5.0 at 4k total incl. Free)* | **2× Infomaniak Web/API Nodes** + **1–2× Dedicated 6–8 vCPU Solver Nodes** + **Exoscale Managed PostgreSQL Business-8 HA (Geneva/Zurich)** + Swiss Backup S3 | **~CHF 624 / mo** | **> 98%** |
