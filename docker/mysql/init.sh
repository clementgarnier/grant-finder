#!/bin/bash
# Runs once on first container start (docker-entrypoint-initdb.d), after
# MYSQL_DATABASE/MYSQL_USER (the admin user, from docker-compose env) already exist.
# Creates a SELECT-only user for the MCP server, separate from the admin
# user the loader (scripts/build_mysql.py) uses. Credentials come from the
# container environment (MYSQL_RO_USER/MYSQL_RO_PASSWORD in .env) rather
# than being hardcoded here.
set -euo pipefail

mysql -u root -p"${MYSQL_ROOT_PASSWORD}" <<-EOSQL
    CREATE USER IF NOT EXISTS '${MYSQL_RO_USER}'@'%' IDENTIFIED BY '${MYSQL_RO_PASSWORD}';
    GRANT SELECT ON ${MYSQL_DATABASE}.* TO '${MYSQL_RO_USER}'@'%';
    FLUSH PRIVILEGES;
EOSQL
