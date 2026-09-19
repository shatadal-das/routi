import os
import json
import re
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

# Configure Gemini API
API_KEY = os.getenv("GEMINI_API_KEY")
if API_KEY:
    try:
        genai.configure(api_key=API_KEY, transport="rest")
    except Exception as e:
        print(f"Warning configuring Gemini in ai_curator.py: {e}")


def get_curator_model() -> genai.GenerativeModel:
    """
    Instantiate gemini-3.8-flash model with fallback to other flash models if needed.
    """
    primary_model = "gemini-2.5-flash"
    fallback_models = ["gemini-flash-latest", "gemini-3.8-flash"]

    try:
        return genai.GenerativeModel(primary_model)
    except Exception as e:
        print(f"Warning: Primary model {primary_model} failed to instantiate: {e}")
        for fb in fallback_models:
            try:
                return genai.GenerativeModel(fb)
            except Exception:
                continue
        raise RuntimeError("No compatible Gemini Flash model could be initialized.")


def curate_itinerary(
    places_list: List[Dict[str, Any]],
    time_hours: float,
    vibe_preference: Optional[str] = None,
    price_level: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Use Gemini (gemini-3.8-flash) to dynamically curate the best combination
    of places and realistic visit durations based on user vibe and budget.

    Returns a list of dicts:
    [
        {
            "place_id": str,
            "duration_mins": int,
            "ai_reasoning": str
        },
        ...
    ]
    """
    if not places_list:
        return []

    vibe = vibe_preference.strip() if vibe_preference and vibe_preference.strip() else "Balanced sightseeing, scenic views, and popular local dining"
    budget = price_level.strip() if price_level and price_level.strip() else "Moderate / Flexible"

    # Format simplified candidate list for the prompt
    candidates = []
    for p in places_list:
        candidates.append({
            "place_id": p.get("place_id"),
            "name": p.get("name"),
            "rating": p.get("rating"),
            "types": p.get("types", [p.get("type")]),
            "price_level": p.get("price_level", "Unknown"),
            "address": p.get("address", "")
        })

    prompt = f"""You are an elite travel concierge and AI time-management expert.
The user is planning a personalized day trip with the following constraints:
- Total Time Available: {time_hours} hours total ({int(time_hours * 60)} minutes including transit between stops).
- Desired Vibe / Theme: "{vibe}"
- Budget / Price Tier: "{budget}"

Here is the candidate list of top places discovered in the area:
{json.dumps(candidates, indent=2)}

Instructions:
1. Select the optimal subset of candidate places that best matches the requested vibe ("{vibe}") and budget ("{budget}").
2. AI Time Estimation (Crucial): For EACH selected spot, allocate a realistic visit duration rounded to clean 15-minute increments (e.g. 30, 45, 60, 75, 90, or 120 mins, NEVER odd numbers like 38 or 52 mins) based on:
   - Venue scale and nature (e.g., 30-45 mins for quick bakeries/cafes/viewpoints, 60-75 mins for parks/markets/casual dining, 90-120 mins for major museums or full sit-down meals).
   - Expected pace and buffer for ordering/queuing.
   - Pacing within the user's total available {time_hours} hours (assuming ~15-20 minutes transit between stops).
3. Provide "time_estimate_reason": Exactly 1 sentence detailing why this specific time duration was allocated (e.g. "45 minutes allows ample time to sample signature pastries and coffee without rushing").
4. Provide "ai_reasoning": Exactly 1 sentence explaining why this place was chosen for the requested vibe and budget.

You must output a JSON array conforming to this schema:
[
  {{
    "place_id": "exact_place_id_from_candidates",
    "duration_mins": 60,
    "time_estimate_reason": "Specific rationale for the estimated visit duration.",
    "ai_reasoning": "Why this place fits the requested theme and budget."
  }}
]
"""

    models_to_try = ["gemini-2.5-flash", "gemini-flash-latest", "gemini-3.8-flash"]
    curated_data = None

    for model_name in models_to_try:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(
                prompt,
                generation_config={"response_mime_type": "application/json"}
            )

            response_text = response.text.strip()
            # Clean any accidental markdown code block formatting
            if response_text.startswith("```"):
                response_text = re.sub(r"^```(?:json)?\s*", "", response_text)
                response_text = re.sub(r"\s*```$", "", response_text)

            parsed = json.loads(response_text)
            if isinstance(parsed, list) and len(parsed) > 0:
                curated_data = parsed
                print(f"Successfully curated itinerary with AI time estimation using {model_name}")
                break
        except Exception as e:
            print(f"Model {model_name} attempt failed ({e}), trying fallback...")
            continue

    if not curated_data:
        print("All Gemini models failed or rate limited. Using dynamic heuristic fallback.")
        return _fallback_curation(places_list, time_hours)

    # Validate entries
    valid_place_ids = {p.get("place_id") for p in places_list if p.get("place_id")}
    validated_items = []
    for item in curated_data:
        if isinstance(item, dict) and item.get("place_id") in valid_place_ids:
            dur = int(item.get("duration_mins") or 60)
            validated_items.append({
                "place_id": item["place_id"],
                "duration_mins": dur,
                "time_estimate_reason": str(item.get("time_estimate_reason") or f"AI estimated {dur} minutes based on typical visitor dwell time."),
                "ai_reasoning": str(item.get("ai_reasoning") or "Curated highlight matching your day trip vibe.")
            })

    if validated_items:
        return validated_items
    else:
        print("Warning: No matching place_ids from Gemini response. Falling back to default selection.")
        return _fallback_curation(places_list, time_hours)


def _estimate_venue_time(place: Dict[str, Any]) -> tuple[int, str]:
    """
    Intelligently estimate duration and reason based on venue types.
    """
    types = [t.lower() for t in place.get("types", [])]
    name = place.get("name", "").lower()

    if any(t in types for t in ["museum", "art_gallery"]):
        return 90, "90 minutes estimated to tour key exhibition galleries and exhibits."
    if any(t in types for t in ["bakery", "cafe"]) or "coffee" in name or "bakery" in name:
        return 45, "45 minutes estimated to order, sample signature items, and relax."
    if any(t in types for t in ["park", "campground"]) or "park" in name:
        return 60, "60 minutes estimated for scenic walking trails and skyline viewpoints."
    if any(t in types for t in ["restaurant", "food"]):
        return 75, "75 minutes estimated for a relaxed dining experience."
    return 60, "60 minutes estimated for a comprehensive visit."


def _fallback_curation(places_list: List[Dict[str, Any]], time_hours: float) -> List[Dict[str, Any]]:
    """
    Deterministic fallback with dynamic time estimation based on venue characteristics.
    """
    selected = []
    restaurants = [p for p in places_list if p.get("type") == "restaurant"]
    attractions = [p for p in places_list if p.get("type") != "restaurant"]

    if restaurants:
        r = restaurants[0]
        dur, reason = _estimate_venue_time(r)
        selected.append({
            "place_id": r["place_id"],
            "duration_mins": dur,
            "time_estimate_reason": reason,
            "ai_reasoning": "Top-rated dining destination selected for your meal stop."
        })

    max_attractions = max(1, min(4, int(time_hours - 2.0)))
    for att in attractions[:max_attractions]:
        dur, reason = _estimate_venue_time(att)
        selected.append({
            "place_id": att["place_id"],
            "duration_mins": dur,
            "time_estimate_reason": reason,
            "ai_reasoning": "Highly rated attraction selected for your itinerary."
        })

    return selected
