from flask import Flask, jsonify, request
from database import Database

db = Database()


def create_app():
    app = Flask(__name__)

    @app.get("/api/stats")
    def stats():
        return jsonify(db.get_stats())

    @app.get("/api/games")
    def games():
        limit = int(request.args.get("limit", 20))
        return jsonify(db.get_recent_games(limit))

    @app.get("/api/saves")
    def saves():
        return jsonify(db.list_saved())

    @app.get("/api/saves/<int:save_id>")
    def load_save(save_id):
        data = db.load_saved(save_id)
        if not data:
            return jsonify({"error": "not found"}), 404
        return jsonify(data)

    @app.delete("/api/saves/<int:save_id>")
    def delete_save(save_id):
        db.delete_saved(save_id)
        return jsonify({"ok": True})

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok"})

    return app


def run_api(host="127.0.0.1", port=5000):
    app = create_app()
    app.run(host=host, port=port, debug=False, use_reloader=False)