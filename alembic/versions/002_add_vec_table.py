"""add vec0 table for embeddings

Revision ID: 002
Revises: 001
Create Date: 2026-04-26
"""
from typing import Sequence, Union

from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.connection.enable_load_extension(True)
    import sqlite_vec

    sqlite_vec.load(conn.connection)
    conn.connection.enable_load_extension(False)
    conn.execute(
        "CREATE VIRTUAL TABLE IF NOT EXISTS vec_chunks "
        "USING vec0(chunk_id INTEGER PRIMARY KEY, embedding float[384] distance_metric=cosine)",
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS vec_chunks")
