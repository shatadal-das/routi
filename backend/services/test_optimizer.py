"""
Test & Verification Suite for RoamAround Route Optimizer & AI Agent
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.test_scorer import MOCK_PLACES, ORIGIN_LAT, ORIGIN_LNG
from services.optimizer import optimize_day_itinerary, OptimizedItineraryPlan
from services.agent import RoamAroundAgent


def test_optimizer_direct():
    print("=" * 80)
    print("TEST: OPTIMIZER DIRECT EXECUTION")
    print("=" * 80)

    total_hours = 4.0
    vibe = "Relaxed waterfront walk and seafood, scenic bay views"

    plan: OptimizedItineraryPlan = optimize_day_itinerary(
        origin_lat=ORIGIN_LAT,
        origin_lng=ORIGIN_LNG,
        origin_name="San Francisco Ferry Building",
        candidates=MOCK_PLACES,
        total_hours=total_hours,
        user_vibe=vibe,
        cuisine_preference="Seafood",
        travel_mode="DRIVE",
        start_time_clock="09:30 AM"
    )

    print(f"\nStart Location: {plan.start_location['name']}")
    print(f"Start Clock:    {plan.start_clock}")
    print(f"End Clock:      {plan.end_clock}")
    print(f"Total Span:     {plan.total_trip_mins} mins ({plan.total_trip_hours} hours)")
    print(f"Total Dwell:    {plan.total_dwell_mins} mins")
    print(f"Total Travel:   {plan.total_travel_mins} mins")
    print(f"Total Dist:     {plan.total_distance_km} km")
    print(f"Slack Left:     {plan.slack_remaining_mins} mins")

    print("\n--- TIMETABLE ---")
    header = f"{'Stop':<5} | {'Venue Name':<28} | {'Arrival':<10} | {'Dwell':<8} | {'Departure':<10} | {'Transit From Prev'}"
    print(header)
    print("-" * 90)

    for s in plan.stops:
        transit_str = f"{s.transit_from_prev_mins}m ({s.transit_from_prev_km}km)"
        print(f"{s.stop_index:<5} | {s.name[:28]:<28} | {s.arrival_clock:<10} | {s.duration_mins:>2} mins  | {s.departure_clock:<10} | {transit_str}")

    ret = plan.return_leg
    print(f"Return| {ret['destination'][:28]:<28} | {ret['final_return_clock']:<10} | --       | --         | {ret['duration_mins']}m ({ret['distance_km']}km)")

    # Assertions
    # 1. Total span must not exceed budget of 240 mins
    assert plan.total_trip_mins <= int(total_hours * 60), f"Error: Total trip {plan.total_trip_mins} exceeded budget!"
    print("\n[PASS] Total trip duration is within user budget.")

    # 2. Number of stops >= 2 and <= 5
    assert 2 <= len(plan.stops) <= 5, f"Unexpected stop count: {len(plan.stops)}"
    print(f"[PASS] Stop count ({len(plan.stops)}) satisfies pacing criteria.")

    # 3. Time elapsed sequence is strictly increasing (interleaved arrival and departure)
    rel_times = []
    for s in plan.stops:
        rel_times.append(s.arrival_rel_mins)
        rel_times.append(s.departure_rel_mins)
    assert all(rel_times[i] <= rel_times[i+1] for i in range(len(rel_times)-1))
    print("[PASS] Chronological timeline is strictly monotonic.")

    return plan


def test_agent_enrichment():
    print("\n" + "=" * 80)
    print("TEST: AI AGENT CONCIERGE WORKFLOW")
    print("=" * 80)

    agent = RoamAroundAgent()
    result = agent.plan_itinerary(
        origin_lat=ORIGIN_LAT,
        origin_lng=ORIGIN_LNG,
        origin_name="San Francisco Ferry Building",
        candidates=MOCK_PLACES,
        total_hours=4.0,
        user_vibe="Relaxed waterfront walk and seafood",
        cuisine_preference="Seafood",
        price_level="$$",
        travel_mode="DRIVE",
        start_time_clock="09:30 AM"
    )

    print(f"Curator Model: {result['curator_model']}")
    print(f"Narrative:     {result['narrative']}")
    print("\nStops with Enriched AI Rationales:")
    for p in result['optimized_places']:
        print(f"  [{p['arrival_time']} - {p['departure_time']}] {p['name']} ({p['category']})")
        print(f"    AI Rationale: {p['ai_reasoning']}")
        print(f"    Time Reason:  {p['time_estimate_reason']}")

    assert result["status"] == "success"
    assert len(result["optimized_places"]) >= 2
    assert "narrative" in result
    print("\n[PASS] Agent planned and enriched itinerary successfully.")


if __name__ == "__main__":
    test_optimizer_direct()
    test_agent_enrichment()
    print("\n" + "=" * 80)
    print("ALL OPTIMIZER & AGENT TESTS PASSED.")
    print("=" * 80)
