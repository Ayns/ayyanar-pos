"""
AYY-30 — HO Console models migration.

Creates tables with tenant_id isolation and indexes
required for Postgres RLS policy enforcement.
"""
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name="Tenant",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=128)),
                ("active", models.BooleanField(default=True)),
                ("licence_expiry", models.DateField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "db_table": "hoc_tenant",
            },
        ),
        migrations.CreateModel(
            name="Store",
            fields=[
                ("id", models.CharField(max_length=32, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=128)),
                ("city", models.CharField(blank=True, default="", max_length=64)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("tenant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="stores", to="hoc.tenant")),
            ],
            options={
                "db_table": "hoc_store",
            },
        ),
        migrations.CreateModel(
            name="HocUser",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False)),
                ("email", models.EmailField(max_length=254, unique=True)),
                ("name", models.CharField(max_length=128)),
                ("role", models.CharField(max_length=32)),
                ("assigned_stores", models.JSONField(blank=True, default=list)),
                ("active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("tenant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="users", to="hoc.tenant")),
            ],
            options={
                "db_table": "hoc_user",
            },
        ),
        migrations.CreateModel(
            name="StockTransfer",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False)),
                ("items", models.JSONField(default=list)),
                ("status", models.CharField(max_length=16)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("tenant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="stock_transfers", to="hoc.tenant")),
                ("from_store", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="outbound_transfers", to="hoc.store")),
                ("to_store", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="inbound_transfers", to="hoc.store")),
            ],
            options={
                "db_table": "hoc_stock_transfer",
            },
        ),
        migrations.CreateModel(
            name="PendingReconciliation",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False)),
                ("variant_id", models.CharField(blank=True, default="", max_length=64)),
                ("reason", models.CharField(max_length=32)),
                ("detail", models.JSONField(default=dict)),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("store", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="reconciliations", to="hoc.store")),
                ("tenant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="reconciliations", to="hoc.tenant")),
            ],
            options={
                "db_table": "hoc_reconciliation",
            },
        ),
        migrations.CreateModel(
            name="CatalogueUpdate",
            fields=[
                ("feed_cursor", models.BigAutoField(primary_key=True, serialize=False)),
                ("variant_id", models.CharField(max_length=64)),
                ("field", models.CharField(max_length=32)),
                ("new_value", models.JSONField()),
                ("emitted_at", models.DateTimeField(auto_now_add=True)),
                ("tenant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="catalog_updates", to="hoc.tenant")),
            ],
            options={
                "db_table": "hoc_catalogue_update",
            },
        ),
        migrations.CreateModel(
            name="ChangeFeedCursor",
            fields=[
                ("store", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, primary_key=True, related_name="change_feed_cursor", serialize=False, to="hoc.store")),
                ("cursor", models.BigIntegerField(default=0)),
                ("last_sync", models.DateTimeField(blank=True, null=True)),
            ],
            options={
                "db_table": "hoc_change_feed_cursor",
            },
        ),
    ]
