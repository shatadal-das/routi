import os
from typing import Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

from services.time_manager import calculate_activities
from services.places import fetch_places, fetch_candidate_places
from services.ai_curator import curate_itinerary
from services.routing import get_optimized_route, build_google_maps_directions_url
from services.geocoding import geocode_location, search_place_suggestions
from services.agent import RoamAroundAgent

load_dotenv()

app = FastAPI(title="Routi API", version="1.0.0")

# Allow all origins for cloud deployment
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
roam_agent = RoamAroundAgent()

class RouteRequest(BaseModel):
    # Support both object and flattened coordinates
    start_location: Optional[dict] = None
    start_lat: Optional[float] = None
    start_lng: Optional[float] = None
    address: Optional[str] = None

    # Support both minutes and hours
    available_time_minutes: Optional[int] = None
    time_hours: Optional[float] = None

    # Support transport mode
    transport_mode: Optional[str] = "DRIVE"
    transportation_mode: Optional[str] = None

    # Support list or string interests
    interests: Optional[list] = None
    vibe: Optional[str] = None
    vibe_preference: Optional[str] = None

    cuisine: Optional[str] = None
    price_level: Optional[str] = None


@app.get("/api/health")
def health_check():
    has_key = bool(os.getenv("GOOGLE_MAPS_API_KEY"))
    has_gemini = bool(os.getenv("GEMINI_API_KEY"))
    return {
        "status": "ok",
        "message": "Backend is running",
        "google_maps_configured": has_key,
        "gemini_configured": has_gemini
    }


class AgentChatRequest(BaseModel):
    message: str
    conversation_history: Optional[list] = None
    current_itinerary: Optional[dict] = None
    start_location: Optional[dict] = None


@app.post("/api/agent/chat")
def agent_chat(request: AgentChatRequest):
    """
    Conversational AI concierge endpoint.
    Handles natural-language requests to generate new itineraries or modify existing ones.
    """
    res = roam_agent.chat(
        message=request.message,
        conversation_history=request.conversation_history,
        current_itinerary=request.current_itinerary,
        default_location=request.start_location
    )

    if res.get("status") == "success":
        opt_out = res.get("raw_optimizer_output") or {}
        ordered_stops = opt_out.get("ordered_itinerary") or []
        start_loc = opt_out.get("starting_location") or (request.start_location or {})

        formatted = []
        for s in ordered_stops:
            dwell_m = s.get("dwell_mins") or s.get("duration_mins", 60)
            formatted.append({
                "place_id": s.get("place_id"),
                "name": s.get("name") or s.get("place"),
                "coordinates": {"lat": s.get("lat"), "lng": s.get("lng")},
                "lat": s.get("lat"),
                "lng": s.get("lng"),
                "duration_mins": dwell_m,
                "duration_hours": round(dwell_m / 60.0, 2),
                "arrival_time": s.get("arrival_time", ""),
                "departure_time": s.get("departure_time", ""),
                "category": s.get("category", "attraction"),
                "type": "restaurant" if s.get("category") in ["restaurant", "cafe", "food"] else "attraction",
                "selection_reasons": s.get("selection_reasons", []),
                "rating": s.get("rating"),
                "address": s.get("address", ""),
                "ai_reasoning": s.get("ai_reasoning", "Curated for your day trip."),
                "time_estimate_reason": s.get("time_estimate_reason", "")
            })

        start_lat = start_loc.get("lat")
        start_lng = start_loc.get("lng")
        polyline = ""
        google_maps_url = ""
        legs = opt_out.get("legs", [])

        if start_lat and start_lng and formatted:
            try:
                route_res = get_optimized_route(start_lat, start_lng, formatted)
                polyline = route_res.get("overview_polyline", "")
                google_maps_url = route_res.get("google_maps_url", "")
                if route_res.get("legs"):
                    legs = route_res.get("legs")
            except Exception:
                google_maps_url = build_google_maps_directions_url(start_lat, start_lng, formatted)

        total_mins = opt_out.get("total_duration") or 240
        total_hours = round(total_mins / 60.0, 1)

        res["route_result"] = {
            "status": "success",
            "message": res.get("message", "Route updated"),
            "curator_model": "roam-agent",
            "start_location": start_loc,
            "optimized_places": formatted,
            "total_trip_time": f"{total_hours} hours",
            "total_trip_hours": total_hours,
            "total_travel_mins": opt_out.get("total_travel_time", 0),
            "total_dwell_mins": opt_out.get("total_visit_time", 0),
            "polyline": polyline,
            "google_maps_url": google_maps_url,
            "legs": legs,
            "rejected_destinations": opt_out.get("rejected_destinations", []),
            "narrative": res.get("modification_applied") or res.get("message", "")
        }

    return res


