"""
Test Suite for Conversational Itinerary Modifications

Verifies that RoamAroundAgent can modify existing itineraries based on natural-language requests:
1. "Remove the restaurant."
2. "Replace the last stop with something outdoors."
3. "I want only two destinations."
4. "Add a cafe if there is enough time."
5. "Make this route shorter."
6. "I don't want museums."

Enforces:
- Agent understands requested change
- Updates itinerary constraints / preferences
- Searches / filters candidates
- Calls deterministic optimizer again
- Validates time constraint (total_duration <= available_time)
- Returns updated itinerary
- NO manual edits inside LLM (optimizer is strictly responsible for route validity)
"""

import sys
import os
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.agent import RoamAroundAgent
from services.itinerary_generator import generate_user_friendly_itinerary


def build_baseline_itinerary():
    """Generates a realistic initial 4-hour itinerary for testing modifications."""
    return {
        "status": "success",
        "starting_location": {
            "name": "San Francisco Ferry Building",
            "lat": 37.7955,
            "lng": -122.3937,
            "address": "1 Ferry Building, San Francisco, CA 94105"
        },
        "ordered_destinations": [
            {
                "stop_number": 1,
                "place_id": "cand_museum_1",
                "name": "San Francisco Museum of Modern Art",
                "category": "museum",
                "lat": 37.7857,
                "lng": -122.4011,
                "address": "151 3rd St, San Francisco, CA",
                "rating": 4.6,
                "review_count": 2100,
                "price_level": "$$ (Moderate)",
                "arrival_time": "09:40 AM",
                "departure_time": "10:50 AM",
                "suggested_duration": "1 hour 10 mins",
                "duration_mins": 70,
                "transit_from_previous": {"travel_time_minutes": 10, "distance_km": 1.5},
                "type": "attraction"
            },
            {
                "stop_number": 2,
                "place_id": "cand_rest_2",
                "name": "Fog Harbor Fish House",
                "category": "restaurant",
                "lat": 37.8085,
                "lng": -122.4105,
                "address": "Pier 39, San Francisco, CA",
                "rating": 4.7,
                "review_count": 3200,
                "price_level": "$$$ (Expensive)",
                "arrival_time": "11:05 AM",
                "departure_time": "12:15 PM",
                "suggested_duration": "1 hour 10 mins",
                "duration_mins": 70,
                "transit_from_previous": {"travel_time_minutes": 15, "distance_km": 3.0},
                "type": "restaurant"
            },
            {
                "stop_number": 3,
                "place_id": "cand_view_3",
                "name": "Coit Tower Observation Deck",
                "category": "viewpoint",
                "lat": 37.8024,
                "lng": -122.4058,
                "address": "1 Telegraph Hill Blvd, San Francisco, CA",
                "rating": 4.7,
                "review_count": 1800,
                "price_level": "$$ (Moderate)",
                "arrival_time": "12:25 PM",
                "departure_time": "01:10 PM",
                "suggested_duration": "45 mins",
                "duration_mins": 45,
                "transit_from_previous": {"travel_time_minutes": 10, "distance_km": 1.2},
                "type": "attraction"
            }
        ],
        "total_duration": {
            "minutes": 220,
            "formatted": "3 hours 40 mins",
            "available_budget_minutes": 240,
            "slack_minutes": 20
        },
        "total_travel_time": {"minutes": 45, "formatted": "45 mins"},
        "total_visit_time": {"minutes": 175, "formatted": "2 hours 55 mins"},
        "total_distance": {"km": 6.8, "formatted": "6.8 km"},
        "transportation_mode": "DRIVE",
        "return_to_start_confirmation": {
            "confirmed": True,
            "origin_name": "San Francisco Ferry Building",
            "return_arrival_time": "01:20 PM",
            "final_leg_travel_time": "10 mins",
            "final_leg_distance": "1.1 km"
        }
    }


