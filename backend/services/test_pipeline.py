"""
End-to-End Test for the Complete RoamAround Pipeline
Invokes generate_route directly to verify Places API -> Scorer -> Optimizer -> Agent -> Routes API.
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from main import generate_route, RouteRequest


def test_full_pipeline():
    print("=" * 80)
    print("TESTING FULL ROAMAROUND BACKEND PIPELINE")
    print("=" * 80)

    req = RouteRequest(
        address="San Francisco Ferry Building",
        start_lat=37.7955,
        start_lng=-122.3937,
        time_hours=4.0,
        vibe="Relaxed waterfront walk and seafood",
        price_level="$$"
    )

    print("\nSending RouteRequest for 4.0h trip from SF Ferry Building...")
    result = generate_route(req)

    print(f"\nResponse Status: {result.get('status')}")
    print(f"Curator Model:   {result.get('curator_model')}")
    print(f"Total Trip Time: {result.get('total_trip_time')}")
    print(f"Total Hours:     {result.get('total_trip_hours')}")
    print(f"Polyline length: {len(result.get('polyline', ''))} chars")
    print(f"Google Maps URL: {result.get('google_maps_url')[:65]}...")
    print(f"Narrative:       {result.get('narrative')}")

    print("\n--- SCHEDULED STOPS ---")
    header = f"{'Stop':<5} | {'Venue Name':<30} | {'Category':<12} | {'Timetable':<23} | {'Rating'}"
    print(header)
    print("-" * 85)

    places = result.get("optimized_places", [])
    for idx, p in enumerate(places, start=1):
        clock_str = f"{p.get('arrival_time', 'N/A')} - {p.get('departure_time', 'N/A')}"
        rating_str = f"{p.get('rating', 4.0)}* ({p.get('price_level', '$$')})"
        print(f"{idx:<5} | {p['name'][:30]:<30} | {p.get('category', 'attraction'):<12} | {clock_str:<23} | {rating_str}")
        print(f"      AI Rationale: {p.get('ai_reasoning')}")
        print(f"      Time Reason:  {p.get('time_estimate_reason')}")

    print("\n--- TRANSIT LEGS ---")
    for leg in result.get("legs", []):
        print(f"  Leg {leg['leg_index']}: {leg['duration_text']} ({leg['distance_text']})")

    # Invariants
    assert result["status"] == "success"
    assert len(places) >= 2
    assert len(result.get("polyline", "")) > 10, "Polyline must be generated"
    assert "narrative" in result
    print("\n" + "=" * 80)
    print("ALL END-TO-END PIPELINE CHECKS PASSED.")
    print("=" * 80)


if __name__ == "__main__":
    test_full_pipeline()
