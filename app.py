import csv
import io
import os
import socket
import uuid
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from flask import Flask, jsonify, render_template, request, send_file

from card_ocr import extract_card_data
from db import (
    DEFAULT_FIELDS, get_field_config, save_field_config,
    get_all_cards, insert_card, update_card, delete_card, delete_all_cards,
    count_cards, upload_image, verify_token,
)
from spreadsheet import generate_excel

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024

UPLOAD_DIR = Path(__file__).parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".heic"}


def _get_api_key():
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY environment variable is not set.")
    return key


def _local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


def _get_user_id():
    """Extract and verify Bearer token from Authorization header or ?token= query param."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return verify_token(auth[7:])
    token = request.args.get("token", "")
    if token:
        return verify_token(token)
    return None


@app.route("/")
def index():
    return render_template("index.html")


# ── Field config ──────────────────────────────────────────────────────────────

@app.route("/field-config", methods=["GET"])
def get_config():
    user_id = _get_user_id()
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401
    config = get_field_config(user_id)
    return jsonify({"config": config})


@app.route("/field-config", methods=["POST"])
def post_config():
    user_id = _get_user_id()
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json()
    if not data or "fields" not in data:
        return jsonify({"error": "Missing fields"}), 400
    ok = save_field_config(data["fields"], user_id)
    return jsonify({"success": ok})


# ── Scan ──────────────────────────────────────────────────────────────────────

@app.route("/scan", methods=["POST"])
def scan():
    user_id = _get_user_id()
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    if "image" not in request.files:
        return jsonify({"error": "No image uploaded"}), 400

    file = request.files["image"]
    suffix = Path(file.filename).suffix.lower() if file.filename else ".jpg"
    if suffix not in ALLOWED_EXTENSIONS:
        suffix = ".jpg"

    filename = f"{uuid.uuid4().hex}{suffix}"
    save_path = UPLOAD_DIR / filename
    file.save(str(save_path))

    try:
        with open(save_path, "rb") as f:
            image_bytes = f.read()
        image_path = upload_image(filename, image_bytes)

        api_key = _get_api_key()
        multi = request.form.get("multi") == "1"
        cards = extract_card_data(str(save_path), api_key, multi=multi)
        for card in cards:
            card["image_path"] = image_path or ""
        return jsonify({"success": True, "cards": cards, "count": len(cards)})
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        return jsonify({"error": f"OCR failed: {e}"}), 500


# ── Cards CRUD ────────────────────────────────────────────────────────────────

@app.route("/save", methods=["POST"])
def save():
    user_id = _get_user_id()
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data"}), 400
    card = insert_card(data, user_id)
    if card is None:
        return jsonify({"error": "Insert failed"}), 500
    return jsonify({"success": True, "count": count_cards(user_id), "card": card})


@app.route("/cards")
def cards():
    user_id = _get_user_id()
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify(get_all_cards(user_id))


@app.route("/update/<int:card_id>", methods=["PATCH"])
def update(card_id):
    user_id = _get_user_id()
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data"}), 400
    ok = update_card(card_id, data, user_id)
    return jsonify({"success": ok})


@app.route("/delete/<int:card_id>", methods=["DELETE"])
def delete(card_id):
    user_id = _get_user_id()
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401
    ok = delete_card(card_id, user_id)
    return jsonify({"success": ok})


@app.route("/delete-all", methods=["DELETE"])
def delete_all():
    user_id = _get_user_id()
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401
    ok = delete_all_cards(user_id)
    return jsonify({"success": ok})


# ── Export ────────────────────────────────────────────────────────────────────

@app.route("/download")
def download():
    user_id = _get_user_id()
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401
    all_cards = get_all_cards(user_id)
    config = get_field_config(user_id) or DEFAULT_FIELDS
    buf = generate_excel(all_cards, config)
    return send_file(buf, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                     as_attachment=True, download_name="graded_cards.xlsx")


@app.route("/download/csv")
def download_csv():
    user_id = _get_user_id()
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401
    all_cards = get_all_cards(user_id)
    config = get_field_config(user_id) or DEFAULT_FIELDS
    enabled = [f for f in config if f.get("enabled", True)]
    buf = io.StringIO()
    headers = [f["label"] for f in enabled]
    writer = csv.DictWriter(buf, fieldnames=headers, extrasaction="ignore")
    writer.writeheader()
    for card in all_cards:
        row = {f["label"]: card.get(f["key"]) for f in enabled}
        writer.writerow(row)
    output = io.BytesIO(buf.getvalue().encode("utf-8"))
    return send_file(output, mimetype="text/csv", as_attachment=True,
                     download_name="graded_cards.csv")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    ip = _local_ip()
    print(f"\n  Card Scanner running at:")
    print(f"  Local:   http://localhost:{port}")
    print(f"  Network: http://{ip}:{port}")
    print(f"\n  Make sure ANTHROPIC_API_KEY is set in your environment.\n")
    app.run(host="0.0.0.0", port=port, debug=False)
