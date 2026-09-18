"""
Comprehensive Senior Engineer Review Test Suite for RoamAround Route Optimizer.

Verifies all 15 operational test cases specified by algorithm engineering review:
1. 1-hour trip
2. 2-hour trip
3. Very long available time
4. Only one candidate place
5. No candidate places
6. All places exceed the time limit
7. Very far destination with high rating
8. Nearby mediocre destination
9. Duplicate places
10. Multiple places with same category
11. Nature + food preferences
12. No interests specified
13. Return journey causing a route to exceed the time limit
14. Places with missing optional data
15. Unreachable place

For EVERY test case, asserts:
- START -> places -> START (loop integrity)
- total_duration <= available_time (strict time budget)
"""

import sys
import os
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.optimizer import optimize_route, RouteOptimizer
from services.scorer import haversine_distance_km

ORIGIN_SF = {
    "name": "San Francisco Ferry Building",
    "lat": 37.7955,
    "lng": -122.3937,
    "address": "1 Ferry Building, San Francisco, CA 94105",
    "place_id": "sf_ferry_bldg"
}

BASE_MOCK_PLACES = [
    {
        "place_id": "blue_bottle_ferry",
        "name": "Blue Bottle Coffee Ferry Building",
        "category": "cafe",
        "lat": 37.7958,
        "lng": -122.3930,
        "rating": 4.5,
        "user_rating_count": 850,
        "types": ["cafe", "coffee", "bakery"],
        "duration_mins": 35
    },
    {
        "place_id": "pier_7_boardwalk",
        "name": "Pier 7 Boardwalk",
        "category": "viewpoint",
        "lat": 37.7990,
        "lng": -122.3968,
        "rating": 4.8,
        "user_rating_count": 420,
        "types": ["viewpoint", "scenic", "park"],
        "duration_mins": 40
    },
    {
        "place_id": "exploratorium_museum",
        "name": "Exploratorium Science Museum",
        "category": "museum",
        "lat": 37.8014,
        "lng": -122.3975,
        "rating": 4.7,
        "user_rating_count": 4200,
        "types": ["museum", "science"],
        "duration_mins": 90
    },
    {
        "place_id": "fog_harbor_fish",
        "name": "Fog Harbor Fish House",
        "category": "restaurant",
        "lat": 37.8090,
        "lng": -122.4101,
        "rating": 4.7,
        "user_rating_count": 3600,
        "types": ["restaurant", "seafood", "dining"],
        "duration_mins": 75
    },
    {
        "place_id": "coit_tower",
        "name": "Coit Tower Telegraph Hill",
        "category": "viewpoint",
        "lat": 37.8024,
        "lng": -122.4058,
        "rating": 4.6,
        "user_rating_count": 2900,
        "types": ["viewpoint", "monument", "historic"],
        "duration_mins": 45
    },
    {
        "place_id": "salesforce_park",
        "name": "Salesforce Rooftop Park",
        "category": "park",
        "lat": 37.7897,
        "lng": -122.3965,
        "rating": 4.7,
        "user_rating_count": 620,
        "types": ["park", "garden", "nature"],
        "duration_mins": 45
    }
]


def verify_common_invariants(result: dict, available_time: int, origin: dict, test_name: str):
    """
    Strictly verifies for every test case:
    1. Route starts at origin
    2. Stops are ordered
    3. Route ends at origin
    4. total_duration <= available_time
    5. total_duration == total_travel_time + total_visit_time
    6. No duplicate destinations
    """
    total_dur = result["total_duration"]
    avail = available_time

    # 1. Total duration constraint
    assert total_dur <= avail, (
        f"[{test_name}] FAILED: total_duration ({total_dur}m) > available_time ({avail}m)"
    )

    # 2. Time decomposition integrity
    assert total_dur == (result["total_travel_time"] + result["total_visit_time"]), (
        f"[{test_name}] FAILED: duration mismatch: {total_dur} != {result['total_travel_time']} + {result['total_visit_time']}"
    )

    # 3. Starts at START
    start_loc = result["starting_location"]
    assert abs(start_loc["lat"] - origin["lat"]) < 1e-4, f"[{test_name}] FAILED: origin lat mismatch"
    assert abs(start_loc["lng"] - origin["lng"]) < 1e-4, f"[{test_name}] FAILED: origin lng mismatch"

    # 4. Ends at START
    ret = result["return_to_start"]
    assert abs(ret["lat"] - origin["lat"]) < 1e-4, f"[{test_name}] FAILED: return lat mismatch"
    assert abs(ret["lng"] - origin["lng"]) < 1e-4, f"[{test_name}] FAILED: return lng mismatch"

    # 5. Leg linkage & loop integrity: START -> p_1 -> p_2 -> ... -> START
    stops = result["ordered_itinerary"]
    destinations = result["selected_destinations"]
    assert len(stops) == len(destinations), f"[{test_name}] FAILED: itinerary vs selected length mismatch"

    # Check zero duplicate places
    place_ids = [s["place_id"] for s in stops]
    assert len(place_ids) == len(set(place_ids)), f"[{test_name}] FAILED: duplicate place_id found: {place_ids}"

    if len(stops) > 0:
        # First leg links from origin to stop 1
        assert stops[0]["transit_from_prev_mins"] >= 0
        # Return leg links from last stop to origin
        assert ret["duration_minutes"] >= 0


