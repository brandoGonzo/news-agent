# ADR-0003: v1 scope and requirements baseline

- **Status:** Accepted
- **Date:** 2026-10-26
- **Phase:** Definition
- **Requirements addressed:** FR-001 to FR-044, NFR-001 to NFR-025, SEC-001 to SEC-023
- **Supersedes:** none

## Context

The Definition phase produced the functional, non-functional, and security
requirements for News Agent in the [Notion Requirements database](https://app.notion.com/p/e1aaccdff30d40e884616cc12e257ebf), the source of
truth for later phases. Several scope decisions were made along the way, driven by
external constraints (source API access, licensing, cost) and by the single-user
distribution model. This ADR records those decisions and closes the phase per the
exit check in [ADR-0002](0002-phased-design-process-with-exit-checks.md).

## Decision

### v1 scope

| Area | Decision |
|---|---|
| Users | Single user per install. Each person who downloads the repo runs their own instance. No multi-tenancy. |
| Sources | RSS/Atom, Hacker News, and Bluesky (authenticated with an app password). |
| Social platform | Bluesky. Free API, no approval required. |
| Bias ratings | AllSides Media Bias Ratings, by domain lookup, displayed as Left, Center, or Right with attribution (CC BY-NC 4.0). The LLM never assigns bias. |
| Content | Detailed summaries with ranking, bias, citations, and links. Full article text kept 7 days; quotes limited. |
| Delivery | Email and a web client. The web client is localhost only in v1. |
| Schedule | User-configured start time, update run interval, final run, and delivery time. The final run produces the digest and ends the run window. |
| LLM | Provider and model are configurable, including a local model option (Must). |
| Budget | $100/month for all paid services (default cap; targets refined in later phases). |
| Deferred | Remote access and a hosted dashboard (FR-044, Won't this release). |

### Requirements baseline

| Type | Must | Should | Could | Won't | Total |
|---|---|---|---|---|---|
| Functional | 34 | 8 | 1 | 1 | 44 |
| Non-functional | 21 | 4 | 0 | 0 | 25 |
| Security | 19 | 4 | 0 | 0 | 23 |
| **Total** | **74** | **16** | **1** | **1** | **92** |

### Exit check result

Passed on 2026-10-26. Every requirement has an ID, type, priority, description,
acceptance criteria, verification method, and Approved status. No duplicate IDs; all
cross-references resolve. Four conflicts found during review were resolved:

1. SEC-001 now exempts the token-protected email feedback endpoint (SEC-012).
2. The single nightly run was replaced by configurable update runs and a final run
   (FR-004, FR-009, FR-043, NFR-005), removing the timing conflict with delivery.
3. FR-042 defines rebuild behavior after the 7-day article text retention period.
4. NFR-025 adds the health check endpoint that SEC-001 depends on.

## Alternatives considered

| Option | Pros | Cons | Why not chosen |
|---|---|---|---|
| Reddit as social source | Strong news discussion | API access requires approval since Nov 2025; new requests reportedly closing; each repo user would need approval | Not available to users who download the repo |
| X as social source | Largest news audience | Pay-per-use at $0.005 per post read competes with the $100 budget | Bluesky is free and sufficient for v1 |
| Ad Fontes for bias | Also rates reliability | Paid data license | AllSides is free for non-commercial use |
| Single nightly run | Simplest | Misses overnight developments; tight timing before delivery | Update runs keep stories current |
| Remote web access in v1 | Digest readable anywhere | Adds auth, TLS, and hosting work to v1 | Deferred; email carries the full digest |

## Consequences

- **Positive:** Logical Design has a complete, approved baseline to trace against.
  Scope is bounded by explicit Won't items.
- **Negative:** Localhost-only access means email feedback links work only on the
  host machine in v1.
- **Follow-ups:** Logical Design maps every requirement to architecture elements
  (the Architecture Elements field in Notion). Cost targets (NFR-007, NFR-008) are
  provisional and will be refined in Platform. New requirements found in Security
  Review reopen Definition per ADR-0002.
