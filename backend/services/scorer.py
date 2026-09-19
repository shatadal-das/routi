"""
RoamAround / Routi - Place Scoring & Ranking Module

This module provides multi-criteria scoring for candidate destinations
prior to route optimization. It evaluates venues across 6 distinct dimensions:
1. Interest / Vibe Match Score
2. Rating Quality Score (Bayesian smoothed)
3. Popularity & Review Confidence Score
4. Distance & Proximity Score (inverse of distance penalty)
5. Hidden Gem Score
6. Category Diversity Contribution

All configuration weights, thresholds, and Bayesian priors are centralized
in the ScoringConfig dataclass.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Set, Tuple
import math
import re

from services.taxonomy import normalize_category


@dataclass
class ScoringConfig:
    """
    Centralized configuration for scoring weights, Bayesian priors,
    and threshold parameters. Keeps all 'magic numbers' in one place.
    """
    # --- Component Weights (Sum to 1.0) ---
    weight_interest: float = 0.30      # Semantic relevance to user prompt/vibe
    weight_quality: float = 0.25       # Bayesian smoothed rating
    weight_popularity: float = 0.15    # Review volume confidence
    weight_proximity: float = 0.15     # Proximity to origin/anchor
    weight_hidden_gem: float = 0.15    # Under-the-radar high quality reward

    # --- Bayesian Rating Smoothing Priors ---
    # Shrinks low-sample ratings toward global expectation so 5.0 with 2 reviews doesn't dominate
    prior_rating_mean: float = 4.0     # Baseline expected rating for any venue
    prior_confidence_m: float = 30.0   # Weight given to prior (in units of reviews)

    # --- Popularity & Review Confidence ---
    # Log-scaled: venues with >= saturated_reviews reach 100% confidence
    saturated_reviews: int = 1500

    # --- Proximity & Distance Parameters ---
    # Ideal max radius in km before proximity score drops aggressively
    ideal_max_distance_km: float = 5.0
    distance_decay_power: float = 1.4

    # --- Hidden Gem Thresholds ---
    # High rating (>= 4.4) with moderate, local review counts (30 to 600 reviews)
    hidden_gem_min_rating: float = 4.4
    hidden_gem_min_reviews: int = 30
    hidden_gem_max_reviews: int = 600
    hidden_gem_sweet_spot_reviews: int = 180

    # --- Category Diversity Decay ---
    # Exponential discount applied when category is already selected in route
    category_decay_factor: float = 0.30


@dataclass
class PlaceScoreBreakdown:
    """
    Strongly typed breakdown of all sub-scores for a single venue.
    Provides complete transparency and explainability for AI rationale.
    """
    place_id: str
    name: str
    category: str
    interest_match_score: float         # 0.0 to 100.0
    rating_quality_score: float         # 0.0 to 100.0 (Bayesian)
    popularity_confidence_score: float  # 0.0 to 100.0
    proximity_score: float              # 0.0 to 100.0 (100 = adjacent, 0 = distant)
    distance_penalty: float             # 0.0 to 100.0 (100 - proximity_score)
    hidden_gem_score: float             # 0.0 to 100.0
    diversity_multiplier: float         # 0.0 to 1.0 (decay based on existing categories)
    final_score: float                  # 0.0 to 100.0
    distance_km: float                  # Direct distance to origin
    explanation: str                    # Human/AI-readable rationale
    sub_scores: Dict[str, float] = field(default_factory=dict)


def safe_float(val: Any, default: float = 0.0) -> float:
    """Safely cast value to float, defaulting on None or malformed strings."""
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def safe_int(val: Any, default: int = 0) -> int:
    """Safely cast value to int, defaulting on None or malformed strings."""
    if val is None:
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def extract_place_coordinates(
    place: Dict[str, Any],
    default_lat: float = 0.0,
    default_lng: float = 0.0
) -> Tuple[float, float]:
    """
    Safely extract latitude and longitude from varied place dictionary formats:
    - {"lat": 40.7, "lng": -74.0}
    - {"location": {"latitude": 40.7, "longitude": -74.0}} or {"location": {"lat": 40.7, "lng": -74.0}}
    - {"coordinates": {"lat": 40.7, "lng": -74.0}}
    - string representations "40.7", "-74.0"
    - Handles None without throwing AttributeError
    """
    if not isinstance(place, dict):
        return default_lat, default_lng

    lat = place.get("lat")
    lng = place.get("lng")

    loc = place.get("location")
    if isinstance(loc, dict):
        if lat is None:
            lat = loc.get("latitude") if loc.get("latitude") is not None else loc.get("lat")
        if lng is None:
            lng = loc.get("longitude") if loc.get("longitude") is not None else loc.get("lng")

    coords = place.get("coordinates")
    if isinstance(coords, dict):
        if lat is None:
            lat = coords.get("lat") if coords.get("lat") is not None else coords.get("latitude")
        if lng is None:
            lng = coords.get("lng") if coords.get("lng") is not None else coords.get("longitude")

    f_lat = safe_float(lat, default_lat)
    f_lng = safe_float(lng, default_lng)
    return f_lat, f_lng


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great-circle distance between two points in kilometers
    using the Haversine formula with clamped math domain bounds.
    """
    R = 6371.0  # Earth's radius in kilometers
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2.0) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2.0) ** 2
    )
    a_clamped = max(0.0, min(1.0, a))
    c = 2.0 * math.atan2(math.sqrt(a_clamped), math.sqrt(max(0.0, 1.0 - a_clamped)))
    return round(R * c, 2)