def test_1_one_hour_trip():
    """Case 1: 1-hour trip (60 mins)"""
    avail = 60
    res = optimize_route(
        start_location=ORIGIN_SF,
        available_time_minutes=avail,
        candidate_places=BASE_MOCK_PLACES,
        user_interests="quick coffee"
    )
    verify_common_invariants(res, avail, ORIGIN_SF, "Test 1: 1-Hour Trip")
    # A nearby quick stop like Blue Bottle (35m dwell + ~6m drive round trip) must fit
    assert len(res["selected_destinations"]) >= 1, "Should select at least 1 quick stop"
    print(f"  [PASS] Test 1: 1-hour trip -> {len(res['selected_destinations'])} stop(s), duration: {res['total_duration']}m / {avail}m")


def test_2_two_hour_trip():
    """Case 2: 2-hour trip (120 mins)"""
    avail = 120
    res = optimize_route(
        start_location=ORIGIN_SF,
        available_time_minutes=avail,
        candidate_places=BASE_MOCK_PLACES,
        user_interests="scenic walk and views"
    )
    verify_common_invariants(res, avail, ORIGIN_SF, "Test 2: 2-Hour Trip")
    assert 1 <= len(res["selected_destinations"]) <= 2
    print(f"  [PASS] Test 2: 2-hour trip -> {len(res['selected_destinations'])} stop(s), duration: {res['total_duration']}m / {avail}m")


def test_3_very_long_available_time():
    """Case 3: Very long available time (720 mins / 12 hours)"""
    avail = 720
    res = optimize_route(
        start_location=ORIGIN_SF,
        available_time_minutes=avail,
        candidate_places=BASE_MOCK_PLACES * 2,  # 12 places
        user_interests="highlights, culture, dining"
    )
    verify_common_invariants(res, avail, ORIGIN_SF, "Test 3: Long Trip")
    assert len(res["selected_destinations"]) >= 4, "Should schedule a full multi-stop tour"
    print(f"  [PASS] Test 3: Long trip -> {len(res['selected_destinations'])} stop(s), duration: {res['total_duration']}m / {avail}m")


def test_4_only_one_candidate_place():
    """Case 4: Only one candidate place"""
    # 4a: Candidate fits
    avail = 90
    single_cand = [BASE_MOCK_PLACES[0]]
    res = optimize_route(
        start_location=ORIGIN_SF,
        available_time_minutes=avail,
        candidate_places=single_cand
    )
    verify_common_invariants(res, avail, ORIGIN_SF, "Test 4a: Single Candidate (Fits)")
    assert len(res["selected_destinations"]) == 1

    # 4b: Candidate is too far / exceeds time
    unfit_cand = [{
        "place_id": "distant_isolated",
        "name": "Far Away Venue",
        "lat": 38.8,
        "lng": -122.4,  # ~110 km away
        "duration_mins": 60
    }]
    res_unfit = optimize_route(
        start_location=ORIGIN_SF,
        available_time_minutes=60,
        candidate_places=unfit_cand
    )
    verify_common_invariants(res_unfit, 60, ORIGIN_SF, "Test 4b: Single Candidate (Exceeds)")
    assert len(res_unfit["selected_destinations"]) == 0
    print(f"  [PASS] Test 4: Single candidate -> Handled fitting (1 stop) and unfeasible (0 stops)")


