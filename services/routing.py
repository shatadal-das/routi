import os
import requests
from urllib.parse import quote
from typing import List, Dict, Any, Optional

def build_google_maps_directions_url(
    start_lat: float,
    start_lng: float,
    places: List[Dict[str, Any]],
    travelmode: str = "driving",
    max_waypoints: int = 9,
    dest_lat: Optional[float] = None,
    dest_lng: Optional[float] = None,
) -> str:
    """
    Construct a Universal Google Maps Directions URL:
    https://www.google.com/maps/dir/?api=1&origin=...&destination=...&waypoints=...&travelmode=driving
    Handles up to max_waypoints (3 on mobile browser intents, up to 9 on desktop).
    """
    origin = f"{start_lat},{start_lng}"
    d_lat = dest_lat if dest_lat is not None else start_lat
    d_lng = dest_lng if dest_lng is not None else start_lng
    destination = f"{d_lat},{d_lng}"

    waypoints = [f"{p['lat']},{p['lng']}" for p in places[:max_waypoints]]
    url = (
        f"https://www.google.com/maps/dir/?api=1"
        f"&origin={quote(origin)}"
        f"&destination={quote(destination)}"
        f"&travelmode={travelmode}"
    )

    if waypoints:
        waypoints_param = "|".join(waypoints)
        url += f"&waypoints={quote(waypoints_param)}"

    return url

