"""
Test & Demonstration Suite for the Place Scoring Engine (RoamAround / Routi)

Demonstrates how the 6-dimensional scoring formula and Bayesian smoothing
operate on 8 diverse mock destinations under specific user constraints.
"""

import sys
import os

# Ensure backend root is on PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.scorer import (
    ScoringConfig,
    score_place,
    score_and_rank_candidates,
    haversine_distance_km
)


# Origin: San Francisco Ferry Building
ORIGIN_LAT = 37.7955
ORIGIN_LNG = -122.3937
USER_VIBE = "Relaxed waterfront walk and seafood, scenic bay views"
CUISINE = "Seafood"

MOCK_PLACES = [
    {
        "place_id": "mock_p1_pier7",
        "name": "Pier 7 Boardwalk",
        "lat": 37.7985,
        "lng": -122.3965,
        "rating": 4.8,
        "user_rating_count": 420,
        "types": ["tourist_attraction", "park", "promenade"],
        "type": "scenic_walk",
        "category": "viewpoint",
        "address": "Pier 7, San Francisco, CA"
    },
    {
        "place_id": "mock_p2_fogharbor",
        "name": "Fog Harbor Fish House",
        "lat": 37.8090,
        "lng": -122.4103,
        "rating": 4.7,
        "user_rating_count": 11400,
        "types": ["restaurant", "seafood", "food"],
        "type": "restaurant",
        "cuisine": "Seafood",
        "category": "restaurant",
        "address": "Pier 39, San Francisco, CA"
    },
    {
        "place_id": "mock_p3_hiddenvine",
        "name": "The Hidden Vine Lounge",
        "lat": 37.7972,
        "lng": -122.4021,
        "rating": 4.8,
        "user_rating_count": 180,
        "types": ["bar", "lounge", "food"],
        "type": "restaurant",
        "category": "nightlife",
        "address": "408 Merchant St, San Francisco, CA"
    },
    {
        "place_id": "mock_p4_coittower",
        "name": "Coit Tower",
        "lat": 37.8024,
        "lng": -122.4058,
        "rating": 4.6,
        "user_rating_count": 8200,
        "types": ["tourist_attraction", "point_of_interest", "monument"],
        "type": "attraction",
        "category": "viewpoint",
        "address": "1 Telegraph Hill Blvd, San Francisco, CA"
    },
    {
        "place_id": "mock_p5_bluebottle",
        "name": "Blue Bottle Coffee Pier 1",
        "lat": 37.7960,
        "lng": -122.3948,
        "rating": 4.5,
        "user_rating_count": 1850,
        "types": ["cafe", "bakery", "food"],
        "type": "restaurant",
        "category": "cafe",
        "address": "1 Ferry Building #7, San Francisco, CA"
    },
    {
        "place_id": "mock_p6_shady5star",
        "name": "Suspicious 5-Star Pop-Up",
        "lat": 37.7940,
        "lng": -122.3920,
        "rating": 5.0,
        "user_rating_count": 2,  # Low confidence outlier: Bayesian test
        "types": ["cafe", "food"],
        "type": "restaurant",
        "category": "cafe",
        "address": "Market St, San Francisco, CA"
    },
    {
        "place_id": "mock_p7_distant_legion",
        "name": "Legion of Honor",
        "lat": 37.7844,
        "lng": -122.5008,  # ~9.5 km away: Distance penalty test
        "rating": 4.8,
        "user_rating_count": 7100,
        "types": ["museum", "art_gallery", "tourist_attraction"],
        "type": "attraction",
        "category": "museum",
        "address": "100 34th Ave, San Francisco, CA"
    },
    {
        "place_id": "mock_p8_maritime",
        "name": "SF Maritime National Historical Park",
        "lat": 37.8062,
        "lng": -122.4227,
        "rating": 4.5,
        "user_rating_count": 1250,
        "types": ["park", "museum", "tourist_attraction"],
        "type": "attraction",
        "category": "museum",
        "address": "499 Jefferson St, San Francisco, CA"
    }
]