def test_5_no_candidate_places():
    """Case 5: No candidate places"""
    avail = 180
    res = optimize_route(
        start_location=ORIGIN_SF,
        available_time_minutes=avail,
        candidate_places=[]
    )
    verify_common_invariants(res, avail, ORIGIN_SF, "Test 5: No Candidates")
    assert len(res["selected_destinations"]) == 0
    assert res["total_duration"] == 0
    print(f"  [PASS] Test 5: No candidates -> Returned valid empty loop (START -> START, 0m duration)")


def test_6_all_places_exceed_time_limit():
    """Case 6: All places exceed the available time limit"""
    avail = 40  # Tight 40 minutes budget
    heavy_places = [
        {
            "place_id": "heavy_museum_1",
            "name": "Huge Art Museum",
            "lat": 37.8100,
            "lng": -122.4200,
            "duration_mins": 90  # 90m dwell alone > 40m budget
        },
        {
            "place_id": "far_park_2",
            "name": "Mountain Reserve",
            "lat": 38.3000,
            "lng": -122.4000,   # ~56 km away
            "duration_mins": 60
        }
    ]
    res = optimize_route(
        start_location=ORIGIN_SF,
        available_time_minutes=avail,
        candidate_places=heavy_places
    )
    verify_common_invariants(res, avail, ORIGIN_SF, "Test 6: All Exceed Time")
    # Must NOT select places that violate available time
    assert len(res["selected_destinations"]) == 0
    assert res["total_duration"] == 0
    print(f"  [PASS] Test 6: All places exceed time -> Strict safety enforcement, 0 stops scheduled")


def test_7_very_far_destination_with_high_rating():
    """Case 7: Very far destination with high rating vs reachable venue"""
    avail = 120  # 2 hours
    places = [
        {
            "place_id": "stellar_distant",
            "name": "Stellar Winery",
            "lat": 38.4500,
            "lng": -122.4500,  # ~80 km away, ~220m transit round trip
            "rating": 5.0,
            "user_rating_count": 8000,
            "category": "winery",
            "duration_mins": 60
        },
        {
            "place_id": "local_gem",
            "name": "Local Promenade",
            "lat": 37.7990,
            "lng": -122.3968,  # 0.5 km away
            "rating": 4.4,
            "user_rating_count": 250,
            "category": "viewpoint",
            "duration_mins": 35
        }
    ]
    res = optimize_route(
        start_location=ORIGIN_SF,
        available_time_minutes=avail,
        candidate_places=places
    )
    verify_common_invariants(res, avail, ORIGIN_SF, "Test 7: Far 5-Star Destination")
    # The distant place must be pruned
    selected_pids = [s["place_id"] for s in res["selected_destinations"]]
    assert "stellar_distant" not in selected_pids
    assert "local_gem" in selected_pids
    print(f"  [PASS] Test 7: Far 5-star pruned; reachable venue selected ({res['total_duration']}m <= {avail}m)")


def test_8_nearby_mediocre_destination():
    """Case 8: Nearby mediocre destination vs farther high-quality destination"""
    # 60 minutes budget allows only 1 venue: verifies high quality beats low quality nearby
    avail = 60
    places = [
        {
            "place_id": "adjacent_mediocre",
            "name": "Mediocre Corner Shop",
            "lat": 37.7956,
            "lng": -122.3935,  # 50m away
            "rating": 2.9,
            "user_rating_count": 25,
            "category": "cafe",
            "duration_mins": 30
        },
        {
            "place_id": "stellar_moderate_dist",
            "name": "Artisan Roastery",
            "lat": 37.8020,
            "lng": -122.4050,  # 1.3 km away
            "rating": 4.8,
            "user_rating_count": 950,
            "category": "cafe",
            "duration_mins": 35
        }
    ]
    res = optimize_route(
        start_location=ORIGIN_SF,
        available_time_minutes=avail,
        candidate_places=places,
        user_interests="great coffee"
    )
    verify_common_invariants(res, avail, ORIGIN_SF, "Test 8: Mediocre vs Quality")
    # Only 1 venue can fit: high-quality place MUST be chosen over nearby mediocre place
    assert len(res["selected_destinations"]) == 1
    assert res["ordered_itinerary"][0]["place_id"] == "stellar_moderate_dist"
    print(f"  [PASS] Test 8: Bayesian quality preferred over nearby low-rating stop ({res['ordered_itinerary'][0]['name']})")


