"""テストケースとタグの組の表（testcase_tags）

タグで絞り込むために、記録の JSON の中のタグを、別の表にも持つ（S13）。
もうある記録のタグも写す。タグを足す前の記録はタグを持たないので、写すものはない。

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-17
"""

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    testcase_tags = op.create_table(
        "testcase_tags",
        sa.Column("testcase_id", sa.Text(), primary_key=True),
        sa.Column("tag", sa.Text(), primary_key=True),
    )
    testcases = sa.table("testcases", sa.column("id"), sa.column("record"))
    rows = op.get_bind().execute(sa.select(testcases.c.id, testcases.c.record))
    pairs = [
        {"testcase_id": testcase_id, "tag": tag}
        for testcase_id, record in rows
        for tag in json.loads(record)["testcase"].get("tags", [])
    ]
    if pairs:
        op.bulk_insert(testcase_tags, pairs)


def downgrade() -> None:
    op.drop_table("testcase_tags")
