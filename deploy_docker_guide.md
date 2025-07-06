$ docker compose down -v
[+] Running 3/3
 ✔ Container sg_bookkeeper             Removed                                                                                                                                                                                         1.0s 
 ✔ Volume sg-bookkeeper_postgres_data  Removed                                                                                                                                                                                         0.1s 
 ✔ Network sg-bookkeeper_default       Removed                                                                                                                                                                                         0.2s 

$ docker compose up --build -d
[+] Running 3/3
 ✔ Network sg-bookkeeper_default         Created                                                                                                                                                                                       0.1s 
 ✔ Volume "sg-bookkeeper_postgres_data"  Created                                                                                                                                                                                       0.0s 
 ✔ Container sg_bookkeeper               Started                                                                                                                                                                                       1.6s 

$ docker ps -a
CONTAINER ID   IMAGE                                   COMMAND                  CREATED         STATUS                     PORTS                                                                                                NAMES
124ae10b3e16   postgres:16                             "docker-entrypoint.s…"   9 seconds ago   Up 7 seconds (healthy)     0.0.0.0:5432->5432/tcp, [::]:5432->5432/tcp                                                          sg_bookkeeper

$ poetry run sg_bookkeeper_db_init   --user postgres   --password $PGPASSWORD   --dbname sg_bookkeeper   --drop-existing
Warning: 'sg_bookkeeper_db_init' is an entry point defined in pyproject.toml, but it's not installed as a script. You may get improper `sys.argv[0]`.

The support to run uninstalled scripts will be removed in a future release.

Run `poetry install` to resolve and get rid of this message.

Terminating connections to 'sg_bookkeeper'...
Dropping existing database 'sg_bookkeeper'...
Creating database 'sg_bookkeeper'...
Initializing database schema from /cdrom/project/SG-Bookkeeper/scripts/schema.sql...
Schema execution completed.
Loading initial data from /cdrom/project/SG-Bookkeeper/scripts/initial_data.sql...
Initial data loading completed.
Setting default search_path for database 'sg_bookkeeper'...
Default search_path set.
Database 'sg_bookkeeper' created and initialized successfully.

# docker exec -e PGPASSWORD=PGAdmin1234 -it sg_bookkeeper psql -U postgres -d postgres

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

---
# Why the “executable file not found” Error Occurred  

Docker saw `PGPASSWORD=PGAdmin1234` as the command to run inside the container—so it looked for a binary of that name and failed. You need to tell Docker to run `psql`, and either (a) pass the env-var into the container or (b) wrap your invocation in a shell.

---

# How to Connect as `postgres` from Inside the Container

Below are two simple approaches:

## 1. Use Docker’s `-e` Flag to Inject `PGPASSWORD`  

```bash
docker exec -e PGPASSWORD=PGAdmin1234 -it sg_bookkeeper \
  psql -U postgres -d postgres
```

- `-e PGPASSWORD=…` sets the env var for **that** process.  
- `psql -U postgres -d postgres` then uses it to authenticate.  

## 2. Wrap Your Command in a Shell  

If you prefer a single `bash -c` line:

```bash
docker exec -it sg_bookkeeper bash -c \
  "PGPASSWORD=PGAdmin1234 psql -U postgres -d postgres"
```

- Here you run `bash -c "…"` so the env-var is scoped to the `psql` call.  

---

# Bonus: Connect Directly from Your Host  

You don’t strictly need to exec into the container. From your host shell:

```bash
export PGPASSWORD=PGAdmin1234

psql -h localhost -p 5432 \
  -U postgres -d postgres
```

This is often more convenient for ad-hoc queries or user/password testing.

https://copilot.microsoft.com/shares/ZTbxuDjHavA5SuqfDqrSX

---
# Provisioning `postgres` as Superuser with Init Scripts

You can let Docker’s official image create the default `postgres` superuser (with your chosen password), then use an init‐script to create the `sgbookkeeper_user` and its database. That way:

- `docker compose up` →  
  - `POSTGRES_PASSWORD=PGAdmin1234` sets the password for the built-in `postgres` account  
  - Your SQL in `/docker-entrypoint-initdb.d` creates the app user & database  

---

## 1. Remove `POSTGRES_USER` / `POSTGRES_DB` envs

By default, if you don’t set `POSTGRES_USER`, the image uses:

- Superuser: `postgres`  
- Database: `postgres`  

So your service section simplifies to:

```yaml
services:
  db:
    image: postgres:16
    container_name: sg_bookkeeper
    restart: unless-stopped
    environment:
      POSTGRES_PASSWORD: PGAdmin1234        # ← only this
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./db/init:/docker-entrypoint-initdb.d
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres -d postgres"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 10s

volumes:
  postgres_data:
    driver: local
```

> **Tip**: Remove the top-level `version:` key to silence Compose V2 warnings.

---

## 2. Add an init‐script to create your app user & DB

Create `db/init/01-create-app-db.sql`:

```sql
-- 1. Create the sgbookkeeper_user with secure password
CREATE USER sgbookkeeper_user
  WITH PASSWORD 'SGkeeperPass123'
  CREATEDB LOGIN;

-- 2. Create the database owned by that user
CREATE DATABASE sg_bookkeeper
  OWNER sgbookkeeper_user;

-- 3. (Optional) Lock down default postgres database
REVOKE CONNECT ON DATABASE postgres FROM PUBLIC, sgbookkeeper_user;
```

- On **first** container startup, Docker runs this SQL (because the volume is empty).  
- `sgbookkeeper_user` can now `CONNECT` only to `sg_bookkeeper` and owns it.  

