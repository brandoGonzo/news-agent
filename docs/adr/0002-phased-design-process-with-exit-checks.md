# ADR-0002: Phased design process with exit checks

- **Status:** Accepted
- **Date:** 2026-10-26
- **Phase:** Discovery
- **Requirements addressed:** n/a (process decision)
- **Supersedes:** none

## Context

The project follows a structured design flow before any development begins. Each
phase feeds the next, and Logical Design acts as a feedback loop that later phases
can reopen. Phases need a clear definition of "done" so that gaps are caught before
moving on and so a phase can be reopened deliberately rather than by drift.

## Decision

Design proceeds through seven phases. A phase is complete only when its exit check
passes. If a later phase invalidates an earlier output, that phase is reopened, the
change is recorded in a superseding ADR, and its exit check is run again.

| Phase | Steps | Output | Lives in |
|---|---|---|---|
| Discovery | 1–2 | Concept and candidate tech stack | Project notes |
| Definition | 3 | Functional, non-functional, and security requirements | Notion |
| Logical Design | 4–5 | Logical architecture; final tech stack (stack follows architecture) | Lucid, ADRs |
| Platform | 6 | Environments, hosting, IaC, CI/CD strategy | ADRs, Lucid |
| Security Review | 7–8 | Threat model, then security controls and architecture | Notion, Lucid, ADRs |
| Consolidation | 9 | One system architecture combining technology, infrastructure, and security | Lucid |
| Implementation Design | 10 | C4 diagrams (context, container, component) and UML where needed | Lucid |

### Exit checks

- **Discovery:** concept statement and candidate stack written down.
- **Definition:** every requirement has an ID (`FR-`, `NFR-`, `SEC-`), priority,
  acceptance criteria, and status; security requirements are included.
- **Logical Design:** every requirement maps to at least one architecture element;
  every technology choice has an ADR naming the requirements it addresses.
- **Platform:** environments, hosting, IaC tooling, and CI/CD pipeline stages are
  decided and recorded in ADRs.
- **Security Review:** threat model covers every data flow and trust boundary; every
  identified threat has a control, or an accepted risk with rationale.
- **Consolidation:** a single architecture reconciles all prior ADRs; no open
  conflicts between phases.
- **Implementation Design:** C4 levels 1–3 are complete and consistent with the
  consolidated architecture; UML exists for the complex flows.

## Alternatives considered

| Option | Pros | Cons | Why not chosen |
|---|---|---|---|
| Start coding, design as needed | Fast feedback | Rework; weak traceability | Project goal is production-grade practice |
| Strict waterfall, no reopening | Simple | Later findings can't improve the design | Security and platform decisions must be able to shape architecture |

## Consequences

- **Positive:** each phase is a verifiable checkpoint; changes across phases are
  traceable through superseding ADRs.
- **Negative:** slower start before code exists.
- **Follow-ups:** Definition phase begins next in Notion.
