# ADR-0007: Language, API framework, and security modules

- **Status:** Accepted
- **Date:** 2026-10-27
- **Phase:** Logical Design (step 5, stack selection)
- **Requirements addressed:** FR-001, FR-002, FR-003, FR-004, FR-005, FR-006, FR-007, FR-008, FR-016, FR-037, FR-038, FR-039, FR-041, FR-042, NFR-006, NFR-017, NFR-025, SEC-001, SEC-002, SEC-004, SEC-007, SEC-012, SEC-018, SEC-019, SEC-020
- **Supersedes:** none

## Context

C2 Application API serves the web client and programmatic clients. The language choice
also covers the pipeline, because the orchestrator ([ADR-0006](0006-orchestrator-selection.md))
runs our code as Airflow tasks, and the scheduling library is used by both the tick DAG and
the API's schedule preview (FR-004).

| Need | Requirements |
|---|---|
| Schema validation; unknown fields rejected with 422; body size limit | SEC-007 |
| Login, Argon2id password hashing, 12-hour idle sessions | SEC-001 |
| CSRF protection, CSP and security headers, secure cookies | SEC-019 |
| Scoped, hashed, revocable API tokens | SEC-002 |
| Rate limiting with 429 and Retry-After | SEC-020 |
| Signed, single-purpose, expiring feedback links | SEC-012, FR-039 |
| Audit entries through the INSERT-only role | SEC-018, [ADR-0005](0005-database-selection.md) |
| Versioned migrations including partitions, roles, and audit triggers | NFR-017, ADR-0005 |
| Config endpoints under 300 ms p95; search under 1 s | NFR-006 |
| Async I/O for source test-fetch and starting runs through Airflow | FR-002, FR-042 |
| Health check with no internal details | NFR-025 |
| Localhost-only binding in v1 | SEC-004 |

Facts checked on 2026-10-27:

