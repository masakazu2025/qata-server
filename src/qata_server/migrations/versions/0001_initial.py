"""最初の表（testcases・runs）

Alembic を入れる前の保存先には、表はあるがマイグレーションの記録がない。
そのときは表を作らず、記録だけを付ける（中のデータはそのまま読める）。

Revision ID: 0001
Revises:
Create Date: 2026-11-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    existing = set(sa.inspect(op.get_bind()).get_table_names())
    if "testcases" not in existing:
        op.create_table(
            "testcases",
            sa.Column("id", sa.Text(), primary_key=True),
            sa.Column("app_id", sa.Text(), nullable=False),
            sa.Column("record", sa.Text(), nullable=False),
        )
    if "runs" not in existing:
        op.create_table(
            "runs",
            sa.Column("id", sa.Text(), primary_key=True),
            sa.Column("testcase_id", sa.Text(), nullable=False),
            sa.Column("record", sa.Text(), nullable=False),
        )


def downgrade() -> None:
    op.drop_table("runs")
    op.drop_table("testcases")