def run_tests():
    print("=" * 80)
    print("ROAMAROUND / ROUTI - PLACE SCORING ENGINE DEMONSTRATION")
    print(f"Origin: ({ORIGIN_LAT}, {ORIGIN_LNG})")
    print(f"User Vibe Request: '{USER_VIBE}'")
    print(f"Cuisine: '{CUISINE}'")
    print("=" * 80)

    config = ScoringConfig()

    # 1. Score all candidates with empty selection
    ranked_places = score_and_rank_candidates(
        candidates=MOCK_PLACES,
        origin_lat=ORIGIN_LAT,
        origin_lng=ORIGIN_LNG,
        user_vibe=USER_VIBE,
        cuisine_preference=CUISINE,
        selected_categories=[],
        config=config
    )

    print("\n--- TEST 1: INITIAL CANDIDATE RANKING ---")
    header = f"{'Rank':<5} | {'Place Name':<28} | {'Category':<11} | {'Dist':<7} | {'Rating':<6} | {'Reviews':<7} | {'Score':<6} | {'Explanation'}"
    print(header)
    print("-" * 125)

    for idx, sp in enumerate(ranked_places, start=1):
        raw_r = next(p["rating"] for p in MOCK_PLACES if p["place_id"] == sp.place_id)
        reviews = next(p["user_rating_count"] for p in MOCK_PLACES if p["place_id"] == sp.place_id)
        row = (
            f"{idx:<5} | {sp.name[:28]:<28} | {sp.category:<11} | {sp.distance_km:>4.1f}km | "
            f"{raw_r:>4.1f}* | {reviews:>7} | {sp.final_score:>5.1f} | {sp.explanation}"
        )
        print(row)

    # 2. Inspect dimensional sub-scores of key cases
    print("\n--- TEST 2: DIMENSIONAL BREAKDOWN OF KEY ARCHETYPES ---")
    spotlights = ["mock_p1_pier7", "mock_p6_shady5star", "mock_p7_distant_legion", "mock_p3_hiddenvine"]
    for pid in spotlights:
        sp = next(s for s in ranked_places if s.place_id == pid)
        print(f"\nPlace: {sp.name} ({sp.category}) - Final Score: {sp.final_score}/100")
        print(f"  - Interest Match:      {sp.interest_match_score:>5.1f} / 100 (Weight: {config.weight_interest})")
        print(f"  - Rating Quality:       {sp.rating_quality_score:>5.1f} / 100 (Weight: {config.weight_quality}) [Bayesian smoothed]")
        print(f"  - Popularity Conf.:     {sp.popularity_confidence_score:>5.1f} / 100 (Weight: {config.weight_popularity})")
        print(f"  - Proximity:            {sp.proximity_score:>5.1f} / 100 (Weight: {config.weight_proximity}) [Distance penalty: {sp.distance_penalty:.1f}]")
        print(f"  - Hidden Gem Reward:    {sp.hidden_gem_score:>5.1f} / 100 (Weight: {config.weight_hidden_gem})")
        print(f"  - Diversity Multiplier: {sp.diversity_multiplier:.2f}x")
        print(f"  -> Rationale: {sp.explanation}")

    # 3. Test Category Diversity Saturation
    print("\n--- TEST 3: DIVERSITY DECAY DEMONSTRATION ---")
    print("Suppose 'Blue Bottle Coffee Pier 1' (category: 'cafe') is already chosen as Stop 1.")
    print("Evaluating second cafe ('Suspicious 5-Star Pop-Up'):")

    scored_with_cafe = score_place(
        place=next(p for p in MOCK_PLACES if p["place_id"] == "mock_p6_shady5star"),
        origin_lat=ORIGIN_LAT,
        origin_lng=ORIGIN_LNG,
        user_vibe=USER_VIBE,
        cuisine_preference=CUISINE,
        selected_categories=["cafe"],  # 1 prior cafe selected
        config=config
    )
    unpenalized = next(s for s in ranked_places if s.place_id == "mock_p6_shady5star")
    print(f"  Score without prior cafe: {unpenalized.final_score} / 100")
    print(f"  Score with 1 prior cafe:   {scored_with_cafe.final_score} / 100 (Decay factor: {config.category_decay_factor})")
    print(f"  Explanation: {scored_with_cafe.explanation}")

    # 4. Verify Assertions
    print("\n--- TEST 4: SYSTEM INVARIANT VERIFICATION ---")
    # Invariant A: Bayesian smoothing dampens 5.0 star with 2 reviews below verified high-quality spot
    shady_score = next(s.final_score for s in ranked_places if s.place_id == "mock_p6_shady5star")
    pier7_score = next(s.final_score for s in ranked_places if s.place_id == "mock_p1_pier7")
    assert pier7_score > shady_score, "Error: Pier 7 should outrank 2-review 5.0 star place!"
    print("  [PASS] Bayesian smoothing correctly prevented 2-review outlier from dominating.")

    # Invariant B: Distance penalty pushes 9.5 km venue down despite 4.8 star rating
    legion_score = next(s.final_score for s in ranked_places if s.place_id == "mock_p7_distant_legion")
    fogharbor_score = next(s.final_score for s in ranked_places if s.place_id == "mock_p2_fogharbor")
    assert fogharbor_score > legion_score, "Error: Distant venue was not appropriately penalized!"
    print("  [PASS] Distance penalty correctly downweighted distant 9.5 km venue.")

    # Invariant C: Hidden gem venue receives non-zero hidden gem reward
    hiddenvine = next(s for s in ranked_places if s.place_id == "mock_p3_hiddenvine")
    assert hiddenvine.hidden_gem_score > 50.0, "Error: Hidden gem did not receive expected bonus!"
    print(f"  [PASS] Hidden gem bonus verified ({hiddenvine.hidden_gem_score:.1f} / 100).")

    # Invariant D: All final scores bounded within [0.0, 100.0]
    for s in ranked_places:
        assert 0.0 <= s.final_score <= 100.0, f"Error: Score {s.final_score} out of bounds for {s.name}!"
    print("  [PASS] All final scores strictly bounded within [0.0, 100.0].")

    print("\n" + "=" * 80)
    print("ALL TESTS PASSED SUCCESSFULLY.")
    print("=" * 80)


if __name__ == "__main__":
    run_tests()
