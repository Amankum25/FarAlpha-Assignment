import os
import time
from datetime import datetime
from urllib.parse import quote_plus
from flask import Flask, request, jsonify
from pymongo import MongoClient
from pymongo.errors import PyMongoError

app = Flask(__name__)

# Configuration via environment variables
DB_NAME = os.getenv("MONGODB_DATABASE", "flask_db")
DB_HOST = os.getenv("MONGODB_HOST", "localhost")
DB_PORT = os.getenv("MONGODB_PORT", "27017")
DB_USER = os.getenv("MONGO_APP_USERNAME")
DB_PASS = os.getenv("MONGO_APP_PASSWORD")
CUSTOM_URI = os.getenv("MONGODB_URI")

if CUSTOM_URI:
    mongo_uri = CUSTOM_URI
elif DB_USER and DB_PASS:
    user = quote_plus(DB_USER)
    password = quote_plus(DB_PASS)
    mongo_uri = f"mongodb://{user}:{password}@{DB_HOST}:{DB_PORT}/{DB_NAME}?authSource={DB_NAME}"
else:
    mongo_uri = f"mongodb://{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Initialize MongoDB client with sensible timeouts
client = MongoClient(
    mongo_uri,
    serverSelectionTimeoutMS=3000,
    connectTimeoutMS=3000,
)
db = client[DB_NAME]
collection = db.data


@app.route("/", methods=["GET"])
def index():
    """Root endpoint: returns welcome message with current timestamp."""
    return f"Welcome to the Flask app! The current time is: {datetime.now()}"


@app.route("/data", methods=["GET", "POST"])
def data():
    """Data endpoint:
    - POST: inserts document into MongoDB 'data' collection
    - GET: retrieves all documents excluding '_id'
    """
    if request.method == "POST":
        payload = request.get_json(silent=True)
        if not payload or not isinstance(payload, dict):
            return jsonify({"error": "A valid JSON object is required"}), 400

        try:
            collection.insert_one(payload)
            # Response matching the exact assignment specification
            return jsonify({"status": "Data inserted"}), 201
        except PyMongoError as exc:
            app.logger.error("Failed to insert data into MongoDB: %s", exc)
            return jsonify({"error": "Database operation failed"}), 503

    elif request.method == "GET":
        try:
            results = list(collection.find({}, {"_id": 0}))
            return jsonify(results), 200
        except PyMongoError as exc:
            app.logger.error("Failed to fetch data from MongoDB: %s", exc)
            return jsonify({"error": "Database operation failed"}), 503


@app.route("/health/live", methods=["GET"])
def live():
    """Liveness probe: verifies the web application process is running."""
    return jsonify({"status": "alive"}), 200


@app.route("/health/ready", methods=["GET"])
def ready():
    """Readiness probe: verifies active database connectivity before receiving traffic."""
    try:
        client[DB_NAME].command("ping")
        return jsonify({"status": "ready"}), 200
    except PyMongoError as exc:
        app.logger.warning("Readiness check failed - database ping failed: %s", exc)
        return jsonify({"status": "not ready", "reason": "database unavailable"}), 503


@app.route("/stress/cpu", methods=["GET"])
def stress_cpu():
    """Test helper for HPA autoscaling testing:
    Generates controlled CPU load to trigger Horizontal Pod Autoscaler.
    Query param 'duration' in seconds (default 2, max 30).
    """
    duration = min(float(request.args.get("duration", 2)), 30.0)
    end_time = time.time() + duration
    count = 0
    while time.time() < end_time:
        _ = 999999 * 999999
        count += 1
    return jsonify({"status": "CPU stress completed", "duration_seconds": duration, "cycles": count}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)

