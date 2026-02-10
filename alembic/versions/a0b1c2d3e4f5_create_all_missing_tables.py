"""Create all missing tables (products, product_models, product_parts, sla_policies, integrations, escalations, notifications, platform_settings)

Revision ID: a0b1c2d3e4f5
Revises: 9b3c4d5e6f70
Create Date: 2026-02-07

Creates every table defined in models that was not in the initial migration,
so that alembic upgrade head produces a complete schema.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a0b1c2d3e4f5'
down_revision = '9b3c4d5e6f70'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. products (FK: organizations)
    op.create_table(
        'products',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('category', sa.Enum('ac', 'refrigerator', 'washing_machine', 'tv', 'microwave', 'air_purifier', 'water_purifier', 'other', name='productcategory'), nullable=False),
        sa.Column('brand', sa.String(length=100), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('specifications', sa.JSON(), nullable=True),
        sa.Column('default_warranty_months', sa.Integer(), nullable=True),
        sa.Column('extended_warranty_available', sa.Boolean(), nullable=True),
        sa.Column('common_failures', sa.JSON(), nullable=True),
        sa.Column('recommended_parts', sa.JSON(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
    )
    op.create_index(op.f('ix_products_id'), 'products', ['id'], unique=False)
    op.create_index(op.f('ix_products_organization_id'), 'products', ['organization_id'], unique=False)
    op.create_index(op.f('ix_products_category'), 'products', ['category'], unique=False)

    # 2. product_models (FK: products, organizations)
    op.create_table(
        'product_models',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('model_number', sa.String(length=100), nullable=False),
        sa.Column('model_name', sa.String(length=255), nullable=True),
        sa.Column('compatible_parts', sa.JSON(), nullable=True),
        sa.Column('service_instructions', sa.Text(), nullable=True),
        sa.Column('diagnostic_playbook', sa.JSON(), nullable=True),
        sa.Column('error_code_mappings', sa.JSON(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
    )
    op.create_index(op.f('ix_product_models_id'), 'product_models', ['id'], unique=False)
    op.create_index(op.f('ix_product_models_product_id'), 'product_models', ['product_id'], unique=False)
    op.create_index(op.f('ix_product_models_organization_id'), 'product_models', ['organization_id'], unique=False)
    op.create_index(op.f('ix_product_models_model_number'), 'product_models', ['model_number'], unique=False)

    # 3. product_parts (FK: products, parts, organizations)
    op.create_table(
        'product_parts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('part_id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('is_required', sa.Boolean(), nullable=True),
        sa.Column('is_common', sa.Boolean(), nullable=True),
        sa.Column('usage_frequency', sa.String(length=50), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ),
        sa.ForeignKeyConstraint(['part_id'], ['parts.id'], ),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
    )
    op.create_index(op.f('ix_product_parts_id'), 'product_parts', ['id'], unique=False)
    op.create_index(op.f('ix_product_parts_product_id'), 'product_parts', ['product_id'], unique=False)
    op.create_index(op.f('ix_product_parts_part_id'), 'product_parts', ['part_id'], unique=False)
    op.create_index(op.f('ix_product_parts_organization_id'), 'product_parts', ['organization_id'], unique=False)

    # 4. sla_policies (FK: organizations, products, countries, states, cities)
    op.create_table(
        'sla_policies',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('product_category', sa.String(length=100), nullable=True),
        sa.Column('product_id', sa.Integer(), nullable=True),
        sa.Column('country_id', sa.Integer(), nullable=True),
        sa.Column('state_id', sa.Integer(), nullable=True),
        sa.Column('city_id', sa.Integer(), nullable=True),
        sa.Column('sla_type', sa.Enum('first_response', 'assignment', 'resolution', 'on_site', name='slatype'), nullable=False),
        sa.Column('target_hours', sa.Integer(), nullable=False),
        sa.Column('priority_overrides', sa.JSON(), nullable=True),
        sa.Column('business_hours_only', sa.Boolean(), nullable=True),
        sa.Column('business_hours', sa.JSON(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ),
        sa.ForeignKeyConstraint(['country_id'], ['countries.id'], ),
        sa.ForeignKeyConstraint(['state_id'], ['states.id'], ),
        sa.ForeignKeyConstraint(['city_id'], ['cities.id'], ),
    )
    op.create_index(op.f('ix_sla_policies_id'), 'sla_policies', ['id'], unique=False)
    op.create_index(op.f('ix_sla_policies_organization_id'), 'sla_policies', ['organization_id'], unique=False)

    # 5. integrations (FK: organizations)
    op.create_table(
        'integrations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('integration_type', sa.Enum('erp', 'crm', 'warehouse', 'payment_gateway', 'sms_provider', 'email_provider', 'webhook', 'api', 'iot', name='integrationtype'), nullable=False),
        sa.Column('provider', sa.String(length=100), nullable=True),
        sa.Column('config', sa.JSON(), nullable=True),
        sa.Column('webhook_url', sa.String(length=500), nullable=True),
        sa.Column('api_endpoint', sa.String(length=500), nullable=True),
        sa.Column('sync_direction', sa.String(length=50), nullable=True),
        sa.Column('sync_frequency', sa.String(length=50), nullable=True),
        sa.Column('last_sync_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.Enum('active', 'inactive', 'error', 'testing', name='integrationstatus'), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('error_count', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
    )
    op.create_index(op.f('ix_integrations_id'), 'integrations', ['id'], unique=False)
    op.create_index(op.f('ix_integrations_organization_id'), 'integrations', ['organization_id'], unique=False)

    # 6. escalations (FK: organizations, tickets, devices, users)
    op.create_table(
        'escalations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('ticket_id', sa.Integer(), nullable=True),
        sa.Column('device_id', sa.Integer(), nullable=True),
        sa.Column('escalation_type', sa.Enum('sla_breach', 'repeated_complaint', 'negative_sentiment', 'technical_issue', 'parts_unavailable', 'unsafe_condition', 'fraud_suspicion', 'customer_request', 'other', name='escalationtype'), nullable=False),
        sa.Column('escalation_level', sa.Enum('city', 'state', 'country', 'organization', 'platform', name='escalationlevel'), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('escalated_by_id', sa.Integer(), nullable=False),
        sa.Column('assigned_to_id', sa.Integer(), nullable=True),
        sa.Column('status', sa.Enum('pending', 'acknowledged', 'in_progress', 'resolved', 'closed', name='escalationstatus'), nullable=True),
        sa.Column('resolution_notes', sa.Text(), nullable=True),
        sa.Column('resolved_by_id', sa.Integer(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('extra_data', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
        sa.ForeignKeyConstraint(['ticket_id'], ['tickets.id'], ),
        sa.ForeignKeyConstraint(['device_id'], ['devices.id'], ),
        sa.ForeignKeyConstraint(['escalated_by_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['assigned_to_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['resolved_by_id'], ['users.id'], ),
    )
    op.create_index(op.f('ix_escalations_id'), 'escalations', ['id'], unique=False)
    op.create_index(op.f('ix_escalations_organization_id'), 'escalations', ['organization_id'], unique=False)
    op.create_index(op.f('ix_escalations_ticket_id'), 'escalations', ['ticket_id'], unique=False)
    op.create_index(op.f('ix_escalations_status'), 'escalations', ['status'], unique=False)
    op.create_index(op.f('ix_escalations_created_at'), 'escalations', ['created_at'], unique=False)

    # 7. notifications (FK: organizations, users, tickets, devices)
    op.create_table(
        'notifications',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('notification_type', sa.Enum('ticket_created', 'ticket_assigned', 'ticket_updated', 'ticket_resolved', 'sla_breach_warning', 'escalation', 'inventory_low', 'part_ordered', 'engineer_eta', 'feedback_received', 'system_alert', name='notificationtype'), nullable=False),
        sa.Column('channel', sa.Enum('in_app', 'email', 'sms', 'whatsapp', 'push', name='notificationchannel'), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('ticket_id', sa.Integer(), nullable=True),
        sa.Column('device_id', sa.Integer(), nullable=True),
        sa.Column('status', sa.Enum('pending', 'sent', 'delivered', 'read', 'failed', name='notificationstatus'), nullable=True),
        sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('extra_data', sa.JSON(), nullable=True),
        sa.Column('action_url', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['ticket_id'], ['tickets.id'], ),
        sa.ForeignKeyConstraint(['device_id'], ['devices.id'], ),
    )
    op.create_index(op.f('ix_notifications_id'), 'notifications', ['id'], unique=False)
    op.create_index(op.f('ix_notifications_organization_id'), 'notifications', ['organization_id'], unique=False)
    op.create_index(op.f('ix_notifications_user_id'), 'notifications', ['user_id'], unique=False)
    op.create_index(op.f('ix_notifications_notification_type'), 'notifications', ['notification_type'], unique=False)
    op.create_index(op.f('ix_notifications_status'), 'notifications', ['status'], unique=False)
    op.create_index(op.f('ix_notifications_created_at'), 'notifications', ['created_at'], unique=False)

    # 8. platform_settings (no FKs)
    op.create_table(
        'platform_settings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('setting_key', sa.String(length=100), nullable=False),
        sa.Column('setting_value', sa.Text(), nullable=True),
        sa.Column('setting_type', sa.String(length=50), nullable=False),
        sa.Column('category', sa.String(length=50), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_public', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('setting_key'),
    )
    op.create_index(op.f('ix_platform_settings_id'), 'platform_settings', ['id'], unique=False)
    op.create_index(op.f('ix_platform_settings_setting_key'), 'platform_settings', ['setting_key'], unique=True)
    op.create_index(op.f('ix_platform_settings_category'), 'platform_settings', ['category'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_platform_settings_category'), table_name='platform_settings')
    op.drop_index(op.f('ix_platform_settings_setting_key'), table_name='platform_settings')
    op.drop_index(op.f('ix_platform_settings_id'), table_name='platform_settings')
    op.drop_table('platform_settings')
    op.drop_index(op.f('ix_notifications_created_at'), table_name='notifications')
    op.drop_index(op.f('ix_notifications_status'), table_name='notifications')
    op.drop_index(op.f('ix_notifications_notification_type'), table_name='notifications')
    op.drop_index(op.f('ix_notifications_user_id'), table_name='notifications')
    op.drop_index(op.f('ix_notifications_organization_id'), table_name='notifications')
    op.drop_index(op.f('ix_notifications_id'), table_name='notifications')
    op.drop_table('notifications')
    op.drop_index(op.f('ix_escalations_created_at'), table_name='escalations')
    op.drop_index(op.f('ix_escalations_status'), table_name='escalations')
    op.drop_index(op.f('ix_escalations_ticket_id'), table_name='escalations')
    op.drop_index(op.f('ix_escalations_organization_id'), table_name='escalations')
    op.drop_index(op.f('ix_escalations_id'), table_name='escalations')
    op.drop_table('escalations')
    op.drop_index(op.f('ix_integrations_organization_id'), table_name='integrations')
    op.drop_index(op.f('ix_integrations_id'), table_name='integrations')
    op.drop_table('integrations')
    op.drop_index(op.f('ix_sla_policies_organization_id'), table_name='sla_policies')
    op.drop_index(op.f('ix_sla_policies_id'), table_name='sla_policies')
    op.drop_table('sla_policies')
    op.drop_index(op.f('ix_product_parts_organization_id'), table_name='product_parts')
    op.drop_index(op.f('ix_product_parts_part_id'), table_name='product_parts')
    op.drop_index(op.f('ix_product_parts_product_id'), table_name='product_parts')
    op.drop_index(op.f('ix_product_parts_id'), table_name='product_parts')
    op.drop_table('product_parts')
    op.drop_index(op.f('ix_product_models_model_number'), table_name='product_models')
    op.drop_index(op.f('ix_product_models_organization_id'), table_name='product_models')
    op.drop_index(op.f('ix_product_models_product_id'), table_name='product_models')
    op.drop_index(op.f('ix_product_models_id'), table_name='product_models')
    op.drop_table('product_models')
    op.drop_index(op.f('ix_products_category'), table_name='products')
    op.drop_index(op.f('ix_products_organization_id'), table_name='products')
    op.drop_index(op.f('ix_products_id'), table_name='products')
    op.drop_table('products')
