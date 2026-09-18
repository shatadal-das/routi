"""
Unit & Integration Test Suite for the RoamAround Optimizer Explainability Layer

Verifies:
1. Every selected destination exposes concise user-facing `selection_reasons: List[str]`
   (e.g., 'Strong match for nature preference', 'High place quality score', 'Low additional travel time', 'Adds category diversity').
2. Major reasons candidates are rejected when useful:
   - 'Exceeds remaining time'
   - 'Excessive travel time'
   - 'Duplicate category'
   - 'Poor preference match'
3. Zero internal implementation details or raw model reasoning/floats exposed.
4. Integration with `itinerary_generator.py` and `tools.py`.
"""

import sys
import os
import json

# Ensure project backend directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.optimizer import optimize_route, RouteOptimizer
from services.itinerary_generator import generate_user_friendly_itinerary
from services.tools import optimize_trip


def test_selected_destination_explainability():
    """Verify that every selected destination includes concise, user-facing selection reasons."""
    start_location = {
        "name": "San Francisco Ferry Building",
        "lat": 37.7955,
        "lng": -122.3937,
        "address": "1 Ferry Building, San Francisco, CA"
    }

    candidates = [
        {
            "place_id": "nature_lake",
            "name": "Example Lake & Botanical Park",
            "category": "park",
            "lat": 37.7990,
            "lng": -122.3980,
            "rating": 4.8,
            "review_count": 1200,
            "duration_mins": 45
        },
        {
            "place_id": "seafood_harbor",
            "name": "Harbor Fresh Seafood",
            "category": "restaurant",
            "lat": 37.8010,
            "lng": -122.4010,
            "rating": 4.7,
            "review_count": 2100,
            "duration_mins": 60
        },
        {
            "place_id": "bay_viewpoint",
            "name": "Panoramic Bay Lookout",
            "category": "viewpoint",
            "lat": 37.7970,
            "lng": -122.3950,
            "rating": 4.6,
            "review_count": 650,
            "duration_mins": 35
        }
    ]

    result = optimize_route(
        start_location=start_location,
        available_time_minutes=240,  # 4 hours
        transportation_mode="DRIVE",
        user_interests="nature and scenic viewpoints",
        candidate_places=candidates
    )

    selected = result["selected_destinations"]
    assert len(selected) > 0, "Expected at least 1 destination to be selected."

    forbidden_tokens = ["0.", "sub_scores", "bayesian", "haversine", "coefficient", "float", "formula"]

    for stop in selected:
        # Check place name and selection_reasons presence
        assert "place" in stop, f"Stop missing 'place' field: {stop}"
        assert "selection_reasons" in stop, f"Stop missing 'selection_reasons' field: {stop}"
        reasons = stop["selection_reasons"]
        assert isinstance(reasons, list), f"'selection_reasons' must be a list: {reasons}"
        assert len(reasons) >= 1, f"Expected at least 1 selection reason for {stop['place']}"

        for r in reasons:
            assert isinstance(r, str), f"Reason must be string: {r}"
            assert len(r.strip()) > 5, f"Reason text too short: '{r}'"
            # Ensure no internal formulas or model details
            for tok in forbidden_tokens:
                assert tok not in r.lower(), f"Forbidden internal detail '{tok}' found in reason: '{r}'"

    # Specific check for nature match on the park
    lake_stop = next((s for s in selected if s["place_id"] == "nature_lake"), None)
    if lake_stop:
        reasons = lake_stop["selection_reasons"]
        assert any("nature" in r.lower() or "preference" in r.lower() for r in reasons), (
            f"Expected nature preference reason for lake stop, got: {reasons}"
        )
        assert any("quality" in r.lower() or "highlight" in r.lower() for r in reasons), (
            f"Expected quality score reason for 4.8-star stop, got: {reasons}"
        )

    print("  [PASS] Selected destination explainability verified (concise, user-facing, zero internal formulas).")