@app.get("/api/places/autocomplete")
def places_autocomplete(query: str = Query(..., min_length=2)):
    """
    Search autocomplete suggestions for place names or addresses using Google Places API.
    """
    results = search_place_suggestions(query)
    return {"status": "success", "results": results}


def process_trip_planning(request: RouteRequest):
    # 1. Parse coordinates & address
    start_loc = request.start_location or {}
    lat = start_loc.get("lat") if start_loc.get("lat") is not None else request.start_lat
    lng = start_loc.get("lng") if start_loc.get("lng") is not None else request.start_lng
    address_str = start_loc.get("address") or start_loc.get("name") or request.address

    start_name = address_str or "Departure Point"

    if (lat is None or lng is None) and address_str:
        geocoded = geocode_location(address_str)
        if geocoded:
            lat = geocoded["lat"]
            lng = geocoded["lng"]
            start_name = geocoded.get("name") or geocoded.get("address") or address_str
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unable to find coordinates for '{address_str}'. Please enter a valid address or city."
            )

    if lat is None or lng is None:
        raise HTTPException(
            status_code=400,
            detail="Starting coordinates or a valid address are required."
        )

    if not (-90.0 <= lat <= 90.0 and -180.0 <= lng <= 180.0):
        raise HTTPException(
            status_code=400,
            detail="Invalid coordinates range."
        )

    # 2. Parse time budget
    if request.available_time_minutes is not None and request.available_time_minutes > 0:
        total_minutes = int(request.available_time_minutes)
        hours = round(total_minutes / 60.0, 2)
    elif request.time_hours is not None and request.time_hours > 0:
        hours = float(request.time_hours)
        total_minutes = int(round(hours * 60))
    else:
        hours = 4.0
        total_minutes = 240

    if total_minutes < 45:
        raise HTTPException(
            status_code=400,
            detail="Time available is too short. Please select at least 45 minutes for a round-trip itinerary."
        )

    # 3. Parse transport mode
    raw_mode = request.transport_mode or request.transportation_mode or "DRIVE"
    mode = str(raw_mode).upper()
    if mode not in ["DRIVE", "WALK", "BICYCLE"]:
        mode = "DRIVE"

    # 4. Parse interests / vibe
    if request.interests and isinstance(request.interests, list):
        vibe_query = ", ".join([str(i) for i in request.interests if i]).strip() or None
    else:
        vibe_query = (request.vibe or request.vibe_preference or "").strip() or None

    cuisine = request.cuisine or None
    price_level = request.price_level or "Moderate"

    # 5. Fetch candidate places
    try:
        candidate_places = fetch_candidate_places(
            lat=lat,
            lng=lng,
            radius=5000.0 if mode == "DRIVE" else 2500.0,
            cuisine=cuisine,
            vibe=vibe_query,
            max_candidates=20
        )
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Google Places API error: {str(e)}")

    if not candidate_places:
        raise HTTPException(
            status_code=404,
            detail=f"No venues or attractions found within range of '{start_name}'. Try selecting a more populated starting location."
        )

    # 6. Run RoamAround AI Concierge Agent & Algorithmic Optimizer
    try:
        agent_plan = roam_agent.plan_itinerary(
            origin_lat=lat,
            origin_lng=lng,
            origin_name=start_name,
            candidates=candidate_places,
            total_hours=hours,
            user_vibe=vibe_query,
            cuisine_preference=cuisine,
            price_level=price_level,
            travel_mode=mode,
            start_time_clock="09:30 AM"
        )
        selected_places = agent_plan.get("optimized_places", [])
        curator_model = agent_plan.get("curator_model", "gemini-2.5-flash")
        narrative = agent_plan.get("narrative", "Curated personalized loop itinerary.")
    except Exception as e:
        print(f"Agent planning error, fallback to baseline curation: {e}")
        curated_items = curate_itinerary(
            places_list=candidate_places,
            time_hours=hours,
            vibe_preference=vibe_query,
            price_level=price_level
        )
        candidate_map = {p["place_id"]: p for p in candidate_places if p.get("place_id")}
        selected_places = []
        for item in curated_items:
            pid = item.get("place_id")
            if pid in candidate_map:
                place = dict(candidate_map[pid])
                duration_mins = int(item.get("duration_mins") or 60)
                place["duration_mins"] = duration_mins
                place["duration_hours"] = round(duration_mins / 60.0, 2)
                place["time_estimate_reason"] = item.get("time_estimate_reason", f"AI estimated {duration_mins} mins.")
                place["ai_reasoning"] = item.get("ai_reasoning", "Curated for your day trip.")
                selected_places.append(place)
        curator_model = "algorithmic-fallback"
        narrative = f"Curated day trip around {start_name} focusing on top local highlights."

    if not selected_places:
        selected_places = candidate_places[:min(3, len(candidate_places))]
        for p in selected_places:
            p["duration_mins"] = 60
            p["duration_hours"] = 1.0
            p["time_estimate_reason"] = "Standard 60 mins recommended visit duration."
            p["ai_reasoning"] = "Curated highlight for your itinerary."

    # 7. Routing Polyline & Legs (Google Routes API)
    try:
        route_result = get_optimized_route(
            start_lat=lat,
            start_lng=lng,
            places=selected_places
        )
    except Exception as e:
        print(f"Routing API exception ({e}), falling back to direct sequencing")
        route_result = {
            "optimized_places": selected_places,
            "total_trip_hours": hours,
            "overview_polyline": "",
            "google_maps_url": build_google_maps_directions_url(lat, lng, selected_places),
            "legs": []
        }

    optimized_places = route_result.get("optimized_places", selected_places)
    total_trip_hours = route_result.get("total_trip_hours", hours)
    polyline = route_result.get("overview_polyline", "")
    google_maps_url = route_result.get("google_maps_url", "")

    # Map enriched fields
    agent_map = {p.get("place_id"): p for p in selected_places}

    formatted_places = []
    for p in optimized_places:
        pid = p.get("place_id")
        extra = agent_map.get(pid, {})
        d_mins = p.get("duration_mins", extra.get("duration_mins", 60))
        formatted_places.append({
            "place_id": p.get("place_id"),
            "name": p.get("name"),
            "coordinates": {"lat": p.get("lat"), "lng": p.get("lng")},
            "lat": p.get("lat"),
            "lng": p.get("lng"),
            "duration_mins": d_mins,
            "duration_hours": p.get("duration_hours", extra.get("duration_hours", round(d_mins / 60.0, 2))),
            "time_estimate_reason": p.get("time_estimate_reason", extra.get("time_estimate_reason", "")),
            "type": p.get("type", extra.get("type", "attraction")),
            "cuisine": p.get("cuisine", extra.get("cuisine")),
            "rating": p.get("rating", extra.get("rating")),
            "price_level": p.get("price_level", extra.get("price_level")),
            "ai_reasoning": p.get("ai_reasoning", extra.get("ai_reasoning", "Curated stop.")),
            "address": p.get("address", extra.get("address", "")),
            "arrival_time": extra.get("arrival_time", ""),
            "departure_time": extra.get("departure_time", ""),
            "category": extra.get("category", p.get("type", "attraction")),
            "selection_reasons": extra.get("selection_reasons", []),
            "score_breakdown": extra.get("score_breakdown", {})
        })

    agent_data = agent_plan if "agent_plan" in locals() and isinstance(agent_plan, dict) else {}
    total_travel = agent_data.get("total_travel_mins", 0)
    total_dwell = agent_data.get("total_dwell_mins", 0)
    total_duration = agent_data.get("total_trip_mins", int(round(total_trip_hours * 60)))
    total_dist = agent_data.get("total_distance_km", 0.0)
    start_clock = agent_data.get("start_clock", "09:30 AM")
    end_clock = agent_data.get("end_clock", "")
    rejected_destinations = agent_data.get("rejected_destinations", [])

    # Construct the unified 'trip' contract representation
    trip_stops = [
        {
            "id": p["place_id"],
            "name": p["name"],
            "category": p["category"],
            "rating": p.get("rating"),
            "lat": p["lat"],
            "lng": p["lng"],
            "arrival_time": p["arrival_time"],
            "departure_time": p["departure_time"],
            "visit_duration_minutes": p["duration_mins"],
            "selection_reasons": p.get("selection_reasons", []),
            "reason": p.get("ai_reasoning", ""),
            "address": p.get("address", "")
        }
        for p in formatted_places
    ]

    route_coords = [{"lat": lat, "lng": lng}] + [{"lat": p["lat"], "lng": p["lng"]} for p in formatted_places] + [{"lat": lat, "lng": lng}]

    trip_contract = {
        "total_duration_minutes": total_duration,
        "travel_time_minutes": total_travel,
        "visit_time_minutes": total_dwell,
        "distance_km": total_dist,
        "transport_mode": mode,
        "start_clock": start_clock,
        "end_clock": end_clock,
        "return_to_start": True,
        "stops": trip_stops,
        "route": route_coords,
        "summary": narrative,
        "rejected_destinations": rejected_destinations
    }

    try:
        time_info = calculate_activities(total_trip_hours)
    except Exception:
        time_info = {"num_attractions": len(formatted_places), "has_dinner": any(p.get("type") == "restaurant" for p in formatted_places)}

    return {
        "success": True,
        "status": "success",
        "trip": trip_contract,
        "message": "AI-curated route generated successfully",
        "curator_model": curator_model,
        "vibe": vibe_query,
        "vibe_preference": vibe_query or "Balanced sightseeing and dining",
        "price_level": price_level,
        "start_location": {
            "name": start_name,
            "address": address_str or start_name,
            "lat": lat,
            "lng": lng
        },
        "optimized_places": formatted_places,
        "total_trip_time": f"{total_trip_hours} hours",
        "total_trip_hours": total_trip_hours,
        "total_travel_mins": total_travel,
        "total_dwell_mins": total_dwell,
        "slack_remaining_mins": agent_data.get("slack_remaining_mins", 0),
        "start_clock": start_clock,
        "end_clock": end_clock,
        "rejected_destinations": rejected_destinations,
        "user_itinerary": agent_data.get("user_itinerary", {}),
        "polyline": polyline,
        "google_maps_url": google_maps_url,
        "time_breakdown": time_info,
        "legs": route_result.get("legs", []),
        "narrative": narrative,
        "is_mock": False
    }


@app.post("/api/plan-trip")
def plan_trip(request: RouteRequest):
    """
    Primary unified trip planning endpoint matching the API contract specification:
    Accepts start_location, available_time_minutes, transport_mode, interests.
    Returns deterministic trip object with stops, timetable, explainability, and route.
    """
    return process_trip_planning(request)


@app.post("/api/generate-route")
def generate_route(request: RouteRequest):
    """
    Backward-compatible trip planning endpoint for existing frontend clients.
    """
    return process_trip_planning(request)