- Airflow 3.3 supports Python 3.10 to 3.14
  ([prerequisites](https://airflow.apache.org/docs/apache-airflow/stable/installation/prerequisites.html)).
  Its Java and Go task SDKs are experimental and the DAG is still declared in Python
  ([Airflow 3.3.0](https://airflow.apache.org/blog/airflow-3.3.0/)).
- FastAPI 0.162.0 (October 23, 2026) supports Python 3.10 to 3.14 ([PyPI](https://pypi.org/project/fastapi/)).
- fastapi-users is in maintenance mode: security updates only, no new features
  ([announcement](https://github.com/fastapi-users/fastapi-users/discussions/1543)).
- Litestar 2.25 ships CSRF, rate limiting, and server-side sessions
  ([PyPI](https://pypi.org/project/litestar/2.24.0/)); recent releases fixed a CSRF HTML
  injection and a rate-limit bypass through a spoofed `X-Forwarded-For`
  ([changelog](https://docs.litestar.dev/2/release-notes/changelog.html)).
- Django 6.0 added built-in Content Security Policy support
  ([release notes](https://docs.djangoproject.com/en/6.0/releases/6.0/)).
- The Python Bluesky SDK, atproto 0.0.73, is maintained but pre-1.0 and marked alpha
  ([PyPI](https://pypi.org/project/atproto/)).
- OWASP's minimum for Argon2id is 19 MiB memory, 2 iterations, 1 degree of parallelism
  ([Password Storage Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html)).

## Decision

1. **Language: Python 3.13** for the API, pipeline, scheduling library, and tooling. One
   language keeps the FR-004 rules, domain models, and FR-008 configuration schema in a
   single implementation. 3.13 is chosen over 3.14 for wider library support; confirmed
   when images are built in the Platform phase.
2. **API framework: FastAPI with Pydantic v2.** Pydantic models use `extra="forbid"`, so
   unknown fields return 422 (SEC-007). The OpenAPI document generated from the code is the
   API contract and is checked into the repository.
3. **Data access: SQLAlchemy 2 and Alembic** as the only data layer, used by both the API
   and the pipeline. Alembic migrations create the partitions, database roles, and audit
   triggers from ADR-0005 using raw SQL where needed. Database drivers are pinned
   explicitly in the connection URL.
4. **Package layout.**
   - `core`: domain models, the scheduling library, data access, the run launcher
     interface, and `core/security`. It never imports Airflow.
   - `api`: the FastAPI application. Its image does not include Airflow, so Airflow's
     pinned dependencies never constrain FastAPI or Pydantic.
   - `pipeline`: Airflow DAGs and tasks that call `core`. `core` must install within
     Airflow's constraint set.
5. **Security modules we own (`core/security`), built on vetted primitives.** We write the
   policy, the connections between parts, and the tests; we do not write cryptography.

   | Module | Requirement | Built on | Rules |
   |---|---|---|---|
   | Security headers | SEC-019 | none | Strict CSP (nonces or no inline scripts), `X-Content-Type-Options`, `Referrer-Policy`, `frame-ancestors`; HSTS only over HTTPS |
   | Validation and body limit | SEC-007 | Pydantic | 1 MB default limit; errors expose no stack traces or internals |
   | Rate limiting | SEC-020 | none | Per-client limits (60/min general, 10/min auth); 429 with `Retry-After`; `X-Forwarded-For` ignored unless set by a configured trusted proxy |
   | API tokens | SEC-002 | `secrets`, SHA-256, `hmac.compare_digest` | Shown once, stored as a hash; read-only or read-write scope checked on every route, denying by default; revocation is immediate |
   | Password hashing | SEC-001 | `argon2-cffi` | Argon2id at or above OWASP minimums; re-hash on login when parameters change |
   | Sessions | SEC-001, SEC-019 | `secrets`; server-side store in PostgreSQL | New session ID at login; 12-hour idle timeout plus an absolute maximum; all sessions revoked on password change; `Secure`, `HttpOnly`, `SameSite` cookies |
   | CSRF | SEC-019 | `secrets`, `hmac` | Token bound to the session; login form protected; `Origin` header checked as a second layer |
   | Feedback tokens | SEC-012, FR-039 | `hmac` (or `itsdangerous`) | Bound to one story and one rating; 30-day expiry; rate limited |
   | Audit logging | SEC-018 | `audit_writer` role (ADR-0005) | Logins (success and failure), config changes, tokens, credentials, manual runs; never contains secrets |

6. **Feedback links are safe against link scanners.** Email security scanners open links
   before the recipient does
   ([suped.com](https://www.suped.com/learn/email-deliverability/how-should-one-click-unsubscribe-links-handle-get-vs-post-requests)).
   A GET on a feedback link only shows a confirmation page; the rating is recorded only by a
   POST from that page. In v1 links point to localhost, so this matters most once FR-044
   remote access arrives, but the design is fixed now.
7. **Verification.** Each security module has tests mapped to its SEC acceptance criteria.
   The modules are reviewed against the OWASP Application Security Verification Standard
   (ASVS) authentication and session management sections in the Security Review phase.
   Third-party libraries are scanned for vulnerabilities in CI (Platform phase).
8. **Localhost binding (SEC-004).** The API server binds to `127.0.0.1` by default; other
   interfaces require an explicit, documented-as-unsupported setting.

## Alternatives considered

| Option | Why not chosen |
|---|---|
| TypeScript | Official Bluesky SDK and strong web tooling, but splits the codebase: scheduling rules and domain models would exist twice |
| Go | Lean runtime, but its Airflow task SDK is experimental and the DAG must still be Python |
| Java or Kotlin | Heavier memory footprint; experimental Airflow SDK |
| Litestar | Built-in CSRF, rate limiting, and sessions, but smaller community, a breaking major version in development, and recent security fixes show built-ins still need the same review |
| Django with Django Ninja | Most built-in security, but its own ORM means a second data layer and migration system on the same schema (the pipeline uses SQLAlchemy inside Airflow); partitions and database roles fit poorly. Revisit if the web client becomes server-rendered |
| Flask | Synchronous; everything from extensions; no advantage over FastAPI |
| fastapi-users for authentication | In maintenance mode; imposes its own user model |
| Writing our own cryptography | Never. Hashing, signing, and randomness come from vetted libraries or the standard library |

## Consequences

- One language and one data layer across API, pipeline, and tooling.
- We own more security-critical code than with a batteries-included framework. This is
  accepted so every control is visible, tested, and traceable to its SEC requirement.
- The Security Review phase must cover `core/security` in full.
- The Bluesky SDK is pinned to an exact version and used only behind the C4 ingestion
  adapter, so SDK changes stay contained.
- The web client ADR may revisit this decision if it chooses server-rendered pages.
- The run launcher interface from ADR-0006 lives in `core` and is defined during
  Implementation Design.
