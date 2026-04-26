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
    return None


def downgrade() -> None:
    return None