def calculate_interest_match(
    place: Dict[str, Any],
    user_vibe: Optional[str] = None,
    cuisine_preference: Optional[str] = None
) -> tuple[float, str]:
    """
    Dimension 1: Interest & Vibe Match Score (0 to 100).
    Evaluates lexical and semantic tag alignment between user interests and venue attributes.
    """
    terms = set()
    if user_vibe:
        # Extract keywords of 3+ letters
        clean_vibe = re.findall(r'[a-zA-Z]{3,}', user_vibe.lower())
        terms.update(clean_vibe)
    if cuisine_preference:
        terms.update(re.findall(r'[a-zA-Z]{3,}', cuisine_preference.lower()))

    if not terms:
        return 70.0, "Neutral interest match (no specific vibe requested)."

    # Venue text corpus
    name_str = place.get("name", "").lower()
    types_list = [t.lower().replace("_", " ") for t in place.get("types", [])]
    category_str = place.get("type", "").lower()
    cuisine_str = place.get("cuisine", "").lower() if place.get("cuisine") else ""
    address_str = place.get("address", "").lower()

    venue_corpus = f"{name_str} {' '.join(types_list)} {category_str} {cuisine_str} {address_str}"

    matches = []
    # Synonym & category mapping helpers
    synonym_map = {
        "coffee": ["cafe", "bakery", "coffee", "roastery"],
        "food": ["restaurant", "cafe", "bakery", "food", "dining", "eatery", "bistro", "deli", "bar", "kitchen", "grill"],
        "view": ["viewpoint", "park", "tower", "overlook", "scenic", "bridge"],
        "scenic": ["park", "viewpoint", "waterfront", "promenade", "walk", "scenic"],
        "waterfront": ["pier", "wharf", "marina", "waterfront", "bay", "beach", "ferry"],
        "walk": ["park", "promenade", "trail", "bridge", "wharf", "pier", "walk"],
        "seafood": ["fish", "seafood", "oyster", "clam", "crab"],
        "art": ["art gallery", "museum", "sculpture", "cultural", "art"],
        "culture": ["museum", "gallery", "historic", "heritage", "monument", "culture"],
        "spicy": ["sichuan", "thai", "mexican", "indian", "spicy"],
        "nature": ["park", "garden", "trail", "botanical", "arboretum", "nature", "reserve"],
        "park": ["park", "garden", "trail", "nature", "reserve", "green", "arboretum", "botanical"],
        "hiking": ["trail", "park", "nature", "reserve", "mountain", "hike", "walk"]
    }

    raw_score = 0.0
    for term in terms:
        if term in venue_corpus:
            raw_score += 25.0
            matches.append(term)
        else:
            # Check synonyms
            synonyms = synonym_map.get(term, [])
            synonym_hit = any(syn in venue_corpus for syn in synonyms)
            if synonym_hit:
                raw_score += 18.0
                matches.append(f"{term}*")

    # Baseline score for discovery
    base_score = 40.0 if not matches else 55.0
    total_score = min(100.0, base_score + raw_score)

    if matches:
        matched_str = ", ".join(matches[:4])
        explanation = f"Matches user vibe keywords: {matched_str}."
    else:
        explanation = "General interest venue within trip area."

    return round(total_score, 1), explanation