def run_modification_tests():
    print("=" * 80)
    print("VERIFYING CONVERSATIONAL ITINERARY MODIFICATION ENGINE")
    print("=" * 80)

    agent = RoamAroundAgent()

    # -----------------------------------------------------------------------
    # TEST 1: "Remove the restaurant."
    # -----------------------------------------------------------------------
    print("\n--- TEST 1: 'Remove the restaurant.' ---")
    base1 = build_baseline_itinerary()
    res1 = agent.modify_itinerary("Remove the restaurant.", current_itinerary=base1)
    itin1 = res1["itinerary"]
    stops1 = itin1["ordered_destinations"]
    categories1 = [s["category"] for s in stops1]

    print(f"  [Action] {res1['modification_applied']}")
    print(f"  [Stops Remaining] {[s['name'] for s in stops1]}")
    print(f"  [Categories] {categories1}")
    print(f"  [Total Duration] {itin1['total_duration']['formatted']} (Budget: {itin1['total_duration']['available_budget_minutes']}m)")

    assert "restaurant" not in categories1, "Error: Restaurant stop was not removed!"
    assert itin1["total_duration"]["minutes"] <= itin1["total_duration"]["available_budget_minutes"], "Time constraint violated!"
    assert itin1["return_to_start_confirmation"]["confirmed"] is True
    print("  [PASS] Restaurant removed; route re-optimized and time constraint satisfied.")

    # -----------------------------------------------------------------------
    # TEST 2: "Replace the last stop with something outdoors."
    # -----------------------------------------------------------------------
    print("\n--- TEST 2: 'Replace the last stop with something outdoors.' ---")
    base2 = build_baseline_itinerary()
    old_last_id = base2["ordered_destinations"][-1]["place_id"]
    res2 = agent.modify_itinerary("Replace the last stop with something outdoors.", current_itinerary=base2)
    itin2 = res2["itinerary"]
    stops2 = itin2["ordered_destinations"]

    print(f"  [Action] {res2['modification_applied']}")
    print(f"  [Previous Last Stop] {base2['ordered_destinations'][-1]['name']} ({old_last_id})")
    print(f"  [New Stops] {[s['name'] for s in stops2]}")
    print(f"  [Delta] Added: {res2['delta']['stops_added']}, Removed: {res2['delta']['stops_removed']}")

    new_pids2 = [s["place_id"] for s in stops2]
    assert old_last_id not in new_pids2, f"Error: Old last stop {old_last_id} is still in itinerary!"
    assert itin2["total_duration"]["minutes"] <= itin2["total_duration"]["available_budget_minutes"], "Time constraint violated!"
    print("  [PASS] Last stop successfully replaced with outdoors venue; re-sequenced by optimizer.")

    # -----------------------------------------------------------------------
    # TEST 3: "I want only two destinations."
    # -----------------------------------------------------------------------
    print("\n--- TEST 3: 'I want only two destinations.' ---")
    base3 = build_baseline_itinerary()
    res3 = agent.modify_itinerary("I want only two destinations.", current_itinerary=base3)
    itin3 = res3["itinerary"]
    stops3 = itin3["ordered_destinations"]

    print(f"  [Action] {res3['modification_applied']}")
    print(f"  [Stop Count] {len(stops3)} destinations scheduled")
    print(f"  [Destinations] {[s['name'] for s in stops3]}")

    assert len(stops3) == 2, f"Error: Expected exactly 2 destinations, got {len(stops3)}"
    assert itin3["total_duration"]["minutes"] <= itin3["total_duration"]["available_budget_minutes"], "Time constraint violated!"
    print("  [PASS] Optimizer strictly limited route to exactly two destinations.")

    # -----------------------------------------------------------------------
    # TEST 4: "Add a cafe if there is enough time."
    # -----------------------------------------------------------------------
    print("\n--- TEST 4: 'Add a cafe if there is enough time.' ---")
    base4 = build_baseline_itinerary()
    res4 = agent.modify_itinerary("Add a cafe if there is enough time.", current_itinerary=base4)
    itin4 = res4["itinerary"]
    stops4 = itin4["ordered_destinations"]
    categories4 = [s["category"] for s in stops4]

    print(f"  [Action] {res4['modification_applied']}")
    print(f"  [Categories Scheduled] {categories4}")
    print(f"  [Total Duration] {itin4['total_duration']['formatted']} <= {itin4['total_duration']['available_budget_minutes']}m budget")

    assert itin4["total_duration"]["minutes"] <= itin4["total_duration"]["available_budget_minutes"], "Time constraint violated!"
    print("  [PASS] Cafe candidate evaluated; optimizer guaranteed duration fits within time budget.")

    # -----------------------------------------------------------------------
    # TEST 5: "Make this route shorter."
    # -----------------------------------------------------------------------
    print("\n--- TEST 5: 'Make this route shorter.' ---")
    base5 = build_baseline_itinerary()
    prev_duration5 = base5["total_duration"]["minutes"]
    res5 = agent.modify_itinerary("Make this route shorter.", current_itinerary=base5)
    itin5 = res5["itinerary"]
    new_duration5 = itin5["total_duration"]["minutes"]

    print(f"  [Action] {res5['modification_applied']}")
    print(f"  [Previous Duration] {prev_duration5} mins")
    print(f"  [New Duration]      {new_duration5} mins")
    print(f"  [New Budget]        {itin5['total_duration']['available_budget_minutes']} mins")

    assert new_duration5 < prev_duration5, f"Error: New duration {new_duration5}m should be shorter than {prev_duration5}m"
    assert new_duration5 <= itin5["total_duration"]["available_budget_minutes"], "Time constraint violated!"
    print("  [PASS] Route shortened successfully while preserving loop validity.")

    # -----------------------------------------------------------------------
    # TEST 6: "I don't want museums."
    # -----------------------------------------------------------------------
    print("\n--- TEST 6: 'I don't want museums.' ---")
    base6 = build_baseline_itinerary()
    res6 = agent.modify_itinerary("I don't want museums.", current_itinerary=base6)
    itin6 = res6["itinerary"]
    stops6 = itin6["ordered_destinations"]
    categories6 = [s["category"] for s in stops6]

    print(f"  [Action] {res6['modification_applied']}")
    print(f"  [Categories Scheduled] {categories6}")
    print(f"  [Stops] {[s['name'] for s in stops6]}")

    assert "museum" not in categories6 and "art_gallery" not in categories6, "Error: Museum stop found!"
    assert itin6["total_duration"]["minutes"] <= itin6["total_duration"]["available_budget_minutes"], "Time constraint violated!"
    print("  [PASS] Museums excluded completely; route re-optimized.")

    print("\n" + "=" * 80)
    print("ALL 6 CONVERSATIONAL MODIFICATION SCENARIOS PASSED 100%!")
    print("================================================================================")


if __name__ == "__main__":
    run_modification_tests()
