import os
import requests
from typing import Optional, Dict, Any, List

def geocode_location(query: str) -> Optional[Dict[str, Any]]:
    """
    Geocode a query or address using Google Places API (New) searchText.
    Returns dict with lat, lng, formatted_address, name or None.
    """
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key or not query:
        return None

    url = "https://places.googleapis.com/v1/places:searchText"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.location,places.id"
    }

    try:
        res = requests.post(url, json={"textQuery": query}, headers=headers, timeout=8)
        data = res.json()
        if res.status_code == 200 and data.get("places"):
            top = data["places"][0]
            loc = top.get("location", {})
            return {
                "place_id": top.get("id"),
                "name": top.get("displayName", {}).get("text", query),
                "address": top.get("formattedAddress", query),
                "lat": loc.get("latitude"),
                "lng": loc.get("longitude")
            }
    except Exception as e:
        print(f"Error in geocode_location: {e}")

    return None

def search_place_suggestions(query: str) -> List[Dict[str, Any]]:
    """
    Return autocomplete suggestions for a search query using Google Places searchText.
    """
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key or not query or len(query.strip()) < 2:
        return []

    url = "https://places.googleapis.com/v1/places:searchText"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.location,places.id"
    }

    try:
        res = requests.post(url, json={"textQuery": query, "maxResultCount": 5}, headers=headers, timeout=6)
        data = res.json()
        if res.status_code == 200 and data.get("places"):
            results = []
            for p in data["places"]:
                loc = p.get("location", {})
                if loc.get("latitude") and loc.get("longitude"):
                    results.append({
                        "place_id": p.get("id"),
                        "name": p.get("displayName", {}).get("text", ""),
                        "address": p.get("formattedAddress", ""),
                        "lat": loc.get("latitude"),
                        "lng": loc.get("longitude")
                    })
            return results
    except Exception as e:
        print(f"Error in search_place_suggestions: {e}")

    return []