def calculate_rating_quality(
    rating: float,
    review_count: int,
    config: ScoringConfig
) -> tuple[float, str]:
    """
    Dimension 2: Rating Quality Score (0 to 100) via Bayesian Smoothing.
    Dampens small-sample ratings (e.g. 5.0 with 2 reviews shrinks toward 4.0),
    rewarding venues with statistically robust evidence of satisfaction.
    """
    r = max(1.0, min(5.0, float(rating or 4.0)))
    n = max(0, int(review_count or 0))
    m = config.prior_confidence_m
    c = config.prior_rating_mean

    # Bayesian adjusted rating: (N*R + m*C) / (N + m)
    r_bayes = (n * r + m * c) / (n + m)

    # Scale from [3.0, 5.0] to [0, 100]
    scaled = ((r_bayes - 3.0) / 2.0) * 100.0
    score = max(0.0, min(100.0, scaled))

    explanation = (
        f"Bayesian rating {r_bayes:.2f} stars from raw {r:.1f} ({n} reviews smoothed with prior {c:.1f})."
    )
    return round(score, 1), explanation


def calculate_popularity_confidence(
    review_count: int,
    config: ScoringConfig
) -> tuple[float, str]:
    """
    Dimension 3: Popularity & Review Confidence Score (0 to 100).
    Uses a log curve so confidence grows quickly from 0 to 300 reviews
    and reaches saturation at saturated_reviews (default 1500).
    """
    n = max(0, int(review_count or 0))
    if n == 0:
        return 15.0, "Minimal review confidence (unverified volume)."

    log_n = math.log(1.0 + n)
    log_sat = math.log(1.0 + config.saturated_reviews)

    ratio = min(1.0, log_n / log_sat)
    score = ratio * 100.0

    if n >= config.saturated_reviews:
        exp = f"High review volume ({n}+ reviews) indicating established popularity."
    elif n >= 200:
        exp = f"Reliable review volume ({n} reviews)."
    else:
        exp = f"Modest review sample ({n} reviews)."

    return round(score, 1), exp


def calculate_proximity_score(
    distance_km: float,
    config: ScoringConfig
) -> tuple[float, float, str]:
    """
    Dimension 4: Proximity Score and Distance Penalty (0 to 100).
    Proximity Score: 100 = adjacent to starting depot, approaches 0 as distance grows.
    Distance Penalty: 100 - Proximity Score.
    """
    d = max(0.0, float(distance_km))
    max_d = config.ideal_max_distance_km

    if d <= 0.8:
        proximity_score = 100.0
    else:
        # Non-linear decay: penalty accelerates as distance exceeds ideal_max_distance_km
        normalized_dist = min(2.0, d / max_d)
        proximity_ratio = max(0.0, 1.0 - (normalized_dist ** config.distance_decay_power) * 0.75)
        proximity_score = max(0.0, min(100.0, proximity_ratio * 100.0))

    distance_penalty = round(100.0 - proximity_score, 1)
    proximity_score = round(proximity_score, 1)

    exp = f"{distance_km:.1f} km from departure point (proximity score {proximity_score}/100)."
    return proximity_score, distance_penalty, exp


