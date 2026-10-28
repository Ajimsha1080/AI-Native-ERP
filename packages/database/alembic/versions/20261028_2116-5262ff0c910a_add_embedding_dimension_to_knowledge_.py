"""add_embedding_dimension_to_knowledge_chunks

Revision ID: 5262ff0c910a
Revises: 0001_initial_base_schema
Create Date: 2026-10-28 21:16:16.895685

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5262ff0c910a'
down_revision: Union[str, None] = '0001_initial_base_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    res = conn.execute(sa.text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'knowledge_chunks' AND column_name = 'embedding_dimension'"
    )).scalar()
    if not res:
        op.add_column('knowledge_chunks', sa.Column('embedding_dimension', sa.Integer(), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    res = conn.execute(sa.text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'knowledge_chunks' AND column_name = 'embedding_dimension'"
    )).scalar()
    if res:
        op.drop_column('knowledge_chunks', 'embedding_dimension')
