## Why you’re seeing “CannotConnectNowError”  

Even though your container shows as **healthy**, that healthcheck only probes the `sg_bookkeeper` database with the `sgbookkeeper_user` account. It doesn’t guarantee the **system** (the default `postgres` database) has finished recovery and is accepting connections by the `postgres` superuser. Your CLI tool connects to `-d postgres` as `postgres`, so it hits the still-in-recovery state and fails.

---

## Options to ensure full readiness before your init script runs

### 1. Use Docker Compose’s built-in wait flag  
If you have a recent Docker Compose plugin, you can tell it to wait for the service healthcheck to pass before returning:

```bash
docker compose up -d --wait
```

Then run your Poetry command only once Compose reports “healthy.”

### 2. Poll with `pg_isready` in your script  
Wrap your invocation in a short loop so it retries until the system DB is accepting connections:

```bash
#!/usr/bin/env bash
set -e

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
```

### 3. Broaden your container’s healthcheck  
Modify your Compose healthcheck to check the **system DB** instead of (or in addition to) your app DB. For example, in `docker-compose.yml`:

```yaml
services:
  db:
    # …
    healthcheck:
      test: ["CMD-SHELL",
        "pg_isready -U postgres -d postgres"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 10s
```

Now Compose reports “healthy” only when the `postgres` DB is truly up for your superuser.

---

## Putting it all together: a sample workflow

1. Remove the obsolete `version:` field from your Compose file to silence warnings.  
2. Broaden (or replace) your healthcheck as shown above.  
3. Launch and wait:

   ```bash
   docker compose down -v
   docker compose up -d --wait
   ```

4. Run your init:

   ```bash
   export PGPASSWORD=PGAdmin1234
   poetry install
   poetry run sg_bookkeeper_db_init \
     --user postgres \
     --password $PGPASSWORD \
     --dbname sg_bookkeeper \
     --drop-existing
   ```

With one of these strategies in place, your CLI tool will only attempt to connect once the **entire** Postgres server—including the `postgres` database—is ready.

---
https://copilot.microsoft.com/shares/Md1KQSJBksbqzDVgHMFnQ

