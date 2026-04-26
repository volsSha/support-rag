---
title: Heroku deployment wiring and SQLite-to-Postgres migration for support-rag
date: 2026-04-27
category: workflow-issues
module: support-rag
problem_type: workflow_issue
component: development_workflow
severity: medium
applies_when:
  - Deploying this project to Heroku
- Adding a Postgres-compatible production path while keeping SQLite local defaults
  - Standardizing runtime env configuration across local and production
tags:
  - heroku
  - postgres
  - deployment
  - sqlite-migration
  - env-config
  - support-rag
---

# Heroku deployment wiring and SQLite-to-Postgres migration for support-rag

## Context

The project was initially built around local SQLite and sqlite-vec defaults. To make deployment viable on Heroku, we needed a Postgres-compatible production path and platform-compatible runtime wiring while preserving local development behavior.

## Guidance

Use an environment-driven deployment baseline and treat Heroku as a strict runtime target:

- Add Heroku runtime/process files: `Procfile`, `runtime.txt`, and `requirements.txt`.
- Bind server port from `PORT` instead of a fixed value.
- Accept Heroku-style `DATABASE_URL` and normalize Postgres URLs for async SQLAlchemy.
- Accept both `REDIS_URL` and existing nested env format so local and hosted environments work consistently.
- Add `asyncpg` as the async Postgres driver.
- Add DB-backed embedding storage (`chunk_embeddings`) via Alembic migration `003` and route ingestion/retrieval/admin/seed paths through it when running without sqlite-vec connection wiring.

Implementation touchpoints: `src/config.py`, `src/main.py`, `src/db/models.py`, `src/services/documents.py`, `src/rag/pipeline.py`, `src/ui/admin.py`, `scripts/seed.py`, `alembic/versions/003_add_chunk_embeddings.py`, `pyproject.toml`.

Operational Heroku setup sequence:

- Install Heroku CLI and authenticate.
- Create Heroku app and provision Postgres add-on.
- Set production config vars (at minimum `JWT_SECRET`, and `OPENROUTER__API_KEY` for LLM responses; optional overrides include `APP_NAME`, `APP_URL`, `DEBUG`, `REDIS_URL`).
- Deploy code (app startup auto-runs `alembic upgrade head`), then run seed if needed.

## Why This Matters

Heroku dyno filesystems are ephemeral, so SQLite file persistence is not durable in production. Postgres-backed state plus migration-driven schema evolution makes deploys repeatable and recoverable, while env-based config removes local-only assumptions.

## When to Apply

- You move a local-first Python app to Heroku or another ephemeral runtime.
- Your app currently depends on local `.db` files for durable state.
- You need one codebase to run consistently in local dev, CI, and hosted production.

## Examples

Port binding in `src/main.py`:

```python
port = int(os.getenv("PORT", "8080"))
ui.run(..., host="0.0.0.0", port=port)
```

Database URL compatibility in `src/config.py`:

```python
if value.startswith("postgres://"):
    return "postgresql+asyncpg://" + value[len("postgres://") :]
```

Vector persistence migration in `alembic/versions/003_add_chunk_embeddings.py`:

```python
op.create_table(
    "chunk_embeddings",
    sa.Column("chunk_id", sa.Integer, sa.ForeignKey("document_chunks.id", ondelete="CASCADE"), primary_key=True),
    sa.Column("embedding_json", sa.Text, nullable=False),
)
```

## Related

- Prior implementation plan context: `docs/plans/2026-04-26-001-feat-support-rag-system-plan.md`
- Session history lookup found no directly relevant prior deployment/migration sessions (session history).
