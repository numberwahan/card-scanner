import os
from supabase import create_client, Client

_client: Client = None

DEFAULT_FIELDS = [
    {"key": "grader",         "label": "Grader",            "enabled": True},
    {"key": "grade",          "label": "Grade",             "enabled": True},
    {"key": "cert_number",    "label": "Cert Number",       "enabled": True},
    {"key": "year",           "label": "Year",              "enabled": True},
    {"key": "player_name",    "label": "Player",            "enabled": True},
    {"key": "set_name",       "label": "Set / Manufacturer","enabled": True},
    {"key": "card_number",    "label": "Card #",            "enabled": True},
    {"key": "variation",      "label": "Variation",         "enabled": True},
    {"key": "sport_category", "label": "Sport",             "enabled": True},
    {"key": "purchase_price", "label": "Purchase Price",    "enabled": True},
    {"key": "value",          "label": "Value",             "enabled": True},
    {"key": "sold_price",     "label": "Sold Price",        "enabled": True},
    {"key": "sold_date",      "label": "Sold Date",         "enabled": True},
    {"key": "date_scanned",   "label": "Date Scanned",      "enabled": True},
]

ORIGINAL_LABELS = {f["key"]: f["label"] for f in DEFAULT_FIELDS}


def get_client() -> Client:
    global _client
    if _client is None:
        url = os.environ.get("SUPABASE_URL", "")
        key = os.environ.get("SUPABASE_SECRET_KEY", "")
        _client = create_client(url, key)
    return _client


def verify_token(token: str) -> str | None:
    """Verify a Supabase access token and return the user_id (sub), or None."""
    try:
        sb = get_client()
        response = sb.auth.get_user(token)
        return response.user.id if response.user else None
    except Exception as e:
        print(f"[auth] verify_token: {e}")
        return None


# ── Field config ──────────────────────────────────────────────────────────────

def get_field_config(user_id: str) -> list | None:
    try:
        sb = get_client()
        result = sb.table("field_config").select("fields").eq("user_id", user_id).execute()
        if result.data:
            return result.data[0]["fields"]
        return None
    except Exception as e:
        print(f"[db] get_field_config: {e}")
        return None


def save_field_config(fields: list, user_id: str) -> bool:
    try:
        sb = get_client()
        sb.table("field_config").upsert({"user_id": user_id, "fields": fields}).execute()
        return True
    except Exception as e:
        print(f"[db] save_field_config: {e}")
        return False


# ── Cards ─────────────────────────────────────────────────────────────────────

def get_all_cards(user_id: str) -> list[dict]:
    try:
        sb = get_client()
        result = sb.table("cards").select("*").eq("user_id", user_id).order("created_at").execute()
        return result.data or []
    except Exception as e:
        print(f"[db] get_all_cards: {e}")
        return []


def insert_card(data: dict, user_id: str) -> dict | None:
    try:
        sb = get_client()
        row = {
            "user_id":        user_id,
            "grader":         data.get("grader"),
            "grade":          data.get("grade"),
            "cert_number":    data.get("cert_number"),
            "year":           data.get("year"),
            "player_name":    data.get("player_name"),
            "set_name":       data.get("set_name"),
            "card_number":    data.get("card_number"),
            "variation":      data.get("variation"),
            "sport_category": data.get("sport_category"),
            "purchase_price": data.get("purchase_price"),
            "value":          data.get("value"),
            "image_path":     data.get("image_path"),
        }
        result = sb.table("cards").insert(row).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        print(f"[db] insert_card: {e}")
        return None


def update_card(card_id: int, fields: dict, user_id: str) -> bool:
    try:
        sb = get_client()
        sb.table("cards").update(fields).eq("id", card_id).eq("user_id", user_id).execute()
        return True
    except Exception as e:
        print(f"[db] update_card: {e}")
        return False


def delete_card(card_id: int, user_id: str) -> bool:
    try:
        sb = get_client()
        sb.table("cards").delete().eq("id", card_id).eq("user_id", user_id).execute()
        return True
    except Exception as e:
        print(f"[db] delete_card: {e}")
        return False


def delete_all_cards(user_id: str) -> bool:
    try:
        sb = get_client()
        sb.table("cards").delete().eq("user_id", user_id).execute()
        return True
    except Exception as e:
        print(f"[db] delete_all_cards: {e}")
        return False


def count_cards(user_id: str) -> int:
    try:
        sb = get_client()
        result = sb.table("cards").select("id", count="exact").eq("user_id", user_id).execute()
        return result.count or 0
    except Exception:
        return 0


# ── Images ────────────────────────────────────────────────────────────────────

def upload_image(filename: str, image_bytes: bytes, content_type: str = "image/jpeg") -> str | None:
    try:
        sb = get_client()
        sb.storage.from_("card-images").upload(
            filename, image_bytes,
            {"content-type": content_type, "upsert": "true"}
        )
        return sb.storage.from_("card-images").get_public_url(filename)
    except Exception as e:
        print(f"[db] upload_image: {e}")
        return None
