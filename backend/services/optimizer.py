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
from typing import List, Dict, Any, Optional, Tuple, Set
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
from services.taxonomy import (
    normalize_category,
    get_venue_canonical_categories,
    is_iconic_landmark,
    calculate_tourism_significance,
    CATEGORY_LANDMARK,
    CATEGORY_FOOD,
    CATEGORY_CAFE,
    CATEGORY_NATURE,
    CATEGORY_CULTURE,
    CATEGORY_VIEWPOINT,
    CATEGORY_WATERFRONT,
    CATEGORY_SHOPPING
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
    meal_type: Optional[str] = None  # "breakfast", "lunch", "dinner", or None
    travel_time_from_previous: int = 0
    visit_duration: int = 45

    def to_dict(self) -> Dict[str, Any]:
        cat = "food" if self.meal_type or self.category in ["restaurant", "cafe", "dining", "bakery"] else self.category
        return {
            "stop_index": self.stop_index,
            "place_id": self.place_id,
            "place": self.name,
            "name": self.name,
            "selection_reasons": self.selection_reasons,
            "category": cat,
            "meal_type": self.meal_type,
            "is_meal_stop": bool(self.meal_type),
            "lat": self.lat,
            "lng": self.lng,
            "coordinates": {"lat": self.lat, "lng": self.lng},
            "address": self.address,
            "rating": self.rating,
            "review_count": self.review_count,
            "price_level": self.price_level,
            "duration_mins": self.visit_duration,
            "duration_hours": round(self.visit_duration / 60.0, 2),
            "visit_duration": self.visit_duration,
            "travel_time_from_previous": self.travel_time_from_previous,
            "time_estimate_reason": self.time_estimate_reason,
            "ai_reasoning": self.ai_reasoning,
            "arrival_time": self.arrival_clock,
            "departure_time": self.departure_clock,
            "arrival_rel_mins": self.arrival_rel_mins,
            "departure_rel_mins": self.departure_rel_mins,
            "transit_from_prev_mins": self.travel_time_from_previous,
            "transit_from_prev_km": self.transit_from_prev_km,
            "score_breakdown": self.score_breakdown or {},
            "type": "restaurant" if self.meal_type or self.category in ["restaurant", "cafe", "food", "bakery"] else "attraction"
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
    safety_buffer_mins: int = 0
    start_clock: str = "09:30 AM"
    end_clock: str = "05:30 PM"
    return_leg: Dict[str, Any] = field(default_factory=dict)
    legs_data: List[Dict[str, Any]] = field(default_factory=list)
    route_score: float = 0.0
    rejected_destinations: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def travel_time_minutes(self) -> int:
        return self.total_travel_mins

    @property
    def visit_time_minutes(self) -> int:
        return self.total_dwell_mins

    @property
    def safety_buffer_minutes(self) -> int:
        return self.safety_buffer_mins

    @property
    def total_duration_minutes(self) -> int:
        return self.total_travel_mins + self.total_dwell_mins + self.safety_buffer_mins


@dataclass
class RouteScoringConfig:
    """Configuration weights and hyperparameters for holistic route-level scoring."""
    weight_quality: float = 0.30
    weight_preference: float = 0.20
    weight_landmark: float = 0.20
    weight_diversity: float = 0.15
    weight_completeness: float = 0.10
    weight_travel_cost: float = 0.05
    unused_time_penalty_per_hour: float = 1.5
    saturated_travel_mins: float = 120.0
    target_stops_per_hour: float = 0.6


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
        # Average cycling speed ~14 km/h -> 4.3 mins/km + 1.0 min buffer
        duration_mins = int(round(dist_km * 4.3 + 1.0))
    else:
        # Default DRIVE: Urban city traffic factor (~24 km/h) -> 2.5 mins/km + 1.5 mins parking/buffer
        duration_mins = int(round(dist_km * 2.5 + 1.5))

    duration_mins = max(1, duration_mins)
    return duration_mins, dist_km


def parse_clock_time(clock_str: str) -> datetime:
    """Safely parse clock string into datetime object."""
    if not clock_str or not isinstance(clock_str, str):
        return datetime.strptime("09:30 AM", "%I:%M %p")
    cleaned = clock_str.strip().upper()
    formats = ["%I:%M %p", "%I:%M%p", "%H:%M", "%H:%M:%S"]
    for fmt in formats:
        try:
            return datetime.strptime(cleaned, fmt)
        except ValueError:
            continue
    return datetime.strptime("09:30 AM", "%I:%M %p")


def get_minute_of_day(dt: datetime) -> int:
    """Returns minute of the day (0 to 1439)."""
    return dt.hour * 60 + dt.minute


def calculate_meal_timing_multiplier(arrival_dt: datetime, category: str, user_interests: Optional[str] = None) -> float:
    """
    Evaluates whether a dining stop matches appropriate meal windows:
    - Lunch: 11:30 AM - 02:30 PM (690 - 870 mins)
    - Dinner: 06:00 PM - 09:30 PM (1080 - 1290 mins)
    - Cafe: Morning (08:00 AM - 11:30 AM) or Afternoon (02:30 PM - 05:30 PM)
    """
    cat = (category or "").lower()
    m = get_minute_of_day(arrival_dt)
    interests_str = (user_interests or "").lower()
    wants_food = any(term in interests_str for term in ["food", "dining", "restaurant", "lunch", "dinner", "eat"])

    if cat in ["restaurant", "dining", "food"]:
        is_lunch = (675 <= m <= 900)    # 11:15 AM - 03:00 PM
        is_dinner = (1080 <= m <= 1320) # 06:00 PM - 10:00 PM
        if is_lunch or is_dinner:
            return 1.3  # Prime meal window boost
        elif (600 <= m < 675) or (900 < m <= 960) or (1020 <= m < 1080):
            return 1.1 if wants_food else 0.8  # Shoulder hours
        else:
            return 0.95 if wants_food else 0.35  # Off hours

    elif cat in ["cafe", "bakery"]:
        is_morning = (480 <= m <= 690)
        is_afternoon = (870 <= m <= 1050)
        if is_morning or is_afternoon:
            return 1.25
        return 0.9

    return 1.0


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Centralized Deterministic Safety-Buffer Configuration
# ---------------------------------------------------------------------------
DEFAULT_BUFFER_PERCENTAGE: float = 0.15  # 15% of total travel time
MIN_SAFETY_BUFFER_MINUTES: int = 5       # Fixed minimum to absorb traffic lights / parking
MAX_SAFETY_BUFFER_MINUTES: int = 30      # Reasonable upper cap for planning uncertainty


def calculate_safety_buffer_mins(
    total_travel_mins: int,
    percentage: float = DEFAULT_BUFFER_PERCENTAGE,
    min_mins: int = MIN_SAFETY_BUFFER_MINUTES,
    max_mins: int = MAX_SAFETY_BUFFER_MINUTES
) -> int:
    """
    Calculates a rational, bounded planning safety buffer based primarily on
    actual uncertainty in travel time.
    buffer = clamp(round(total_travel_time * percentage), min_mins, max_mins)

    Never scales with total available trip time.
    Never scales with destination dwell time.
    """
    raw_buffer = int(round(max(0, total_travel_mins) * percentage))
    return max(min_mins, min(max_mins, raw_buffer))

# Centralized Deterministic Visit-Duration Registry
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CategoryVisitDuration:
    category: str
    min_minutes: int
    default_minutes: int
    max_minutes: int
    description: str


VISIT_DURATION_REGISTRY: Dict[str, CategoryVisitDuration] = {
    "breakfast": CategoryVisitDuration("breakfast", min_minutes=30, default_minutes=45, max_minutes=45, description="Morning breakfast stop"),
    "lunch": CategoryVisitDuration("lunch", min_minutes=45, default_minutes=60, max_minutes=75, description="Midday lunch meal"),
    "dinner": CategoryVisitDuration("dinner", min_minutes=60, default_minutes=75, max_minutes=90, description="Evening dinner meal"),
    "cafe": CategoryVisitDuration("cafe", min_minutes=30, default_minutes=45, max_minutes=45, description="Artisan coffee or bakery pause"),
    "bakery": CategoryVisitDuration("bakery", min_minutes=30, default_minutes=45, max_minutes=45, description="Bakery or quick refreshment"),
    "park": CategoryVisitDuration("park", min_minutes=30, default_minutes=45, max_minutes=60, description="Public park or botanical garden"),
    "nature": CategoryVisitDuration("nature", min_minutes=30, default_minutes=45, max_minutes=60, description="Nature reserve or scenic green space"),
    "lake": CategoryVisitDuration("lake", min_minutes=30, default_minutes=30, max_minutes=45, description="Scenic lakefront walk or overlook"),
    "viewpoint": CategoryVisitDuration("viewpoint", min_minutes=30, default_minutes=30, max_minutes=45, description="Scenic viewpoint or observation deck"),
    "museum": CategoryVisitDuration("museum", min_minutes=60, default_minutes=60, max_minutes=90, description="Museum exhibition or gallery visit"),
    "art": CategoryVisitDuration("art", min_minutes=60, default_minutes=60, max_minutes=90, description="Art museum or cultural gallery"),
    "monument": CategoryVisitDuration("monument", min_minutes=45, default_minutes=60, max_minutes=90, description="Historic monument or landmark"),
    "historic": CategoryVisitDuration("historic", min_minutes=45, default_minutes=60, max_minutes=90, description="Historic fort, palace or heritage site"),
    "major_attraction": CategoryVisitDuration("major_attraction", min_minutes=60, default_minutes=90, max_minutes=120, description="Major iconic landmark/complex"),
    "culture": CategoryVisitDuration("culture", min_minutes=45, default_minutes=60, max_minutes=90, description="Cultural complex or heritage center"),
    "shopping": CategoryVisitDuration("shopping", min_minutes=30, default_minutes=45, max_minutes=60, description="Bazaar, artisan market or shopping promenade"),
    "default": CategoryVisitDuration("default", min_minutes=30, default_minutes=45, max_minutes=60, description="Standard sightseeing exploration"),
}


def get_category_visit_duration(place: Dict[str, Any], meal_type: Optional[str] = None) -> CategoryVisitDuration:
    """
    Deterministically resolves the visit duration configuration for a venue.
    Zero random numbers. Zero LLM invention.
    """
    if meal_type and meal_type in VISIT_DURATION_REGISTRY:
        return VISIT_DURATION_REGISTRY[meal_type]

    if not isinstance(place, dict):
        return VISIT_DURATION_REGISTRY["default"]

    cat = str(place.get("category") or place.get("type") or "").lower()
    name = str(place.get("name") or "").lower()
    types_raw = place.get("types")
    types = [str(t).lower() for t in types_raw] if isinstance(types_raw, (list, tuple, set)) else []

    # Check for meal categories
    if is_restaurant_venue(place):
        if "breakfast" in name or "morning" in name:
            return VISIT_DURATION_REGISTRY["breakfast"]
        if "dinner" in name:
            return VISIT_DURATION_REGISTRY["dinner"]
        if any(t in types for t in ["bakery", "cafe"]) or cat in ["cafe", "bakery"] or "coffee" in name:
            return VISIT_DURATION_REGISTRY["cafe"]
        return VISIT_DURATION_REGISTRY["lunch"]

    # Major attractions / iconic monuments
    if any(kw in name for kw in ["fort", "palace", "akshardham", "taj", "colosseum", "disney", "universal"]) or "major" in cat:
        return VISIT_DURATION_REGISTRY["major_attraction"]

    if any(t in types for t in ["museum", "art_gallery"]) or cat in ["museum", "art", "gallery"]:
        return VISIT_DURATION_REGISTRY["museum"]

    if any(t in types for t in ["park", "garden", "campground"]) or cat in ["park", "garden", "nature"]:
        return VISIT_DURATION_REGISTRY["park"]

    if any(t in types for t in ["lake", "viewpoint"]) or any(kw in name for kw in ["lake", "viewpoint", "lookout", "overlook", "point"]) or cat in ["viewpoint", "lake"]:
        return VISIT_DURATION_REGISTRY["viewpoint"]

    if any(t in types for t in ["monument", "historic", "historical_landmark"]) or cat in ["monument", "historic"]:
        return VISIT_DURATION_REGISTRY["monument"]

    if cat in ["shopping", "market", "bazaar"] or any(t in types for t in ["shopping_mall", "market"]):
        return VISIT_DURATION_REGISTRY["shopping"]

    if cat in VISIT_DURATION_REGISTRY:
        return VISIT_DURATION_REGISTRY[cat]

    return VISIT_DURATION_REGISTRY["default"]


def determine_visit_duration_mins(place: Dict[str, Any], meal_type: Optional[str] = None) -> int:
    """
    Returns deterministic visit duration in minutes (clean 15-minute intervals).
    """
    model = get_category_visit_duration(place, meal_type)
    raw_dur = place.get("duration_mins") or place.get("user_dwell_mins")
    if raw_dur is not None:
        try:
            val = int(raw_dur)
            if model.min_minutes <= val <= model.max_minutes:
                return max(model.min_minutes, min(model.max_minutes, int(round(val / 15.0) * 15)))
        except (ValueError, TypeError):
            pass
    return model.default_minutes


def determine_default_dwell_mins(place: Dict[str, Any]) -> int:
    """
    Determine a realistic venue dwell time based on category and venue types.
    Standardized to predictable 15-minute intervals.
    """
    return determine_visit_duration_mins(place)


# ---------------------------------------------------------------------------
# 2-Opt Local Search Tour Optimization
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Explicit Configurable Meal Periods (Breakfast, Lunch, Dinner)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MealPeriod:
    """Configurable definition of an itinerary meal window."""
    name: str                   # "breakfast", "lunch", "dinner"
    start_time: str             # "07:00", "11:30", "18:00"
    end_time: str               # "10:30", "14:30", "21:30"
    start_minute: int           # minutes from midnight
    end_minute: int             # minutes from midnight
    default_dwell_mins: int     # standard visit time
    min_dwell_mins: int         # minimum viable visit time
    min_trip_overlap_mins: int  # minimum trip overlap to trigger meal eligibility


DEFAULT_MEAL_PERIODS: Dict[str, MealPeriod] = {
    "breakfast": MealPeriod(
        name="breakfast",
        start_time="07:00",
        end_time="10:30",
        start_minute=7 * 60,         # 420
        end_minute=10 * 60 + 30,     # 630
        default_dwell_mins=45,
        min_dwell_mins=30,
        min_trip_overlap_mins=45
    ),
    "lunch": MealPeriod(
        name="lunch",
        start_time="11:30",
        end_time="14:30",
        start_minute=11 * 60 + 30,   # 690
        end_minute=14 * 60 + 30,     # 870
        default_dwell_mins=60,
        min_dwell_mins=45,
        min_trip_overlap_mins=45
    ),
    "dinner": MealPeriod(
        name="dinner",
        start_time="18:00",
        end_time="21:30",
        start_minute=18 * 60,        # 1080
        end_minute=21 * 60 + 30,     # 1290
        default_dwell_mins=75,
        min_dwell_mins=45,
        min_trip_overlap_mins=45
    )
}


def get_place_operating_window(place: Dict[str, Any]) -> Tuple[int, int]:
    """
    Returns (open_minute, close_minute) in minutes from midnight (0 to 1440).
    If no opening hours specified, defaults to (0, 1440) (assumed open).
    """
    if not isinstance(place, dict):
        return (0, 1440)

    open_str = place.get("open_time") or place.get("opening_time")
    close_str = place.get("close_time") or place.get("closing_time")
    if open_str and close_str:
        try:
            o_dt = parse_clock_time(str(open_str))
            c_dt = parse_clock_time(str(close_str))
            o_min = get_minute_of_day(o_dt)
            c_min = get_minute_of_day(c_dt)
            if c_min <= o_min:
                c_min = 1440
            return (o_min, c_min)
        except Exception:
            pass

    op_hours = place.get("opening_hours")
    if isinstance(op_hours, dict) and "periods" in op_hours and isinstance(op_hours["periods"], list):
        for period in op_hours["periods"]:
            if isinstance(period, dict) and "open" in period and "close" in period:
                try:
                    o_t = str(period["open"].get("time", "0000"))
                    c_t = str(period["close"].get("time", "2359"))
                    o_min = int(o_t[:2]) * 60 + int(o_t[2:])
                    c_min = int(c_t[:2]) * 60 + int(c_t[2:])
                    return (o_min, c_min)
                except Exception:
                    pass

    return (0, 1440)


def is_restaurant_venue(place: Optional[Dict[str, Any]]) -> bool:
    """Check if venue is a dedicated dining establishment (restaurant, cafe, bistro, etc.)."""
    if not place or not isinstance(place, dict):
        return False
    cat = str(place.get("category") or place.get("type") or "").lower()
    if any(rc in cat for rc in ["restaurant", "dining", "bistro", "eatery", "dhaba", "diner", "pizzeria", "steakhouse", "cafe", "bakery"]):
        return True
    types_raw = place.get("types")
    if isinstance(types_raw, (list, tuple, set)):
        types = [str(t).lower() for t in types_raw]
        if any(t in ["restaurant", "food", "dining", "meal_takeaway", "cafe", "bakery"] for t in types):
            return True
    name = str(place.get("name") or "").lower()
    if any(kw in name for kw in ["restaurant", "cafe", "coffee", "bistro", "dhaba", "bakery", "eatery", "diner", "pizzeria", "kitchen", "bar"]):
        # Disambiguate against attractions that mention bar/gate
        if not any(sc in cat for sc in ["museum", "park", "garden", "monument", "historic", "culture", "viewpoint"]):
            return True
    return False


def is_sightseeing_venue(place: Optional[Dict[str, Any]]) -> bool:
    """Check if venue is a cultural, outdoor, or sightseeing destination."""
    if not place or not isinstance(place, dict):
        return True
    cat = str(place.get("category") or place.get("type") or "").lower()
    name = str(place.get("name") or "").lower()
    if any(sc in cat for sc in ["museum", "art", "gallery", "park", "garden", "monument", "historic", "culture", "viewpoint", "scenic", "landmark", "shopping", "bazaar"]):
        return True
    if any(kw in name for kw in ["museum", "park", "garden", "tomb", "fort", "gate", "monument", "temple", "gallery", "palace"]):
        return True
    return False


FOOD_CATEGORIES = {
    "restaurant", "dining", "cafe", "food", "bakery", "bistro", "bar", "pub",
    "coffee", "eatery", "fast_food", "food_court", "meal_takeaway"
}


def is_food_candidate(c_dict: Optional[Dict[str, Any]]) -> bool:
    """Check if candidate venue is a food/beverage establishment (restaurant, cafe, bakery, etc.)."""
    if not c_dict or not isinstance(c_dict, dict):
        return False
    cat = str(c_dict.get("category") or c_dict.get("type") or "").lower()
    if any(fc in cat for fc in ["restaurant", "dining", "cafe", "bakery", "bistro", "food", "eatery", "coffee"]):
        return True
    types_raw = c_dict.get("types")
    if isinstance(types_raw, (list, tuple, set)):
        types = [str(t).lower() for t in types_raw]
        if any(t in FOOD_CATEGORIES or any(fc in t for fc in ["restaurant", "cafe", "bakery", "food", "dining"]) for t in types):
            return True
    name = str(c_dict.get("name") or "").lower()
    if any(kw in name for kw in ["restaurant", "cafe", "coffee", "bistro", "dhaba", "bakery", "eatery", "rooftop cafe"]):
        return True
    return False


def get_canonical_stop_category(stop: Dict[str, Any]) -> str:
    """
    Deterministically resolves the canonical category for a tour stop.
    Returns canonical category key:
      'nature', 'food', 'cafe', 'culture', 'viewpoint', 'waterfront', 'shopping', 'landmark'
    or fallback to normalized raw category/type, or 'attraction'.
    """
    if not isinstance(stop, dict):
        return "attraction"

    if stop.get("meal_type") or is_food_candidate(stop):
        cat = stop.get("category") or stop.get("type")
        norm = normalize_category(str(cat)) if cat else None
        return norm if norm in (CATEGORY_FOOD, CATEGORY_CAFE) else CATEGORY_FOOD

    raw_cat = stop.get("category")
    if raw_cat:
        norm = normalize_category(str(raw_cat))
        if norm:
            return norm

    raw_type = stop.get("type")
    if raw_type:
        norm = normalize_category(str(raw_type))
        if norm:
            return norm

    venue_cats = get_venue_canonical_categories(stop)
    if venue_cats:
        for preferred in [
            CATEGORY_CULTURE, CATEGORY_NATURE, CATEGORY_FOOD, CATEGORY_CAFE,
            CATEGORY_VIEWPOINT, CATEGORY_WATERFRONT, CATEGORY_SHOPPING, CATEGORY_LANDMARK
        ]:
            if preferred in venue_cats:
                return preferred
        return next(iter(venue_cats))

    return "attraction"


def violates_consecutive_category_limit(
    tour: List[Dict[str, Any]],
    max_consecutive: int = 2
) -> bool:
    """
    Validates whether the same canonical category appears consecutively more than max_consecutive times.
    Example with max_consecutive = 2:
      Park -> Park -> Attraction  (Valid: run of 2 nature, run of 1 culture)
      Park -> Park -> Restaurant  (Valid: run of 2 nature, run of 1 food)
      Park -> Park -> Park        (Invalid: run of 3 nature > 2)
      Rest -> Rest -> Rest        (Invalid: run of 3 food > 2)
      Park -> Attr -> Park        (Valid: run of 1, 1, 1)
      Museum -> Museum -> Park    (Valid: run of 2, 1)
    """
    if not tour or len(tour) <= max_consecutive:
        return False

    current_cat = None
    run_len = 0

    for stop in tour:
        cat = get_canonical_stop_category(stop)
        if cat == current_cat:
            run_len += 1
            if run_len > max_consecutive:
                return True
        else:
            current_cat = cat
            run_len = 1

    return False


def two_opt_optimize_loop(
    stops: List[Dict[str, Any]],
    origin_lat: float,
    origin_lng: float,
    mode: str = "DRIVE",
    travel_matrix: Optional[Dict[Tuple[str, str], Dict[str, Any]]] = None,
    origin_id: str = "origin",
    start_time_clock: Optional[str] = None,
    allow_adjacent_food: bool = False,
    max_consecutive_same_category: int = 2
) -> List[Dict[str, Any]]:
    """
    2-Opt local search improvement for the round-trip tour:
    Origin -> s_1 -> s_2 -> ... -> s_k -> Origin.
    Reverses sub-segments to remove crossed edges and minimize transit time.
    Enforces max_consecutive_same_category constraint (rejects 3+ consecutive same category).
    """
    if len(stops) <= 2:
        return stops

    def respects_meal_windows(tour: List[Dict[str, Any]]) -> bool:
        if not start_time_clock:
            return True
        try:
            start_dt = parse_clock_time(start_time_clock)
        except Exception:
            return True
        cur_elapsed = 0
        p_lat, p_lng, p_id = origin_lat, origin_lng, origin_id
        for item in tour:
            t_leg, _ = estimate_transit_time_minutes(
                p_lat, p_lng, item["lat"], item["lng"],
                mode, travel_matrix, p_id, item.get("place_id")
            )
            cur_elapsed += t_leg
            arr_dt = start_dt + timedelta(minutes=cur_elapsed)
            arr_m = get_minute_of_day(arr_dt)
            m_type = item.get("meal_type")
            if m_type and m_type in DEFAULT_MEAL_PERIODS:
                mp = DEFAULT_MEAL_PERIODS[m_type]
                if not (mp.start_minute <= arr_m <= mp.end_minute):
                    return False
            cur_elapsed += item.get("dwell_mins", 60)
            p_lat, p_lng, p_id = item["lat"], item["lng"], item.get("place_id")
        return True

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
                # Enforce max_consecutive_same_category constraint
                if violates_consecutive_category_limit(new_tour, max_consecutive=max_consecutive_same_category):
                    continue
                if not respects_meal_windows(new_tour):
                    continue
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
# Complete Itinerary Holistic Route Evaluation
# ---------------------------------------------------------------------------

def calculate_route_score(
    tour: List[Dict[str, Any]],
    total_budget_mins: int,
    total_travel_mins: int,
    total_visit_mins: int,
    user_interests: Optional[str] = None,
    explicit_categories: Optional[Set[str]] = None,
    config: Optional[RouteScoringConfig] = None
) -> float:
    """
    Evaluates the quality of the COMPLETE itinerary rather than individual destinations.
    Combines:
    1. Average destination quality (Bayesian ratings)
    2. User interest / vibe alignment
    3. Landmark value & tourism significance
    4. Category diversity across the route
    5. Itinerary completeness / pacing
    6. Soft travel efficiency penalty (travel is a cost, not an overwhelming barrier)
    7. Soft unused time penalty (unused time gently penalized, not forced)
    8. Category repetition penalty (penalizes consecutive runs and excessive duplicates)
    """
    if not tour:
        return 0.0

    cfg = config or RouteScoringConfig()
    n_stops = len(tour)

    # 1. Destination Quality (0 - 100)
    quality_scores = []
    for p in tour:
        bd = p.get("score_breakdown")
        if isinstance(bd, PlaceScoreBreakdown):
            quality_scores.append(bd.final_score)
        elif isinstance(bd, dict) and "final_score" in bd:
            quality_scores.append(float(bd["final_score"]))
        else:
            rating = safe_float(p.get("rating"), 4.0)
            quality_scores.append(rating * 20.0)
    avg_quality = sum(quality_scores) / max(1, len(quality_scores))

    # 2. Preference Match (0 - 100)
    interests_str = (user_interests or "").lower().strip()
    if interests_str:
        pref_scores = []
        for p in tour:
            bd = p.get("score_breakdown")
            if isinstance(bd, PlaceScoreBreakdown):
                pref_scores.append(float(getattr(bd, "interest_match_score", 70.0)))
            elif isinstance(bd, dict) and "interest_match_score" in bd:
                pref_scores.append(float(bd["interest_match_score"]))
            else:
                pref_scores.append(70.0)
        avg_preference = sum(pref_scores) / max(1, len(pref_scores))
    else:
        avg_preference = avg_quality  # Neutral default

    # 3. Landmark Value & Tourism Significance (0 - 100)
    landmark_scores = [calculate_tourism_significance(p) for p in tour]
    avg_landmark = sum(landmark_scores) / max(1, len(landmark_scores))
    max_landmark = max(landmark_scores) if landmark_scores else 20.0
    composite_landmark = (0.55 * max_landmark + 0.45 * avg_landmark)

    # 4. Category Diversity (0 - 100)
    tour_cats = [get_canonical_stop_category(p) for p in tour]
    distinct_cats = set(tour_cats)
    adjacent_same_count = sum(1 for i in range(len(tour) - 1) if tour_cats[i] == tour_cats[i+1])
    diversity_score = max(50.0, 100.0 - (adjacent_same_count * 8.0))

    # Diversity & Repetition Penalties
    repetition_penalty = 0.0
    if not explicit_categories:
        if violates_consecutive_category_limit(tour, max_consecutive=2):
            repetition_penalty += 25.0
        for cat in distinct_cats:
            count = tour_cats.count(cat)
            if count >= 3:
                repetition_penalty += (count - 2) * 8.0

    # 5. Itinerary Completeness (0 - 100)
    budget_hours = max(1.0, total_budget_mins / 60.0)
    target_stops = max(1, min(7, int(round(budget_hours * cfg.target_stops_per_hour))))
    stop_ratio = min(1.0, n_stops / target_stops)
    completeness_score = stop_ratio * 100.0

    # 6. Travel Efficiency (Soft cost, not an overwhelming penalty)
    travel_ratio = min(1.0, total_travel_mins / max(30.0, cfg.saturated_travel_mins))
    travel_score = (1.0 - travel_ratio * 0.45) * 100.0

    # 7. Soft Unused Time Penalty
    total_active_mins = total_travel_mins + total_visit_mins
    unused_mins = max(0, total_budget_mins - total_active_mins)
    unused_hours = unused_mins / 60.0
    unused_time_penalty = min(12.0, unused_hours * cfg.unused_time_penalty_per_hour)

    # Holistic Weighted Combination
    raw_score = (
        cfg.weight_quality * avg_quality +
        cfg.weight_preference * avg_preference +
        cfg.weight_landmark * composite_landmark +
        cfg.weight_diversity * diversity_score +
        cfg.weight_completeness * completeness_score +
        cfg.weight_travel_cost * travel_score
    ) - repetition_penalty - unused_time_penalty

    return round(max(5.0, min(100.0, raw_score)), 2)


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
    selected_categories: List[str],
    explicit_categories: Optional[List[str]] = None,
    allow_iconic_landmarks: bool = False
) -> List[str]:
    """
    Generates concise user-facing explanations for why a candidate was not selected into the route.
    Allowed categories:
    - Ineligible category: outside user-selected categories
    - Exceeds remaining time
    - Excessive travel time
    - Duplicate category
    - Poor preference match
    """
    reasons = []
    if explicit_categories:
        allowed_cats = {normalize_category(c) for c in explicit_categories if normalize_category(c)}
        if allowed_cats:
            venue_cats = get_venue_canonical_categories(cand)
            is_allowed = bool(venue_cats & allowed_cats)
            is_landmark = allow_iconic_landmarks and (CATEGORY_LANDMARK in venue_cats or is_iconic_landmark(cand))
            if not is_allowed and not is_landmark:
                return ["Ineligible category: outside user-selected categories"]

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

    def __init__(
        self,
        config: Optional[ScoringConfig] = None,
        route_scoring_config: Optional[RouteScoringConfig] = None
    ):
        self.config = config or ScoringConfig()
        self.route_scoring_config = route_scoring_config or RouteScoringConfig()

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
        max_destinations: Optional[int] = None,
        selected_categories: Optional[List[str]] = None,
        allow_iconic_landmarks: bool = False,
        max_consecutive_same_category: int = 2,
        route_scoring_config: Optional[RouteScoringConfig] = None
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

        # Usable budget: travel + visit + travel-based safety buffer <= total_budget_mins
        # Nominal initial buffer (5 mins minimum) allows prioritizing user exploration
        usable_budget_mins = total_budget_mins

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

        # -------------------------------------------------------------------
        # Step 0.5: Enforce deterministic hard category filtering
        # -------------------------------------------------------------------
        explicit_category_set: Set[str] = set()
        raw_explicit = selected_categories or []
        if isinstance(raw_explicit, str):
            raw_explicit = [c.strip() for c in raw_explicit.split(",") if c.strip()]
        for c_entry in raw_explicit:
            norm_c = normalize_category(str(c_entry))
            if norm_c:
                explicit_category_set.add(norm_c)

        ineligible_candidates_log: List[Dict[str, Any]] = []
        if explicit_category_set:
            eligible_candidates: List[Dict[str, Any]] = []
            for c in unique_candidates:
                venue_cats = get_venue_canonical_categories(c)
                is_cat_match = bool(venue_cats & explicit_category_set)
                is_landmark_match = bool(allow_iconic_landmarks and (CATEGORY_LANDMARK in venue_cats or is_iconic_landmark(c)))
                if is_cat_match or is_landmark_match:
                    eligible_candidates.append(c)
                else:
                    ineligible_candidates_log.append({
                        "place": str(c.get("name") or "Candidate Venue"),
                        "place_id": str(c.get("place_id") or ""),
                        "category": str(c.get("category") or "attraction"),
                        "rejection_reasons": ["Ineligible category: outside user-selected categories"]
                    })
            unique_candidates = eligible_candidates

        if not unique_candidates:
            return self._build_empty_itinerary(
                start_location, origin_name, origin_lat, origin_lng,
                start_time_clock, total_budget_mins, mode,
                rejected_destinations=ineligible_candidates_log[:10]
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
        # Step 3: Multi-Seed Route Generation & Complete Itinerary Optimization
        # -------------------------------------------------------------------
        start_clock_dt = parse_clock_time(start_time_clock)
        start_minute = get_minute_of_day(start_clock_dt)
        trip_end_minute = start_minute + total_budget_mins
        is_early_start = (start_minute < 675)  # before 11:15 AM

        # Calculate which meal periods overlap the user's trip window [start_minute, trip_end_minute]
        eligible_meal_periods: List[MealPeriod] = []
        for mp in DEFAULT_MEAL_PERIODS.values():
            overlap_start = max(start_minute, mp.start_minute)
            overlap_end = min(trip_end_minute, mp.end_minute)
            overlap_mins = overlap_end - overlap_start
            if overlap_mins >= mp.min_trip_overlap_mins:
                eligible_meal_periods.append(mp)

        # Rule 13: If trip is short (<= 150 mins), only allow at most 1 meal period
        if total_budget_mins <= 150 and len(eligible_meal_periods) > 1:
            eligible_meal_periods = [eligible_meal_periods[0]]

        interests_str = (user_interests or "").lower()
        only_wants_food = ("food" in interests_str or "dining" in interests_str) and not any(term in interests_str for term in ["nature", "park", "outdoor", "museum", "art", "scenic", "view"])
        if explicit_category_set and explicit_category_set.issubset({CATEGORY_FOOD, CATEGORY_CAFE}):
            only_wants_food = True

        all_candidates_food = bool(unique_candidates and all(is_food_candidate(c) for c in unique_candidates))
        allow_adjacent_food = bool(only_wants_food or all_candidates_food)

        # Dynamic stop count targets based on available time
        if total_budget_mins < 90:
            max_stops = 1
        elif total_budget_mins < 180:
            max_stops = 2
        elif total_budget_mins < 270:
            max_stops = 3
        elif total_budget_mins < 390:
            max_stops = 4
        elif total_budget_mins < 510:
            max_stops = 5
        elif total_budget_mins < 630:
            max_stops = 7
        elif total_budget_mins < 750:
            max_stops = 9
        else:
            max_stops = 11

        if max_destinations is not None and max_destinations > 0:
            max_stops = min(max_stops, int(max_destinations))

        cfg_route = route_scoring_config or self.route_scoring_config

        # -------------------------------------------------------------------
        # Metrics and Feasibility Helpers
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

            # Last stop -> Origin (return time reserved)
            t_last, d_last = estimate_transit_time_minutes(
                current_tour[-1]["lat"], current_tour[-1]["lng"], origin_lat, origin_lng,
                mode, travel_matrix, current_tour[-1].get("place_id"), origin_id
            )
            travel_total += t_last
            dist_total_km += d_last

            total_span = dwell_total + travel_total
            return total_span, travel_total, dwell_total, round(dist_total_km, 2)

        def tour_respects_meal_windows(t_list: List[Dict[str, Any]]) -> bool:
            cur_elapsed = 0
            p_lat, p_lng, p_id = origin_lat, origin_lng, origin_id
            for item in t_list:
                t_leg, _ = estimate_transit_time_minutes(
                    p_lat, p_lng, item["lat"], item["lng"],
                    mode, travel_matrix, p_id, item.get("place_id")
                )
                cur_elapsed += t_leg
                arr_dt = start_clock_dt + timedelta(minutes=cur_elapsed)
                arr_m = get_minute_of_day(arr_dt)
                m_type = item.get("meal_type")
                if m_type and m_type in DEFAULT_MEAL_PERIODS:
                    mp = DEFAULT_MEAL_PERIODS[m_type]
                    if not (mp.start_minute <= arr_m <= mp.end_minute):
                        return False
                cur_elapsed += item.get("dwell_mins", 60)
                p_lat, p_lng, p_id = item["lat"], item["lng"], item.get("place_id")
            return True

        def adjust_dwell_times_for_budget(tour_to_adjust: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
            """Expands dwell times if under budget or cleanly compresses if over budget."""
            if not tour_to_adjust:
                return tour_to_adjust

            total_span, cur_travel, _, _ = calculate_loop_metrics(tour_to_adjust)
            cur_buffer = calculate_safety_buffer_mins(cur_travel)
            max_activity_budget = total_budget_mins - cur_buffer

            # 1. Expand dwell times if significantly under budget
            if total_span < max_activity_budget - 45:
                slack_to_fill = max_activity_budget - total_span - 15
                for p in tour_to_adjust:
                    if slack_to_fill <= 0:
                        break
                    model = get_category_visit_duration(p, p.get("meal_type"))
                    cur_d = p.get("dwell_mins", model.default_minutes)
                    max_d = model.max_minutes
                    expandable = max(0, max_d - cur_d)
                    if expandable > 0:
                        added = min(expandable, min(slack_to_fill, 30))
                        snapped_added = int(round(added / 15.0) * 15)
                        if snapped_added > 0:
                            p["dwell_mins"] = cur_d + snapped_added
                            p["visit_duration"] = p["dwell_mins"]
                            if not tour_respects_meal_windows(tour_to_adjust):
                                p["dwell_mins"] = cur_d
                                p["visit_duration"] = cur_d
                            else:
                                slack_to_fill -= snapped_added

            # 2. Compress dwell times cleanly if over budget
            total_span, cur_travel, _, _ = calculate_loop_metrics(tour_to_adjust)
            cur_buffer = calculate_safety_buffer_mins(cur_travel)
            if (total_span + cur_buffer) > total_budget_mins:
                excess = (total_span + cur_buffer) - total_budget_mins
                for p in tour_to_adjust:
                    cur_d = p.get("dwell_mins", 60)
                    model = get_category_visit_duration(p, p.get("meal_type"))
                    min_viable_dwell = model.min_minutes
                    reducible = max(0, cur_d - min_viable_dwell)
                    reduction = min(excess, reducible)
                    snapped_reduction = int(round(reduction / 15.0) * 15)
                    if snapped_reduction > 0:
                        p["dwell_mins"] = max(min_viable_dwell, cur_d - snapped_reduction)
                        p["visit_duration"] = p["dwell_mins"]
                        excess -= snapped_reduction
                    if excess <= 0:
                        break

            # 3. Prune lowest-utility stops if still over budget
            while tour_to_adjust and (calculate_loop_metrics(tour_to_adjust)[0] + calculate_safety_buffer_mins(calculate_loop_metrics(tour_to_adjust)[1])) > total_budget_mins:
                worst_idx = min(
                    range(len(tour_to_adjust)),
                    key=lambda i: tour_to_adjust[i].get("score_breakdown").final_score
                    if isinstance(tour_to_adjust[i].get("score_breakdown"), PlaceScoreBreakdown) else 0.0
                )
                tour_to_adjust.pop(worst_idx)
                if tour_to_adjust:
                    tour_to_adjust = two_opt_optimize_loop(
                        tour_to_adjust, origin_lat, origin_lng, mode, travel_matrix, origin_id,
                        start_time_clock=start_time_clock, allow_adjacent_food=allow_adjacent_food,
                        max_consecutive_same_category=max_consecutive_same_category
                    )

            return tour_to_adjust

        # -------------------------------------------------------------------
        # Candidate Tour Construction from Seed
        # -------------------------------------------------------------------
        def build_candidate_tour_from_seed(seed_bd: PlaceScoreBreakdown) -> List[Dict[str, Any]]:
            raw_seed = cand_map[seed_bd.place_id]
            seed_entry = dict(raw_seed)
            t_out_seed, _ = estimate_transit_time_minutes(
                origin_lat, origin_lng, raw_seed["lat"], raw_seed["lng"], mode, travel_matrix, origin_id, seed_bd.place_id
            )
            t_back_seed, _ = estimate_transit_time_minutes(
                raw_seed["lat"], raw_seed["lng"], origin_lat, origin_lng, mode, travel_matrix, seed_bd.place_id, origin_id
            )
            seed_model = get_category_visit_duration(raw_seed)
            seed_dwell = seed_model.default_minutes
            max_possible_dwell = total_budget_mins - (t_out_seed + t_back_seed)
            if seed_dwell > max_possible_dwell and max_possible_dwell >= seed_model.min_minutes:
                seed_dwell = int(round(max_possible_dwell / 15.0) * 15)
                seed_dwell = max(seed_model.min_minutes, seed_dwell)

            seed_entry["dwell_mins"] = seed_dwell
            seed_entry["visit_duration"] = seed_dwell
            seed_entry["travel_time_from_previous"] = t_out_seed
            seed_entry["score_breakdown"] = seed_bd

            tour_seed: List[Dict[str, Any]] = [seed_entry]
            selected_pids = {seed_bd.place_id}
            selected_geos = {(round(raw_seed["lat"], 4), round(raw_seed["lng"], 4))}
            selected_cats: List[str] = [seed_entry["category"]]
            claimed_meals: Set[str] = set()
            if seed_entry.get("meal_type"):
                claimed_meals.add(seed_entry["meal_type"])

            # Greedy insertion loop
            while len(tour_seed) < max_stops:
                best_cand_entry = None
                best_insert_pos = -1
                best_efficiency = -1.0
                current_span, current_travel, _, _ = calculate_loop_metrics(tour_seed)

                for cand_bd in reachable_candidates:
                    pid = cand_bd.place_id
                    if pid in selected_pids:
                        continue
                    raw_c = cand_map.get(pid)
                    if not raw_c:
                        continue
                    geo_key = (round(raw_c["lat"], 4), round(raw_c["lng"], 4))
                    if geo_key in selected_geos:
                        continue

                    c_cat = str(raw_c.get("category") or raw_c.get("type") or "attraction").lower()
                    c_canon_cat = get_canonical_stop_category(raw_c)
                    is_rest = is_restaurant_venue(raw_c)
                    is_food = is_food_candidate(raw_c)

                    if is_rest and not eligible_meal_periods and not allow_adjacent_food:
                        continue
                    if is_rest and not allow_adjacent_food and len(claimed_meals) >= len(eligible_meal_periods):
                        continue
                    if is_rest and not allow_adjacent_food and total_budget_mins <= 360 and len(claimed_meals) >= 1:
                        continue
                    if not is_rest and not explicit_category_set and selected_cats.count(c_cat) >= 3:
                        continue

                    c_lat = raw_c["lat"]
                    c_lng = raw_c["lng"]

                    for k in range(len(tour_seed) + 1):
                        projected_elapsed = 0
                        p_prev_lat, p_prev_lng, p_prev_id = origin_lat, origin_lng, origin_id
                        for s_idx in range(k):
                            s_item = tour_seed[s_idx]
                            t_leg, _ = estimate_transit_time_minutes(
                                p_prev_lat, p_prev_lng, s_item["lat"], s_item["lng"],
                                mode, travel_matrix, p_prev_id, s_item.get("place_id")
                            )
                            projected_elapsed += t_leg + s_item.get("dwell_mins", 60)
                            p_prev_lat, p_prev_lng, p_prev_id = s_item["lat"], s_item["lng"], s_item.get("place_id")

                        t_to_trial, _ = estimate_transit_time_minutes(
                            p_prev_lat, p_prev_lng, c_lat, c_lng,
                            mode, travel_matrix, p_prev_id, pid
                        )
                        arrival_elapsed = projected_elapsed + t_to_trial
                        arrival_dt = start_clock_dt + timedelta(minutes=arrival_elapsed)
                        arr_minute = get_minute_of_day(arrival_dt)

                        matching_mp = None
                        if is_rest:
                            for mp in eligible_meal_periods:
                                if mp.name in claimed_meals:
                                    continue
                                if mp.start_minute <= arr_minute <= mp.end_minute:
                                    op_start, op_close = get_place_operating_window(raw_c)
                                    if op_start <= arr_minute and (arr_minute + mp.min_dwell_mins) <= op_close:
                                        matching_mp = mp
                                        break
                            if not matching_mp:
                                continue
                            c_dwell = matching_mp.default_dwell_mins
                        else:
                            c_dwell = determine_default_dwell_mins(raw_c)

                        trial_entry = dict(raw_c)
                        trial_entry["lat"] = c_lat
                        trial_entry["lng"] = c_lng
                        trial_entry["dwell_mins"] = c_dwell
                        trial_entry["visit_duration"] = c_dwell
                        trial_entry["score_breakdown"] = cand_bd
                        if matching_mp:
                            trial_entry["meal_type"] = matching_mp.name
                            trial_entry["matching_meal_period"] = matching_mp.name
                        else:
                            trial_entry["meal_type"] = None

                        trial_tour = tour_seed[:k] + [trial_entry] + tour_seed[k:]

                        if violates_consecutive_category_limit(trial_tour, max_consecutive=max_consecutive_same_category):
                            continue

                        trial_span, trial_travel, trial_visit, _ = calculate_loop_metrics(trial_tour)
                        added_span = trial_span - current_span
                        trial_buffer = calculate_safety_buffer_mins(trial_travel)

                        if (trial_span + trial_buffer) <= total_budget_mins and added_span > 0:
                            if not tour_respects_meal_windows(trial_tour):
                                continue

                            is_adjacent_same_cat = False
                            if k > 0 and get_canonical_stop_category(tour_seed[k-1]) == c_canon_cat:
                                is_adjacent_same_cat = True
                            elif k < len(tour_seed) and get_canonical_stop_category(tour_seed[k]) == c_canon_cat:
                                is_adjacent_same_cat = True

                            soft_diversity_mult = 0.92 if is_adjacent_same_cat else 1.0

                            prior_matches = sum(1 for sc in selected_cats if normalize_category(sc) == c_canon_cat)
                            saturation_mult = (0.85 ** max(0, prior_matches - 1)) if prior_matches >= 2 else 1.0

                            post_meal_mult = 1.0
                            if not is_food and k > 0 and is_food_candidate(tour_seed[k-1]):
                                post_meal_mult = 1.35

                            meal_timing_mult = 1.25 if is_rest else 1.0
                            added_travel = max(1, trial_travel - current_travel)
                            travel_detour_cost = max(3.0, float(added_travel))

                            c_tourism_sig = calculate_tourism_significance(raw_c)
                            cand_priority = cand_bd.final_score * 0.70 + c_tourism_sig * 0.30

                            efficiency = (cand_priority * soft_diversity_mult * saturation_mult * meal_timing_mult * post_meal_mult) / travel_detour_cost
                            if efficiency > best_efficiency or (abs(efficiency - best_efficiency) < 1e-6 and k > best_insert_pos):
                                best_efficiency = efficiency
                                best_cand_entry = trial_entry
                                best_insert_pos = k

                if best_cand_entry and best_insert_pos >= 0:
                    tour_seed.insert(best_insert_pos, best_cand_entry)
                    selected_pids.add(best_cand_entry["place_id"])
                    selected_geos.add((round(best_cand_entry["lat"], 4), round(best_cand_entry["lng"], 4)))
                    selected_cats.append(best_cand_entry["category"])
                    if best_cand_entry.get("matching_meal_period"):
                        claimed_meals.add(best_cand_entry["matching_meal_period"])
                else:
                    break

            # 2-Opt local search
            tour_seed = two_opt_optimize_loop(
                tour_seed, origin_lat, origin_lng, mode, travel_matrix, origin_id,
                start_time_clock=start_time_clock, allow_adjacent_food=allow_adjacent_food,
                max_consecutive_same_category=max_consecutive_same_category
            )

            # Meal pacing adjustment & anti-adjacency
            if len(tour_seed) >= 2 and not allow_adjacent_food:
                first_is_premature_meal = False
                if is_food_candidate(tour_seed[0]):
                    m_type = tour_seed[0].get("meal_type")
                    if m_type and m_type in DEFAULT_MEAL_PERIODS:
                        mp = DEFAULT_MEAL_PERIODS[m_type]
                        t_first, _ = estimate_transit_time_minutes(
                            origin_lat, origin_lng, tour_seed[0]["lat"], tour_seed[0]["lng"], mode, travel_matrix, origin_id, tour_seed[0].get("place_id")
                        )
                        first_arr_m = start_minute + t_first
                        if first_arr_m < mp.start_minute:
                            first_is_premature_meal = True
                    elif is_early_start:
                        first_is_premature_meal = True

                if first_is_premature_meal:
                    for swap_idx in range(1, len(tour_seed)):
                        if not is_food_candidate(tour_seed[swap_idx]):
                            tour_seed[0], tour_seed[swap_idx] = tour_seed[swap_idx], tour_seed[0]
                            break

                seen_meals = set()
                prune_indices = []
                for idx, p in enumerate(tour_seed):
                    m_type = p.get("meal_type")
                    if m_type:
                        if m_type in seen_meals:
                            prune_indices.append(idx)
                        else:
                            seen_meals.add(m_type)
                for idx in reversed(prune_indices):
                    tour_seed.pop(idx)

                consecutive_food_count = 0
                for idx in range(len(tour_seed)):
                    if is_food_candidate(tour_seed[idx]):
                        consecutive_food_count += 1
                        if consecutive_food_count > max_consecutive_same_category:
                            for alt_idx in range(len(tour_seed)):
                                if not is_food_candidate(tour_seed[alt_idx]):
                                    item = tour_seed.pop(alt_idx)
                                    tour_seed.insert(idx, item)
                                    break
                            break
                    else:
                        consecutive_food_count = 0

                tour_seed = two_opt_optimize_loop(
                    tour_seed, origin_lat, origin_lng, mode, travel_matrix, origin_id,
                    start_time_clock=start_time_clock, allow_adjacent_food=allow_adjacent_food,
                    max_consecutive_same_category=max_consecutive_same_category
                )

            # Dwell adjustment to respect total budget
            tour_seed = adjust_dwell_times_for_budget(tour_seed)
            return tour_seed

        # -------------------------------------------------------------------
        # Candidate Replacement / Backtracking Improvement (Option B / LNS)
        # -------------------------------------------------------------------
        def improve_tour_with_candidate_replacement(
            initial_tour: List[Dict[str, Any]],
            current_route_score: float
        ) -> Tuple[List[Dict[str, Any]], float]:
            """
            Option B / LNS: 1-remove-1-insert candidate replacement.
            Tests replacing each stop in the tour with an unused reachable candidate.
            If the replacement is feasible, respects all hard constraints, and yields
            a higher holistic route score, the replacement is committed.
            """
            if not initial_tour:
                return initial_tour, 0.0

            best_t = [dict(p) for p in initial_tour]
            best_s = current_route_score

            for _ in range(2):
                made_improvement = False
                for i in range(len(best_t)):
                    old_stop = best_t[i]
                    current_tour_pids = {p.get("place_id") for p in best_t}

                    candidate_pool = [
                        bd for bd in reachable_candidates
                        if bd.place_id not in current_tour_pids
                    ]
                    candidate_pool.sort(
                        key=lambda bd: (
                            bd.final_score * 0.65 +
                            calculate_tourism_significance(cand_map.get(bd.place_id, {})) * 0.35
                        ),
                        reverse=True
                    )

                    for cand_bd in candidate_pool[:8]:
                        raw_c = cand_map.get(cand_bd.place_id)
                        if not raw_c:
                            continue

                        geo_key = (round(raw_c["lat"], 4), round(raw_c["lng"], 4))
                        other_geos = {
                            (round(p["lat"], 4), round(p["lng"], 4))
                            for idx_p, p in enumerate(best_t) if idx_p != i
                        }
                        if geo_key in other_geos:
                            continue

                        is_rest = is_restaurant_venue(raw_c)
                        is_c_food = is_rest or is_food_candidate(raw_c)
                        if not allow_adjacent_food and is_c_food:
                            if not eligible_meal_periods:
                                continue
                            current_food = sum(1 for idx_p, p in enumerate(best_t) if idx_p != i and (is_restaurant_venue(p) or is_food_candidate(p)))
                            if total_budget_mins <= 360 and current_food >= 1:
                                continue
                            if current_food >= len(eligible_meal_periods):
                                continue

                        c_dwell = determine_default_dwell_mins(raw_c)
                        trial_entry = dict(raw_c)
                        trial_entry["lat"] = raw_c["lat"]
                        trial_entry["lng"] = raw_c["lng"]
                        trial_entry["dwell_mins"] = c_dwell
                        trial_entry["visit_duration"] = c_dwell
                        trial_entry["score_breakdown"] = cand_bd
                        trial_entry["meal_type"] = old_stop.get("meal_type") if is_rest else None

                        trial_tour = best_t[:i] + [trial_entry] + best_t[i+1:]

                        if violates_consecutive_category_limit(trial_tour, max_consecutive=max_consecutive_same_category):
                            continue

                        if not allow_adjacent_food:
                            has_adj = any(
                                (is_food_candidate(trial_tour[chk]) or is_restaurant_venue(trial_tour[chk])) and
                                (is_food_candidate(trial_tour[chk+1]) or is_restaurant_venue(trial_tour[chk+1]))
                                for chk in range(len(trial_tour) - 1)
                            )
                            if has_adj:
                                continue

                        opt_tour = two_opt_optimize_loop(
                            trial_tour, origin_lat, origin_lng, mode, travel_matrix, origin_id,
                            start_time_clock=start_time_clock, allow_adjacent_food=allow_adjacent_food,
                            max_consecutive_same_category=max_consecutive_same_category
                        )

                        if not allow_adjacent_food:
                            has_adj_opt = any(
                                (is_food_candidate(opt_tour[chk]) or is_restaurant_venue(opt_tour[chk])) and
                                (is_food_candidate(opt_tour[chk+1]) or is_restaurant_venue(opt_tour[chk+1]))
                                for chk in range(len(opt_tour) - 1)
                            )
                            if has_adj_opt:
                                continue

                        if not tour_respects_meal_windows(opt_tour):
                            continue

                        span, travel, visit, _ = calculate_loop_metrics(opt_tour)
                        if (span + calculate_safety_buffer_mins(travel)) > total_budget_mins:
                            continue

                        cand_route_score = calculate_route_score(
                            opt_tour, total_budget_mins, travel, visit,
                            user_interests=user_interests,
                            explicit_categories=explicit_category_set,
                            config=cfg_route
                        )

                        if cand_route_score > best_s + 0.5:
                            best_t = opt_tour
                            best_s = cand_route_score
                            made_improvement = True
                            break

                if not made_improvement:
                    break

            best_t = adjust_dwell_times_for_budget(best_t)
            return best_t, best_s

        # -------------------------------------------------------------------
        # Identify Diverse Candidate Seeds (Option C)
        # -------------------------------------------------------------------
        seed_candidates: List[PlaceScoreBreakdown] = []
        seen_seed_ids: Set[str] = set()

        def add_seed(bd: PlaceScoreBreakdown):
            if bd.place_id not in seen_seed_ids:
                seen_seed_ids.add(bd.place_id)
                seed_candidates.append(bd)

        # 1. Landmark Seed (highest tourism significance)
        non_food_reachable = [
            bd for bd in reachable_candidates
            if allow_adjacent_food or not (is_restaurant_venue(cand_map.get(bd.place_id, {})) or is_food_candidate(cand_map.get(bd.place_id, {})))
        ]
        pool_for_seeds = non_food_reachable if non_food_reachable else reachable_candidates

        landmark_seed = max(
            pool_for_seeds,
            key=lambda bd: calculate_tourism_significance(cand_map.get(bd.place_id, {}))
        )
        add_seed(landmark_seed)

        # 2. Preference / Vibe Seed (highest interest match)
        if interests_str:
            vibe_seed = max(
                pool_for_seeds,
                key=lambda bd: float(getattr(bd, "interest_match_score", 0.0) or 0.0)
            )
            add_seed(vibe_seed)

        # 3. Overall Quality Seed (highest Bayesian score)
        quality_seed = max(
            pool_for_seeds,
            key=lambda bd: bd.final_score
        )
        add_seed(quality_seed)

        # 4. Diverse category seeds (top place for each canonical category)
        cat_seen = set()
        for bd in sorted(pool_for_seeds, key=lambda b: b.final_score, reverse=True):
            raw_p = cand_map.get(bd.place_id, {})
            cat = get_canonical_stop_category(raw_p)
            if cat not in cat_seen:
                cat_seen.add(cat)
                add_seed(bd)
            if len(seed_candidates) >= 5:
                break

        # -------------------------------------------------------------------
        # Multi-Seed Generation & Route Evaluation Loop
        # -------------------------------------------------------------------
        best_tour: List[Dict[str, Any]] = []
        best_route_score: float = -1.0

        for seed_bd in seed_candidates:
            cand_tour = build_candidate_tour_from_seed(seed_bd)
            if not cand_tour:
                continue

            span, travel, visit, _ = calculate_loop_metrics(cand_tour)
            cand_score = calculate_route_score(
                cand_tour, total_budget_mins, travel, visit,
                user_interests=user_interests,
                explicit_categories=explicit_category_set,
                config=cfg_route
            )

            # Option B: Candidate replacement improvement
            improved_tour, improved_score = improve_tour_with_candidate_replacement(
                cand_tour, cand_score
            )

            if improved_score > best_route_score or not best_tour:
                best_route_score = improved_score
                best_tour = improved_tour

        tour = best_tour

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

        selected_place_ids = {p.get("place_id") for p in tour}
        selected_categories = [p.get("category") for p in tour]

        # -------------------------------------------------------------------
        # Step 8: Construct Concrete Timetable and Standard Output Data
        # -------------------------------------------------------------------
        current_dt = parse_clock_time(start_time_clock)

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
            arrival_dt = current_dt
            arrival_clock = arrival_dt.strftime("%I:%M %p")
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

            arr_m = get_minute_of_day(arrival_dt)
            curr_mp = None
            for mp in DEFAULT_MEAL_PERIODS.values():
                if mp.start_minute <= arr_m <= mp.end_minute:
                    curr_mp = mp.name
                    break
            stop_meal_type = curr_mp if is_restaurant_venue(p) else p.get("meal_type")

            stop_cat = "food" if stop_meal_type or is_food_candidate(p) else (p.get("category") or p.get("type") or "attraction")
            stop_obj = ScheduledItineraryStop(
                stop_index=idx + 1,
                place_id=p_id or f"stop_{idx+1}",
                name=p.get("name") or "Local Venue",
                category=stop_cat,
                lat=p["lat"],
                lng=p["lng"],
                address=p.get("address") or "",
                rating=safe_float(p.get("rating"), 4.5),
                review_count=safe_int(p.get("user_rating_count") or p.get("review_count"), 150),
                price_level=p.get("price_level") or "$$ (Moderate)",
                duration_mins=dwell_mins,
                duration_hours=round(dwell_mins / 60.0, 2),
                visit_duration=dwell_mins,
                travel_time_from_previous=t_leg,
                time_estimate_reason=time_reason,
                ai_reasoning=ai_reason,
                arrival_rel_mins=arrival_rel,
                departure_rel_mins=departure_rel,
                arrival_clock=arrival_clock,
                departure_clock=departure_clock,
                transit_from_prev_mins=t_leg,
                transit_from_prev_km=d_leg,
                score_breakdown=score_dict,
                selection_reasons=reasons,
                meal_type=stop_meal_type
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
        rejected_destinations_list: List[Dict[str, Any]] = list(ineligible_candidates_log)
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
                selected_categories=tour_cats,
                explicit_categories=list(explicit_category_set) if explicit_category_set else None,
                allow_iconic_landmarks=allow_iconic_landmarks
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
            "travel_time_minutes": total_travel,
            "total_visit_time": total_visit,
            "visit_time_minutes": total_visit,
            "safety_buffer": calculate_safety_buffer_mins(total_travel),
            "safety_buffer_mins": calculate_safety_buffer_mins(total_travel),
            "safety_buffer_minutes": calculate_safety_buffer_mins(total_travel),
            "total_duration": total_span,
            "total_duration_minutes": total_span + calculate_safety_buffer_mins(total_travel),
            "total_distance": total_dist,
            "score": best_route_score if best_route_score >= 0 else avg_score,
            "route_score": best_route_score if best_route_score >= 0 else avg_score,
            "average_destination_score": avg_score,
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
            "route_score": 0.0,
            "average_destination_score": 0.0,
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
    max_destinations: Optional[int] = None,
    start_time_clock: str = "09:30 AM",
    selected_categories: Optional[List[str]] = None,
    allow_iconic_landmarks: bool = False,
    max_consecutive_same_category: int = 2,
    route_scoring_config: Optional[RouteScoringConfig] = None
) -> Dict[str, Any]:
    """
    Stand-alone functional interface matching the exact problem specification.
    """
    optimizer = RouteOptimizer(config=scoring_config, route_scoring_config=route_scoring_config)
    return optimizer.optimize(
        start_location=start_location,
        available_time_minutes=available_time_minutes,
        transportation_mode=transportation_mode,
        user_interests=user_interests,
        candidate_places=candidate_places or [],
        travel_matrix=travel_matrix,
        max_destinations=max_destinations,
        start_time_clock=start_time_clock,
        selected_categories=selected_categories,
        allow_iconic_landmarks=allow_iconic_landmarks,
        max_consecutive_same_category=max_consecutive_same_category,
        route_scoring_config=route_scoring_config
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
    scoring_config: Optional[ScoringConfig] = None,
    selected_categories: Optional[List[str]] = None,
    allow_iconic_landmarks: bool = False,
    max_consecutive_same_category: int = 2,
    route_scoring_config: Optional[RouteScoringConfig] = None
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
        scoring_config=scoring_config,
        start_time_clock=start_time_clock,
        selected_categories=selected_categories,
        allow_iconic_landmarks=allow_iconic_landmarks,
        max_consecutive_same_category=max_consecutive_same_category,
        route_scoring_config=route_scoring_config
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
            duration_mins=s.get("visit_duration", s.get("duration_mins", 45)),
            duration_hours=s.get("duration_hours", round(s.get("duration_mins", 45) / 60.0, 2)),
            visit_duration=s.get("visit_duration", s.get("duration_mins", 45)),
            travel_time_from_previous=s.get("travel_time_from_previous", s.get("transit_from_prev_mins", 0)),
            time_estimate_reason=s["time_estimate_reason"],
            ai_reasoning=s["ai_reasoning"],
            arrival_rel_mins=s["arrival_rel_mins"],
            departure_rel_mins=s["departure_rel_mins"],
            arrival_clock=s["arrival_time"],
            departure_clock=s["departure_time"],
            transit_from_prev_mins=s.get("travel_time_from_previous", s.get("transit_from_prev_mins", 0)),
            transit_from_prev_km=s["transit_from_prev_km"],
            score_breakdown=s.get("score_breakdown", {}),
            selection_reasons=s.get("selection_reasons", []),
            meal_type=s.get("meal_type")
        ))

    ret_leg = raw_res.get("return_to_start", {})
    return_leg_data = {
        "duration_mins": ret_leg.get("duration_minutes", 0),
        "duration_text": ret_leg.get("duration_text", "0 mins"),
        "distance_km": ret_leg.get("distance_km", 0.0),
        "distance_text": ret_leg.get("distance_text", "0.0 km"),
        "destination": ret_leg.get("destination", origin_name),
        "final_return_clock": ret_leg.get("arrival_clock", start_time_clock),
        "arrival_clock": ret_leg.get("arrival_clock", start_time_clock)
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
        safety_buffer_mins=raw_res.get('safety_buffer_minutes', calculate_safety_buffer_mins(raw_res.get('total_travel_time', 0))),
        start_clock=start_time_clock,
        end_clock=ret_leg.get("arrival_clock", start_time_clock),
        return_leg=return_leg_data,
        legs_data=raw_res.get("legs", []),
        route_score=raw_res.get("score", 0.0),
        rejected_destinations=raw_res.get("rejected_destinations", [])
    )
