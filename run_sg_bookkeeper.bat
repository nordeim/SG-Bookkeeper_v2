@echo off
REM Switch to H: drive and project directory
h:
cd \project\SG-Bookkeeper_v2

REM Activate the virtual environment (Windows CMD syntax)
call .venv\Scripts\activate.bat

REM Set database connection parameters
set PGUSER=sgbookkeeper_user
set PGPASSWORD=SGkeeperPass123
set PGHOST=localhost
set PGPORT=5432
set PGDATABASE=sg_bookkeeper

REM Debug: Show environment variable values
echo PGUSER=%PGUSER%
echo PGPASSWORD=%PGPASSWORD%
echo PGHOST=%PGHOST%
echo PGPORT=%PGPORT%
echo PGDATABASE=%PGDATABASE%

REM Launch the SG Bookkeeper application
poetry run sg_bookkeeper
