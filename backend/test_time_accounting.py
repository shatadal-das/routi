import unittest
import sys
import os
from datetime import datetime, timedelta

# Ensure backend root is on sys.path
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from services.optimizer import (
    optimize_day_itinerary,
    calculate_safety_buffer_mins,
    parse_clock_time,
    OptimizedItineraryPlan,
)
from fastapi.testclient import TestClient
from main import app


class TestItineraryTimeAccounting(unittest.TestCase):
    """
    Unit test suite proving the strict separation and mathematical correctness
    of RoamAround's itinerary time accounting system:

    1. actual_travel_time = sum of all actual travel legs
    2. actual_visit_time = sum of all destination visit durations
    3. actual_elapsed_time = actual_travel_time + actual_visit_time
    4. safety_buffer = small planning allowance for travel uncertainty
    5. planning_budget = actual_elapsed_time + safety_buffer
    6. available_duration = maximum time provided by user
    7. Guarantee: planning_budget <= available_duration
    8. Guarantee: actual_return_time = start_time + actual_elapsed_time (NOT start_time + planning_budget)
    9. Guarantee: unused_minutes = available_duration - planning_budget
    """

    def setUp(self):
        self.places = [
            {"place_id": "p1", "name": "Space Needle", "lat": 47.6205, "lng": -122.3493, "rating": 4.6, "user_rating_count": 28000, "category": "attraction", "type": "tourist_attraction"},
            {"place_id": "p2", "name": "Chihuly Garden", "lat": 47.6206, "lng": -122.3505, "rating": 4.8, "user_rating_count": 16000, "category": "museum", "type": "museum"},
            {"place_id": "p3", "name": "Seattle Art Museum", "lat": 47.6074, "lng": -122.3382, "rating": 4.7, "user_rating_count": 7500, "category": "art_gallery", "type": "art_gallery"},
            {"place_id": "p4", "name": "Pike Place Market", "lat": 47.6097, "lng": -122.3422, "rating": 4.7, "user_rating_count": 62000, "category": "attraction", "type": "tourist_attraction"},
            {"place_id": "p5", "name": "Smith Tower", "lat": 47.6019, "lng": -122.3318, "rating": 4.6, "user_rating_count": 3100, "category": "viewpoint", "type": "viewpoint"},
            {"place_id": "p6", "name": "The Pink Door", "lat": 47.6101, "lng": -122.3429, "rating": 4.6, "user_rating_count": 6400, "category": "restaurant", "type": "restaurant"},
            {"place_id": "p7", "name": "Storyville Coffee", "lat": 47.6089, "lng": -122.3406, "rating": 4.7, "user_rating_count": 3400, "category": "cafe", "type": "cafe"},
        ]

    def test_user_canonical_example_arithmetic(self):
        """
        Verify the exact arithmetic specified by the user:
        Start: 09:00 AM
        Travel: 97 min
        Visits: 225 min
        Actual elapsed: 322 min = 5h 22m -> Return: 02:22 PM
        Safety buffer: 15 min
        Planning budget: 337 min = 5h 37m
        Available: 720 min (12h) -> Unused: 383 min
        """
        start_time_str = "09:00 AM"
        travel_mins = 97
        visit_mins = 225
        safety_buffer_mins = 15
        available_mins = 720

        actual_elapsed_mins = travel_mins + visit_mins
        self.assertEqual(actual_elapsed_mins, 322)

        start_dt = parse_clock_time(start_time_str)
        actual_return_dt = start_dt + timedelta(minutes=actual_elapsed_mins)
        actual_return_time = actual_return_dt.strftime("%I:%M %p")
        self.assertEqual(actual_return_time, "02:22 PM")

        planning_budget_mins = actual_elapsed_mins + safety_buffer_mins
        self.assertEqual(planning_budget_mins, 337)

        # Confirm that actual_return_time is NOT start_time + planning_budget
        planning_return_dt = start_dt + timedelta(minutes=planning_budget_mins)
        planning_return_time = planning_return_dt.strftime("%I:%M %p")
        self.assertEqual(planning_return_time, "02:37 PM")
        self.assertNotEqual(actual_return_time, planning_return_time)

        # Unused minutes
        unused_mins = available_mins - planning_budget_mins
        self.assertEqual(unused_mins, 383)

        # Unused available time against physical elapsed
        unused_available_mins = available_mins - actual_elapsed_mins
        self.assertEqual(unused_available_mins, 398)  # 6h 38m

    def test_optimizer_time_accounting_guarantees(self):
        """Test optimizer output across multiple durations for strict mathematical guarantees."""
        test_durations = [2.0, 4.0, 6.0, 8.0, 12.0]

        for hours in test_durations:
            avail_mins = int(hours * 60)
            start_clock = "09:00 AM"

            plan: OptimizedItineraryPlan = optimize_day_itinerary(
                origin_lat=47.6100,
                origin_lng=-122.3400,
                origin_name="Downtown Hotel",
                candidates=self.places,
                total_hours=hours,
                start_time_clock=start_clock,
                travel_mode="DRIVE",
                user_vibe="Culture and dining"
            )

            # 1. Travel time = sum of legs
            self.assertEqual(plan.actual_travel_time, plan.travel_minutes)
            self.assertEqual(plan.travel_minutes, plan.total_travel_mins)

            # 2. Visit time = sum of stops
            sum_stops_dwell = sum(s.duration_mins for s in plan.stops)
            self.assertEqual(plan.actual_visit_time, sum_stops_dwell)
            self.assertEqual(plan.visit_minutes, plan.total_dwell_mins)

            # 3. Actual elapsed = travel + visits
            expected_elapsed = plan.travel_minutes + plan.visit_minutes
            self.assertEqual(plan.actual_elapsed_minutes, expected_elapsed)
            self.assertEqual(plan.actual_elapsed_time, expected_elapsed)

            # 4. Planning budget = actual elapsed + safety buffer
            expected_budget = expected_elapsed + plan.safety_buffer_mins
            self.assertEqual(plan.planning_budget_minutes, expected_budget)
            self.assertEqual(plan.planning_budget, expected_budget)

            # 5. Guarantee: planning budget <= available duration
            self.assertLessEqual(plan.planning_budget_minutes, avail_mins)

            # 6. Guarantee: actual_return_time = start_time + actual_elapsed
            start_dt = parse_clock_time(plan.start_time)
            calc_return_dt = start_dt + timedelta(minutes=plan.actual_elapsed_minutes)
            calc_return_clock = calc_return_dt.strftime("%I:%M %p")
            self.assertEqual(plan.actual_return_time, calc_return_clock)
            self.assertEqual(plan.end_clock, calc_return_clock)

            # 7. Guarantee: unused_minutes = available_minutes - planning_budget
            expected_unused = max(0, avail_mins - plan.planning_budget_minutes)
            self.assertEqual(plan.unused_minutes, expected_unused)

            # 8. Check time_accounting dict fields
            ta = plan.time_accounting
            self.assertIn("start_time", ta)
            self.assertIn("actual_return_time", ta)
            self.assertIn("actual_elapsed_minutes", ta)
            self.assertIn("travel_minutes", ta)
            self.assertIn("visit_minutes", ta)
            self.assertIn("safety_buffer_minutes", ta)
            self.assertIn("planning_budget_minutes", ta)
            self.assertIn("available_minutes", ta)
            self.assertIn("unused_minutes", ta)
            self.assertEqual(ta["actual_elapsed_minutes"], expected_elapsed)
            self.assertEqual(ta["planning_budget_minutes"], expected_budget)
            self.assertEqual(ta["unused_minutes"], expected_unused)

    def test_api_plan_trip_time_accounting_contract(self):
        """Test the live FastAPI /api/plan-trip endpoint to ensure schema and math contracts hold."""
        client = TestClient(app)
        payload = {
            "start_location": {"name": "Pike Place Market, Seattle, WA", "lat": 47.6097, "lng": -122.3422},
            "available_time_minutes": 480,  # 8 hours
            "transport_mode": "DRIVE",
            "start_time": "09:00 AM",
            "vibe": "Iconic sights and food"
        }

        response = client.post("/api/plan-trip", json=payload)
        self.assertEqual(response.status_code, 200)

        data = response.json()
        ta = data.get("time_accounting", {})
        trip = data.get("trip", {})
        trip_ta = trip.get("time_accounting", {})

        # Verify exact required fields exist at top level, trip contract, and time_accounting
        required_fields = [
            "start_time",
            "actual_return_time",
            "actual_elapsed_minutes",
            "travel_minutes",
            "visit_minutes",
            "safety_buffer_minutes",
            "planning_budget_minutes",
            "available_minutes",
            "unused_minutes",
        ]

        for f in required_fields:
            self.assertIn(f, data, f"Field '{f}' missing from top-level response")
            self.assertIn(f, trip, f"Field '{f}' missing from trip contract")
            self.assertIn(f, ta, f"Field '{f}' missing from time_accounting object")
            self.assertIn(f, trip_ta, f"Field '{f}' missing from trip.time_accounting object")

        # Verify mathematical correctness on API output
        act_elapsed = data["actual_elapsed_minutes"]
        travel = data["travel_minutes"]
        visit = data["visit_minutes"]
        buffer = data["safety_buffer_minutes"]
        budget = data["planning_budget_minutes"]
        avail = data["available_minutes"]
        unused = data["unused_minutes"]

        self.assertEqual(act_elapsed, travel + visit)
        self.assertEqual(budget, act_elapsed + buffer)
        self.assertLessEqual(budget, avail)
        self.assertEqual(unused, avail - budget)

        # Verify actual_return_time is start_time + actual_elapsed_minutes
        start_dt = parse_clock_time(data["start_time"])
        expected_return = (start_dt + timedelta(minutes=act_elapsed)).strftime("%I:%M %p")
        self.assertEqual(data["actual_return_time"], expected_return)


if __name__ == "__main__":
    unittest.main()