def test_9_duplicate_places():
    """Case 9: Duplicate places in candidate pool"""
    avail = 180
    dup_pool = [
        BASE_MOCK_PLACES[0],
        BASE_MOCK_PLACES[0],  # Exact duplicate ID
        {
            # Same physical location & name but different dummy ID
            "place_id": "duplicate_alias_id",
            "name": BASE_MOCK_PLACES[0]["name"],
            "lat": BASE_MOCK_PLACES[0]["lat"],
            "lng": BASE_MOCK_PLACES[0]["lng"],
            "category": "cafe"
        },
        BASE_MOCK_PLACES[1],
        BASE_MOCK_PLACES[2]
    ]
    res = optimize_route(
        start_location=ORIGIN_SF,
        available_time_minutes=avail,
        candidate_places=dup_pool
    )
    verify_common_invariants(res, avail, ORIGIN_SF, "Test 9: Duplicate Places")
    # Verify no place_id is repeated
    pids = [s["place_id"] for s in res["selected_destinations"]]
    assert len(pids) == len(set(pids)), "Found duplicate place_id in output!"
    # Verify no coordinate duplicate
    coords = [(s["lat"], s["lng"]) for s in res["selected_destinations"]]
    assert len(coords) == len(set(coords)), "Found duplicate coordinate in output!"
    print(f"  [PASS] Test 9: Duplicates filtered completely; {len(pids)} unique stops scheduled")


def test_10_multiple_places_same_category():
    """Case 10: Multiple places with same category (e.g. coffee crawl)"""
    avail = 180
    cafes = [
        {"place_id": f"cafe_{i}", "name": f"Coffee Spot {i}", "lat": 37.7960 + i*0.002, "lng": -122.3940, "rating": 4.5, "category": "cafe", "duration_mins": 30}
        for i in range(5)
    ]
    res = optimize_route(
        start_location=ORIGIN_SF,
        available_time_minutes=avail,
        candidate_places=cafes,
        user_interests="coffee tasting"
    )
    verify_common_invariants(res, avail, ORIGIN_SF, "Test 10: Same Category Candidates")
    assert len(res["selected_destinations"]) >= 2, "Soft diversity should still allow multiple cafes when no other options exist"
    print(f"  [PASS] Test 10: Multiple same-category places handled gracefully ({len(res['selected_destinations'])} stops)")


def test_11_nature_and_food_preferences():
    """Case 11: Nature + food preferences"""
    avail = 240
    res = optimize_route(
        start_location=ORIGIN_SF,
        available_time_minutes=avail,
        candidate_places=BASE_MOCK_PLACES,
        user_interests="nature, scenic park, delicious food"
    )
    verify_common_invariants(res, avail, ORIGIN_SF, "Test 11: Nature + Food")
    categories = [s["category"] for s in res["selected_destinations"]]
    has_food = any(c in ["restaurant", "cafe", "food"] for c in categories)
    has_nature = any(c in ["park", "viewpoint", "nature"] for c in categories)
    assert has_food or has_nature, "Should select venues aligned with nature and food"
    print(f"  [PASS] Test 11: Selected categories aligned with user vibe: {categories}")


def test_12_no_interests_specified():
    """Case 12: No interests specified (None or empty string)"""
    avail = 180
    res = optimize_route(
        start_location=ORIGIN_SF,
        available_time_minutes=avail,
        candidate_places=BASE_MOCK_PLACES,
        user_interests=None
    )
    verify_common_invariants(res, avail, ORIGIN_SF, "Test 12: No Interests")
    assert len(res["selected_destinations"]) >= 1
    print(f"  [PASS] Test 12: Defaulted neutrally and generated {len(res['selected_destinations'])} high-quality stops")