def calculate_hidden_gem_score(
    rating: float,
    review_count: int,
    config: ScoringConfig
) -> tuple[float, str]:
    """
    Dimension 5: Hidden Gem Score (0 to 100).
    Identifies under-the-radar treasures: venues with stellar ratings (>= 4.4)
    and moderate review counts (30 to 600) rather than commercial tourist traps.
    """
    r = float(rating or 0.0)
    n = int(review_count or 0)

    # Must meet baseline criteria
    if (
        r < config.hidden_gem_min_rating
        or n < config.hidden_gem_min_reviews
        or n > config.hidden_gem_max_reviews
    ):
        if n > config.hidden_gem_max_reviews:
            return 0.0, "Mainstream/popular destination (not a hidden gem)."
        return 0.0, "Does not meet hidden-gem threshold."

    # Rating factor: 4.4 -> 0.0, 5.0 -> 1.0
    rating_factor = min(1.0, (r - config.hidden_gem_min_rating) / (5.0 - config.hidden_gem_min_rating))

    # Volume factor: centered around sweet spot (e.g. 180 reviews)
    sweet_spot = config.hidden_gem_sweet_spot_reviews
    dist_from_sweet = abs(n - sweet_spot)
    max_dist = max(sweet_spot - config.hidden_gem_min_reviews, config.hidden_gem_max_reviews - sweet_spot)
    volume_factor = max(0.2, 1.0 - (dist_from_sweet / max_dist) * 0.6)

    score = 100.0 * rating_factor * volume_factor
    score = max(0.0, min(100.0, score))

    exp = f"Authentic hidden gem candidate: Exceptional {r:.1f} stars with local volume ({n} reviews)."
    return round(score, 1), exp


def calculate_category_diversity(
    category: str,
    selected_categories: List[str],
    config: ScoringConfig
) -> tuple[float, str]:
    """
    Dimension 6: Category Diversity Contribution Multiplier (0.0 to 1.0).
    Applies diminishing returns if the category already appears in the itinerary.
    """
    cat = (category or "general").lower().strip()
    cat_norm = normalize_category(category) or cat
    match_count = sum(1 for c in selected_categories if (normalize_category(c) or (c or "").lower().strip()) == cat_norm)

    # Multiplier decays: 1.0 (0 prior), 0.3 (1 prior), 0.09 (2 prior)
    multiplier = config.category_decay_factor ** match_count

    if match_count == 0:
        exp = f"First venue for category '{cat}' (100% diversity contribution)."
    elif match_count == 1:
        exp = f"Second venue for category '{cat}' ({int(multiplier * 100)}% contribution due to saturation)."
    else:
        exp = f"Multiple venues already selected in category '{cat}' ({int(multiplier * 100)}% contribution)."

    return round(multiplier, 3), exp


