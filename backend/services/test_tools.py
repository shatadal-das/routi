"""
Automated Test Suite for RoamAround Agent Deterministic Tools:
1. search_places()
2. get_place_details()
3. get_route()
4. optimize_trip()
5. execute_tool() dispatcher
"""

import sys
import os
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.tools import (
    search_places,
    get_place_details,
    get_route,
    optimize_trip,
    execute_tool,
    TOOL_DEFINITIONS
)
from services.test_scorer import MOCK_PLACES, ORIGIN_LAT, ORIGIN_LNG


def test_search_places():
    print("\n--- TEST 1: search_places() ---")

    # 1a. Normal search with coordinates
    res = search_places(
        lat=ORIGIN_LAT,
        lng=ORIGIN_LNG,
        query="waterfront coffee and scenic views",
        radius_meters=3000.0,
        max_results=5
    )
    assert res["status"] == "success", f"search_places failed: {res}"
    assert "places" in res
    assert isinstance(res["places"], list)
    assert len(res["places"]) > 0
    first = res["places"][0]
    assert "name" in first
    assert "lat" in first
    assert "lng" in first
    assert "rating" in first
    print(f"  [PASS] search_places returned {len(res['places'])} venues near ({ORIGIN_LAT}, {ORIGIN_LNG})")

    # 1b. Validation: Out of bounds latitude
    res_bad = search_places(lat=150.0, lng=ORIGIN_LNG)
    assert res_bad["status"] == "error"
    print(f"  [PASS] search_places rejected invalid coordinates: {res_bad['message']}")


def test_get_place_details():
    print("\n--- TEST 2: get_place_details() ---")

    # 2a. Valid place_id
    res = get_place_details("blue_bottle_ferry")
    assert res["status"] == "success"
    assert "name" in res
    assert "address" in res
    assert "rating" in res
    assert "opening_hours" in res
    print(f"  [PASS] get_place_details retrieved verified info for '{res['name']}' ({res['rating']} stars)")

    # 2b. Validation: Empty string
    res_empty = get_place_details("")
    assert res_empty["status"] == "error"
    print(f"  [PASS] get_place_details rejected empty place_id")


def test_get_route():
    print("\n--- TEST 3: get_route() ---")

    # 3a. Round trip with 2 waypoints
    waypoints = [
        {"name": "Stop 1", "lat": 37.7990, "lng": -122.3968},  # ~0.5 km away
        {"name": "Stop 2", "lat": 37.8090, "lng": -122.4101}   # ~2.0 km away
    ]

    res = get_route(
        origin_lat=ORIGIN_LAT,
        origin_lng=ORIGIN_LNG,
        waypoints=waypoints,
        travel_mode="DRIVE"
    )
    assert res["status"] == "success"
    assert res["total_travel_time_minutes"] > 0
    assert res["total_distance_km"] > 0.0
    assert len(res["legs"]) == 3  # Origin->Stop1, Stop1->Stop2, Stop2->Origin
    assert "google_maps_url" in res
    assert "waypoints=" in res["google_maps_url"]
    assert "destination=" in res["google_maps_url"]
    print(f"  [PASS] get_route computed exact transit: {res['total_travel_time_minutes']} mins, {res['total_distance_km']} km across {len(res['legs'])} legs")
    print(f"  [PASS] Directions URL: {res['google_maps_url']}")

    # 3b. Mode-specific check (Walking speed must take longer than Driving)
    res_walk = get_route(
        origin_lat=ORIGIN_LAT,
        origin_lng=ORIGIN_LNG,
        waypoints=waypoints,
        travel_mode="WALK"
    )
    assert res_walk["total_travel_time_minutes"] > res["total_travel_time_minutes"], "Walking must take longer than driving!"
    print(f"  [PASS] Walking transit ({res_walk['total_travel_time_minutes']}m) correctly exceeds driving ({res['total_travel_time_minutes']}m)")


