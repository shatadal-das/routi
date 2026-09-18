"""
End-to-End Integration Flow Verification Suite for RoamAround.

Tests all 8 core integration cases specified:
CASE 1: 4 hours, Nature + Food
CASE 2: 2 hours, Nature
CASE 3: 6 hours, Food + sightseeing
CASE 4: Very short available time
CASE 5: No matching places
CASE 6: AI service unavailable (deterministic fallback verification)
CASE 7: Routing service unavailable (direct sequencing & URL fallback)
CASE 8: User modifies an existing itinerary via Agent Chat
"""

import sys
import os
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi import HTTPException
from main import app, RouteRequest, process_trip_planning, agent_chat, AgentChatRequest, roam_agent
from services.test_scorer import MOCK_PLACES, ORIGIN_LAT, ORIGIN_LNG


class TestIntegrationFlow(unittest.TestCase):

    def test_case_1_four_hours_nature_and_food(self):
        print("\n[RUNNING] CASE 1: 4 hours, Nature + Food")
        req = RouteRequest(
            start_location={"lat": ORIGIN_LAT, "lng": ORIGIN_LNG, "address": "San Francisco Ferry Building"},
            available_time_minutes=240,
            transport_mode="DRIVE",
            interests=["nature", "food", "cafe"]
        )
        res = process_trip_planning(req)
        self.assertTrue(res["success"])
        trip = res["trip"]
        self.assertTrue(trip["return_to_start"], "Loop invariant violated")
        self.assertLessEqual(trip["total_duration_minutes"], 240, "Time budget exceeded")
        self.assertGreaterEqual(len(trip["stops"]), 1, "Expected at least 1 stop")
        
        # Verify loop coords: START -> ... -> START
        self.assertEqual(trip["route"][0]["lat"], ORIGIN_LAT)
        self.assertEqual(trip["route"][-1]["lat"], ORIGIN_LAT)
        print(f"  [PASS] Case 1 passed: {len(trip['stops'])} stops, duration {trip['total_duration_minutes']}m <= 240m")

    def test_case_2_two_hours_nature(self):
        print("\n[RUNNING] CASE 2: 2 hours, Nature")
        req = RouteRequest(
            start_lat=ORIGIN_LAT,
            start_lng=ORIGIN_LNG,
            address="San Francisco Ferry Building",
            time_hours=2.0,
            interests=["nature", "park"]
        )
        res = process_trip_planning(req)
        self.assertTrue(res["success"])
        trip = res["trip"]
        self.assertTrue(trip["return_to_start"])
        self.assertLessEqual(trip["total_duration_minutes"], 120)
        print(f"  [PASS] Case 2 passed: {len(trip['stops'])} stops, duration {trip['total_duration_minutes']}m <= 120m")

    def test_case_3_six_hours_food_and_sightseeing(self):
        print("\n[RUNNING] CASE 3: 6 hours, Food + sightseeing")
        req = RouteRequest(
            start_location={"lat": ORIGIN_LAT, "lng": ORIGIN_LNG, "address": "San Francisco Ferry Building"},
            available_time_minutes=360,
            transport_mode="DRIVE",
            interests=["dining", "sightseeing", "attraction"]
        )
        res = process_trip_planning(req)
        self.assertTrue(res["success"])
        trip = res["trip"]
        self.assertTrue(trip["return_to_start"])
        self.assertLessEqual(trip["total_duration_minutes"], 360)
        self.assertGreaterEqual(len(trip["stops"]), 2)
        print(f"  [PASS] Case 3 passed: {len(trip['stops'])} stops, duration {trip['total_duration_minutes']}m <= 360m")

    def test_case_4_very_short_available_time(self):
        print("\n[RUNNING] CASE 4: Very short available time (< 45 mins)")
        req = RouteRequest(
            start_lat=ORIGIN_LAT,
            start_lng=ORIGIN_LNG,
            address="San Francisco Ferry Building",
            available_time_minutes=30
        )
        with self.assertRaises(HTTPException) as cm:
            process_trip_planning(req)
        self.assertEqual(cm.exception.status_code, 400)
        self.assertIn("Time available is too short", cm.exception.detail)
        print(f"  [PASS] Case 4 passed: Correctly raised 400: '{cm.exception.detail}'")

    def test_case_5_no_matching_places(self):
        print("\n[RUNNING] CASE 5: No matching places in extreme location")
        # Middle of the Atlantic Ocean where no Google Places exist
        req = RouteRequest(
            start_lat=0.0,
            start_lng=0.0,
            address="Null Island Ocean",
            available_time_minutes=180
        )
        with self.assertRaises(HTTPException) as cm:
            process_trip_planning(req)
        self.assertEqual(cm.exception.status_code, 404)
        self.assertIn("No venues or attractions found", cm.exception.detail)
        print(f"  [PASS] Case 5 passed: Correctly returned 404: '{cm.exception.detail}'")

    def test_case_6_ai_service_unavailable(self):
        print("\n[RUNNING] CASE 6: AI service unavailable / fallback")
        # Set roam_agent.model to None to simulate AI unavailable/offline
        orig_model = roam_agent.model
        try:
            roam_agent.model = None
            req = RouteRequest(
                start_location={"lat": ORIGIN_LAT, "lng": ORIGIN_LNG, "address": "Ferry Building"},
                available_time_minutes=180,
                interests=["cafe", "park"]
            )
            res = process_trip_planning(req)
            self.assertTrue(res["success"])
            self.assertTrue(res["trip"]["return_to_start"])
            self.assertLessEqual(res["trip"]["total_duration_minutes"], 180)
            self.assertEqual(res["curator_model"], "algorithmic-optimizer")
            print("  [PASS] Case 6 passed: Deterministic optimizer successfully generated valid route when AI offline.")
        finally:
            roam_agent.model = orig_model

    def test_case_7_routing_service_unavailable(self):
        print("\n[RUNNING] CASE 7: Google Routes service unavailable")
        # Mock get_optimized_route to simulate Google Routes outage
        with patch("main.get_optimized_route") as mock_route:
            mock_route.side_effect = Exception("Google Routes API 503 Service Unavailable")
            
            req = RouteRequest(
                start_lat=ORIGIN_LAT,
                start_lng=ORIGIN_LNG,
                address="Ferry Building",
                available_time_minutes=180,
                interests=["park"]
            )
            res = process_trip_planning(req)
            self.assertTrue(res["success"])
            self.assertIn("google_maps_url", res)
            self.assertTrue(res["trip"]["return_to_start"])
            print("  [PASS] Case 7 passed: Fell back to direct sequence and universal directions URL cleanly.")

    def test_case_8_user_modifies_itinerary(self):
        print("\n[RUNNING] CASE 8: User modifies an existing itinerary via Agent Chat")
        orig_model = roam_agent.model
        try:
            roam_agent.model = None
            # Generate initial itinerary
            req = RouteRequest(
                start_location={"lat": ORIGIN_LAT, "lng": ORIGIN_LNG, "address": "Ferry Building"},
                available_time_minutes=240,
                interests=["nature", "food"]
            )
            base_plan = process_trip_planning(req)
            
            # User requests conversational modification: "Remove the restaurant"
            chat_req = AgentChatRequest(
                message="Remove the restaurant.",
                current_itinerary=base_plan
            )
            chat_res = agent_chat(chat_req)
            self.assertEqual(chat_res["status"], "success")
            self.assertIn("route_result", chat_res)
            
            updated_trip = chat_res["route_result"]
            # Assert no restaurant remains in stops
            cats = [s.get("category", "") for s in updated_trip["optimized_places"]]
            self.assertNotIn("restaurant", cats)
            self.assertEqual(chat_res.get("modification_applied"), "Removed restaurant")
            print(f"  [PASS] Case 8 passed: Action '{chat_res.get('modification_applied')}' executed, updated route returned.")
        finally:
            roam_agent.model = orig_model


if __name__ == "__main__":
    unittest.main()
