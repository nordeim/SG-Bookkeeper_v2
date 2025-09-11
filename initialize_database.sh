#!/usr/bin/env bash
set -e

# poetry install
# docker-compose down --volumes
# docker-compose up -d --build
# docker ps
# wait for postgres superuser to be ready
until pg_isready -h localhost -p 5432 -U postgres -d postgres; do
  echo "Waiting for postgres system DB…"
  sleep 2
done

# now safe to run your init tool
poetry run sg_bookkeeper_db_init \
  --user postgres \
  --password PGAdmin1234 \
  --dbname sg_bookkeeper \
  --drop-existing

sudo -u postgres PGPASSWORD=PGAdmin1234 psql -h localhost

exit 0

```sql
-- Run as postgres user
-- create application user
CREATE USER sgbookkeeper_user WITH PASSWORD 'SGkeeperPass123';
-- grant user privileges
GRANT ALL PRIVILEGES ON DATABASE sg_bookkeeper TO sgbookkeeper_user;
-- connect to application specific database
\c sg_bookkeeper

GRANT USAGE ON SCHEMA core, accounting, business, audit TO sgbookkeeper_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA core TO sgbookkeeper_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA accounting TO sgbookkeeper_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA business TO sgbookkeeper_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA audit TO sgbookkeeper_user;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA core TO sgbookkeeper_user;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA accounting TO sgbookkeeper_user;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA audit TO sgbookkeeper_user;
-- For sequences (needed for INSERTs if app uses them directly or via default values)
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA core TO sgbookkeeper_user;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA accounting TO sgbookkeeper_user;
-- Grant privileges for future tables too
ALTER DEFAULT PRIVILEGES IN SCHEMA core GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO sgbookkeeper_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA accounting GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO sgbookkeeper_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA business GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO sgbookkeeper_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA audit GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO sgbookkeeper_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA core GRANT USAGE, SELECT ON SEQUENCES TO sgbookkeeper_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA accounting GRANT USAGE, SELECT ON SEQUENCES TO sgbookkeeper_user;
```

poetry run sg_bookkeeper

