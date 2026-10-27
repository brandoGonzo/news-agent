# ADR-0005: Database selection and raw capture storage

- **Status:** Accepted
- **Date:** 2026-10-27
- **Phase:** Logical Design (step 5, stack selection)
- **Requirements addressed:** FR-013, FR-014, FR-017, FR-018, FR-019, FR-020, FR-022, FR-023, FR-038, FR-039, FR-042, FR-043, NFR-002, NFR-004, NFR-017, NFR-018, NFR-019, NFR-020, NFR-023, SEC-013, SEC-014, SEC-017, SEC-018
- **Supersedes:** none. Refines decision D1 in [ADR-0004](0004-logical-architecture.md), which was marked provisional pending this analysis.

## Context

C10 Data Stores ([ADR-0004](0004-logical-architecture.md)) holds configuration, raw
captures (30 days), article text (7 days), stories and digests (1 year), runs, costs and
health, the audit log, and the AllSides reference data. The reference workload is about
1,000 items a night for one user, so scale does not drive the choice. The requirements do:

| Need | Driving requirements |
|---|---|
| Strongly linked relational data (articles, source references, stories, topic scores, digests, feedback) | FR-017 to FR-023, FR-039, FR-043 |
| Unique keys and upserts so reruns never create duplicates | NFR-002, FR-017 |
| Keyword search across one year of stories | FR-038 |
| Similarity search for story clustering and story updates (likely embeddings) | FR-018, FR-043 |
| Separate least-privilege roles for API and pipeline; no runtime superuser | SEC-017 |
| Append-only audit log the application cannot change | SEC-018 |
| Time-based retention with a record of what was deleted | NFR-023, FR-013, FR-014 |
| Daily backup, tested restore, versioned migrations | NFR-004, NFR-017 |
| One-command setup, under 8 GB RAM, under 10 GB disk per year | NFR-018, NFR-020 |
| Same images locally and on AWS | NFR-019 |

Facts checked on 2026-10-27:

- PostgreSQL 18 is the current major version; its latest minor release is 18.6
  ([PostgreSQL versioning policy](https://www.postgresql.org/support/versioning/)).
  PostgreSQL 19 is at release candidate 1.
- Airflow 3.3 is tested with PostgreSQL 14 to 18
  ([Airflow prerequisites](https://airflow.apache.org/docs/apache-airflow/stable/installation/prerequisites.html)),
  and Airflow states SQLite must never be used in production
  ([Airflow database backend](https://airflow.apache.org/docs/apache-airflow/stable/howto/set-up-database.html)).
- pgvector 0.8.7 fixes an IVFFlat index-build buffer overflow, CVE-2026-103484
  ([PostgreSQL news](https://www.postgresql.org/about/news/pgvector-087-released-3392/)).
- The MinIO community repository was archived in 2026 and its community binaries were
  withdrawn ([revisit.tech](https://revisit.tech/blog/minio-and-its-alternatives-revisit-your-self-hosted-s3/)),
  removing the usual local S3-compatible store.

## Decision

1. **Engine.** PostgreSQL 18 with the pgvector extension, minimum version 0.8.7, as the
   single database engine for v1. Built-in full-text search (tsvector and GIN) serves
   FR-038; pgvector serves similarity search.
2. **Layout (refines D1).** One PostgreSQL server with separate databases:
   - `newsagent` for application data, with schemas `config`, `ingest` (raw captures),
     `content` (articles, story membership, embeddings), `digest`, `ops` (runs, costs,
     health, retention and export records), and `audit`.
   - `airflow` for orchestrator metadata, if the orchestrator ADR selects Airflow. The
     orchestrator and the application cannot reach each other's tables.
3. **Roles (SEC-017, SEC-018).** `migrator` (owns schemas, used only by migrations),
   `api_rw`, `pipeline_rw`, `housekeeping`, and `audit_writer` (INSERT only on `audit`).
   Triggers reject UPDATE and DELETE on audit tables. The API role has no access to raw
   captures or article text (D6). No component connects as a superuser at runtime.
4. **Raw captures in PostgreSQL.** Raw source responses (feeds and source APIs only) are
   stored compressed in `ingest`, in tables partitioned by day. Each capture is written in
   the same transaction as its run record. Article HTML is not kept as raw capture;
   rebuilds after the 7-day article text window fetch it again (FR-042). Access goes
   through a storage interface so an object-storage backend can be added later without
   changing the pipeline.
5. **Retention (NFR-023).** Raw captures are removed by dropping whole daily partitions
   past 30 days. Article text and per-article embeddings are deleted after 7 days. Only
   story-level embeddings are kept for the digest history period. Every deletion is
   recorded in `ops`.
6. **Backups (NFR-004).**
   - Core backup: a daily `pg_dump` of `newsagent` excluding raw-capture tables. Kept 7 days.
   - Raw capture export: once a day's run window closes, Housekeeping exports that day's
     partition once to a compressed file with a checksum and records the export in `ops`.
     Partitions never change after their window closes, so each day is stored once,
     not once per backup.
   - Export files are deleted when their partition is dropped at 30 days, and the
     deletion is logged.
   - Restore: restore the core backup first, then re-import exports still within the
     30-day window. The import skips rows whose run is not in the restored database. The
     NFR-004 restore test covers both steps.

### Disk estimate (NFR-020, to be confirmed in schema design)

| Data | Estimate |
|---|---|
| Raw captures, 30 days (50 sources x 4 runs x ~150 KB) | ~1 GB before compression |
| Raw capture exports | Same data, stored once |
| Article metadata and stories, 1 year | ~0.6 GB |
| Core backups, 7 days | Several hundred MB each, compressed |

This stays under 10 GB a year, provided per-article embeddings follow the 7-day article
text retention and article HTML is not stored as raw capture.

## Alternatives considered

| Option | Why not chosen |
|---|---|
| SQLite with FTS5 and sqlite-vec | No database roles (fails SEC-017); weak with concurrent writers (API plus pipeline); not supported by Airflow for production |
| MySQL 8.4 | Meets roles and constraints, but full-text and vector support is weaker; no advantage over PostgreSQL here |
| MongoDB or another document store | The core data is relational; integrity and joins would move into application code |
| PostgreSQL plus a dedicated vector database plus an object store | Three stateful services instead of one; works against NFR-018 and NFR-020 with no benefit at this volume |
| Raw captures as files on disk with a metadata row | Two live stores to keep consistent (orphans, dangling references); coarse volume permissions instead of database roles; harder point-in-time backup; local and cloud code paths differ with no maintained local S3 stand-in |
| Raw captures included in every daily backup | Stores the same immutable data up to 7 times, pressuring NFR-020 |
| Raw captures excluded from backup entirely | A restore would lose the 30-day replay window (FR-014, FR-042) |

## Consequences

- One engine covers relational data, search, vectors, roles, and retention, keeping local
  setup to one database container.
- D1 in ADR-0004 is refined: separate databases on one server, not only separate schemas.
- Raw data written during the current run window is not in any backup until the window
  closes. A disk failure mid-window loses only that night's replay data.
- Backups and exports live on the same machine as the database in v1, which protects
  against corruption and mistakes but not disk loss. Off-machine copies are a Platform
  phase decision.
- Export files contain untrusted external content. The Security Review phase must set
  file permissions and, for cloud deployments, encryption at rest (SEC-013).
- Revisit raw capture storage (add an object-storage backend) on the move to AWS, or if
  raw captures exceed 5 GB.
- Schema design and the ERD for C10 follow in Implementation Design (step 10).
- The orchestrator ADR must confirm the `airflow` database or remove it.
