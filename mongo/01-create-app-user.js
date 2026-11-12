// MongoDB initialization script for mongosh
// Note: When executed directly, ensure MONGO_APP_USERNAME and MONGO_APP_PASSWORD are provided.
const targetDb = db.getSiblingDB(process.env.MONGO_INITDB_DATABASE || "flask_db");
const appUsername = process.env.MONGO_APP_USERNAME;
const appPassword = process.env.MONGO_APP_PASSWORD;

if (appUsername && appPassword) {
  if (!targetDb.getUser(appUsername)) {
    targetDb.createUser({
      user: appUsername,
      pwd: appPassword,
      roles: [{ role: "readWrite", db: targetDb.getName() }]
    });
    print(`User ${appUsername} created successfully on ${targetDb.getName()}`);
  } else {
    print(`User ${appUsername} already exists on ${targetDb.getName()}`);
  }
} else {
  print("Warning: MONGO_APP_USERNAME or MONGO_APP_PASSWORD not available in process.env");
}
