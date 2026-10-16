# Production Database Backup, Restore & Point-in-Time Recovery (PITR) Runbook

## Overview

This runbook outlines standard operating procedures for backing up and restoring PostgreSQL databases hosting the multi-tenant AI-Native-ERP platform. It covers physical snapshots, WAL continuous archiving, logical exports via `pg_dump`, point-in-time recovery (PITR), and mandatory post-restore validation of Row-Level Security (RLS) policies.

---

## 1. Automated Continuous Backups (AWS RDS)

In production, AWS RDS PostgreSQL is deployed in Multi-AZ mode with automated continuous WAL archiving:
- **Backup Retention**: 30 days
- **Daily Snapshot Window**: `03:00-04:00 UTC`
- **Encryption**: AWS KMS Customer-Managed Key (`aws_kms_key.main_key`)
- **Point-in-Time Recovery (PITR)**: Granular restoration to any specific second within the last 30 days.

### Triggering an Ad-Hoc RDS Manual Snapshot
```bash
aws rds create-db-snapshot \
    --db-instance-identifier production-agentic-erp-postgres \
    --db-snapshot-identifier erp-pre-deploy-$(date +%Y%m%d%H%M) \
    --tags Key=Environment,Value=production Key=Type,Value=manual
```

---

## 2. Logical Backups (pg_dump)

Logical backups are used for tenant data portability, compliance archives, or staging/sandbox replication.

### Creating a Full Database Backup
Always use the custom compressed format (`-Fc`) with directory parallelization when possible:

```bash
# Set connection credentials
export PGPASSWORD="${DB_PASSWORD}"
DB_HOST="production-agentic-erp-postgres.internal"
DB_USER="erp_admin"
DB_NAME="agentic_platform"
BACKUP_FILE="erp_backup_$(date +%Y%m%d_%H%M%S).dump"

# Execute dump with object ownership and privileges preserved
pg_dump \
    -h "$DB_HOST" \
    -U "$DB_USER" \
    -d "$DB_NAME" \
    -F c \
    -b \
    -v \
    -f "$BACKUP_FILE"

# Upload securely to encrypted S3 backup bucket
aws s3 cp "$BACKUP_FILE" s3://agentic-erp-backups/logical/ \
    --sse aws:kms \
    --sse-kms-key-id alias/production-agentic-erp
rm -f "$BACKUP_FILE"
```

---

## 3. Restore Procedures

### Scenario A: Restoring RDS to a Point-in-Time (PITR)
Used when catastrophic corruption or accidental bulk data loss occurs.

```bash
RESTORE_TIME="2026-10-15T18:30:00Z"
TARGET_INSTANCE="production-erp-restored-$(date +%Y%m%d)"

aws rds restore-db-instance-to-point-in-time \
    --source-db-instance-identifier production-agentic-erp-postgres \
    --target-db-instance-identifier "$TARGET_INSTANCE" \
    --restore-time "$RESTORE_TIME" \
    --db-subnet-group-name production-rds-subnet-group \
    --vpc-security-group-ids sg-0123456789abcdef \
    --multi-az \
    --auto-minor-version-upgrade
```

### Scenario B: Restoring Logical Backup (`pg_restore`)
Used to restore an empty staging/recovery database from a `.dump` file:

```bash
# Download snapshot from S3
aws s3 cp s3://agentic-erp-backups/logical/erp_backup_20261015.dump ./restore.dump

# Restore into target database
pg_restore \
    -h "$RESTORE_HOST" \
    -U "$RESTORE_USER" \
    -d "$RESTORE_DB" \
    --clean \
    --if-exists \
    --no-owner \
    --role=erp_admin \
    -v ./restore.dump
```

---

## 4. Mandatory Post-Restore Verification Checklist

After any restore procedure, execute the following verification steps before redirecting production application traffic:

### Step 1: Run Alembic Verification
Verify the restored database schema matches head:
```bash
alembic current
alembic check
```

### Step 2: Validate Row-Level Security (RLS) Activation
Confirm that **all 45 tenant tables** have RLS enabled and active policies:
```bash
python -c "
import asyncio
from packages.database import assert_rls_policies_active
asyncio.run(assert_rls_policies_active())
print('SUCCESS: All tenant tables have active RLS policies!')
"
```

### Step 3: Run Isolation & Smoke Tests
Run the automated tenant isolation suite against the restored database:
```bash
pytest tests/integration/test_tenant_isolation.py
python scripts/smoke_test.py
```

### Step 4: Verify App User Role Permissions
Ensure the unprivileged connection pool role `app_user` cannot read data across tenants or bypass RLS:
```sql
SET ROLE app_user;
-- Should return 0 rows when tenant context is unset:
SELECT count(*) FROM users;
-- Should return only tenant rows when set:
SET LOCAL app.tenant_id = '00000000-0000-0000-0000-000000000001';
SELECT count(*) FROM users;
RESET ROLE;
```
