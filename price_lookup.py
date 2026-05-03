import json
import os
import re
import statistics

import anthropic

PROMPT = """You are a sports and trading card market expert. Estimate the current market value of this graded card based on recent eBay sold listings and your knowledge of the card market.

Card details:
- Player / Subject: {player_name}
- Year: {year}
- Set / Manufacturer: {set_name}
- Card Number: {card_number}
- Grader: {grader}
- Grade: {grade}
- Variation / Parallel: {variation}
- Sport / Category: {sport_category}

Return ONLY a JSON object, no explanation:
{{"value": "$X.XX"}}

Use your best estimate of the median recent sold price. If there is genuinely not enough information to estimate, return {{"value": null}}."""


def get_estimated_value(data: dict) -> dict | None:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return None

    player   = data.get("player_name") or ""
    grader   = data.get("grader") or ""
    grade    = data.get("grade") or ""

    # Need at least a player/subject and grade to estimate
    if not player or not (grader and grade):
        return None

    client = anthropic.Anthropic(api_key=api_key)

    prompt = PROMPT.format(
        player_name=player,
        year=data.get("year") or "unknown",
        set_name=data.get("set_name") or "unknown",
        card_number=data.get("card_number") or "unknown",
        grader=grader,
        grade=grade,
        variation=data.get("variation") or "base",
        sport_category=data.get("sport_category") or "unknown",
    )

    try:
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=64,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        result = json.loads(raw)
        value = result.get("value")
        if value and str(value).lower() != "null":
            return {"value": str(value), "source": "est.", "n": 1}
        print(f"[price_lookup] Claude returned no value for: {player} {grader} {grade}")
    except Exception as e:
        print(f"[price_lookup] Error: {e}")

    return None
