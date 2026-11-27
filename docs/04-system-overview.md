# 04 — System Overview (Use Case & Information Flow)

> **Traceability**: Visualizes the system boundary, external interfaces, actors (`docs/03-users-and-use-cases.md`), and end-to-end data flows supporting `NEED-01`–`NEED-16`. All diagrams are maintained as standard PlantUML sources under [`docs/diagrams/`](diagrams/).

---

## 1. System Boundary & External Interfaces

**Solveur Magique (V1.0.0)** operates as a **standalone, 100% Swiss-hosted scheduling companion** that bridges human planning inputs and legacy institutional ERPs via structured file exports—avoiding intrusive ERP migrations while guaranteeing mathematical validity and `nLPD` data sovereignty.

| External Entity / System | Interface Direction | Data Exchanged | Purpose |
| :--- | :--- | :--- | :--- |
| **Team Manager / SME Owner** | Bidirectional (HTTPS Web UI) | Shift templates, staff pensums, absences, soft wishes, pinned cells ↔ Interactive monthly grid, conflict diagnostics, downloadable files | Primary scheduling workflow (`UC-01`–`UC-11`). |
| **Institution Director** | Bidirectional (HTTPS / PDF) | *Pack Direction* PDF, `nLPD` DPA acceptance, billing profile ↔ Subscription confirmation, Swiss QR-Bill PDF | Institutional B2B sign-off and compliance (`UC-11`). |
| **Staff Member** *(Pro/Business)* | Bidirectional (HTTPS Mobile Web) | Tokenized wish link ↔ Hard vacation requests, weighted soft preferences, published iCal/PDF | Self-service wish submission (`UC-12`). |
| **Legacy ERP / Payroll** *(Polypoint, Abacus, Bexio, Crésus, Excel)* | Outbound File Bridge (`.xlsx`, `.csv`) | ERP-mapped shift codes (`MC1`, `V`, `X`, `SDE`), flat normalized rows, *pouliste* gap list | Manual fast transcription or automated ERP import (`UC-10`). |
| **Stripe Switzerland** | Bidirectional (HTTPS API / Webhooks) | Checkout session (CHF / TWINT) ↔ Payment confirmation, invoice events | Self-serve card/TWINT subscriptions (`UC-11`). |
| **Swiss Banking (QR-Bill)** | Outbound PDF / Manual or Camt.054 Reconciliation | ISO 20022 Swiss QR-Invoice with structured reference | Annual institutional invoicing (`UC-11`). |
| **Swiss Transactional Mail (Infomaniak SMTP)** | Outbound (TLS SMTP) | Wish-collection links, published schedule notices, QR-Bill PDFs | Notification delivery within Swiss infrastructure (`UC-11`, `UC-12`). |

---

## 2. System Use Case Diagram (PlantUML)

**Source**: [`docs/diagrams/use-case-diagram.puml`](diagrams/use-case-diagram.puml)

Highlights:
- Clearly separates **primary human actors** (Team Manager, SME Owner inheriting Manager + Director capabilities, Institution Director, Staff Member) from **external systems** (Legacy ERP, Billing/Stripe & Swiss QR, Swiss Email Service).
- Explicitly marks higher-tier capability gating (`UC-12` Pro/Business Employee Wish Portal).
- Models key behavioral dependencies:
  - `UC-06` (*Generate Optimized Schedule*) `<<include>>`s Swiss legal validation (`UC-03`) and `<<extend>>`s into `UC-07` (*Diagnose Infeasible Constraints*) when no feasible assignment exists.
  - `UC-08` (*Pin & Re-Optimize*) `<<include>>`s `UC-06`.
  - `UC-01` (*Anonymous Sandbox*) `<<extend>>`s into `UC-11` (*Pack Direction & Upgrade*) upon successful evaluation.

---

## 3. End-to-End Information Flow (PlantUML)

**Source**: [`docs/diagrams/information-flow.puml`](diagrams/information-flow.puml)

The scheduling data pipeline is strictly structured into **five deterministic stages** so every decision is auditable and reversible:

1. **Stage 1 — Structured Input & Privacy Boundary**:
   - Collects shift templates (ERP codes, split intervals, breaks), cantonal holiday calendar, staff profiles (`%` pensum, prior *solde d'heures*, *doublure* pairs), hard absences (`V` + automatic adjacent weekend buffers, fixed `SDE`), and unlimited weighted soft preferences.
   - Enforces Zero-PII pseudonymization in Sandbox mode and rejects/omits sensitive medical free-text fields across all tiers (`nLPD` data minimization).
2. **Stage 2 — Validation & Asynchronous Dispatch**:
   - Validates structural integrity (e.g., break minimums, valid shift codes) and dispatches a self-contained JSON problem snapshot to the Redis task queue with tier-specific CPU timeout caps (`5s` / `15s` / `30s`).
3. **Stage 3 — CP-SAT Optimization & Diagnostics**:
   - Builds the discrete binary assignment model ($x_{e,d,s} \in \{0,1\}$) incorporating hard legal rules (`LTr` / `OLT 2` / `L-GAV` / `CCT`), hard coverage, pinned cells, optional *pouliste* slack variables, and the multi-term soft objective (wish weights × rolling multi-month equity + hour-balance proximity + stability).
   - If **Optimal/Feasible**: emits the schedule matrix, daily coverage totals, projected ending hour balances, and fairness metrics.
   - If **Infeasible**: invokes `SufficientAssumptionsForInfeasibility` to extract the minimal conflict core and translates it into actionable plain-language conflict cards.
4. **Stage 4 — Human-in-the-Loop Review & Pinning**:
   - Manager reviews the ERP-familiar monthly grid, toggles manual cell pins or edits (with instant client/server rule checking), and optionally triggers a fast partial re-solve.
5. **Stage 5 — ERP Companion Export & Period Finalization**:
   - Finalizing the month snapshots the schedule (retained 5 years on Business tier per Art. 46 `LTr`), updates each employee's rolling fairness score and carry-over *solde d'heures*, and generates styled **Excel (`.xlsx`)**, **CSV**, **PDF**, and **iCal (`.ics`)** outputs aligned with the legacy ERP's shift codes.

---

## 4. Zero-PII Sandbox to Institutional B2B Flow (PlantUML)

**Source**: [`docs/diagrams/sandbox-to-b2b-flow.puml`](diagrams/sandbox-to-b2b-flow.puml)

Illustrates how Solveur Magique resolves the Swiss `nLPD` "Shadow IT" trap:
- Managers never expose real employee PII during evaluation, eliminating personal CHF 250k criminal-liability exposure.
- Once value is proven on real shift patterns using pseudonyms, a single click generates the **Pack Direction** (ROI calculation + pre-signed `nLPD` Art. 9 DPA + Infomaniak Swiss ISO 27001 hosting attestation).
- The director approves and activates the institutional account via Stripe CHF or annual **Swiss QR-Bill**, seamlessly promoting the sandbox shift templates and rules into a full multi-tenant workspace.
