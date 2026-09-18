"""
Test the /api/agent/chat FastAPI endpoint directly.
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from main import app, AgentChatRequest, agent_chat
from services.test_agent_modifications import build_baseline_itinerary

def test_endpoint():
    print("Testing /api/agent/chat endpoint...")
    base = build_baseline_itinerary()
    req = AgentChatRequest(
        message="Remove the restaurant.",
        current_itinerary=base
    )
    res = agent_chat(req)
    assert res["status"] == "success"
    cats = [s["category"] for s in res["itinerary"]["ordered_destinations"]]
    assert "restaurant" not in cats
    print(f"Endpoint returned success! Message: {res['message']}, Action: {res['modification_applied']}")
    print("ALL ENDPOINT CHECKS PASSED.")

if __name__ == "__main__":
    test_endpoint()