---

## 3. Workflow

1. **Bring up Postgres**  
   ```bash
   docker compose down -v  
   docker compose up -d --wait
   ```
2. **Install your CLI tool**  
   ```bash
   poetry install
   ```
3. **Run your init script**  
   ```bash
   export PGHOST=localhost
   export PGUSER=postgres
   export PGPASSWORD=PGAdmin1234

   poetry run sg_bookkeeper_db_init \
     --user postgres \
     --password $PGPASSWORD \
     --dbname sg_bookkeeper \
     --drop-existing
   ```

Now:

- The `postgres` superuser exists with the password you set via `POSTGRES_PASSWORD`.  
- Your CLI can connect as `postgres`, drop/create `sg_bookkeeper`, then hand off to `sgbookkeeper_user` for migrations.  

---

## Next Explorations

- Parameterize the SQL script with environment variables (e.g. `${SG_USER}`)  
- Add a second healthcheck that checks your app DB readiness  
- Bake this logic into a small “entrypoint” so your CI job just does `docker compose up --build --wait && run-tests`

https://copilot.microsoft.com/shares/CeWZwH2sQ47LdgB2BybBX

---
## 1. Create an init‐script directory

Next to your docker-compose.yml, make a folder for SQL scripts that will run _once_ when the volume is first initialized:

```bash
mkdir -p db/init
```

---

## 2. Add SQL files to:

- set the `postgres` password  
- revoke all default rights from `sgbookkeeper_user` on other DBs  
- explicitly grant it only on `sg_bookkeeper`

### db/init/01-alter-postgres.sql  
```sql
-- set a known password for the postgres superuser
ALTER USER postgres WITH PASSWORD 'PGAdmin1234';
```

### db/init/02-lockdown-sgbookkeeper.sql  
```sql
-- revoke any accidental rights on the default "postgres" database
REVOKE CONNECT ON DATABASE postgres FROM sgbookkeeper_user, PUBLIC;

-- ensure sgbookkeeper_user can connect to its own database
GRANT CONNECT ON DATABASE sg_bookkeeper TO sgbookkeeper_user;

\c sg_bookkeeper

-- inside sg_bookkeeper: revoke public schema rights from everyone
REVOKE ALL ON SCHEMA public FROM PUBLIC, sgbookkeeper_user;

-- allow sgbookkeeper_user full control of its schema
GRANT ALL ON SCHEMA public TO sgbookkeeper_user;
```

---

## 3. Mount the init directory in your compose file

```yaml
version: "3.8"

services:
  db:
    image: postgres:16
    container_name: sg_bookkeeper
    restart: unless-stopped
    environment:
      POSTGRES_USER: sgbookkeeper_user
      POSTGRES_PASSWORD: SGkeeperPass123
      POSTGRES_DB: sg_bookkeeper
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./db/init:/docker-entrypoint-initdb.d   # ← mount init scripts
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $${POSTGRES_USER} -d $${POSTGRES_DB}"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 10s

volumes:
  postgres_data:
    driver: local
```

---

## 4. Re-initialize if you’ve already created the volume

Because `/docker-entrypoint-initdb.d` scripts run **only if** the PGDATA dir is empty, you have two choices:

1. **Fresh start**  
   ```bash
   docker-compose down -v        # destroys postgres_data volume
   docker-compose up -d
   ```
2. **On an existing container**  
   ```bash
   docker exec -it sg_bookkeeper \
     psql -U postgres -c "ALTER USER postgres WITH PASSWORD 'PGAdmin1234';"
   docker exec -it sg_bookkeeper \
     psql -U postgres -d sg_bookkeeper -f /docker-entrypoint-initdb.d/02-lockdown-sgbookkeeper.sql
   ```

---

## 5. How your build can drop & recreate

Now that `postgres` has a known password, your CI/build can:

```bash
PGPASSWORD=PGAdmin1234 psql -h localhost -U postgres \
  -c "DROP DATABASE IF EXISTS sg_bookkeeper;"
PGPASSWORD=PGAdmin1234 psql -h localhost -U postgres \
  -c "CREATE DATABASE sg_bookkeeper OWNER sgbookkeeper_user;"
```

From there, migrations/schema-sync tools (Alembic, Flyway, etc.) connect as `sgbookkeeper_user` and apply changes.

---

### Next steps you might explore

- **Automate routine migrations** via a sidecar container that checks for schema drift on each deploy  
- **Per-environment overrides** by templating that SQL folder (e.g. use `${POSTGRES_ADMIN_PASS}`)  
- **Zero-downtime migrations** using shadow-table or Canary-schema patterns if you can’t afford downtime

---
https://copilot.microsoft.com/shares/3t1BneaVB19JmdvfF3cS7

---
## Does `--build` remove volumes?  

No. `docker compose up --build -d` only forces image rebuilds. It does **not** touch named or anonymous volumes. Volumes persist across restarts and rebuilds unless you explicitly remove them.

---

## When to use `docker compose down -v`  

- If you want to **preserve** your database data (or any persisted volume), just run:  
  ```bash
  docker compose down
  ```  
- If you want to **wipe** all volumes (dropping your DB, caches, etc.) and start truly clean, add `-v`:  
  ```bash
  docker compose down -v
  ```

---

## Typical clean-rebuild workflow  

1. Tear everything down **including** volumes:  
   ```bash
   docker compose down -v
   ```  
2. Rebuild images and start fresh containers:  
   ```bash
   docker compose up --build -d
   ```  

That combo ensures you get brand-new images _and_ empty volume state every time.

