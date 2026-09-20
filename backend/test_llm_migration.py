"""
Comprehensive test suite for OpenAI / Bedrock LLM migration.
"""

import os
import json
import unittest
from unittest.mock import MagicMock

from services.llm_client import (
    get_openai_client,
    extract_response_text,
    extract_json_from_text,
    call_llm,
    call_llm_json,
    DEFAULT_MODEL,
    DEFAULT_SERVICE_TIER
)
from services.agent import RoamAroundAgent
from services.ai_curator import curate_itinerary
from services.itinerary_generator import generate_user_friendly_itinerary


class TestLLMMigration(unittest.TestCase):

    def test_default_model_and_tier(self):
        self.assertEqual(DEFAULT_MODEL, "google.gemma-3-27b-it")
        self.assertEqual(DEFAULT_SERVICE_TIER, "flex")

    def test_json_extraction_clean(self):
        raw = '{"status": "ok", "message": "hello"}'
        parsed = extract_json_from_text(raw)
        self.assertEqual(parsed.get("status"), "ok")

    def test_json_extraction_markdown_codeblock(self):
        raw = '```json\n{"status": "ok", "count": 42}\n```'
        parsed = extract_json_from_text(raw)
        self.assertEqual(parsed.get("count"), 42)

    def test_json_extraction_surrounding_text(self):
        raw = 'Here is the JSON result:\n```json\n[{"place_id": "p1", "duration_mins": 60}]\n```\nHope that helps!'
        parsed = extract_json_from_text(raw)
        self.assertIsInstance(parsed, list)
        self.assertEqual(parsed[0]["place_id"], "p1")

    def test_extract_response_text_chat_completions(self):
        mock_msg = MagicMock()
        mock_msg.content = "Hello from Bedrock Chat API"
        mock_choice = MagicMock()
        mock_choice.message = mock_msg
        mock_resp = MagicMock()
        mock_resp.choices = [mock_choice]
        mock_resp.output_text = None
        mock_resp.output = None

        text = extract_response_text(mock_resp)
        self.assertEqual(text, "Hello from Bedrock Chat API")

    def test_extract_response_text_responses_api(self):
        mock_resp = MagicMock(spec=["output_text"])
        mock_resp.output_text = "Hello from Bedrock Gemma 3!"
        text = extract_response_text(mock_resp)
        self.assertEqual(text, "Hello from Bedrock Gemma 3!")

    def test_call_llm_chat_completions_with_flex_tier(self):
        mock_client = MagicMock()
        mock_msg = MagicMock()
        mock_msg.content = '{"narrative": "A wonderful day in Mumbai"}'
        mock_choice = MagicMock()
        mock_choice.message = mock_msg
        mock_resp = MagicMock()
        mock_resp.choices = [mock_choice]
        mock_client.chat.completions.create.return_value = mock_resp

        result = call_llm(
            prompt="Plan a trip in Mumbai",
            model="google.gemma-3-27b-it",
            client=mock_client
        )
        self.assertEqual(result, '{"narrative": "A wonderful day in Mumbai"}')

        mock_client.chat.completions.create.assert_called_once_with(
            model="google.gemma-3-27b-it",
            messages=[{"role": "user", "content": "Plan a trip in Mumbai"}],
            service_tier="flex"
        )

    def test_curate_itinerary(self):
        places = [
            {"place_id": "test_1", "name": "Coit Tower", "type": "tourist_attraction", "rating": 4.6},
            {"place_id": "test_2", "name": "Boudin Bakery", "type": "restaurant", "rating": 4.5}
        ]
        curated = curate_itinerary(places_list=places, time_hours=3.0)
        self.assertTrue(len(curated) > 0)
        self.assertIn("place_id", curated[0])
        self.assertIn("duration_mins", curated[0])

    def test_agent_plan_itinerary(self):
        agent = RoamAroundAgent(model_name="google.gemma-3-27b-it")
        self.assertEqual(agent.model_name, "google.gemma-3-27b-it")

        candidates = [
            {"place_id": "p1", "name": "SF Ferry Building", "lat": 37.7955, "lng": -122.3937, "rating": 4.7, "user_ratings_total": 500, "types": ["point_of_interest"]},
            {"place_id": "p2", "name": "Coit Tower", "lat": 37.8024, "lng": -122.4058, "rating": 4.6, "user_ratings_total": 800, "types": ["tourist_attraction"]}
        ]
        result = agent.plan_itinerary(
            origin_lat=37.7955,
            origin_lng=-122.3937,
            origin_name="Ferry Building",
            candidates=candidates,
            total_hours=3.0
        )
        self.assertEqual(result["status"], "success")
        self.assertIn("user_itinerary", result)
        self.assertIn("narrative", result)


if __name__ == "__main__":
    unittest.main()
