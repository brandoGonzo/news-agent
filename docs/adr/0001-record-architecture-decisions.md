# ADR-0001: Record architecture decisions

- **Status:** Accepted
- **Date:** 2026-10-26
- **Phase:** Discovery
- **Requirements addressed:** n/a (process decision)
- **Supersedes:** none

## Context

News Agent is a solo learning project run as a production-grade product. The design
process includes a feedback loop: decisions made in later phases (Platform, Security
Review) may change the logical architecture and tech stack. Without a written record,
the diagrams would show what the system looks like but not why it changed.

## Decision

Every significant architecture, technology, infrastructure, or security decision is
recorded as an Architecture Decision Record (ADR) in `docs/adr/`.

- **File naming:** `NNNN-kebab-case-title.md`, numbered sequentially and never reused.
- **Format:** [`template.md`](template.md): Context, Decision, Alternatives considered,
  Consequences, Status, and the requirement IDs addressed.
- **Immutability:** once Accepted, an ADR is not rewritten. A changed decision gets a
  new ADR that supersedes the old one, and the old one's status is updated to
  `Superseded by ADR-XXXX`.
- **Traceability:** ADRs reference requirement IDs from Notion (`FR-`, `NFR-`, `SEC-`).
  Lucid diagrams reference the ADRs that shaped them.
- **Index:** [`README.md`](README.md) lists every ADR with its status.

## Alternatives considered

| Option | Pros | Cons | Why not chosen |
|---|---|---|---|
| Decisions only in Notion | Next to requirements | Separated from code; not visible on GitHub | Repo should show the reasoning |
| Notes inside diagrams | Close to the visual design | Hard to version; no history of changes | Loses the feedback-loop trail |
| No formal record | Fastest | Reasoning is lost | Defeats the learning goal |

## Consequences

- **Positive:** the repo shows why the design evolved; superseded ADRs document the
  feedback loop between phases.
- **Negative:** small overhead per decision.
- **Follow-ups:** ADR-0002 records the pre-development design process itself.