def test_rejection_reasons_coverage():
    """
    Verify that major candidate rejection reasons are accurately surfaced:
    - Exceeds remaining time
    - Excessive travel time
    - Duplicate category
    - Poor preference match
    """
    start_location = {
        "name": "Downtown Departure Hub",
        "lat": 37.7955,
        "lng": -122.3937
    }

    # Setup candidate set specifically tailored to trigger all 4 rejection reasons
    candidates = [
        # Candidate 1: High quality anchor that will get selected (park)
        {
            "place_id": "anchor_park",
            "name": "Central Rose Garden",
            "category": "park",
            "lat": 37.7960,
            "lng": -122.3940,
            "rating": 4.9,
            "review_count": 1500,
            "duration_mins": 50
        },
        # Candidate 2: High quality restaurant that gets selected
        {
            "place_id": "main_restaurant",
            "name": "Gourmet Bistro",
            "category": "restaurant",
            "lat": 37.7975,
            "lng": -122.3960,
            "rating": 4.8,
            "review_count": 950,
            "duration_mins": 60
        },
        # Candidate 3: Duplicate category (2nd restaurant when 1 is already selected & budget is tight)
        {
            "place_id": "duplicate_restaurant",
            "name": "Secondary Burger Joint",
            "category": "restaurant",
            "lat": 37.7980,
            "lng": -122.3970,
            "rating": 4.2,
            "review_count": 200,
            "duration_mins": 60
        },
        # Candidate 4: Poor preference match (commercial shopping center when user wants purely outdoor nature)
        {
            "place_id": "unmatched_mall",
            "name": "Mega Outlet Shopping Center",
            "category": "shopping",
            "lat": 37.7990,
            "lng": -122.3980,
            "rating": 3.9,
            "review_count": 400,
            "duration_mins": 60
        },
        # Candidate 5: Excessive travel time (very far away - 35 km detour)
        {
            "place_id": "distant_resort",
            "name": "Distant Mountain Retreat",
            "category": "nature",
            "lat": 38.1500,
            "lng": -122.8000,
            "rating": 4.7,
            "review_count": 800,
            "duration_mins": 75
        },
        # Candidate 6: Exceeds remaining time (requires 2.5 hours dwell on a 2-hour total trip)
        {
            "place_id": "huge_museum",
            "name": "Immense Comprehensive History Museum",
            "category": "museum",
            "lat": 37.7965,
            "lng": -122.3945,
            "rating": 4.6,
            "review_count": 1100,
            "duration_mins": 140  # Dwell alone exceeds available slack
        }
    ]

    result = optimize_route(
        start_location=start_location,
        available_time_minutes=135,  # 2h 15m allows park (50m) + bistro (60m) + transit, leaving no room for a 3rd stop
        transportation_mode="DRIVE",
        user_interests="outdoor nature and dining",
        candidate_places=candidates
    )

    rejected = result.get("rejected_destinations", [])
    assert len(rejected) > 0, "Expected candidates to be rejected under 2-hour budget."

    rejected_reasons_by_name = {r["place"]: r["rejection_reasons"] for r in rejected}

    # 1. Verify 'Duplicate category'
    dup_reasons = rejected_reasons_by_name.get("Secondary Burger Joint", [])
    assert any("duplicate category" in r.lower() for r in dup_reasons), (
        f"Expected 'Duplicate category' for Secondary Burger Joint, got: {dup_reasons}"
    )

    # 2. Verify 'Poor preference match'
    mall_reasons = rejected_reasons_by_name.get("Mega Outlet Shopping Center", [])
    assert any("poor preference match" in r.lower() for r in mall_reasons), (
        f"Expected 'Poor preference match' for Shopping Center when vibe is nature, got: {mall_reasons}"
    )

    # 3. Verify 'Excessive travel time'
    distant_reasons = rejected_reasons_by_name.get("Distant Mountain Retreat", [])
    assert any("excessive travel time" in r.lower() for r in distant_reasons), (
        f"Expected 'Excessive travel time' for distant place, got: {distant_reasons}"
    )

    # 4. Verify 'Exceeds remaining time'
    museum_reasons = rejected_reasons_by_name.get("Immense Comprehensive History Museum", [])
    assert any("exceeds remaining time" in r.lower() for r in museum_reasons), (
        f"Expected 'Exceeds remaining time' for massive museum, got: {museum_reasons}"
    )

    # Ensure all rejected candidates have clean schema
    for rej in rejected:
        assert "place" in rej
        assert "category" in rej
        assert "rejection_reasons" in rej
        assert isinstance(rej["rejection_reasons"], list)
        assert len(rej["rejection_reasons"]) > 0

    print("  [PASS] All 4 candidate rejection reasons verified ('Exceeds remaining time', 'Excessive travel time', 'Duplicate category', 'Poor preference match').")


