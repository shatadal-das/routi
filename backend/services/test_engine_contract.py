"""
Contract & Constraint Test Suite for the RoamAround Route Optimization Engine
"""

import sys
import os
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.test_scorer import MOCK_PLACES, ORIGIN_LAT, ORIGIN_LNG
from services.optimizer import optimize_route


def run_contract_tests():
    print("=" * 80)
    print("VERIFYING ROUTE OPTIMIZATION ENGINE CONTRACT & CONSTRAINTS")
    print("=" * 80)

    start_loc = {
        "name": "San Francisco Ferry Building",
        "lat": ORIGIN_LAT,
        "lng": ORIGIN_LNG,
        "address": "1 Ferry Building, San Francisco, CA 94105"
    }

    avail_mins = 240  # 4.0 hours

    # 1. Execute Optimizer
    result = optimize_route(
        start_location=start_loc,
        available_time_minutes=avail_mins,
        transportation_mode="DRIVE",
        user_interests="Relaxed waterfront walk, scenic bay views, and seafood",
        candidate_places=MOCK_PLACES
    )

    print(f"Status:             {result['status']}")
    print(f"Total Duration:     {result['total_duration']} mins (Budget: {avail_mins} mins)")
    print(f"Total Travel Time:  {result['total_travel_time']} mins")
    print(f"Total Visit Time:   {result['total_visit_time']} mins")
    print(f"Total Distance:     {result['total_distance']} km")
    print(f"Route Score:        {result['score']} / 100")
    print(f"Selected Stops:     {len(result['selected_destinations'])}")

    print("\n--- ORDERED ITINERARY ---")
    for s in result["ordered_itinerary"]:
        print(f"Stop {s['stop_index']}: {s['name']} ({s['category']})")
        print(f"  Schedule: {s['arrival_time']} to {s['departure_time']} (Dwell: {s['duration_mins']} mins)")
        print(f"  Transit from prev: {s['transit_from_prev_mins']} mins ({s['transit_from_prev_km']} km)")
        print(f"  AI Rationale: {s['ai_reasoning']}")
        print(f"  Time Reason:  {s['time_estimate_reason']}")

    ret = result["return_to_start"]
    print(f"\nReturn Leg:")
    print(f"  Destination: {ret['destination']} ({ret['lat']}, {ret['lng']})")
    print(f"  Arrival:     {ret['arrival_clock']} (Drive: {ret['duration_minutes']} mins, {ret['distance_km']} km)")

    # -------------------------------------------------------------------
    # Verification of Hard Constraints
    # -------------------------------------------------------------------
    print("\n--- HARD CONSTRAINT VERIFICATION ---")

    # Hard Constraint 1: Route starts at starting location
    first_stop = result["ordered_itinerary"][0]
    assert first_stop["transit_from_prev_mins"] >= 0
    assert result["starting_location"]["name"] == start_loc["name"]
    print("  [PASS] Constraint 1: Route starts at the designated starting location.")

    # Hard Constraint 2: Route ends at starting location
    assert ret["lat"] == start_loc["lat"]
    assert ret["lng"] == start_loc["lng"]
    print("  [PASS] Constraint 2: Route explicitly returns and ends at starting location.")

    # Hard Constraint 3: Total duration <= available time
    assert result["total_duration"] <= avail_mins, (
        f"Violation: {result['total_duration']} > {avail_mins}"
    )
    print(f"  [PASS] Constraint 3: Total duration ({result['total_duration']}m) does not exceed available time ({avail_mins}m).")

    # Hard Constraint 4: Return travel time is strictly reserved
    assert ret["duration_minutes"] > 0
    assert result["total_duration"] == (result["total_travel_time"] + result["total_visit_time"])
    print("  [PASS] Constraint 4: Return travel time is accounted for and reserved.")

    # Hard Constraint 5: No duplicate places
    place_ids = [s["place_id"] for s in result["selected_destinations"]]
    assert len(place_ids) == len(set(place_ids)), "Violation: Duplicate place_ids detected!"
    print("  [PASS] Constraint 5: Zero duplicate places in selected destinations.")

    # Hard Constraint 6: No unreachable destinations
    for s in result["selected_destinations"]:
        assert s["transit_from_prev_mins"] < 60, "Violation: Unreachable destination selected!"
    print("  [PASS] Constraint 6: All selected destinations are reachable within constraints.")

    # -------------------------------------------------------------------
    # Verification of Determinism
    # -------------------------------------------------------------------
    print("\n--- DETERMINISM VERIFICATION ---")
    result_run2 = optimize_route(
        start_location=start_loc,
        available_time_minutes=avail_mins,
        transportation_mode="DRIVE",
        user_interests="Relaxed waterfront walk, scenic bay views, and seafood",
        candidate_places=MOCK_PLACES
    )
    # Compare JSON serializations
    str1 = json.dumps(result, sort_keys=True)
    str2 = json.dumps(result_run2, sort_keys=True)
    assert str1 == str2, "Violation: Non-deterministic output detected!"
    print("  [PASS] Determinism: Consecutive runs with identical inputs produce 100% identical outputs.")

    print("\n" + "=" * 80)
    print("ALL HARD CONSTRAINTS AND CONTRACT CHECKS VERIFIED SUCCESSFULLY.")
    print("=" * 80)


if __name__ == "__main__":
    run_contract_tests()
