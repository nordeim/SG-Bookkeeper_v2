-- 1. Create the sgbookkeeper_user with secure password
CREATE USER sgbookkeeper_user
  WITH PASSWORD 'SGkeeperPass123'
  CREATEDB LOGIN;

-- 2. Create the database owned by that user
CREATE DATABASE sg_bookkeeper
  OWNER sgbookkeeper_user;

-- 3. (Optional) Lock down default postgres database
REVOKE CONNECT ON DATABASE postgres FROM PUBLIC, sgbookkeeper_user;