def score_place(
    place: Dict[str, Any],
    origin_lat: float,
    origin_lng: float,
    user_vibe: Optional[str] = None,
    cuisine_preference: Optional[str] = None,
    selected_categories: Optional[List[str]] = None,
    config: Optional[ScoringConfig] = None
) -> PlaceScoreBreakdown:
    """
    Computes the complete multi-criteria score for a candidate venue.
    Combines all 6 dimensions into a normalized final score [0.0, 100.0]
    with full explainability breakdown.
    """
    cfg = config or ScoringConfig()
    selected_cats = selected_categories or []

    # Extract venue fields with safe defaults
    place_id = str(place.get("place_id") or place.get("id") or "unknown_id")
    name = str(place.get("name") or "Unnamed Venue")
    rating = safe_float(place.get("rating"), 4.0)

    # Handle review count: check user_rating_count, review_count, or infer heuristic default
    raw_rc = place.get("user_rating_count") or place.get("review_count") or place.get("userRatingCount")
    review_count = safe_int(raw_rc, 150)

    # Calculate distance to origin using safe coordinate extraction
    venue_lat, venue_lng = extract_place_coordinates(place, origin_lat, origin_lng)
    distance_km = haversine_distance_km(origin_lat, origin_lng, venue_lat, venue_lng)

    # Categorization
    category = place.get("category") or place.get("type") or "attraction"

    # --- Compute the 6 dimensions ---
    s_interest, exp_interest = calculate_interest_match(place, user_vibe, cuisine_preference)
    s_quality, exp_quality = calculate_rating_quality(rating, review_count, cfg)
    s_popularity, exp_popularity = calculate_popularity_confidence(review_count, cfg)
    s_proximity, s_dist_penalty, exp_proximity = calculate_proximity_score(distance_km, cfg)
    s_gem, exp_gem = calculate_hidden_gem_score(rating, review_count, cfg)
    diversity_mult, exp_diversity = calculate_category_diversity(category, selected_cats, cfg)

    # Weighted linear combination
    base_score = (
        cfg.weight_interest * s_interest
        + cfg.weight_quality * s_quality
        + cfg.weight_popularity * s_popularity
        + cfg.weight_proximity * s_proximity
        + cfg.weight_hidden_gem * s_gem
    )

    # Apply diversity decay multiplier
    final_score = round(max(0.0, min(100.0, base_score * diversity_mult)), 1)

    # Compile clear, natural language explanation
    highlights = []
    if s_gem >= 70.0:
        highlights.append(f"Hidden gem candidate ({rating} stars, {review_count} reviews)")
    elif s_quality >= 80.0:
        highlights.append(f"High-quality rated ({rating} stars)")

    if s_interest >= 75.0:
        highlights.append("Strong vibe match")

    if distance_km <= 1.5:
        highlights.append(f"Convenient distance ({distance_km} km)")
    elif distance_km > cfg.ideal_max_distance_km:
        highlights.append(f"Distant stop ({distance_km} km)")

    if diversity_mult < 1.0:
        highlights.append(f"Category diversity discount ({int(diversity_mult * 100)}%)")

    explanation_str = "; ".join(highlights) if highlights else "Balanced candidate venue."

    return PlaceScoreBreakdown(
        place_id=place_id,
        name=name,
        category=category,
        interest_match_score=s_interest,
        rating_quality_score=s_quality,
        popularity_confidence_score=s_popularity,
        proximity_score=s_proximity,
        distance_penalty=s_dist_penalty,
        hidden_gem_score=s_gem,
        diversity_multiplier=diversity_mult,
        final_score=final_score,
        distance_km=distance_km,
        explanation=explanation_str,
        sub_scores={
            "interest": s_interest,
            "quality": s_quality,
            "popularity": s_popularity,
            "proximity": s_proximity,
            "distance_penalty": s_dist_penalty,
            "hidden_gem": s_gem,
            "diversity_multiplier": diversity_mult
        }
    )


def score_and_rank_candidates(
    candidates: List[Dict[str, Any]],
    origin_lat: float,
    origin_lng: float,
    user_vibe: Optional[str] = None,
    cuisine_preference: Optional[str] = None,
    selected_categories: Optional[List[str]] = None,
    config: Optional[ScoringConfig] = None
) -> List[PlaceScoreBreakdown]:
    """
    Scores and ranks an entire collection of candidate places.
    Returns a sorted list in descending order of final score.
    """
    scored = [
        score_place(
            place=c,
            origin_lat=origin_lat,
            origin_lng=origin_lng,
            user_vibe=user_vibe,
            cuisine_preference=cuisine_preference,
            selected_categories=selected_categories,
            config=config
        )
        for c in candidates
    ]
    # Sort descending by final score
    scored.sort(key=lambda s: s.final_score, reverse=True)
    return scored
