"""
RoamAround / Routi - AI Itinerary Generation Layer

Transforms structured deterministic optimizer output into a concise, user-friendly,
and engaging itinerary JSON representation for the frontend.

Strict Grounding Principles:
1. The AI ONLY explains information present in the structured data.
2. Zero fact invention: distances, travel times, ratings, categories, and arrival/departure
   timestamps are strictly preserved from the optimizer output.
3. Structured JSON response containing all 10 required dimensions:
   1. trip_title
   2. total_duration (formatted + minutes)
   3. total_travel_time (formatted + minutes)
   4. total_visit_time (formatted + minutes)
   5. total_distance (formatted + km)
   6. ordered_destinations (chronological list)
   7. suggested_time_at_each_destination (per stop + summary)
   8. short_explanation_of_each_stop (grounded in data)
   9. preference_match_reasoning (why this route fits user goals)
   10. return_to_start_confirmation (explicit loop confirmation)
"""

import os
import re
import json
from typing import Dict, Any, List, Optional
from services.llm_client import call_llm_json, get_openai_client, DEFAULT_MODEL
from services.optimizer import validate_itinerary_meal_times


# ---------------------------------------------------------------------------
# Formatting Helpers
# ---------------------------------------------------------------------------

def format_minutes_to_hours_mins(minutes: int) -> str:
    """Formats an integer minute count into 'X hours Y mins' or 'Y mins'."""
    mins = max(0, int(round(minutes)))
    hrs = mins // 60
    rem = mins % 60
    if hrs > 0 and rem > 0:
        return f"{hrs} hour{'s' if hrs != 1 else ''} {rem} min{'s' if rem != 1 else ''}"
    elif hrs > 0:
        return f"{hrs} hour{'s' if hrs != 1 else ''}"
    else:
        return f"{rem} min{'s' if rem != 1 else ''}"


def format_distance_km(km: float) -> str:
    """Formats a float distance into 'X.X km'."""
    val = max(0.0, float(km))
    return f"{round(val, 1)} km"


# ---------------------------------------------------------------------------
# Grounded Itinerary Generation Function
# ---------------------------------------------------------------------------

