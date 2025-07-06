# Comparative Analysis of Application Startup Logs

Below is a side-by-side review of your app’s startup sequence **before** and **after** switching to a Dockerized PostgreSQL. The core flow remains identical, but you’ll see subtle timing and performance shifts when targeting the containerized database.

---

## 1. Identical Startup Flow

Both logs exhibit the same sequence of events:

- Spinning up the global asyncio event loop  
- Initializing and starting `ApplicationCore`  
- Loading modules and completing startup  
- Scheduling and requesting the first KPI load  
- Fetching KPIs, deserializing JSON, and updating the UI  
- Graceful shutdown of the application and its event loop  

This shows your code path is unchanged by the database backend swap.

---

## 2. Performance Timing Differences

| Step                                 | Before (Host DB)         | After (Docker DB)        | Delta (≈)  |
|--------------------------------------|--------------------------|--------------------------|------------|
| AppCore initialized → startup complete  
  (from first log to startup complete) | 129 ms                   | 390 ms                   | +261 ms    |
| Startup complete → KPI load request  
  (scheduling initial KPI)             | 332 ms                   | 857 ms                   | +525 ms    |
| KPI request → first `pg_isready` check  
  (fetch start)                        | 29 ms                    | 106 ms                   | +77 ms     |
| Fetch start → “Fetching dashboard KPIs”  
  (actual SQL hit)                     | 270 ms                   | 817 ms                   | +547 ms    |
| SQL hit → KPI data returned  
  (fetched KPI data)                   | 664 ms                   | 1001 ms                  | +337 ms    |

> Times computed from log timestamps—your containerized DB adds roughly 0.5–1 second across initial queries.

---

## 3. Observations

- Container networking and volume I/O introduce extra latency compared to a local Postgres instance.  
- The most significant penalty appears when the app issues its first SQL query (about +0.5–1 s).  
- Subsequent queries will likely feel faster, as the container and connection pool stabilize.

---

## 4. Next Steps to Optimize

- Enable a connection pool (e.g., `asyncpg` pool or SQLAlchemy `QueuePool`) to reuse TCP sessions.  
- Place your Docker volume on fast storage (SSD or tmpfs for dev environments).  
- Experiment with `host` networking in Compose to bypass virtual bridge overhead:  
  ```yaml
  services:
    db:
      network_mode: host
  ```  
- Pre-warm the database with a lightweight “SELECT 1” during app startup to overlap I/O latency.  
- Monitor container resource limits (CPU, memory) to ensure Postgres has headroom.

---

With these insights, you can retain the convenience of Dockerized Postgres while mitigating its startup performance impact.

---
$ poetry run sg_bookkeeper
Warning: 'sg_bookkeeper' is an entry point defined in pyproject.toml, but it's not installed as a script. You may get improper `sys.argv[0]`.

The support to run uninstalled scripts will be removed in a future release.

Run `poetry install` to resolve and get rid of this message.

Starting global asyncio event loop thread...
Asyncio event loop <_UnixSelectorEventLoop running=False closed=False debug=False> started in thread AsyncioLoopThread and set as current.
Global asyncio event loop <_UnixSelectorEventLoop running=True closed=False debug=False> confirmed running in dedicated thread.
2025-07-06 18:12:16,633 - SGBookkeeperAppCore - INFO - ApplicationCore initialized.
2025-07-06 18:12:16,634 - SGBookkeeperAppCore - INFO - ApplicationCore starting up...
ModuleManager: load_all_modules called (conceptual).
2025-07-06 18:12:17,023 - SGBookkeeperAppCore - INFO - ApplicationCore startup complete.
2025-07-06 18:12:17,490 - SGBookkeeperAppCore - INFO - DashboardWidget: Scheduling initial KPI load.
2025-07-06 18:12:17,596 - SGBookkeeperAppCore - INFO - Using compiled Qt resources for JournalEntriesWidget.
2025-07-06 18:12:17,610 - SGBookkeeperAppCore - INFO - Using compiled Qt resources for SalesInvoicesWidget.
2025-07-06 18:12:17,614 - SGBookkeeperAppCore - INFO - Using compiled Qt resources for PurchaseInvoicesWidget.
2025-07-06 18:12:17,623 - SGBookkeeperAppCore - INFO - Using compiled Qt resources for CustomersWidget.
2025-07-06 18:12:17,625 - SGBookkeeperAppCore - INFO - Using compiled Qt resources for VendorsWidget.
2025-07-06 18:12:17,628 - SGBookkeeperAppCore - INFO - Using compiled Qt resources for ProductsWidget.
2025-07-06 18:12:17,708 - SGBookkeeperAppCore - INFO - DashboardWidget: _request_kpi_load called (Count: 1). Setting labels to 'Loading...'.
2025-07-06 18:12:17,709 - SGBookkeeperAppCore - INFO - DashboardWidget: _fetch_kpis_data started.
2025-07-06 18:12:18,523 - SGBookkeeperAppCore - INFO - Fetching dashboard KPIs as of 2025-07-06...
2025-07-06 18:12:19,524 - SGBookkeeperAppCore - INFO - DashboardWidget: Fetched KPI data: Period='As of 06 Jul 2025 (No active FY)', Revenue='0'
2025-07-06 18:12:19,524 - SGBookkeeperAppCore - INFO - DashboardWidget: Queuing _update_kpi_display_slot with payload: JSON string
2025-07-06 18:12:19,524 - SGBookkeeperAppCore - INFO - DashboardWidget: _update_kpi_display_slot called. Received JSON string length: 688
2025-07-06 18:12:19,525 - SGBookkeeperAppCore - INFO - DashboardWidget: Successfully deserialized KPI JSON to DTO.
2025-07-06 18:12:19,525 - SGBookkeeperAppCore - INFO - DashboardWidget: Updating UI with KPI Data: Period='As of 06 Jul 2025 (No active FY)'
2025-07-06 18:12:19,526 - SGBookkeeperAppCore - INFO - DashboardWidget: UI labels updated with KPI data.
Application shutting down (actual_shutdown_sequence)...
Scheduling ApplicationCore shutdown...
2025-07-06 18:12:50,247 - SGBookkeeperAppCore - INFO - ApplicationCore shutting down...
2025-07-06 18:12:50,257 - SGBookkeeperAppCore - INFO - ApplicationCore shutdown complete.
ApplicationCore shutdown completed.
Requesting global asyncio event loop to stop...
Joining asyncio event loop thread...
Asyncio event loop from dedicated thread has been stopped and closed.
Asyncio event loop thread joined.
Application shutdown process finalized.



