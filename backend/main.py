import os
from typing import Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

from services.time_manager import calculate_activities
from services.places import fetch_places, fetch_candidate_places
from services.ai_curator import curate_itinerary
from services.routing import get_optimized_route
from services.geocoding import geocode_location, search_place_suggestions

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

class RouteRequest(BaseModel):
    start_lat: Optional[float] = None
    start_lng: Optional[float] = None
    address: Optional[str] = None
    time_hours: float
    cuisine: Optional[str] = None
    vibe: Optional[str] = None
    vibe_preference: Optional[str] = None
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

@app.get("/api/places/autocomplete")
def places_autocomplete(query: str = Query(..., min_length=2)):
    """
    Search autocomplete suggestions for place names or addresses using Google Places API.
    """
    results = search_place_suggestions(query)
    return {"status": "success", "results": results}

@app.post("/api/generate-route")
def generate_route(request: RouteRequest):
    # 1. Edge-case validation: time available must be at least 2 hours
    if request.time_hours < 2.0:
        raise HTTPException(
            status_code=400,
            detail="Time available is too short. Please select at least 2.0 hours for an itinerary."
        )

    # 2. Resolve coordinates if address is passed without lat/lng
    lat = request.start_lat
    lng = request.start_lng
    start_name = request.address or "Departure Point"

    if (lat is None or lng is None) and request.address:
        geocoded = geocode_location(request.address)
        if geocoded:
            lat = geocoded["lat"]
            lng = geocoded["lng"]
            start_name = geocoded.get("name") or geocoded.get("address") or request.address
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unable to find coordinates for '{request.address}'. Please enter a valid address or city."
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

    vibe_query = (request.vibe or request.vibe_preference or "").strip() or None

    # 3. Calculate baseline time constraints
    try:
        time_info = calculate_activities(request.time_hours)
    except Exception as e:
        time_info = {"num_attractions": 2, "has_dinner": True}

    # 4. Pipeline Step 1: Fetch Top 20 Candidate Places from Google Places
    try:
        candidate_places = fetch_candidate_places(
            lat=lat,
            lng=lng,
            radius=5000.0,
            cuisine=request.cuisine,
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
            detail=f"No venues or attractions found within 5km of '{start_name}'. Try selecting a more populated starting location."
        )

    # 5. Pipeline Step 2: Gemini 3.8 Flash AI Curation
    curated_items = curate_itinerary(
        places_list=candidate_places,
        time_hours=request.time_hours,
        vibe_preference=vibe_query,
        price_level=request.price_level
    )

    # 6. Pipeline Step 3: Match curated items back to place details & attach durations/reasoning
    candidate_map = {p["place_id"]: p for p in candidate_places if p.get("place_id")}
    selected_places = []

    for item in curated_items:
        pid = item.get("place_id")
        if pid in candidate_map:
            place = dict(candidate_map[pid])
            duration_mins = int(item.get("duration_mins") or 60)
            place["duration_mins"] = duration_mins
            place["duration_hours"] = round(duration_mins / 60.0, 2)
            place["time_estimate_reason"] = item.get("time_estimate_reason", f"AI estimated {duration_mins} mins based on venue profile.")
            place["ai_reasoning"] = item.get("ai_reasoning", "Curated for your day trip.")
            selected_places.append(place)

    # Fallback to top candidates if curation matching was empty
    if not selected_places:
        selected_places = candidate_places[:min(3, len(candidate_places))]
        for p in selected_places:
            p["duration_mins"] = 60
            p["duration_hours"] = 1.0
            p["time_estimate_reason"] = "Standard 60 mins recommended visit duration."
            p["ai_reasoning"] = "Curated highlight for your itinerary."

    # 7. Pipeline Step 4: Geographic Route Optimization (Google Routes API)
    try:
        route_result = get_optimized_route(
            start_lat=lat,
            start_lng=lng,
            places=selected_places
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal routing error: {str(e)}")

    optimized_places = route_result.get("optimized_places", selected_places)
    total_trip_hours = route_result.get("total_trip_hours", request.time_hours)
    polyline = route_result.get("overview_polyline", "")
    google_maps_url = route_result.get("google_maps_url", "")

    return {
        "status": "success",
        "message": "AI-curated route generated successfully",
        "curator_model": "gemini-3.8-flash",
        "vibe": vibe_query,
        "vibe_preference": vibe_query or "Balanced sightseeing and dining",
        "price_level": request.price_level or "Moderate",
        "start_location": {
            "name": start_name,
            "address": request.address or start_name,
            "lat": lat,
            "lng": lng
        },
        "optimized_places": [
            {
                "place_id": p.get("place_id"),
                "name": p.get("name"),
                "coordinates": {"lat": p.get("lat"), "lng": p.get("lng")},
                "lat": p.get("lat"),
                "lng": p.get("lng"),
                "duration_mins": p.get("duration_mins", 60),
                "duration_hours": p.get("duration_hours", 1.0),
                "time_estimate_reason": p.get("time_estimate_reason", ""),
                "type": p.get("type"),
                "cuisine": p.get("cuisine"),
                "rating": p.get("rating"),
                "price_level": p.get("price_level"),
                "ai_reasoning": p.get("ai_reasoning", "Curated stop."),
                "address": p.get("address", "")
            }
            for p in optimized_places
        ],
        "total_trip_time": f"{total_trip_hours} hours",
        "total_trip_hours": total_trip_hours,
        "polyline": polyline,
        "google_maps_url": google_maps_url,
        "time_breakdown": time_info,
        "legs": route_result.get("legs", []),
        "is_mock": False
    }
