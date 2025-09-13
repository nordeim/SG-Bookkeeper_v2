@echo off
REM Switch to H: drive and project directory
h:
cd \project\SG-Bookkeeper_v2

REM Activate the virtual environment (Windows CMD syntax)
call .venv\Scripts\activate.bat

REM Set database connection parameters
set PGUSER=your_db_user
set PGPASSWORD=your_db_password
set PGHOST=localhost
set PGPORT=5432
set PGDATABASE=your_db_name

REM Launch the SG Bookkeeper application
poetry run sg_bookkeeper
