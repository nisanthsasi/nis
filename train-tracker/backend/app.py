"""Flask API server for Indian Railways Train Tracker.

Provides endpoints for:
- Searching trains by number/name
- Getting train routes and schedules
- Live train running status
- ETA calculation to destination
- Journey summary between stations
- Station search
- Trains between two stations
"""

import os
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

from services.train_service import TrainService
from services.eta_service import ETAService

app = Flask(__name__, static_folder="static")
CORS(app)


@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")

# Initialize services
train_service = TrainService()
eta_service = ETAService(train_service)


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "train-tracker-api"})


@app.route("/api/trains/search", methods=["GET"])
def search_trains():
    """Search trains by number or name.

    Query params:
        q: search query (train number or name)
    """
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"error": "Search query 'q' is required"}), 400

    results = train_service.search_trains(query)
    return jsonify({"trains": results, "count": len(results)})


@app.route("/api/trains/<train_number>/route", methods=["GET"])
def get_route(train_number):
    """Get the full route/schedule for a train."""
    route = train_service.get_train_route(train_number)
    if not route:
        return jsonify({"error": f"Train {train_number} not found"}), 404
    return jsonify(route.to_dict())


@app.route("/api/trains/<train_number>/live", methods=["GET"])
def get_live_status(train_number):
    """Get live running status of a train.

    Query params:
        date: date in YYYYMMDD format (optional, defaults to today)
    """
    date = request.args.get("date")
    status = train_service.get_live_status(train_number, date)
    if not status:
        return jsonify({"error": f"Could not get status for train {train_number}"}), 404
    return jsonify(status.to_dict())


@app.route("/api/trains/<train_number>/eta", methods=["GET"])
def get_eta(train_number):
    """Calculate ETA to a destination station.

    Query params:
        station: destination station code (required)
        date: date in YYYYMMDD format (optional)
    """
    station = request.args.get("station", "").strip().upper()
    if not station:
        return jsonify({"error": "Destination station code 'station' is required"}), 400

    date = request.args.get("date")
    eta = eta_service.calculate_eta(train_number, station, date)
    if not eta:
        return jsonify({
            "error": f"Could not calculate ETA for train {train_number} to {station}"
        }), 404
    return jsonify(eta.to_dict())


@app.route("/api/trains/<train_number>/journey", methods=["GET"])
def get_journey(train_number):
    """Get journey summary between two stations.

    Query params:
        from: boarding station code (required)
        to: destination station code (required)
    """
    from_station = request.args.get("from", "").strip().upper()
    to_station = request.args.get("to", "").strip().upper()

    if not from_station or not to_station:
        return jsonify({"error": "'from' and 'to' station codes are required"}), 400

    summary = eta_service.get_journey_summary(train_number, from_station, to_station)
    if not summary:
        return jsonify({
            "error": f"Could not get journey info for {from_station} to {to_station}"
        }), 404
    return jsonify(summary)


@app.route("/api/stations/search", methods=["GET"])
def search_stations():
    """Search stations by code or name.

    Query params:
        q: search query
    """
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"error": "Search query 'q' is required"}), 400

    results = train_service.search_stations(query)
    return jsonify({"stations": results, "count": len(results)})


@app.route("/api/trains/between", methods=["GET"])
def trains_between():
    """Find trains running between two stations.

    Query params:
        from: source station code (required)
        to: destination station code (required)
    """
    from_station = request.args.get("from", "").strip().upper()
    to_station = request.args.get("to", "").strip().upper()

    if not from_station or not to_station:
        return jsonify({"error": "'from' and 'to' station codes are required"}), 400

    results = train_service.get_trains_between_stations(from_station, to_station)
    return jsonify({
        "from": from_station,
        "to": to_station,
        "trains": results,
        "count": len(results),
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "true").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug)
