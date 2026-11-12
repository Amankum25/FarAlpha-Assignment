#!/bin/bash
set -eo pipefail

echo "==> Executing MongoDB application user initialization..."

if [ -z "$MONGO_APP_USERNAME" ] || [ -z "$MONGO_APP_PASSWORD" ]; then
  echo "WARN: MONGO_APP_USERNAME or MONGO_APP_PASSWORD not set. Skipping app user creation."
  exit 0
fi

APP_DB="${MONGO_INITDB_DATABASE:-flask_db}"

echo "Creating application user '${MONGO_APP_USERNAME}' for database '${APP_DB}'..."

mongosh -u "$MONGO_INITDB_ROOT_USERNAME" -p "$MONGO_INITDB_ROOT_PASSWORD" --authenticationDatabase admin <<EOF
use $APP_DB;

const existingUser = db.getUser('$MONGO_APP_USERNAME');
if (!existingUser) {
  db.createUser({
    user: '$MONGO_APP_USERNAME',
    pwd: '$MONGO_APP_PASSWORD',
    roles: [
      { role: 'readWrite', db: '$APP_DB' }
    ]
  });
  print("SUCCESS: User '$MONGO_APP_USERNAME' created with readWrite on database '$APP_DB'.");
} else {
  print("NOTICE: User '$MONGO_APP_USERNAME' already exists.");
}
EOF

echo "==> Application user initialization complete."
