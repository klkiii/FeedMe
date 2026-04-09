"""
FeedMe — Flask backend
Run: python app.py
"""
import os
import re
import psycopg2
import psycopg2.extras
from flask import Flask, jsonify
from datetime import datetime, timedelta

DATABASE_URL = os.environ.get("DATABASE_URL")

app = Flask(__name__, static_folder="static", static_url_path="")


def get_conn():
    return psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)


def parse_date_for_sort(date_text):
    if not date_text:
        return datetime.max

    # Strip time portion AND anything after comma (handles ", null", ", 6pm", etc.)
    cleaned = date_text.split(",")[0].strip()

    # Strip ordinal suffixes: 29th → 29
    cleaned = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', cleaned)

    # Strip day names: "Thursday 12 March 2026" → "12 March 2026"
    cleaned = re.sub(r'^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\s+', '', cleaned, flags=re.IGNORECASE).strip()

    # Strip any remaining "null" words
    if 'null' in cleaned.lower() or not cleaned:
        return datetime.max

    formats = [
        "%d %B %Y",   # 12 March 2026
        "%d %b %Y",   # 12 Mar 2026
        "%B %d %Y",   # March 12 2026
        "%b %d %Y",   # Mar 12 2026
        "%d/%m/%Y",   # 12/03/2026
        "%Y-%m-%d",   # 2026-03-12
        "%B %Y",      # March 2026
        "%b %Y",      # Mar 2026
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
        # Use yesterday so today's events are always included
        cutoff = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
        rows = [r for r in rows if r["_parsed_date"] >= cutoff]

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