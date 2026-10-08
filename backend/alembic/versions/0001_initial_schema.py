"""Initial schema creation

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-10-07 14:45:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import pgvector
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = '0001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    has_vector_ext = False
    if conn.dialect.name == "postgresql":
        result = conn.execute(sa.text("SELECT count(*) FROM pg_available_extensions WHERE name = 'vector'")).scalar()
        if result and result > 0:
            op.execute("CREATE EXTENSION IF NOT EXISTS vector")
            has_vector_ext = True

    # 2. Services Table
    op.create_table(
        'services',
        sa.Column('id', sa.CHAR(36) if conn.dialect.name != "postgresql" else postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='HEALTHY'),
        sa.Column('owner_team', sa.String(length=100), nullable=False),
        sa.Column('repository_url', sa.String(length=255), nullable=True),
        sa.Column('metadata_info', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_services_name', 'services', ['name'], unique=True)

    # 3. Incidents Table
    op.create_table(
        'incidents',
        sa.Column('id', sa.CHAR(36) if conn.dialect.name != "postgresql" else postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('service_id', sa.CHAR(36) if conn.dialect.name != "postgresql" else postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('severity', sa.String(length=20), nullable=False, server_default='MEDIUM'),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='OPEN'),
        sa.Column('root_cause', sa.Text(), nullable=True),
        sa.Column('resolution_notes', sa.Text(), nullable=True),
        sa.Column('comments', sa.JSON(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['service_id'], ['services.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_incidents_service_id', 'incidents', ['service_id'], unique=False)
    op.create_index('ix_incidents_title', 'incidents', ['title'], unique=False)
    op.create_index('ix_incidents_severity', 'incidents', ['severity'], unique=False)
    op.create_index('ix_incidents_status', 'incidents', ['status'], unique=False)

    # 4. Documents Table
    op.create_table(
        'documents',
        sa.Column('id', sa.CHAR(36) if conn.dialect.name != "postgresql" else postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('source', sa.String(length=500), nullable=False),
        sa.Column('doc_type', sa.String(length=50), nullable=False, server_default='runbook'),
        sa.Column('content_hash', sa.String(length=64), nullable=False),
        sa.Column('meta_info', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_documents_title', 'documents', ['title'], unique=False)
    op.create_index('ix_documents_content_hash', 'documents', ['content_hash'], unique=False)

    # 5. Document Chunks Table
    op.create_table(
        'document_chunks',
        sa.Column('id', sa.CHAR(36) if conn.dialect.name != "postgresql" else postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('document_id', sa.CHAR(36) if conn.dialect.name != "postgresql" else postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('embedding', Vector(1536) if (conn.dialect.name == "postgresql" and has_vector_ext) else sa.JSON(), nullable=True),
        sa.Column('meta_info', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_document_chunks_document_id', 'document_chunks', ['document_id'], unique=False)
    op.create_index('ix_document_chunks_doc_chunk', 'document_chunks', ['document_id', 'chunk_index'], unique=False)

    # 6. Agent Runs Table
    op.create_table(
        'agent_runs',
        sa.Column('id', sa.CHAR(36) if conn.dialect.name != "postgresql" else postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('conversation_id', sa.String(length=100), nullable=False),
        sa.Column('user_request', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='RUNNING'),
        sa.Column('plan', sa.JSON(), nullable=True),
        sa.Column('final_answer', sa.Text(), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('total_latency_ms', sa.Float(), nullable=True),
        sa.Column('total_tokens', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('meta_info', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_agent_runs_conversation_id', 'agent_runs', ['conversation_id'], unique=False)
    op.create_index('ix_agent_runs_status', 'agent_runs', ['status'], unique=False)

    # 7. Agent Events Table
    op.create_table(
        'agent_events',
        sa.Column('id', sa.CHAR(36) if conn.dialect.name != "postgresql" else postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('run_id', sa.CHAR(36) if conn.dialect.name != "postgresql" else postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('node_name', sa.String(length=100), nullable=False),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=True),
        sa.Column('duration_ms', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['run_id'], ['agent_runs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_agent_events_run_id', 'agent_events', ['run_id'], unique=False)
    op.create_index('ix_agent_events_node_name', 'agent_events', ['node_name'], unique=False)

    # 8. Tool Executions Table
    op.create_table(
        'tool_executions',
        sa.Column('id', sa.CHAR(36) if conn.dialect.name != "postgresql" else postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('run_id', sa.CHAR(36) if conn.dialect.name != "postgresql" else postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tool_name', sa.String(length=100), nullable=False),
        sa.Column('tool_input', sa.JSON(), nullable=False),
        sa.Column('tool_output', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='SUCCESS'),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('latency_ms', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['run_id'], ['agent_runs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_tool_executions_run_id', 'tool_executions', ['run_id'], unique=False)
    op.create_index('ix_tool_executions_tool_name', 'tool_executions', ['tool_name'], unique=False)

    # 9. Approvals Table
    op.create_table(
        'approvals',
        sa.Column('id', sa.CHAR(36) if conn.dialect.name != "postgresql" else postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('run_id', sa.CHAR(36) if conn.dialect.name != "postgresql" else postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tool_name', sa.String(length=100), nullable=False),
        sa.Column('tool_args', sa.JSON(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='PENDING'),
        sa.Column('decided_by', sa.String(length=100), nullable=True),
        sa.Column('decided_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['run_id'], ['agent_runs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_approvals_run_id', 'approvals', ['run_id'], unique=False)
    op.create_index('ix_approvals_status', 'approvals', ['status'], unique=False)


def downgrade() -> None:
    op.drop_table('approvals')
    op.drop_table('tool_executions')
    op.drop_table('agent_events')
    op.drop_table('agent_runs')
    op.drop_table('document_chunks')
    op.drop_table('documents')
    op.drop_table('incidents')
    op.drop_table('services')
