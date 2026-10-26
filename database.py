import sqlite3
import json
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sudoku.db")


class Database:
    def __init__(self, path=DB_PATH):
        self.path = path
        self._init_db()

    def _connect(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS games (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    difficulty  TEXT    NOT NULL,
                    mistakes    INTEGER NOT NULL DEFAULT 0,
                    time_spent  INTEGER NOT NULL DEFAULT 0,
                    completed   INTEGER NOT NULL DEFAULT 0,
                    created_at  TEXT    NOT NULL
                );

                CREATE TABLE IF NOT EXISTS saved_games (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    name        TEXT    NOT NULL,
                    difficulty  TEXT    NOT NULL,
                    board       TEXT    NOT NULL,
                    solution    TEXT    NOT NULL,
                    original    TEXT    NOT NULL,
                    mistakes    INTEGER NOT NULL DEFAULT 0,
                    saved_at    TEXT    NOT NULL
                );
            """)

    # ---------- games ----------
    def add_game(self, difficulty, mistakes, time_spent, completed):
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO games(difficulty, mistakes, time_spent, completed, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (difficulty, mistakes, time_spent, int(completed),
                 datetime.now().isoformat(timespec="seconds")),
            )
            return cur.lastrowid

    def get_stats(self):
        with self._connect() as conn:
            rows = conn.execute("""
                SELECT difficulty,
                       COUNT(*)            AS total,
                       SUM(completed)      AS wins,
                       AVG(mistakes)       AS avg_mistakes,
                       MIN(time_spent)     AS best_time
                FROM games
                GROUP BY difficulty
            """).fetchall()
        return [dict(r) for r in rows]

    def get_recent_games(self, limit=20):
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM games ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    # ---------- saved games ----------
    def save_game(self, name, game):
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO saved_games(name, difficulty, board, solution, original, mistakes, saved_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    name,
                    game.difficulty,
                    json.dumps(game.board),
                    json.dumps(game.solution),
                    json.dumps(game.original),
                    game.mistakes,
                    datetime.now().isoformat(timespec="seconds"),
                ),
            )
            return cur.lastrowid

    def list_saved(self):
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, name, difficulty, mistakes, saved_at FROM saved_games ORDER BY id DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def load_saved(self, save_id):
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM saved_games WHERE id = ?", (save_id,)
            ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["board"] = json.loads(d["board"])
        d["solution"] = json.loads(d["solution"])
        d["original"] = json.loads(d["original"])
        return d

    def delete_saved(self, save_id):
        with self._connect() as conn:
            conn.execute("DELETE FROM saved_games WHERE id = ?", (save_id,))