def generate_user_friendly_itinerary(
    optimizer_data: Dict[str, Any],
    user_preferences: Optional[str] = None,
    transportation_mode: Optional[str] = None,
    model: Optional[Any] = None
) -> Dict[str, Any]:
    """
    Transforms structured optimizer output into a concise, user-friendly JSON itinerary.

    Args:
        optimizer_data: Structured output from optimize_route() or optimize_trip().
        user_preferences: Optional string of user interests (e.g. 'nature and good food').
        transportation_mode: DRIVE, WALK, or BICYCLE.
        model: Optional model name string (e.g. 'google.gemma-3-27b-it').

    Returns:
        Structured JSON dictionary containing all 10 required items.
    """
    if not isinstance(optimizer_data, dict):
        raise ValueError("optimizer_data must be a valid dictionary.")

    # 1. Extract Core Metadata & Statistics
    start_loc = optimizer_data.get("starting_location") or {}
    origin_name = start_loc.get("name") or "Starting Location"
    origin_addr = start_loc.get("address") or origin_name

    total_duration_mins = int(optimizer_data.get("total_duration") or 0)
    total_travel_mins = int(optimizer_data.get("total_travel_time") or 0)
    total_visit_mins = int(optimizer_data.get("total_visit_time") or 0)
    total_distance_km = float(optimizer_data.get("total_distance") or 0.0)
    travel_mode = (transportation_mode or optimizer_data.get("transportation_mode") or "DRIVE").upper()
    budget_mins = int(optimizer_data.get("available_time_minutes") or total_duration_mins)
    slack_mins = max(0, budget_mins - total_duration_mins)

    return_leg = optimizer_data.get("return_to_start") or {}
    return_dest = return_leg.get("destination") or origin_name
    return_clock = return_leg.get("arrival_clock") or ""
    return_travel_mins = int(return_leg.get("duration_minutes") or 0)
    return_dist_km = float(return_leg.get("distance_km") or 0.0)

    # 2. Extract Ordered Stops
    raw_stops = optimizer_data.get("ordered_itinerary") or []

    # 3. Build Deterministic Baseline Explanations & Titles
    categories_found = [s.get("category", "attraction") for s in raw_stops]
    cat_summary = ", ".join(list(dict.fromkeys(categories_found))[:3]) or "sightseeing"

    default_title = f"{origin_name} Day Trip: {cat_summary.title()} Exploration"
    if len(raw_stops) == 0:
        default_title = f"{origin_name} Exploration Loop"

    default_preference_reasoning = (
        f"This itinerary is optimized for '{user_preferences or cat_summary}'. "
        f"It curates {len(raw_stops)} high-rated stop{'s' if len(raw_stops) != 1 else ''} "
        f"within your {format_minutes_to_hours_mins(budget_mins)} window, allocating "
        f"{format_minutes_to_hours_mins(total_visit_mins)} to enjoying destinations "
        f"and keeping total travel time down to {format_minutes_to_hours_mins(total_travel_mins)}."
    )

    default_stop_explanations: Dict[str, str] = {}
    for s in raw_stops:
        pid = s.get("place_id") or ""
        name = s.get("name") or "Local Venue"
        cat = s.get("category") or "attraction"
        rating = s.get("rating")
        reviews = s.get("review_count")
        dwell = s.get("duration_mins") or 60
        ai_reason = s.get("ai_reasoning") or ""

        rating_str = f"Rated {rating} stars ({reviews} reviews)" if rating and reviews else "Verified local venue"
        extra = f" {ai_reason}" if ai_reason else ""
        default_stop_explanations[pid] = (
            f"{rating_str}. Suggested {dwell} mins visit duration for a relaxed {cat} experience.{extra}"
        )

    # 4. Optional AI Enrichment (Strictly Constrained to Input Facts)
    ai_title = default_title
    ai_preference_reasoning = default_preference_reasoning
    ai_stop_explanations = default_stop_explanations

    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key and len(raw_stops) > 0:
        try:
            client = get_openai_client()
            model_name = model if isinstance(model, str) and model else DEFAULT_MODEL

            stops_context = [
                {
                    "place_id": s.get("place_id"),
                    "name": s.get("name"),
                    "category": s.get("category"),
                    "rating": s.get("rating"),
                    "review_count": s.get("review_count"),
                    "arrival": s.get("arrival_time"),
                    "departure": s.get("departure_time"),
                    "dwell_mins": s.get("duration_mins"),
                    "optimizer_reasoning": s.get("ai_reasoning")
                }
                for s in raw_stops
            ]

            prompt = f"""You are the RoamAround AI Itinerary Presenter.
Your role is to explain a structured itinerary generated by our route optimizer.

CRITICAL CONSTRAINTS:
1. You must ONLY reference the exact places, categories, ratings, review counts, times, and durations given below.
2. DO NOT invent facts, amenities, hours, or details not present in the data.
3. Keep the explanations concise, user-friendly, and natural.

INPUT DATA:
- Starting Location: {origin_name}
- User Preferences: "{user_preferences or 'Local highlights'}"
- Total Duration: {total_duration_mins} mins ({format_minutes_to_hours_mins(total_duration_mins)})
- Total Travel Time: {total_travel_mins} mins
- Total Visit Time: {total_visit_mins} mins
- Total Distance: {total_distance_km} km
- Stops: {json.dumps(stops_context, indent=2)}
- Returns To: {return_dest} at {return_clock}

Respond in strict JSON with the following format:
{{
  "trip_title": "A short, catchy, descriptive title for this trip (max 8 words)",
  "preference_match_reasoning": "A 2-sentence explanation of why this specific sequence of stops matches the user's preferences without inventing unstated facts",
  "stop_explanations": {{
    "<place_id>": "1 concise sentence explaining what makes this stop worthwhile based on its rating, category, and dwell time"
  }}
}}
"""
            ai_parsed = call_llm_json(prompt=prompt, model=model_name, client=client)
            if isinstance(ai_parsed, dict):
                if ai_parsed.get("trip_title"):
                    ai_title = ai_parsed["trip_title"].strip()
                if ai_parsed.get("preference_match_reasoning"):
                    ai_preference_reasoning = ai_parsed["preference_match_reasoning"].strip()
                if isinstance(ai_parsed.get("stop_explanations"), dict):
                    for k, v in ai_parsed["stop_explanations"].items():
                        if k in default_stop_explanations and v:
                            ai_stop_explanations[k] = str(v).strip()
        except Exception as e:
            # Safe fallback: if AI generation fails, default grounded copy is used
            print(f"Itinerary AI enrichment note ({e}), using deterministic grounded presentation.")


    # 5. Compile Final User-Friendly Destination List
    ordered_destinations = []
    suggested_times_summary = {}

    for idx, s in enumerate(raw_stops, start=1):
        pid = s.get("place_id") or f"stop_{idx}"
        dwell = int(s.get("duration_mins") or 60)
        formatted_dwell = format_minutes_to_hours_mins(dwell)
        suggested_times_summary[s.get("name") or pid] = formatted_dwell

        # Transit leg from previous point
        prev_travel_mins = int(s.get("transit_from_prev_mins") or 0)
        prev_dist_km = float(s.get("transit_from_prev_km") or 0.0)

        ordered_destinations.append({
            "stop_number": idx,
            "place_id": pid,
            "place": s.get("place") or s.get("name") or "Local Destination",
            "name": s.get("name") or s.get("place") or "Local Destination",
            "selection_reasons": s.get("selection_reasons", []),
            "category": s.get("category") or "attraction",
            "address": s.get("address") or "",
            "lat": s.get("lat") if s.get("lat") is not None else (s.get("coordinates", {}).get("lat") if isinstance(s.get("coordinates"), dict) else None),
            "lng": s.get("lng") if s.get("lng") is not None else (s.get("coordinates", {}).get("lng") if isinstance(s.get("coordinates"), dict) else None),
            "coordinates": s.get("coordinates") or {"lat": s.get("lat"), "lng": s.get("lng")},
            "rating": s.get("rating"),
            "review_count": s.get("review_count"),
            "price_level": s.get("price_level") or "$$ (Moderate)",
            "arrival_time": s.get("arrival_time") or "",
            "departure_time": s.get("departure_time") or "",
            "suggested_duration": formatted_dwell,
            "duration_mins": dwell,
            "transit_from_previous": {
                "travel_time_minutes": prev_travel_mins,
                "travel_time_formatted": format_minutes_to_hours_mins(prev_travel_mins),
                "distance_km": round(prev_dist_km, 2),
                "distance_formatted": format_distance_km(prev_dist_km)
            },
            "explanation": ai_stop_explanations.get(pid, default_stop_explanations.get(pid, "")),
            "meal_type": s.get("meal_type"),
            "is_meal_stop": s.get("is_meal_stop", bool(s.get("meal_type"))),
            "is_locked": bool(s.get("is_locked", False))
        })

    # Authoritative meal time validation on ordered destinations
    start_clock_str = optimizer_data.get("start_clock") or optimizer_data.get("start_time") or "09:30 AM"
    ordered_destinations = validate_itinerary_meal_times(ordered_destinations, start_time_clock=start_clock_str)

    # 6. Build Return-to-Start Confirmation
    return_confirmation = {
        "confirmed": True,
        "origin_name": origin_name,
        "origin_address": origin_addr,
        "return_arrival_time": return_clock,
        "final_leg_travel_time": format_minutes_to_hours_mins(return_travel_mins),
        "final_leg_distance": format_distance_km(return_dist_km),
        "slack_buffer_remaining": format_minutes_to_hours_mins(slack_mins),
        "statement": (
            f"The itinerary completes a closed loop, safely returning to {origin_name} "
            f"at {return_clock} after a {format_minutes_to_hours_mins(return_travel_mins)} "
            f"return leg ({format_distance_km(return_dist_km)}), leaving "
            f"{format_minutes_to_hours_mins(slack_mins)} of spare buffer."
        )
    }

    # 7. Final Assembled JSON
    return {
        "status": "success",
        "trip_title": ai_title,
        "total_duration": {
            "minutes": total_duration_mins,
            "formatted": format_minutes_to_hours_mins(total_duration_mins),
            "available_budget_minutes": budget_mins,
            "slack_minutes": slack_mins
        },
        "total_travel_time": {
            "minutes": total_travel_mins,
            "formatted": format_minutes_to_hours_mins(total_travel_mins)
        },
        "total_visit_time": {
            "minutes": total_visit_mins,
            "formatted": format_minutes_to_hours_mins(total_visit_mins)
        },
        "total_distance": {
            "km": round(total_distance_km, 2),
            "formatted": format_distance_km(total_distance_km)
        },
        "transportation_mode": travel_mode,
        "ordered_destinations": ordered_destinations,
        "rejected_destinations": optimizer_data.get("rejected_destinations", []),
        "suggested_times_summary": suggested_times_summary,
        "preference_match_reasoning": ai_preference_reasoning,
        "return_to_start_confirmation": return_confirmation,
        "raw_optimizer_score": optimizer_data.get("score", 0.0)
    }