def test_optimize_trip():
    print("\n--- TEST 4: optimize_trip() ---")

    start_loc = {
        "name": "San Francisco Ferry Building",
        "lat": ORIGIN_LAT,
        "lng": ORIGIN_LNG,
        "address": "1 Ferry Building, San Francisco, CA"
    }
    avail_mins = 180  # 3.0 hours

    res = optimize_trip(
        start_location=start_loc,
        available_time_minutes=avail_mins,
        transportation_mode="DRIVE",
        user_interests="Relaxed waterfront walk, scenic bay views, and seafood",
        candidate_places=MOCK_PLACES
    )
    assert res["status"] == "success"
    assert res["constraints_satisfied"]["starts_at_origin"] is True
    assert res["constraints_satisfied"]["ends_at_origin"] is True
    assert res["constraints_satisfied"]["within_time_budget"] is True
    assert res["constraints_satisfied"]["return_time_reserved"] is True
    assert res["constraints_satisfied"]["no_duplicates"] is True
    assert res["total_duration"] <= avail_mins
    assert len(res["ordered_itinerary"]) > 0

    print(f"  [PASS] optimize_trip invoked deterministic optimizer: {len(res['ordered_itinerary'])} stops, duration {res['total_duration']}m <= {avail_mins}m")
    print(f"  [PASS] All 6 hard constraints verified.")


def test_execute_tool_dispatcher():
    print("\n--- TEST 5: execute_tool() Dispatcher ---")

    # 5a. Dispatch search_places
    res1 = execute_tool("search_places", {"lat": ORIGIN_LAT, "lng": ORIGIN_LNG, "max_results": 3})
    assert res1["status"] == "success"
    assert len(res1["places"]) <= 3

    # 5b. Dispatch get_place_details
    res2 = execute_tool("get_place_details", {"place_id": "blue_bottle_ferry"})
    assert res2["status"] == "success"

    # 5c. Dispatch get_route
    res3 = execute_tool("get_route", {"origin_lat": ORIGIN_LAT, "origin_lng": ORIGIN_LNG, "waypoints": []})
    assert res3["status"] == "success"

    # 5d. Dispatch optimize_trip
    res4 = execute_tool("optimize_trip", {
        "start_location": {"lat": ORIGIN_LAT, "lng": ORIGIN_LNG},
        "available_time_minutes": 60,
        "candidate_places": MOCK_PLACES
    })
    assert res4["status"] == "success"
    assert res4["total_duration"] <= 60

    # 5e. Unknown tool error handling
    res_unknown = execute_tool("hallucinated_tool_name", {})
    assert res_unknown["status"] == "error"
    assert "Unknown tool" in res_unknown["message"]

    print(f"  [PASS] execute_tool correctly dispatched all 4 tools and handled unknown tool safely.")


def test_tool_definitions_schema():
    print("\n--- TEST 6: TOOL_DEFINITIONS Schema ---")
    assert len(TOOL_DEFINITIONS) == 4
    tool_names = [t["name"] for t in TOOL_DEFINITIONS]
    assert "search_places" in tool_names
    assert "get_place_details" in tool_names
    assert "get_route" in tool_names
    assert "optimize_trip" in tool_names
    for t in TOOL_DEFINITIONS:
        assert "description" in t
        assert "parameters" in t
        assert t["parameters"]["type"] == "object"
        assert "required" in t["parameters"]
    print(f"  [PASS] All 4 Gemini function declaration schemas validated.")


def run_all_tool_tests():
    print("=" * 80)
    print("VERIFYING ROAMAROUND DETERMINISTIC AGENT TOOLS")
    print("=" * 80)

    test_search_places()
    test_get_place_details()
    test_get_route()
    test_optimize_trip()
    test_execute_tool_dispatcher()
    test_tool_definitions_schema()

    print("\n" + "=" * 80)
    print("ALL AGENT TOOLS VERIFIED AND PASSING SUCCESSFULLY!")
    print("=" * 80)


if __name__ == "__main__":
    run_all_tool_tests()