def get_optimized_route(start_lat: float, start_lng: float, places: List[Dict[str, Any]], optimize_waypoints: bool = False) -> Dict[str, Any]:
    """
    Call Google Routes API (or Directions API) with origin/destination at start coordinates
    and optimizeWaypointOrder: true. Generates universal Google Maps directions URL.
    """
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_MAPS_API_KEY is not configured in backend environment.")

    if not places:
        raise ValueError("No places provided for route optimization.")

    # 1. Primary: Google Routes API (computeRoutes)
    routes_url = "https://routes.googleapis.com/directions/v2:computeRoutes"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "routes.duration,routes.distanceMeters,routes.polyline.encodedPolyline,routes.legs,routes.optimizedIntermediateWaypointIndex"
    }

    intermediates = [
        {
            "location": {
                "latLng": {
                    "latitude": p["lat"],
                    "longitude": p["lng"]
                }
            }
        }
        for p in places
    ]

    payload = {
        "origin": {
            "location": {
                "latLng": {
                    "latitude": start_lat,
                    "longitude": start_lng
                }
            }
        },
        "destination": {
            "location": {
                "latLng": {
                    "latitude": start_lat,
                    "longitude": start_lng
                }
            }
        },
        "intermediates": intermediates,
        "travelMode": "DRIVE",
        "optimizeWaypointOrder": "true" if optimize_waypoints else "false"
    }

    try:
        res = requests.post(routes_url, json=payload, headers=headers, timeout=12)
        data = res.json()

        if res.status_code == 200 and data.get("routes"):
            route = data["routes"][0]
            polyline_points = route.get("polyline", {}).get("encodedPolyline", "")

            # waypoint order: index permutation of intermediates
            if optimize_waypoints:
                waypoint_order = route.get("optimizedIntermediateWaypointIndex")
                if waypoint_order is None or len(waypoint_order) != len(places):
                    waypoint_order = list(range(len(places)))
                optimized_places = [places[i] for i in waypoint_order if i < len(places)]
            else:
                waypoint_order = list(range(len(places)))
                optimized_places = list(places)

            legs_data = []
            total_duration_sec = 0
            total_distance_m = 0

            for idx, leg in enumerate(route.get("legs", [])):
                dur_str = leg.get("duration", "0s")
                try:
                    dur_sec = int(dur_str.rstrip("s"))
                except ValueError:
                    dur_sec = 0

                dist_m = leg.get("distanceMeters", 0)
                total_duration_sec += dur_sec
                total_distance_m += dist_m

                legs_data.append({
                    "leg_index": idx,
                    "duration_seconds": dur_sec,
                    "duration_text": f"{round(dur_sec / 60)} mins",
                    "distance_meters": dist_m,
                    "distance_text": f"{round(dist_m / 1000, 1)} km"
                })

            activity_hours = sum(p.get("duration_hours", 1.0) for p in optimized_places)
            drive_hours = total_duration_sec / 3600.0
            total_trip_hours = round(activity_hours + drive_hours, 1)

            google_maps_url = build_google_maps_directions_url(start_lat, start_lng, optimized_places)

            return {
                "status": "success",
                "start_location": {"lat": start_lat, "lng": start_lng},
                "optimized_places": optimized_places,
                "waypoint_order": waypoint_order,
                "legs": legs_data,
                "total_drive_duration_seconds": total_duration_sec,
                "total_drive_duration_text": f"{round(total_duration_sec / 60)} mins",
                "total_distance_meters": total_distance_m,
                "total_distance_text": f"{round(total_distance_m / 1000, 1)} km",
                "total_activity_hours": activity_hours,
                "total_trip_hours": total_trip_hours,
                "overview_polyline": polyline_points,
                "google_maps_url": google_maps_url,
            }
        elif "error" in data:
            err_msg = data["error"].get("message", "Routes API error")
            print(f"Routes API error: {err_msg}")
    except Exception as e:
        print(f"Exception calling Routes API: {e}")

    # 2. Secondary fallback: Google Directions API (legacy)
    directions_url = "https://maps.googleapis.com/maps/api/directions/json"
    wp_prefix = "optimize:true|" if optimize_waypoints else ""
    waypoints_str = wp_prefix + "|".join([f"{p['lat']},{p['lng']}" for p in places])
    params = {
        "origin": f"{start_lat},{start_lng}",
        "destination": f"{start_lat},{start_lng}",
        "waypoints": waypoints_str,
        "mode": "driving",
        "key": api_key,
    }

    try:
        res = requests.get(directions_url, params=params, timeout=12)
        data = res.json()

        if data.get("status") == "OK" and data.get("routes"):
            route = data["routes"][0]
            if optimize_waypoints:
                waypoint_order = route.get("waypoint_order", list(range(len(places))))
                optimized_places = [places[i] for i in waypoint_order if i < len(places)]
            else:
                waypoint_order = list(range(len(places)))
                optimized_places = list(places)
            polyline_points = route.get("overview_polyline", {}).get("points", "")

            legs_data = []
            total_duration_sec = 0
            total_distance_m = 0

            for idx, leg in enumerate(route.get("legs", [])):
                d_sec = leg.get("duration", {}).get("value", 0)
                dist_m = leg.get("distance", {}).get("value", 0)
                total_duration_sec += d_sec
                total_distance_m += dist_m
                legs_data.append({
                    "leg_index": idx,
                    "duration_seconds": d_sec,
                    "duration_text": leg.get("duration", {}).get("text", f"{round(d_sec/60)} mins"),
                    "distance_meters": dist_m,
                    "distance_text": leg.get("distance", {}).get("text", f"{round(dist_m/1000, 1)} km"),
                })

            optimized_places = [places[i] for i in waypoint_order if i < len(places)]
            activity_hours = sum(p.get("duration_hours", 1.0) for p in optimized_places)
            total_trip_hours = round(activity_hours + (total_duration_sec / 3600.0), 1)

            google_maps_url = build_google_maps_directions_url(start_lat, start_lng, optimized_places)

            return {
                "status": "success",
                "start_location": {"lat": start_lat, "lng": start_lng},
                "optimized_places": optimized_places,
                "waypoint_order": waypoint_order,
                "legs": legs_data,
                "total_drive_duration_seconds": total_duration_sec,
                "total_drive_duration_text": f"{round(total_duration_sec / 60)} mins",
                "total_distance_meters": total_distance_m,
                "total_distance_text": f"{round(total_distance_m / 1000, 1)} km",
                "total_activity_hours": activity_hours,
                "total_trip_hours": total_trip_hours,
                "overview_polyline": polyline_points,
                "google_maps_url": google_maps_url,
            }
        else:
            status = data.get("status", "UNKNOWN")
            err_msg = data.get("error_message", "Google Directions API failed")
            raise RuntimeError(f"Google Routing failed ({status}): {err_msg}")

    except Exception as e:
        raise RuntimeError(f"Failed to generate route: {str(e)}")
