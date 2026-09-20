import os
import requests
from typing import List, Dict, Any, Optional

def fetch_places(
    lat: float,
    lng: float,
    num_attractions: int = 2,
    include_dinner: bool = True,
    cuisine: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Fetch 1 highly-rated restaurant (with optional cuisine preference)
    and num_attractions highly-rated tourist attractions within a 5km radius
    using Google Places API (New, with fallback to legacy Nearby Search).
    """
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_MAPS_API_KEY is not configured in backend environment.")

    places: List[Dict[str, Any]] = []

    # 1. Fetch Restaurant (with cuisine filtering if provided)
    if include_dinner:
        restaurant_found = False

        # If user specified a cuisine (e.g. "Italian", "Sushi", "Mexican")
        if cuisine and cuisine.strip():
            query_text = f"{cuisine.strip()} restaurant"
            search_text_url = "https://places.googleapis.com/v1/places:searchText"
            headers = {
                "Content-Type": "application/json",
                "X-Goog-Api-Key": api_key,
                "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.location,places.rating,places.types,places.id"
            }
            payload = {
                "textQuery": query_text,
                "maxResultCount": 10,
                "locationBias": {
                    "circle": {
                        "center": {"latitude": lat, "longitude": lng},
                        "radius": 5000.0
                    }
                }
            }
            try:
                res = requests.post(search_text_url, json=payload, headers=headers, timeout=10)
                data = res.json()
                if res.status_code == 200 and data.get("places"):
                    sorted_restaurants = sorted(
                        data["places"],
                        key=lambda x: x.get("rating") or 0.0,
                        reverse=True
                    )
                    top = sorted_restaurants[0]
                    places.append({
                        "place_id": top.get("id"),
                        "name": top.get("displayName", {}).get("text", f"{cuisine.title()} Restaurant"),
                        "type": "restaurant",
                        "cuisine": cuisine.title(),
                        "lat": top["location"]["latitude"],
                        "lng": top["location"]["longitude"],
                        "rating": top.get("rating", 4.5),
                        "duration_hours": 1.5,
                        "address": top.get("formattedAddress", "")
                    })
                    restaurant_found = True
            except Exception as e:
                print(f"Error fetching cuisine-specific restaurant: {e}")

        # Fallback to general nearby restaurant search if no cuisine or cuisine search yielded no results
        if not restaurant_found:
            new_places_url = "https://places.googleapis.com/v1/places:searchNearby"
            headers = {
                "Content-Type": "application/json",
                "X-Goog-Api-Key": api_key,
                "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.location,places.rating,places.types,places.id"
            }
            payload = {
                "includedTypes": ["restaurant"],
                "maxResultCount": 10,
                "locationRestriction": {
                    "circle": {
                        "center": {"latitude": lat, "longitude": lng},
                        "radius": 5000.0
                    }
                }
            }
            try:
                res = requests.post(new_places_url, json=payload, headers=headers, timeout=10)
                data = res.json()
                if res.status_code == 200 and data.get("places"):
                    sorted_restaurants = sorted(
                        data["places"],
                        key=lambda x: x.get("rating") or 0.0,
                        reverse=True
                    )
                    top = sorted_restaurants[0]
                    places.append({
                        "place_id": top.get("id"),
                        "name": top.get("displayName", {}).get("text", "Dinner Restaurant"),
                        "type": "restaurant",
                        "cuisine": cuisine.title() if cuisine else None,
                        "lat": top["location"]["latitude"],
                        "lng": top["location"]["longitude"],
                        "rating": top.get("rating", 4.5),
                        "duration_hours": 1.5,
                        "address": top.get("formattedAddress", "")
                    })
            except Exception as e:
                print(f"Error calling Places API (New) for restaurant: {e}")

    # 2. Fetch Tourist Attractions
    if num_attractions > 0:
        new_places_url = "https://places.googleapis.com/v1/places:searchNearby"
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.location,places.rating,places.types,places.id"
        }
        payload = {
            "includedTypes": ["tourist_attraction"],
            "maxResultCount": min(20, max(5, num_attractions * 3)),
            "locationRestriction": {
                "circle": {
                    "center": {"latitude": lat, "longitude": lng},
                    "radius": 5000.0
                }
            }
        }
        try:
            res = requests.post(new_places_url, json=payload, headers=headers, timeout=10)
            data = res.json()
            if res.status_code == 200 and data.get("places"):
                sorted_attractions = sorted(
                    data["places"],
                    key=lambda x: x.get("rating") or 0.0,
                    reverse=True
                )
                for att in sorted_attractions[:num_attractions]:
                    places.append({
                        "place_id": att.get("id"),
                        "name": att.get("displayName", {}).get("text", "Tourist Attraction"),
                        "type": "tourist_attraction",
                        "lat": att["location"]["latitude"],
                        "lng": att["location"]["longitude"],
                        "rating": att.get("rating", 4.5),
                        "duration_hours": 1.0,
                        "address": att.get("formattedAddress", "")
                    })
        except Exception as e:
            print(f"Error calling Places API (New) for attractions: {e}")

    # 3. Fallback to legacy Google Places Nearby Search if Places API (New) returned nothing
    if not places:
        legacy_url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
        if include_dinner:
            try:
                params = {
                    "location": f"{lat},{lng}",
                    "radius": 5000,
                    "type": "restaurant",
                    "key": api_key,
                }
                if cuisine:
                    params["keyword"] = cuisine
                res_resp = requests.get(legacy_url, params=params, timeout=10)
                res_data = res_resp.json()
                if res_data.get("status") == "OK" and res_data.get("results"):
                    sorted_res = sorted(
                        res_data["results"],
                        key=lambda x: x.get("rating") or 0.0,
                        reverse=True
                    )
                    top_res = sorted_res[0]
                    loc = top_res["geometry"]["location"]
                    places.append({
                        "place_id": top_res.get("place_id"),
                        "name": top_res.get("name"),
                        "type": "restaurant",
                        "cuisine": cuisine.title() if cuisine else None,
                        "lat": loc["lat"],
                        "lng": loc["lng"],
                        "rating": top_res.get("rating", 4.5),
                        "duration_hours": 1.5,
                        "address": top_res.get("vicinity", "")
                    })
            except Exception as e:
                print(f"Error calling legacy Places API for restaurant: {e}")

        if num_attractions > 0:
            try:
                att_resp = requests.get(legacy_url, params={
                    "location": f"{lat},{lng}",
                    "radius": 5000,
                    "type": "tourist_attraction",
                    "key": api_key,
                }, timeout=10)
                att_data = att_resp.json()
                if att_data.get("status") == "OK" and att_data.get("results"):
                    sorted_att = sorted(
                        att_data["results"],
                        key=lambda x: x.get("rating") or 0.0,
                        reverse=True
                    )
                    for att in sorted_att[:num_attractions]:
                        loc = att["geometry"]["location"]
                        places.append({
                            "place_id": att.get("place_id"),
                            "name": att.get("name"),
                            "type": "tourist_attraction",
                            "lat": loc["lat"],
                            "lng": loc["lng"],
                            "rating": att.get("rating", 4.5),
                            "duration_hours": 1.0,
                            "address": att.get("vicinity", "")
                        })
            except Exception as e:
                print(f"Error calling legacy Places API for attractions: {e}")

    return places



def classify_place_category(types: List[str], name: str = "") -> tuple:
    """
    Returns (category, venue_type) ensuring cafes/bakeries are distinguished
    from full sit-down dining restaurants and specific cultural/nature categories
    are preserved rather than collapsed to generic attraction.
    """
    tl = [str(t).lower() for t in types]
    nl = str(name).lower()

    if any(t in tl for t in ["bakery", "cafe", "coffee_shop"]) or "coffee" in nl or "cafe" in nl or "bakery" in nl:
        return "cafe", "cafe"
    if any(t in tl for t in ["restaurant", "meal_takeaway", "meal_delivery"]) or "restaurant" in nl or "diner" in nl or "bistro" in nl:
        return "restaurant", "restaurant"
    if any(t in tl for t in ["bar", "pub", "night_club"]):
        return "bar", "bar"
    if any(t in tl for t in ["park", "campground", "national_park", "garden", "botanical_garden"]) or "park" in nl or "garden" in nl:
        return "park", "park"
    if any(t in tl for t in ["art_gallery"]) or "gallery" in nl:
        return "art_gallery", "art_gallery"
    if any(t in tl for t in ["museum"]) or "museum" in nl:
        return "museum", "museum"
    if any(t in tl for t in ["viewpoint", "scenic_point", "observation_deck"]) or "view" in nl or "overlook" in nl:
        return "viewpoint", "viewpoint"
    if any(t in tl for t in ["monument", "historical_landmark"]) or any(k in nl for k in ["fort", "palace", "monument", "tomb", "temple", "gate"]):
        return "monument", "monument"
    if any(t in tl for t in ["shopping_mall", "market", "department_store"]) or "market" in nl or "bazaar" in nl:
        return "shopping", "shopping"
    return "attraction", "attraction"


PRICE_LEVEL_MAP = {
    "PRICE_LEVEL_FREE": "Free",
    "PRICE_LEVEL_INEXPENSIVE": "$ (Budget-Friendly)",
    "PRICE_LEVEL_MODERATE": "$$ (Moderate)",
    "PRICE_LEVEL_EXPENSIVE": "$$$ (Upscale)",
    "PRICE_LEVEL_VERY_EXPENSIVE": "$$$$ (Luxury)",
}


def fetch_candidate_places(
    lat: float,
    lng: float,
    radius: float = 5000.0,
    cuisine: Optional[str] = None,
    vibe: Optional[str] = None,
    max_candidates: int = 20,
) -> List[Dict[str, Any]]:
    """
    Fetch up to max_candidates diverse candidate places (attractions,
    parks, cultural sites, cafes, restaurants) around (lat, lng) with price levels
    and ratings for Gemini AI curation. For trips requesting > 20 candidates,
    executes multi-query nearby searches across distinct type groups to bypass
    Google's 20-place per-query response ceiling.
    """
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_MAPS_API_KEY is not configured in backend environment.")

    candidates: List[Dict[str, Any]] = []
    seen_place_ids = set()

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress,places.location,places.rating,places.userRatingCount,places.types,places.priceLevel",
    }

    # Helper to parse and append places safely
    def _ingest_places(place_items: List[Dict[str, Any]]):
        for p in place_items:
            pid = p.get("id")
            if pid and pid not in seen_place_ids and "location" in p:
                seen_place_ids.add(pid)
                types = p.get("types", [])
                name_text = p.get("displayName", {}).get("text", "Local Attraction")
                cat, v_type = classify_place_category(types, name_text)
                candidates.append({
                    "place_id": pid,
                    "name": name_text,
                    "lat": p["location"]["latitude"],
                    "lng": p["location"]["longitude"],
                    "rating": p.get("rating", 4.3),
                    "user_rating_count": p.get("userRatingCount", 150),
                    "price_level": PRICE_LEVEL_MAP.get(p.get("priceLevel"), "$$ (Moderate)"),
                    "types": types,
                    "category": cat,
                    "type": "restaurant" if cat == "restaurant" else ("cafe" if cat == "cafe" else "attraction"),
                    "address": p.get("formattedAddress", "")
                })

    # 1. If user provided a specific cuisine or keyword vibe, query searchText first
    search_query = cuisine or (vibe if vibe and len(vibe) < 50 else None)
    if search_query:
        search_text_url = "https://places.googleapis.com/v1/places:searchText"
        payload = {
            "textQuery": f"{search_query} places",
            "maxResultCount": 10,
            "locationBias": {
                "circle": {
                    "center": {"latitude": lat, "longitude": lng},
                    "radius": radius,
                }
            },
        }
        try:
            res = requests.post(search_text_url, json=payload, headers=headers, timeout=10)
            data = res.json()
            _ingest_places(data.get("places", []))
        except Exception as e:
            print(f"Error fetching vibe/cuisine text candidates: {e}")

    # 2. Query searchNearby for top attractions, cultural landmarks & venues
    nearby_url = "https://places.googleapis.com/v1/places:searchNearby"
    needed = max_candidates - len(candidates)

    if needed > 20:
        # Multi-query strategy for longer trips (e.g. 8-12 hours requiring 25-35+ places)
        # Query 2A: Sightseeing, culture, landmarks, galleries
        query_groups = [
            ["tourist_attraction", "museum", "art_gallery", "historical_landmark", "monument"],
            ["park", "botanical_garden", "viewpoint", "cafe", "restaurant", "bakery"]
        ]
        for type_group in query_groups:
            if len(candidates) >= max_candidates:
                break
            payload = {
                "includedTypes": type_group,
                "maxResultCount": 20,
                "locationRestriction": {
                    "circle": {
                        "center": {"latitude": lat, "longitude": lng},
                        "radius": radius,
                    }
                },
            }
            try:
                res = requests.post(nearby_url, json=payload, headers=headers, timeout=10)
                data = res.json()
                _ingest_places(data.get("places", []))
            except Exception as e:
                print(f"Error in multi-query searchNearby: {e}")
    elif needed > 0:
        nearby_payload = {
            "includedTypes": [
                "tourist_attraction",
                "museum",
                "park",
                "art_gallery",
                "cafe",
                "restaurant"
            ],
            "maxResultCount": min(20, max(10, needed)),
            "locationRestriction": {
                "circle": {
                    "center": {"latitude": lat, "longitude": lng},
                    "radius": radius,
                }
            },
        }
        try:
            res = requests.post(nearby_url, json=nearby_payload, headers=headers, timeout=10)
            data = res.json()
            _ingest_places(data.get("places", []))
        except Exception as e:
            print(f"Error fetching nearby candidate places: {e}")

    # 3. Fallback: if candidates are fewer than 4, fetch standard places
    if len(candidates) < 4:
        standard_places = fetch_places(
            lat=lat,
            lng=lng,
            num_attractions=4,
            include_dinner=True,
            cuisine=cuisine
        )
        for sp in standard_places:
            if sp.get("place_id") not in seen_place_ids:
                seen_place_ids.add(sp.get("place_id"))
                candidates.append({
                    "place_id": sp.get("place_id"),
                    "name": sp.get("name"),
                    "lat": sp.get("lat"),
                    "lng": sp.get("lng"),
                    "rating": sp.get("rating", 4.5),
                    "price_level": "$$ (Moderate)",
                    "types": [sp.get("type", "attraction")],
                    "type": sp.get("type", "attraction"),
                    "address": sp.get("address", "")
                })

    # Sort by rating descending and limit to max_candidates
    candidates.sort(key=lambda x: x.get("rating") or 0.0, reverse=True)
    return candidates[:max_candidates]
