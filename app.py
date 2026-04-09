"""
FeedMe — Flask backend
Run: python app.py
"""
import os
import re
import psycopg2
import psycopg2.extras
from flask import Flask, jsonify
from datetime import datetime

DATABASE_URL = os.environ.get("DATABASE_URL")

app = Flask(__name__, static_folder="static", static_url_path="")


def get_conn():
    return psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)


def parse_date_for_sort(date_text):
    if not date_text or 'null' in date_text.lower():
        return datetime.max
    cleaned = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', date_text)
    cleaned = re.sub(r',.*$', '', cleaned).strip()
    cleaned = re.sub(r'^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\s+', '', cleaned, flags=re.IGNORECASE).strip()
    formats = [
        "%d %B %Y", "%d %b %Y", "%B %d %Y",
        "%b %d %Y", "%d/%m/%Y", "%Y-%m-%d",
        "%B %Y", "%b %Y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(cleaned, fmt)
        except ValueError:
            continue
    return datetime.max


def get_events(filter_past=True):
    con = get_conn()
    cur = con.cursor()
    cur.execute("""
        SELECT title, date_text, location, club, free_food, food_desc,
               is_paid, price, post_url, created_at
        FROM events
    """)
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()
    con.close()

    for r in rows:
        r["_parsed_date"] = parse_date_for_sort(r.get("date_text"))

    rows.sort(key=lambda e: e["_parsed_date"])

    if filter_past:
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        rows = [r for r in rows if r["_parsed_date"] >= today]

    for r in rows:
        r["parsed_date"] = None if r["_parsed_date"] == datetime.max else r["_parsed_date"].strftime("%Y-%m-%d")
        del r["_parsed_date"]

    return rows


@app.route("/api/events")
def events():
    return jsonify(get_events(filter_past=True))


@app.route("/api/events/all")
def events_all():
    return jsonify(get_events(filter_past=False))


@app.route("/api/debug")
def debug():
    con = get_conn()
    cur = con.cursor()
    cur.execute("SELECT title, date_text FROM events")
    rows = cur.fetchall()
    cur.close()
    con.close()
    today = datetime.now()
    return jsonify([{
        "title": r["title"],
        "date_text": r["date_text"],
        "parsed": str(parse_date_for_sort(r["date_text"])),
        "kept": parse_date_for_sort(r["date_text"]) >= today
    } for r in rows])


@app.route("/")
def index():
    return app.send_static_file("index.html")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)