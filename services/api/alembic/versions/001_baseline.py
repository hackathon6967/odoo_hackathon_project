"""Baseline migration - all tables

Revision ID: 001_baseline
Revises: 
Create Date: 2026-07-12
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '001_baseline'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # departments (must come before users for FK)
    op.create_table('departments',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('code', sa.String(50), nullable=False),
        sa.Column('parent_department_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('employee_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('status', sa.String(50), nullable=False, server_default='active'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['parent_department_id'], ['departments.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code'),
    )

    # users
    op.create_table('users',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('full_name', sa.String(255), nullable=False),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('role', sa.String(50), nullable=False, server_default='employee'),
        sa.Column('department_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('xp', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('points', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('gender', sa.String(50), nullable=True),
        sa.Column('hire_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('avatar_url', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['department_id'], ['departments.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
    )
    op.create_index('ix_users_email', 'users', ['email'])

    # categories
    op.create_table('categories',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('type', sa.String(50), nullable=False),
        sa.Column('status', sa.String(50), nullable=False, server_default='active'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )

    # esg_config
    op.create_table('esg_config',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('weight_environmental', sa.Float(), nullable=False, server_default='0.40'),
        sa.Column('weight_social', sa.Float(), nullable=False, server_default='0.30'),
        sa.Column('weight_governance', sa.Float(), nullable=False, server_default='0.30'),
        sa.Column('auto_emission_calc', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('evidence_required', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('badge_auto_award', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )

    # notification_settings
    op.create_table('notification_settings',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('notification_type', sa.String(100), nullable=False),
        sa.Column('in_app_enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('email_enabled', sa.Boolean(), nullable=False, server_default='false'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('notification_type'),
    )

    # notifications
    op.create_table('notifications',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('type', sa.String(100), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('is_read', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # emission_factors
    op.create_table('emission_factors',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('source_type', sa.String(100), nullable=False),
        sa.Column('unit', sa.String(50), nullable=False),
        sa.Column('co2e_per_unit', sa.Float(), nullable=False),
        sa.Column('effective_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='active'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )

    # carbon_transactions
    op.create_table('carbon_transactions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('department_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('source_module', sa.String(100), nullable=False),
        sa.Column('emission_factor_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('quantity', sa.Float(), nullable=False),
        sa.Column('co2e_calculated', sa.Float(), nullable=False),
        sa.Column('transaction_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('is_auto_calculated', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_by_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['department_id'], ['departments.id']),
        sa.ForeignKeyConstraint(['emission_factor_id'], ['emission_factors.id']),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # environmental_goals
    op.create_table('environmental_goals',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('department_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('metric', sa.String(255), nullable=False),
        sa.Column('target_value', sa.Float(), nullable=False),
        sa.Column('current_value', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('unit', sa.String(50), nullable=False),
        sa.Column('target_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('status', sa.String(50), nullable=False, server_default='active'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['department_id'], ['departments.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # product_esg_profiles
    op.create_table('product_esg_profiles',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('product_ref', sa.String(255), nullable=False),
        sa.Column('emission_factor_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('sustainability_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['emission_factor_id'], ['emission_factors.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # csr_activities
    op.create_table('csr_activities',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('category_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('department_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('evidence_required', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('max_participants', sa.Integer(), nullable=True),
        sa.Column('points_reward', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('status', sa.String(50), nullable=False, server_default='active'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['category_id'], ['categories.id']),
        sa.ForeignKeyConstraint(['department_id'], ['departments.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # employee_participations (CSR)
    op.create_table('employee_participations',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('employee_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('activity_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('proof_file_ref', sa.String(500), nullable=True),
        sa.Column('approval_status', sa.String(50), nullable=False, server_default='Pending'),
        sa.Column('points_earned', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('completion_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('reviewer_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['employee_id'], ['users.id']),
        sa.ForeignKeyConstraint(['activity_id'], ['csr_activities.id']),
        sa.ForeignKeyConstraint(['reviewer_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # diversity_metrics
    op.create_table('diversity_metrics',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('department_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('period', sa.String(20), nullable=False),
        sa.Column('gender_male', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('gender_female', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('gender_other', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('tenure_0_1', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('tenure_1_3', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('tenure_3_5', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('tenure_5_plus', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['department_id'], ['departments.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # esg_policies
    op.create_table('esg_policies',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('version', sa.String(50), nullable=False, server_default='1.0'),
        sa.Column('body', sa.Text(), nullable=True),
        sa.Column('file_ref', sa.String(500), nullable=True),
        sa.Column('effective_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('requires_acknowledgement', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('status', sa.String(50), nullable=False, server_default='draft'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )

    # policy_acknowledgements
    op.create_table('policy_acknowledgements',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('policy_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('employee_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('acknowledged_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['policy_id'], ['esg_policies.id']),
        sa.ForeignKeyConstraint(['employee_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # audits
    op.create_table('audits',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('department_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('auditor', sa.String(255), nullable=False),
        sa.Column('scheduled_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('status', sa.String(50), nullable=False, server_default='scheduled'),
        sa.Column('findings_summary', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['department_id'], ['departments.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # compliance_issues
    op.create_table('compliance_issues',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('audit_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('severity', sa.String(50), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('owner_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('due_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('status', sa.String(50), nullable=False, server_default='Open'),
        sa.Column('resolution_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['audit_id'], ['audits.id']),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # challenges
    op.create_table('challenges',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('category_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('xp', sa.Integer(), nullable=False, server_default='50'),
        sa.Column('difficulty', sa.String(50), nullable=False, server_default='medium'),
        sa.Column('evidence_required', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('deadline', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='Draft'),
        sa.Column('created_by_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['category_id'], ['categories.id']),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # challenge_participations
    op.create_table('challenge_participations',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('challenge_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('employee_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('progress', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('proof_file_ref', sa.String(500), nullable=True),
        sa.Column('approval_status', sa.String(50), nullable=False, server_default='Pending'),
        sa.Column('xp_awarded', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['challenge_id'], ['challenges.id']),
        sa.ForeignKeyConstraint(['employee_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # badges
    op.create_table('badges',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('unlock_rule', postgresql.JSONB(), nullable=False),
        sa.Column('icon', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )

    # employee_badges
    op.create_table('employee_badges',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('employee_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('badge_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('awarded_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['employee_id'], ['users.id']),
        sa.ForeignKeyConstraint(['badge_id'], ['badges.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # rewards
    op.create_table('rewards',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('points_required', sa.Integer(), nullable=False),
        sa.Column('stock', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('image_url', sa.String(500), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='active'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )

    # reward_redemptions
    op.create_table('reward_redemptions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('reward_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('employee_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('points_deducted', sa.Integer(), nullable=False),
        sa.Column('redeemed_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('status', sa.String(50), nullable=False, server_default='fulfilled'),
        sa.ForeignKeyConstraint(['reward_id'], ['rewards.id']),
        sa.ForeignKeyConstraint(['employee_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # department_scores
    op.create_table('department_scores',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('department_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('period', sa.String(20), nullable=False),
        sa.Column('environmental_score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('social_score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('governance_score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('total_score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('computed_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['department_id'], ['departments.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('department_id', 'period', name='uq_dept_score_period'),
    )

    # report_jobs
    op.create_table('report_jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('report_type', sa.String(100), nullable=False),
        sa.Column('filters', postgresql.JSONB(), nullable=True),
        sa.Column('format', sa.String(20), nullable=False),
        sa.Column('status', sa.String(50), nullable=False, server_default='pending'),
        sa.Column('file_ref', sa.String(500), nullable=True),
        sa.Column('download_url', sa.String(1000), nullable=True),
        sa.Column('error_msg', sa.String(500), nullable=True),
        sa.Column('requested_by_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['requested_by_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('report_jobs')
    op.drop_table('department_scores')
    op.drop_table('reward_redemptions')
    op.drop_table('rewards')
    op.drop_table('employee_badges')
    op.drop_table('badges')
    op.drop_table('challenge_participations')
    op.drop_table('challenges')
    op.drop_table('compliance_issues')
    op.drop_table('audits')
    op.drop_table('policy_acknowledgements')
    op.drop_table('esg_policies')
    op.drop_table('diversity_metrics')
    op.drop_table('employee_participations')
    op.drop_table('csr_activities')
    op.drop_table('product_esg_profiles')
    op.drop_table('environmental_goals')
    op.drop_table('carbon_transactions')
    op.drop_table('emission_factors')
    op.drop_table('notification_settings')
    op.drop_table('notifications')
    op.drop_table('esg_config')
    op.drop_table('categories')
    op.drop_table('users')
    op.drop_table('departments')