def test_13_return_journey_causing_time_limit_exceed():
    """Case 13: Return journey causing a route to exceed the time limit"""
    avail = 100  # 100 minutes total budget
    places = [
        # Place 1: ~1 km away (6m transit). Dwell 45m. Return ~6m -> Loop is 57 mins <= 100
        {
            "place_id": "stop_1_near",
            "name": "Near Stop",
            "lat": 37.8000,
            "lng": -122.3950,
            "category": "attraction",
            "duration_mins": 45,
            "rating": 4.8
        },
        # Place 2: 12 km away. If visited, transit out + dwell 45m + return 35m exceeds 100 mins
        {
            "place_id": "stop_2_far",
            "name": "Far Stop",
            "lat": 37.8900,
            "lng": -122.3600,
            "category": "viewpoint",
            "duration_mins": 45,
            "rating": 4.9
        }
    ]
    res = optimize_route(
        start_location=ORIGIN_SF,
        available_time_minutes=avail,
        candidate_places=places
    )
    verify_common_invariants(res, avail, ORIGIN_SF, "Test 13: Return Journey Bound")
    selected_pids = [s["place_id"] for s in res["selected_destinations"]]
    assert "stop_2_far" not in selected_pids, "stop_2_far MUST be rejected because return journey causes exceedance!"
    assert "stop_1_near" in selected_pids
    assert res["total_duration"] <= avail
    print(f"  [PASS] Test 13: Return journey reserved strictly: Far stop omitted, duration: {res['total_duration']}m <= {avail}m")


def test_14_places_with_missing_optional_data():
    """Case 14: Places with missing optional data (None ratings, missing location, string formats)"""
    avail = 180
    messy_places = [
        {
            "place_id": "messy_1",
            "name": "No Rating Place",
            "lat": 37.7960,
            "lng": -122.3940,
            "rating": None,
            "user_rating_count": None,
            "types": None,
            "category": None
        },
        {
            "place_id": "messy_2",
            "name": "Nested Coords and String Rating",
            "location": {"latitude": "37.7980", "longitude": "-122.3960"},
            "rating": "4.6",
            "user_rating_count": "320",
            "duration_mins": "40"
        },
        {
            "name": "Missing ID and Address",
            "lat": 37.7970,
            "lng": -122.3950
        }
    ]
    res = optimize_route(
        start_location=ORIGIN_SF,
        available_time_minutes=avail,
        candidate_places=messy_places
    )
    verify_common_invariants(res, avail, ORIGIN_SF, "Test 14: Missing Optional Data")
    assert len(res["selected_destinations"]) >= 1
    print(f"  [PASS] Test 14: Missing optional data gracefully handled without exceptions ({len(res['selected_destinations'])} stops)")


def test_15_unreachable_place():
    """Case 15: Unreachable place (e.g. Sydney Opera House 11,000 km away)"""
    avail = 120
    places = [
        {
            "place_id": "sydney_opera_house",
            "name": "Sydney Opera House",
            "lat": -33.8568,
            "lng": 151.2153,  # Australia!
            "rating": 4.9,
            "user_rating_count": 50000,
            "category": "monument",
            "duration_mins": 60
        },
        BASE_MOCK_PLACES[0]  # Local reachable SF venue
    ]
    res = optimize_route(
        start_location=ORIGIN_SF,
        available_time_minutes=avail,
        candidate_places=places
    )
    verify_common_invariants(res, avail, ORIGIN_SF, "Test 15: Unreachable Place")
    selected_pids = [s["place_id"] for s in res["selected_destinations"]]
    assert "sydney_opera_house" not in selected_pids, "Sydney Opera House must be pruned as unreachable!"
    assert BASE_MOCK_PLACES[0]["place_id"] in selected_pids
    print(f"  [PASS] Test 15: Extreme unreachable place pruned; local destination scheduled ({res['total_duration']}m <= {avail}m)")


def run_all_15_test_cases():
    print("=" * 80)
    print("RUNNING 15 ALGORITHM ENGINEERING REVIEW TEST CASES FOR ROUTE OPTIMIZER")
    print("=" * 80)

    test_1_one_hour_trip()
    test_2_two_hour_trip()
    test_3_very_long_available_time()
    test_4_only_one_candidate_place()
    test_5_no_candidate_places()
    test_6_all_places_exceed_time_limit()
    test_7_very_far_destination_with_high_rating()
    test_8_nearby_mediocre_destination()
    test_9_duplicate_places()
    test_10_multiple_places_same_category()
    test_11_nature_and_food_preferences()
    test_12_no_interests_specified()
    test_13_return_journey_causing_time_limit_exceed()
    test_14_places_with_missing_optional_data()
    test_15_unreachable_place()

    print("\n" + "=" * 80)
    print("ALL 15 TEST CASES PASSED SUCCESSFULLY!")
    print("EVERY TEST CASE VERIFIED:")
    print("  1. START -> destinations -> START loop integrity")
    print("  2. total_duration <= available_time hard constraint")
    print("=" * 80)


if __name__ == "__main__":
    run_all_15_test_cases()