def test_itinerary_generator_explainability_preservation():
    """Verify that the AI presentation layer preserves selection_reasons and rejected_destinations."""
    start_location = {
        "name": "San Francisco Ferry Building",
        "lat": 37.7955,
        "lng": -122.3937
    }

    candidates = [
        {
            "place_id": "stop_1",
            "name": "Waterfront Promenade",
            "category": "park",
            "lat": 37.7980,
            "lng": -122.3950,
            "rating": 4.8,
            "review_count": 900,
            "duration_mins": 45
        },
        {
            "place_id": "stop_rejected",
            "name": "Far Off Winery",
            "category": "winery",
            "lat": 38.3000,
            "lng": -122.5000,
            "rating": 4.5,
            "review_count": 300,
            "duration_mins": 90
        }
    ]

    raw_opt = optimize_route(
        start_location=start_location,
        available_time_minutes=120,
        transportation_mode="DRIVE",
        user_interests="waterfront and parks",
        candidate_places=candidates
    )

    # Generate user-friendly presentation
    presentation = generate_user_friendly_itinerary(
        optimizer_data=raw_opt,
        user_preferences="waterfront and parks",
        transportation_mode="DRIVE"
    )

    # Verify ordered_destinations have selection_reasons
    assert "ordered_destinations" in presentation
    assert len(presentation["ordered_destinations"]) > 0
    first_dest = presentation["ordered_destinations"][0]

    assert "place" in first_dest, f"Missing 'place' in ordered_destination: {first_dest}"
    assert "selection_reasons" in first_dest, f"Missing 'selection_reasons': {first_dest}"
    assert isinstance(first_dest["selection_reasons"], list)
    assert len(first_dest["selection_reasons"]) >= 1

    # Verify rejected_destinations at root
    assert "rejected_destinations" in presentation
    assert isinstance(presentation["rejected_destinations"], list)
    assert len(presentation["rejected_destinations"]) > 0
    first_rej = presentation["rejected_destinations"][0]
    assert "place" in first_rej
    assert "rejection_reasons" in first_rej
    assert isinstance(first_rej["rejection_reasons"], list)

    print("  [PASS] Itinerary generator successfully retains explainability layer for UI display.")


def test_tools_optimize_trip_explainability():
    """Verify that the optimize_trip() tool exposes selection_reasons and rejected_destinations."""
    start_location = {
        "name": "Union Square",
        "lat": 37.7879,
        "lng": -122.4075
    }

    candidates = [
        {
            "place_id": "c1",
            "name": "Yerba Buena Gardens",
            "category": "park",
            "lat": 37.7860,
            "lng": -122.4030,
            "rating": 4.7,
            "review_count": 1800,
            "duration_mins": 45
        }
    ]

    tool_res = optimize_trip(
        start_location=start_location,
        available_time_minutes=90,
        transportation_mode="WALK",
        user_interests="peaceful gardens",
        candidate_places=candidates
    )

    assert tool_res["status"] == "success"
    assert "selected_destinations" in tool_res
    assert len(tool_res["selected_destinations"]) == 1
    dest = tool_res["selected_destinations"][0]
    assert "place" in dest
    assert "selection_reasons" in dest
    assert any("garden" in r.lower() or "nature" in r.lower() or "quality" in r.lower() for r in dest["selection_reasons"])

    print("  [PASS] optimize_trip() tool contract verified with explainability layer.")


if __name__ == "__main__":
    print("=" * 80)
    print("RUNNING EXPLAINABILITY LAYER TEST SUITE FOR ROAMAROUND OPTIMIZER")
    print("=" * 80)
    try:
        test_selected_destination_explainability()
        test_rejection_reasons_coverage()
        test_itinerary_generator_explainability_preservation()
        test_tools_optimize_trip_explainability()
        print("=" * 80)
        print("ALL EXPLAINABILITY LAYER TESTS PASSED SUCCESSFULLY!")
        print("=" * 80)
    except AssertionError as e:
        print(f"\n[FAIL] Test assertion failed: {e}")
        sys.exit(1)
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"\n[ERROR] Unexpected error: {e}")
        sys.exit(1)
