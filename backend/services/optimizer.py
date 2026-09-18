"""
RoamAround / Routi - Route Optimization & Scheduling Engine

Implements an algorithmic Orienteering Problem (OP) solver for round-trip day trips:
- Input: start_location, available_time_minutes, transportation_mode, user_interests, candidate_places, travel_matrix
- Output: ordered_itinerary, starting_location, selected_destinations, return_to_start,
          total_travel_time, total_visit_time, total_duration, total_distance, score, per-destination reasoning.

Hard Constraints:
1. Route starts at starting location.
2. Route ends at starting location (round-trip loop).
3. Total duration <= available time in minutes.
4. Return travel time is strictly reserved during candidate evaluation.
5. No duplicate places.
6. No unreachable destinations.

Soft Objectives:
1. Maximize user-interest relevance.
2. Prefer high-quality places (Bayesian smoothed).
3. Minimize unnecessary travel (value-to-detour ratio + 2-Opt local search).
4. Encourage category diversity (diminishing returns & quotas).
5. Reward authentic hidden gems.

Deterministic heuristic: Seeded Greedy Insertion + 2-Opt Tour Improvement.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import math

from services.scorer import (
    ScoringConfig,
    PlaceScoreBreakdown,
    score_place,
    score_and_rank_candidates,
    haversine_distance_km,
    calculate_category_diversity,
    safe_float,
    safe_int,
    extract_place_coordinates
)


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class ScheduledItineraryStop:
    """Represents a scheduled destination stop in the chronological itinerary."""
    stop_index: int
    place_id: str
    name: str
    category: str
    lat: float
    lng: float
    address: str
    rating: float
    review_count: int
    price_level: str
    duration_mins: int
    duration_hours: float
    time_estimate_reason: str
    ai_reasoning: str
    arrival_rel_mins: int
    departure_rel_mins: int
    arrival_clock: str          # e.g. "10:15 AM"
    departure_clock: str        # e.g. "11:30 AM"
    transit_from_prev_mins: int
    transit_from_prev_km: float
    score_breakdown: Optional[Dict[str, Any]] = None
    selection_reasons: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stop_index": self.stop_index,
            "place_id": self.place_id,
            "place": self.name,
            "name": self.name,
            "selection_reasons": self.selection_reasons,
            "category": self.category,
            "lat": self.lat,
            "lng": self.lng,
            "coordinates": {"lat": self.lat, "lng": self.lng},
            "address": self.address,
            "rating": self.rating,
            "review_count": self.review_count,
            "price_level": self.price_level,
            "duration_mins": self.duration_mins,
            "duration_hours": self.duration_hours,
            "time_estimate_reason": self.time_estimate_reason,
            "ai_reasoning": self.ai_reasoning,
            "arrival_time": self.arrival_clock,
            "departure_time": self.departure_clock,
            "arrival_rel_mins": self.arrival_rel_mins,
            "departure_rel_mins": self.departure_rel_mins,
            "transit_from_prev_mins": self.transit_from_prev_mins,
            "transit_from_prev_km": self.transit_from_prev_km,
            "score_breakdown": self.score_breakdown or {},
            "type": "restaurant" if self.category in ["restaurant", "cafe", "food"] else "attraction"
        }


@dataclass
class OptimizedItineraryPlan:
    """Complete result from the itinerary optimization engine."""
    start_location: Dict[str, Any]
    stops: List[ScheduledItineraryStop]
    total_trip_mins: int
    total_travel_mins: int
    total_dwell_mins: int
    total_distance_km: float
    total_trip_hours: float
    slack_remaining_mins: int
    start_clock: str
    end_clock: str
    return_leg: Dict[str, Any]
    legs_data: List[Dict[str, Any]]
    route_score: float = 0.0
    rejected_destinations: List[Dict[str, Any]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Transit & Dwell Estimation Helpers
# ---------------------------------------------------------------------------

def estimate_transit_time_minutes(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
    mode: str = "DRIVE",
    travel_matrix: Optional[Dict[Tuple[str, str], Dict[str, Any]]] = None,
    from_id: Optional[str] = None,
    to_id: Optional[str] = None
) -> Tuple[int, float]:
    """
    Estimate transit duration in minutes and distance in km.
    If travel_matrix contains (from_id, to_id), uses that; otherwise computes
    deterministic mode-specific speed with urban buffer.
    """
    if from_id and to_id and from_id == to_id:
        return 0, 0.0

    if travel_matrix and from_id and to_id:
        key = (str(from_id), str(to_id))
        if key in travel_matrix:
            entry = travel_matrix[key]
            dur = int(entry.get("duration_mins") or round(entry.get("duration_seconds", 0) / 60))
            dist = float(entry.get("distance_km") or (entry.get("distance_meters", 0) / 1000.0))
            return max(1, dur), round(dist, 2)

    dist_km = haversine_distance_km(lat1, lon1, lat2, lon2)
    if dist_km < 0.01:
        return 0, 0.0

    m = (mode or "DRIVE").upper()

    if m == "WALK":
        # Average walking speed ~4.5 km/h -> 13.3 mins/km + 1 min buffer
        duration_mins = int(round(dist_km * 13.3 + 1.0))
    elif m == "BICYCLE":
        # Average cycling speed ~14 km/h -> 4.3 mins/km + 1.5 min buffer
        duration_mins = int(round(dist_km * 4.3 + 1.5))
    else:
        # Default DRIVE: Urban city traffic factor (~22 km/h) -> 2.7 mins/km + 3 mins parking/buffer
        duration_mins = int(round(dist_km * 2.7 + 3.0))

    duration_mins = max(1, duration_mins)
    return duration_mins, dist_km


def determine_default_dwell_mins(place: Dict[str, Any]) -> int:
    """
    Determine a realistic venue dwell time based on category and venue types.
    Handles missing, malformed, or string values safely.
    """
    if not isinstance(place, dict):
        return 60

    if place.get("duration_mins") is not None:
        custom_dwell = safe_int(place.get("duration_mins"), 0)
        if custom_dwell > 0:
            return custom_dwell

    types_raw = place.get("types")
    types = [str(t).lower() for t in types_raw] if isinstance(types_raw, (list, tuple, set)) else []
    category = str(place.get("category") or place.get("type") or "").lower()
    name = str(place.get("name") or "").lower()

    if any(t in types for t in ["museum", "art_gallery"]) or category == "museum":
        return 90
    if any(t in types for t in ["bakery", "cafe"]) or "coffee" in name or category == "cafe":
        return 35
    if any(t in types for t in ["park", "garden"]) or category == "park":
        return 50
    if any(t in types for t in ["viewpoint", "monument", "historic"]) or category == "viewpoint":
        return 40
    if any(t in types for t in ["restaurant", "food"]) or category == "restaurant":
        return 75
    return 60


# ---------------------------------------------------------------------------
# 2-Opt Local Search Tour Optimization
# ---------------------------------------------------------------------------

def two_opt_optimize_loop(
    stops: List[Dict[str, Any]],
    origin_lat: float,
    origin_lng: float,
    mode: str = "DRIVE",
    travel_matrix: Optional[Dict[Tuple[str, str], Dict[str, Any]]] = None,
    origin_id: str = "origin"
) -> List[Dict[str, Any]]:
    """
    2-Opt local search improvement for the round-trip tour:
    Origin -> s_1 -> s_2 -> ... -> s_k -> Origin.
    Reverses sub-segments to remove crossed edges and minimize transit time.
    Deterministic execution.
    """
    if len(stops) <= 2:
        return stops

    def tour_transit_cost(tour: List[Dict[str, Any]]) -> float:
        if not tour:
            return 0.0
        cost = 0.0
        # Origin -> first stop
        cost += estimate_transit_time_minutes(
            origin_lat, origin_lng, tour[0]["lat"], tour[0]["lng"],
            mode, travel_matrix, origin_id, tour[0].get("place_id")
        )[0]
        # Intermediates
        for i in range(len(tour) - 1):
            cost += estimate_transit_time_minutes(
                tour[i]["lat"], tour[i]["lng"], tour[i+1]["lat"], tour[i+1]["lng"],
                mode, travel_matrix, tour[i].get("place_id"), tour[i+1].get("place_id")
            )[0]
        # Last stop -> Origin
        cost += estimate_transit_time_minutes(
            tour[-1]["lat"], tour[-1]["lng"], origin_lat, origin_lng,
            mode, travel_matrix, tour[-1].get("place_id"), origin_id
        )[0]
        return cost

    best_tour = list(stops)
    best_cost = tour_transit_cost(best_tour)
    improved = True
    iterations = 0

    while improved and iterations < 30:
        improved = False
        iterations += 1
        for i in range(len(best_tour) - 1):
            for j in range(i + 1, len(best_tour)):
                new_tour = best_tour[:i] + best_tour[i:j+1][::-1] + best_tour[j+1:]
                new_cost = tour_transit_cost(new_tour)
                if new_cost < best_cost - 0.5:
                    best_tour = new_tour
                    best_cost = new_cost
                    improved = True
                    break
            if improved:
                break

    return best_tour


# ---------------------------------------------------------------------------
# Explainability Reason Generators (Concise User-Facing Explanations)
# ---------------------------------------------------------------------------

def generate_selection_reasons(
    place: Dict[str, Any],
    score_breakdown: Optional[PlaceScoreBreakdown],
    transit_mins: int,
    user_interests: Optional[str],
    selected_categories: List[str]
) -> List[str]:
    """
    Generates concise user-facing explanations for why a destination was selected into the route.
    No raw floats or internal model formulas are exposed.
    """
    reasons = []
    cat = str(place.get("category") or place.get("type") or "attraction").lower()
    interests_str = (user_interests or "").lower()

    # 1. Preference match
    if interests_str:
        if any(term in interests_str for term in ["nature", "park", "green", "outdoor", "view", "scenic"]) and (
            cat in ["park", "viewpoint", "nature", "garden"] or any(t in cat for t in ["park", "scenic", "view", "nature"])
        ):
            reasons.append("Strong match for nature preference")
        elif any(term in interests_str for term in ["food", "dining", "restaurant", "seafood", "lunch", "dinner", "eat"]) and (
            cat in ["restaurant", "cafe", "food"] or "food" in cat
        ):
            reasons.append("Strong match for dining & food preference")
        elif any(term in interests_str for term in ["art", "culture", "museum", "history"]) and cat in ["museum", "art_gallery"]:
            reasons.append("Strong match for art & culture preference")
        elif any(term in interests_str for term in ["coffee", "cafe"]) and cat == "cafe":
            reasons.append("Strong match for cafe preference")
        elif score_breakdown:
            s_int = getattr(score_breakdown, "interest_match_score", None)
            if s_int is None:
                s_int = getattr(score_breakdown, "sub_scores", {}).get("interest", 0)
            if s_int >= 60:
                reasons.append(f"Strong match for {cat.replace('_', ' ')} preference")

    # 2. Quality
    rating = safe_float(place.get("rating"), 0.0)
    reviews = safe_int(place.get("review_count") or place.get("user_rating_count"), 0)
    if rating >= 4.5:
        reasons.append("High place quality score")
    elif reviews >= 1000:
        reasons.append("Popular local highlight")

    # 3. Travel time
    if transit_mins <= 12:
        reasons.append("Low additional travel time")
    elif transit_mins <= 20:
        reasons.append("Efficient route connection")

    # 4. Diversity
    if selected_categories.count(cat) <= 1:
        reasons.append("Adds category diversity")

    # 5. Hidden gem
    gem_score = 0.0
    if score_breakdown:
        gem_score = getattr(score_breakdown, "hidden_gem_score", None)
        if gem_score is None:
            gem_score = getattr(score_breakdown, "sub_scores", {}).get("hidden_gem", 0.0)
    if gem_score >= 60.0 and reviews < 800:
        reasons.append("Authentic local hidden gem")

    if len(reasons) < 2:
        reasons.append("Convenient detour along route")

    return list(dict.fromkeys(reasons))


def generate_rejection_reasons(
    cand: Dict[str, Any],
    score_breakdown: Optional[PlaceScoreBreakdown],
    tour: List[Dict[str, Any]],
    origin_lat: float,
    origin_lng: float,
    total_budget_mins: int,
    used_duration_mins: int,
    user_interests: Optional[str],
    selected_categories: List[str]
) -> List[str]:
    """
    Generates concise user-facing explanations for why a candidate was not selected into the route.
    Allowed categories:
    - Exceeds remaining time
    - Excessive travel time
    - Duplicate category
    - Poor preference match
    """
    reasons = []
    cat = str(cand.get("category") or cand.get("type") or "").lower()
    interests_str = (user_interests or "").lower()

    dwell = determine_default_dwell_mins(cand)
    rem_time = max(0, total_budget_mins - used_duration_mins)

    min_transit_to_cand = 999
    if tour:
        for p in tour:
            t, _ = estimate_transit_time_minutes(p["lat"], p["lng"], cand["lat"], cand["lng"])
            if t < min_transit_to_cand:
                min_transit_to_cand = t
    else:
        min_transit_to_cand, _ = estimate_transit_time_minutes(origin_lat, origin_lng, cand["lat"], cand["lng"])

    t_back, _ = estimate_transit_time_minutes(cand["lat"], cand["lng"], origin_lat, origin_lng)

    # 1. Exceeds remaining time
    if (min_transit_to_cand + dwell + t_back) > rem_time or (dwell + min_transit_to_cand) > rem_time or dwell > rem_time:
        reasons.append("Exceeds remaining time")

    # 2. Excessive travel time
    if min_transit_to_cand > 25 or t_back > 30 or (min_transit_to_cand + t_back) > 45:
        reasons.append("Excessive travel time")

    # 3. Duplicate category
    normalized_selected_cats = [str(c).lower() for c in selected_categories]
    if cat and (
        (cat in ["restaurant", "cafe", "food", "bakery"] and any(sc in ["restaurant", "cafe", "food", "bakery"] for sc in normalized_selected_cats))
        or normalized_selected_cats.count(cat) >= 2
        or (cat in normalized_selected_cats and total_budget_mins < 360 and cat in ["restaurant", "cafe"])
    ):
        reasons.append("Duplicate category")

    # 4. Poor preference match
    if interests_str:
        interest_score = 100.0
        if score_breakdown:
            if hasattr(score_breakdown, "interest_match_score") and score_breakdown.interest_match_score is not None:
                interest_score = float(score_breakdown.interest_match_score)
            elif "interest" in getattr(score_breakdown, "sub_scores", {}):
                interest_score = float(score_breakdown.sub_scores["interest"])
            elif "interest_match" in getattr(score_breakdown, "sub_scores", {}):
                interest_score = float(score_breakdown.sub_scores["interest_match"])

        if interest_score <= 50.0:
            reasons.append("Poor preference match")
        elif any(term in interests_str for term in ["nature", "park", "green", "outdoor", "scenic", "view"]) and cat in ["shopping", "mall", "store", "commercial", "casino", "nightclub"]:
            reasons.append("Poor preference match")
        elif any(term in interests_str for term in ["nature", "park", "green"]) and cat not in ["park", "nature", "viewpoint", "garden"] and not any(t in cat for t in ["park", "nature", "scenic"]):
            if "dining" not in interests_str and "food" not in interests_str and cat in ["restaurant", "shopping"]:
                reasons.append("Poor preference match")

    if not reasons:
        reasons.append("Exceeds remaining time")

    return list(dict.fromkeys(reasons))


# ---------------------------------------------------------------------------
# Primary Optimizer Engine
# ---------------------------------------------------------------------------

class RouteOptimizer:
    """
    Deterministic Route Optimization Engine using Place Scoring.
    Solves the Orienteering Problem with category constraints and returns to start.
    """

    def __init__(self, config: Optional[ScoringConfig] = None):
        self.config = config or ScoringConfig()

    def optimize(
        self,
        start_location: Dict[str, Any],
        available_time_minutes: int,
        transportation_mode: str = "DRIVE",
        user_interests: Optional[str] = None,
        cuisine_preference: Optional[str] = None,
        candidate_places: List[Dict[str, Any]] = None,
        travel_matrix: Optional[Dict[Tuple[str, str], Dict[str, Any]]] = None,
        start_time_clock: str = "09:30 AM",
        max_destinations: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Executes the optimization algorithm adhering to all hard constraints
        and soft objectives.
        """
        raw_candidates = candidate_places or []
        origin_lat, origin_lng = extract_place_coordinates(start_location, 0.0, 0.0)
        origin_name = str(start_location.get("name") or start_location.get("address") or "Starting Point")
        origin_id = str(start_location.get("place_id") or start_location.get("id") or "origin")
        mode = (transportation_mode or "DRIVE").upper()

        # Hard Constraint 3: Time limit
        total_budget_mins = safe_int(available_time_minutes, 0)
        if total_budget_mins <= 0:
            return self._build_empty_itinerary(
                start_location, origin_name, origin_lat, origin_lng,
                start_time_clock, 0, mode
            )

        # Reserve safety buffer scaled with trip duration
        if total_budget_mins <= 60:
            buffer_mins = 5
        elif total_budget_mins <= 120:
            buffer_mins = 10
        elif total_budget_mins <= 240:
            buffer_mins = 15
        elif total_budget_mins <= 420:
            buffer_mins = 25
        else:
            buffer_mins = 35
        buffer_mins = min(buffer_mins, max(0, int(total_budget_mins * 0.15)))
        usable_budget_mins = max(15, total_budget_mins - buffer_mins)

        # -------------------------------------------------------------------
        # Step 0: Deduplicate and normalize candidates (Hard Constraint 5)
        # -------------------------------------------------------------------
        unique_candidates: List[Dict[str, Any]] = []
        seen_place_ids = set()
        seen_geo_locations = set()

        for idx, c in enumerate(raw_candidates):
            if not isinstance(c, dict):
                continue
            c_lat, c_lng = extract_place_coordinates(c, origin_lat, origin_lng)
            raw_id = c.get("place_id") or c.get("id")
            c_pid = str(raw_id) if raw_id is not None else ""
            c_name = str(c.get("name") or "").strip().lower()

            # Deduplicate by place_id
            if c_pid and c_pid in seen_place_ids:
                continue

            # Deduplicate by physical coordinate (~10m precision)
            geo_key = (round(c_lat, 4), round(c_lng, 4))
            if geo_key in seen_geo_locations:
                continue

            if c_pid:
                seen_place_ids.add(c_pid)
            seen_geo_locations.add(geo_key)

            c_clean = dict(c)
            c_clean["place_id"] = c_pid or f"cand_{idx + 1}"
            c_clean["name"] = str(c.get("name") or "Local Venue")
            c_clean["lat"] = c_lat
            c_clean["lng"] = c_lng
            c_clean["category"] = str(c.get("category") or c.get("type") or "attraction")
            unique_candidates.append(c_clean)

        if not unique_candidates:
            return self._build_empty_itinerary(
                start_location, origin_name, origin_lat, origin_lng,
                start_time_clock, total_budget_mins, mode
            )

        # -------------------------------------------------------------------
        # Step 1: Pre-score candidate places using services.scorer
        # -------------------------------------------------------------------
        scored_breakdowns = score_and_rank_candidates(
            candidates=unique_candidates,
            origin_lat=origin_lat,
            origin_lng=origin_lng,
            user_vibe=user_interests,
            cuisine_preference=cuisine_preference,
            selected_categories=[],
            config=self.config
        )
        cand_map = {c["place_id"]: c for c in unique_candidates}

        # -------------------------------------------------------------------
        # Step 2: Hard Constraint 6 - Prune impossible / unreachable places
        # Round trip transit + realistic dwell must fit in total_budget_mins
        # -------------------------------------------------------------------
        reachable_candidates: List[PlaceScoreBreakdown] = []

        for bd in scored_breakdowns:
            raw = cand_map.get(bd.place_id)
            if not raw:
                continue
            p_lat = raw["lat"]
            p_lng = raw["lng"]
            dwell = determine_default_dwell_mins(raw)
            # Allow at most 25% dwell compression (minimum 20 mins)
            min_dwell = max(20, int(dwell * 0.75))

            t_out, _ = estimate_transit_time_minutes(
                origin_lat, origin_lng, p_lat, p_lng, mode, travel_matrix, origin_id, bd.place_id
            )
            t_back, _ = estimate_transit_time_minutes(
                p_lat, p_lng, origin_lat, origin_lng, mode, travel_matrix, bd.place_id, origin_id
            )

            # Strict feasibility test: round-trip travel + realistic visit must fit available time
            if (t_out + min_dwell + t_back) <= total_budget_mins:
                reachable_candidates.append(bd)

        if not reachable_candidates:
            # All candidate places exceed the available time limit or are unreachable
            rejected_list: List[Dict[str, Any]] = []
            for c in raw_candidates:
                cid = str(c.get("place_id") or c.get("id") or "")
                c_name = str(c.get("name") or "Candidate Venue")
                if any(r["place"] == c_name for r in rejected_list):
                    continue
                rej_reasons = generate_rejection_reasons(
                    cand=c,
                    score_breakdown=None,
                    tour=[],
                    origin_lat=origin_lat,
                    origin_lng=origin_lng,
                    total_budget_mins=total_budget_mins,
                    used_duration_mins=0,
                    user_interests=user_interests,
                    selected_categories=[]
                )
                rejected_list.append({
                    "place": c_name,
                    "place_id": cid,
                    "category": c.get("category") or "attraction",
                    "rejection_reasons": rej_reasons
                })
            return self._build_empty_itinerary(
                start_location, origin_name, origin_lat, origin_lng,
                start_time_clock, total_budget_mins, mode,
                rejected_destinations=rejected_list[:10]
            )

        # -------------------------------------------------------------------
        # Step 3: Seed with highest-utility reachable anchor
        # -------------------------------------------------------------------
        anchor_bd = reachable_candidates[0]
        raw_anchor = cand_map[anchor_bd.place_id]
        anchor_entry = dict(raw_anchor)

        t_out_anchor, _ = estimate_transit_time_minutes(
            origin_lat, origin_lng, raw_anchor["lat"], raw_anchor["lng"], mode, travel_matrix, origin_id, anchor_bd.place_id
        )
        t_back_anchor, _ = estimate_transit_time_minutes(
            raw_anchor["lat"], raw_anchor["lng"], origin_lat, origin_lng, mode, travel_matrix, anchor_bd.place_id, origin_id
        )
        def_dwell = determine_default_dwell_mins(raw_anchor)
        min_anchor_dwell = max(20, int(def_dwell * 0.75))
        max_possible_dwell = total_budget_mins - (t_out_anchor + t_back_anchor)
        anchor_dwell = max(min_anchor_dwell, min(def_dwell, max_possible_dwell))

        anchor_entry["dwell_mins"] = anchor_dwell
        anchor_entry["score_breakdown"] = anchor_bd

        tour: List[Dict[str, Any]] = [anchor_entry]
        selected_place_ids = {anchor_bd.place_id}
        selected_geo_locations = {(round(raw_anchor["lat"], 4), round(raw_anchor["lng"], 4))}
        selected_categories: List[str] = [anchor_entry["category"]]

        # -------------------------------------------------------------------
        # Loop Time Evaluator Helper
        # -------------------------------------------------------------------
        def calculate_loop_metrics(current_tour: List[Dict[str, Any]]) -> Tuple[int, int, int, float]:
            if not current_tour:
                return 0, 0, 0, 0.0

            dwell_total = sum(p.get("dwell_mins", 60) for p in current_tour)
            travel_total = 0
            dist_total_km = 0.0

            # Origin -> Stop 1
            t_first, d_first = estimate_transit_time_minutes(
                origin_lat, origin_lng, current_tour[0]["lat"], current_tour[0]["lng"],
                mode, travel_matrix, origin_id, current_tour[0].get("place_id")
            )
            travel_total += t_first
            dist_total_km += d_first

            # Intermediate legs
            for i in range(len(current_tour) - 1):
                t_leg, d_leg = estimate_transit_time_minutes(
                    current_tour[i]["lat"], current_tour[i]["lng"],
                    current_tour[i+1]["lat"], current_tour[i+1]["lng"],
                    mode, travel_matrix, current_tour[i].get("place_id"), current_tour[i+1].get("place_id")
                )
                travel_total += t_leg
                dist_total_km += d_leg

            # Last stop -> Origin (Hard Constraints 2 & 4: return time reserved)
            t_last, d_last = estimate_transit_time_minutes(
                current_tour[-1]["lat"], current_tour[-1]["lng"], origin_lat, origin_lng,
                mode, travel_matrix, current_tour[-1].get("place_id"), origin_id
            )
            travel_total += t_last
            dist_total_km += d_last

            total_span = dwell_total + travel_total
            return total_span, travel_total, dwell_total, round(dist_total_km, 2)

        # -------------------------------------------------------------------
        # Step 4: Iterative Seeded Greedy Insertion with Soft Diversity
        # -------------------------------------------------------------------
        if total_budget_mins < 90:
            max_stops = 1
        elif total_budget_mins < 180:
            max_stops = 2
        elif total_budget_mins < 300:
            max_stops = 3
        elif total_budget_mins < 450:
            max_stops = 4
        elif total_budget_mins < 600:
            max_stops = 5
        else:
            max_stops = 6

        if max_destinations is not None and max_destinations > 0:
            max_stops = min(max_stops, int(max_destinations))

        while len(tour) < max_stops:
            best_cand_entry = None
            best_insert_pos = -1
            best_efficiency = -1.0
            current_span, _, _, _ = calculate_loop_metrics(tour)

            for cand_bd in reachable_candidates:
                pid = cand_bd.place_id
                # Hard Constraint 5: Do not select duplicate places
                if pid in selected_place_ids:
                    continue

                raw_c = cand_map.get(pid)
                if not raw_c:
                    continue

                geo_key = (round(raw_c["lat"], 4), round(raw_c["lng"], 4))
                if geo_key in selected_geo_locations:
                    continue

                c_cat = raw_c["category"]

                # Pacing & Diversity Quotas
                if c_cat == "restaurant":
                    if total_budget_mins < 360 and selected_categories.count("restaurant") >= 1:
                        continue
                    elif selected_categories.count("restaurant") >= 2:
                        continue

                # Category saturation guard (at most 3 of the exact same category)
                if selected_categories.count(c_cat) >= 3:
                    continue

                div_mult, _ = calculate_category_diversity(c_cat, selected_categories, self.config)

                c_lat = raw_c["lat"]
                c_lng = raw_c["lng"]
                c_dwell = determine_default_dwell_mins(raw_c)

                # Test inserting at each edge k in tour (0 to len(tour))
                for k in range(len(tour) + 1):
                    trial_entry = dict(raw_c)
                    trial_entry["lat"] = c_lat
                    trial_entry["lng"] = c_lng
                    trial_entry["dwell_mins"] = c_dwell
                    trial_entry["score_breakdown"] = cand_bd

                    trial_tour = tour[:k] + [trial_entry] + tour[k:]
                    trial_span, _, _, _ = calculate_loop_metrics(trial_tour)
                    added_span = trial_span - current_span

                    # Hard Constraints 3 & 4: Total duration <= available time & return reserved
                    if trial_span <= usable_budget_mins and added_span > 0:
                        efficiency = (cand_bd.final_score * div_mult) / float(added_span)
                        if efficiency > best_efficiency:
                            best_efficiency = efficiency
                            best_cand_entry = trial_entry
                            best_insert_pos = k

            # If no candidate fit in usable_budget_mins, try within total_budget_mins before giving up
            if not best_cand_entry and current_span < total_budget_mins - 30:
                for cand_bd in reachable_candidates:
                    pid = cand_bd.place_id
                    if pid in selected_place_ids:
                        continue
                    raw_c = cand_map.get(pid)
                    if not raw_c:
                        continue
                    geo_key = (round(raw_c["lat"], 4), round(raw_c["lng"], 4))
                    if geo_key in selected_geo_locations:
                        continue
                    c_cat = raw_c["category"]
                    if c_cat == "restaurant" and selected_categories.count("restaurant") >= 1 and total_budget_mins < 360:
                        continue
                    if selected_categories.count(c_cat) >= 3:
                        continue

                    div_mult, _ = calculate_category_diversity(c_cat, selected_categories, self.config)
                    c_dwell = min(determine_default_dwell_mins(raw_c), total_budget_mins - current_span - 20)
                    if c_dwell < 20:
                        continue

                    for k in range(len(tour) + 1):
                        trial_entry = dict(raw_c)
                        trial_entry["lat"] = raw_c["lat"]
                        trial_entry["lng"] = raw_c["lng"]
                        trial_entry["dwell_mins"] = c_dwell
                        trial_entry["score_breakdown"] = cand_bd

                        trial_tour = tour[:k] + [trial_entry] + tour[k:]
                        trial_span, _, _, _ = calculate_loop_metrics(trial_tour)
                        added_span = trial_span - current_span

                        if trial_span <= total_budget_mins and added_span > 0:
                            efficiency = (cand_bd.final_score * div_mult) / float(added_span)
                            if efficiency > best_efficiency:
                                best_efficiency = efficiency
                                best_cand_entry = trial_entry
                                best_insert_pos = k

            if best_cand_entry and best_insert_pos >= 0:
                tour.insert(best_insert_pos, best_cand_entry)
                selected_place_ids.add(best_cand_entry["place_id"])
                selected_geo_locations.add((round(best_cand_entry["lat"], 4), round(best_cand_entry["lng"], 4)))
                selected_categories.append(best_cand_entry["category"])
            else:
                break

        # -------------------------------------------------------------------
        # Step 5: 2-Opt Tour Optimization
        # -------------------------------------------------------------------
        tour = two_opt_optimize_loop(tour, origin_lat, origin_lng, mode, travel_matrix, origin_id)

        # -------------------------------------------------------------------
        # Step 6: Meal Pacing Adjustment
        # -------------------------------------------------------------------
        if len(tour) >= 3 and any(p.get("category") == "restaurant" for p in tour):
            if tour[0].get("category") == "restaurant":
                rest_item = tour.pop(0)
                insert_target = min(len(tour), 2)
                tour.insert(insert_target, rest_item)
                tour = two_opt_optimize_loop(tour, origin_lat, origin_lng, mode, travel_matrix, origin_id)

        # -------------------------------------------------------------------
        # Step 7: Strict Invariant Enforcement (Hard Constraint 3 & 4)
        # Total duration MUST NOT exceed available time.
        # -------------------------------------------------------------------
        total_span, _, _, _ = calculate_loop_metrics(tour)

        # 1. Compress dwell times if slightly over budget
        if total_span > total_budget_mins:
            excess = total_span - total_budget_mins
            for p in tour:
                cur_d = p.get("dwell_mins", 60)
                # Allow at most 25% dwell compression (minimum 20 mins)
                min_viable_dwell = max(20, int(determine_default_dwell_mins(p) * 0.75))
                reducible = max(0, cur_d - min_viable_dwell)
                reduction = min(excess, reducible)
                p["dwell_mins"] = cur_d - reduction
                excess -= reduction
                if excess <= 0:
                    break
            total_span, _, _, _ = calculate_loop_metrics(tour)

        # 2. Prune lowest-utility stops if still over budget
        while tour and total_span > total_budget_mins:
            worst_idx = min(
                range(len(tour)),
                key=lambda i: tour[i].get("score_breakdown").final_score
                if isinstance(tour[i].get("score_breakdown"), PlaceScoreBreakdown) else 0.0
            )
            removed = tour.pop(worst_idx)
            selected_place_ids.discard(removed.get("place_id"))
            if tour:
                tour = two_opt_optimize_loop(tour, origin_lat, origin_lng, mode, travel_matrix, origin_id)
            total_span, _, _, _ = calculate_loop_metrics(tour)

        if not tour:
            rejected_list = []
            for c in raw_candidates:
                cid = str(c.get("place_id") or c.get("id") or "")
                c_name = str(c.get("name") or "Candidate Venue")
                if any(r["place"] == c_name for r in rejected_list):
                    continue
                rej_reasons = generate_rejection_reasons(
                    cand=c,
                    score_breakdown=None,
                    tour=[],
                    origin_lat=origin_lat,
                    origin_lng=origin_lng,
                    total_budget_mins=total_budget_mins,
                    used_duration_mins=0,
                    user_interests=user_interests,
                    selected_categories=[]
                )
                rejected_list.append({
                    "place": c_name,
                    "place_id": cid,
                    "category": c.get("category") or "attraction",
                    "rejection_reasons": rej_reasons
                })
            return self._build_empty_itinerary(
                start_location, origin_name, origin_lat, origin_lng,
                start_time_clock, total_budget_mins, mode,
                rejected_destinations=rejected_list[:10]
            )

        # -------------------------------------------------------------------
        # Step 8: Construct Concrete Timetable and Standard Output Data
        # -------------------------------------------------------------------
        try:
            current_dt = datetime.strptime(start_time_clock, "%I:%M %p")
        except ValueError:
            current_dt = datetime.strptime("09:30 AM", "%I:%M %p")

        start_clock_str = current_dt.strftime("%I:%M %p")
        scheduled_stops: List[ScheduledItineraryStop] = []
        ordered_itinerary_list: List[Dict[str, Any]] = []
        selected_destinations_list: List[Dict[str, Any]] = []
        legs_data: List[Dict[str, Any]] = []

        elapsed_rel_mins = 0
        prev_lat = origin_lat
        prev_lng = origin_lng
        prev_id = origin_id

        route_score_accumulator = 0.0

        for idx, p in enumerate(tour):
            p_id = p.get("place_id")
            t_leg, d_leg = estimate_transit_time_minutes(
                prev_lat, prev_lng, p["lat"], p["lng"],
                mode, travel_matrix, prev_id, p_id
            )
            elapsed_rel_mins += t_leg
            current_dt += timedelta(minutes=t_leg)
            arrival_clock = current_dt.strftime("%I:%M %p")
            arrival_rel = elapsed_rel_mins

            dwell_mins = p.get("dwell_mins", 60)
            elapsed_rel_mins += dwell_mins
            current_dt += timedelta(minutes=dwell_mins)
            departure_clock = current_dt.strftime("%I:%M %p")
            departure_rel = elapsed_rel_mins

            # Leg details
            leg_info = {
                "leg_index": idx,
                "duration_minutes": t_leg,
                "duration_seconds": t_leg * 60,
                "duration_text": f"{t_leg} mins",
                "distance_km": d_leg,
                "distance_meters": int(d_leg * 1000),
                "distance_text": f"{d_leg:.1f} km"
            }
            legs_data.append(leg_info)

            # Explainability & Rationales
            bd = p.get("score_breakdown")
            if isinstance(bd, PlaceScoreBreakdown):
                time_reason = f"Allocated {dwell_mins} minutes based on venue characteristics."
                ai_reason = bd.explanation
                score_dict = bd.sub_scores
                route_score_accumulator += bd.final_score
            else:
                time_reason = f"Allocated {dwell_mins} minutes for comprehensive visit."
                ai_reason = "Curated stop matching user criteria."
                score_dict = {}
                route_score_accumulator += 70.0

            # Generate explainability reasons for this selected destination
            reasons = generate_selection_reasons(
                place=p,
                score_breakdown=bd if isinstance(bd, PlaceScoreBreakdown) else None,
                transit_mins=t_leg,
                user_interests=user_interests,
                selected_categories=selected_categories
            )

            stop_obj = ScheduledItineraryStop(
                stop_index=idx + 1,
                place_id=p_id or f"stop_{idx+1}",
                name=p.get("name") or "Local Venue",
                category=p.get("category") or p.get("type") or "attraction",
                lat=p["lat"],
                lng=p["lng"],
                address=p.get("address") or "",
                rating=safe_float(p.get("rating"), 4.5),
                review_count=safe_int(p.get("user_rating_count") or p.get("review_count"), 150),
                price_level=p.get("price_level") or "$$ (Moderate)",
                duration_mins=dwell_mins,
                duration_hours=round(dwell_mins / 60.0, 2),
                time_estimate_reason=time_reason,
                ai_reasoning=ai_reason,
                arrival_rel_mins=arrival_rel,
                departure_rel_mins=departure_rel,
                arrival_clock=arrival_clock,
                departure_clock=departure_clock,
                transit_from_prev_mins=t_leg,
                transit_from_prev_km=d_leg,
                score_breakdown=score_dict,
                selection_reasons=reasons
            )
            scheduled_stops.append(stop_obj)
            stop_dict = stop_obj.to_dict()
            ordered_itinerary_list.append(stop_dict)
            selected_destinations_list.append(stop_dict)

            prev_lat = p["lat"]
            prev_lng = p["lng"]
            prev_id = p_id

        # Hard Constraint 2: Return to Starting Location
        return_mins, return_km = estimate_transit_time_minutes(
            prev_lat, prev_lng, origin_lat, origin_lng,
            mode, travel_matrix, prev_id, origin_id
        )
        elapsed_rel_mins += return_mins
        current_dt += timedelta(minutes=return_mins)
        final_return_clock = current_dt.strftime("%I:%M %p")

        return_leg_dict = {
            "destination": origin_name,
            "lat": origin_lat,
            "lng": origin_lng,
            "duration_minutes": return_mins,
            "duration_text": f"{return_mins} mins",
            "distance_km": return_km,
            "distance_text": f"{return_km:.1f} km",
            "arrival_clock": final_return_clock
        }
        legs_data.append({
            "leg_index": len(tour),
            "duration_minutes": return_mins,
            "duration_seconds": return_mins * 60,
            "duration_text": f"{return_mins} mins",
            "distance_km": return_km,
            "distance_meters": int(return_km * 1000),
            "distance_text": f"{return_km:.1f} km"
        })

        total_span, total_travel, total_visit, total_dist = calculate_loop_metrics(tour)
        avg_score = round(route_score_accumulator / max(1, len(tour)), 1)

        # Step 9: Generate explainability reasons for unselected/rejected candidates
        rejected_destinations_list: List[Dict[str, Any]] = []
        selected_pids = {p.get("place_id") for p in tour}
        scored_map = {bd.place_id: bd for bd in scored_breakdowns}

        tour_cats = [str(p.get("category") or p.get("type") or "").lower() for p in tour]

        for c in raw_candidates:
            cid = str(c.get("place_id") or c.get("id") or "")
            if cid in selected_pids:
                continue

            c_name = str(c.get("name") or "Candidate Venue")
            if any(r["place"] == c_name for r in rejected_destinations_list):
                continue

            c_bd = scored_map.get(cid)
            rejection_reasons = generate_rejection_reasons(
                cand=c,
                score_breakdown=c_bd,
                tour=tour,
                origin_lat=origin_lat,
                origin_lng=origin_lng,
                total_budget_mins=total_budget_mins,
                used_duration_mins=total_span,
                user_interests=user_interests,
                selected_categories=tour_cats
            )

            rejected_destinations_list.append({
                "place": c_name,
                "place_id": cid,
                "category": c.get("category") or "attraction",
                "rejection_reasons": rejection_reasons
            })

        # Return comprehensive standardized output matching user requirements
        return {
            "status": "success",
            "starting_location": {
                "name": origin_name,
                "lat": origin_lat,
                "lng": origin_lng,
                "address": start_location.get("address") or origin_name
            },
            "selected_destinations": selected_destinations_list,
            "ordered_itinerary": ordered_itinerary_list,
            "rejected_destinations": rejected_destinations_list[:10],
            "return_to_start": return_leg_dict,
            "total_travel_time": total_travel,
            "total_visit_time": total_visit,
            "total_duration": total_span,
            "total_distance": total_dist,
            "score": avg_score,
            "transportation_mode": mode,
            "available_time_minutes": available_time_minutes,
            "constraints_satisfied": {
                "starts_at_origin": True,
                "ends_at_origin": True,
                "within_time_budget": (total_span <= available_time_minutes),
                "return_time_reserved": True,
                "no_duplicates": (len(selected_place_ids) == len(tour)),
                "no_unreachable": True
            },
            "legs": legs_data
        }

    def _build_empty_itinerary(
        self,
        start_location: Dict[str, Any],
        origin_name: str,
        origin_lat: float,
        origin_lng: float,
        start_time_clock: str,
        total_budget_mins: int,
        transportation_mode: str = "DRIVE",
        rejected_destinations: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        return {
            "status": "success",
            "starting_location": {
                "name": origin_name,
                "lat": origin_lat,
                "lng": origin_lng,
                "address": start_location.get("address") or origin_name
            },
            "selected_destinations": [],
            "ordered_itinerary": [],
            "rejected_destinations": rejected_destinations or [],
            "return_to_start": {
                "destination": origin_name,
                "lat": origin_lat,
                "lng": origin_lng,
                "duration_minutes": 0,
                "distance_km": 0.0,
                "arrival_clock": start_time_clock
            },
            "total_travel_time": 0,
            "total_visit_time": 0,
            "total_duration": 0,
            "total_distance": 0.0,
            "score": 0.0,
            "transportation_mode": transportation_mode,
            "available_time_minutes": total_budget_mins,
            "constraints_satisfied": {
                "starts_at_origin": True,
                "ends_at_origin": True,
                "within_time_budget": True,
                "return_time_reserved": True,
                "no_duplicates": True,
                "no_unreachable": True
            },
            "legs": []
        }


# ---------------------------------------------------------------------------
# Public Functional Interfaces
# ---------------------------------------------------------------------------

_default_optimizer = RouteOptimizer()


def optimize_route(
    start_location: Dict[str, Any],
    available_time_minutes: int,
    transportation_mode: str = "DRIVE",
    user_interests: Optional[str] = None,
    candidate_places: List[Dict[str, Any]] = None,
    travel_matrix: Optional[Dict[Tuple[str, str], Dict[str, Any]]] = None,
    scoring_config: Optional[ScoringConfig] = None,
    max_destinations: Optional[int] = None
) -> Dict[str, Any]:
    """
    Stand-alone functional interface matching the exact problem specification.
    """
    optimizer = RouteOptimizer(config=scoring_config)
    return optimizer.optimize(
        start_location=start_location,
        available_time_minutes=available_time_minutes,
        transportation_mode=transportation_mode,
        user_interests=user_interests,
        candidate_places=candidate_places or [],
        travel_matrix=travel_matrix,
        max_destinations=max_destinations
    )


def optimize_day_itinerary(
    origin_lat: float,
    origin_lng: float,
    origin_name: str,
    candidates: List[Dict[str, Any]],
    total_hours: float,
    user_vibe: Optional[str] = None,
    cuisine_preference: Optional[str] = None,
    travel_mode: str = "DRIVE",
    start_time_clock: str = "09:30 AM",
    scoring_config: Optional[ScoringConfig] = None
) -> OptimizedItineraryPlan:
    """
    Maintained for backward compatibility with services.agent and existing tests.
    Translates input parameters into optimize_route format.
    """
    start_loc = {
        "name": origin_name,
        "lat": origin_lat,
        "lng": origin_lng,
        "address": origin_name
    }
    avail_mins = int(round(total_hours * 60))
    raw_res = optimize_route(
        start_location=start_loc,
        available_time_minutes=avail_mins,
        transportation_mode=travel_mode,
        user_interests=user_vibe,
        candidate_places=candidates,
        scoring_config=scoring_config
    )

    # Convert dictionary stops to ScheduledItineraryStop list
    stops = []
    for s in raw_res.get("ordered_itinerary", []):
        stops.append(ScheduledItineraryStop(
            stop_index=s["stop_index"],
            place_id=s["place_id"],
            name=s["name"],
            category=s["category"],
            lat=s["lat"],
            lng=s["lng"],
            address=s["address"],
            rating=s["rating"],
            review_count=s["review_count"],
            price_level=s["price_level"],
            duration_mins=s["duration_mins"],
            duration_hours=s["duration_hours"],
            time_estimate_reason=s["time_estimate_reason"],
            ai_reasoning=s["ai_reasoning"],
            arrival_rel_mins=s["arrival_rel_mins"],
            departure_rel_mins=s["departure_rel_mins"],
            arrival_clock=s["arrival_time"],
            departure_clock=s["departure_time"],
            transit_from_prev_mins=s["transit_from_prev_mins"],
            transit_from_prev_km=s["transit_from_prev_km"],
            score_breakdown=s.get("score_breakdown", {}),
            selection_reasons=s.get("selection_reasons", [])
        ))

    ret_leg = raw_res.get("return_to_start", {})
    return_leg_data = {
        "duration_mins": ret_leg.get("duration_minutes", 0),
        "duration_text": ret_leg.get("duration_text", "0 mins"),
        "distance_km": ret_leg.get("distance_km", 0.0),
        "distance_text": ret_leg.get("distance_text", "0.0 km"),
        "destination": ret_leg.get("destination", origin_name),
        "final_return_clock": ret_leg.get("arrival_clock", start_time_clock)
    }

    total_span = raw_res.get("total_duration", 0)
    slack = max(0, avail_mins - total_span)

    return OptimizedItineraryPlan(
        start_location={"name": origin_name, "lat": origin_lat, "lng": origin_lng},
        stops=stops,
        total_trip_mins=total_span,
        total_travel_mins=raw_res.get("total_travel_time", 0),
        total_dwell_mins=raw_res.get("total_visit_time", 0),
        total_distance_km=raw_res.get("total_distance", 0.0),
        total_trip_hours=round(total_span / 60.0, 1),
        slack_remaining_mins=slack,
        start_clock=start_time_clock,
        end_clock=ret_leg.get("arrival_clock", start_time_clock),
        return_leg=return_leg_data,
        legs_data=raw_res.get("legs", []),
        route_score=raw_res.get("score", 0.0),
        rejected_destinations=raw_res.get("rejected_destinations", [])
    )
