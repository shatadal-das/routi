"""
RoamAround / Routi - Centralized Category Taxonomy & Landmark Policy Module

Defines canonical category taxonomies, case-insensitive alias normalization,
multi-attribute venue category resolution, and deterministic iconic landmark detection.
"""

from typing import Dict, Any, List, Set, Optional
import re


# ---------------------------------------------------------------------------
# Canonical Categories
# ---------------------------------------------------------------------------
CATEGORY_NATURE = "nature"
CATEGORY_FOOD = "food"
CATEGORY_CAFE = "cafe"
CATEGORY_CULTURE = "culture"
CATEGORY_VIEWPOINT = "viewpoint"
CATEGORY_WATERFRONT = "waterfront"
CATEGORY_SHOPPING = "shopping"
CATEGORY_LANDMARK = "landmark"

CANONICAL_CATEGORIES = {
    CATEGORY_NATURE,
    CATEGORY_FOOD,
    CATEGORY_CAFE,
    CATEGORY_CULTURE,
    CATEGORY_VIEWPOINT,
    CATEGORY_WATERFRONT,
    CATEGORY_SHOPPING,
    CATEGORY_LANDMARK,
}

# ---------------------------------------------------------------------------
# Alias Mapping (Input variant -> Canonical ID)
# ---------------------------------------------------------------------------
CATEGORY_ALIAS_MAP: Dict[str, str] = {
    # Nature & Parks
    "nature": CATEGORY_NATURE,
    "nature & parks": CATEGORY_NATURE,
    "nature and parks": CATEGORY_NATURE,
    "park": CATEGORY_NATURE,
    "parks": CATEGORY_NATURE,
    "parks & gardens": CATEGORY_NATURE,
    "parks and gardens": CATEGORY_NATURE,
    "garden": CATEGORY_NATURE,
    "gardens": CATEGORY_NATURE,
    "botanical": CATEGORY_NATURE,
    "botanical_garden": CATEGORY_NATURE,
    "botanical garden": CATEGORY_NATURE,
    "arboretum": CATEGORY_NATURE,
    "nature_reserve": CATEGORY_NATURE,
    "nature reserve": CATEGORY_NATURE,
    "campground": CATEGORY_NATURE,
    "national_park": CATEGORY_NATURE,
    "national park": CATEGORY_NATURE,
    "forest": CATEGORY_NATURE,
    "greenery": CATEGORY_NATURE,
    "trail": CATEGORY_NATURE,
    "hiking": CATEGORY_NATURE,

    # Food & Dining
    "food": CATEGORY_FOOD,
    "dining": CATEGORY_FOOD,
    "dining & food": CATEGORY_FOOD,
    "dining and food": CATEGORY_FOOD,
    "food & dining": CATEGORY_FOOD,
    "restaurant": CATEGORY_FOOD,
    "restaurants": CATEGORY_FOOD,
    "eatery": CATEGORY_FOOD,
    "bistro": CATEGORY_FOOD,
    "diner": CATEGORY_FOOD,
    "pizzeria": CATEGORY_FOOD,
    "steakhouse": CATEGORY_FOOD,
    "meal_takeaway": CATEGORY_FOOD,
    "meal_delivery": CATEGORY_FOOD,
    "food_court": CATEGORY_FOOD,
    "dhaba": CATEGORY_FOOD,
    "bar": CATEGORY_FOOD,
    "pub": CATEGORY_FOOD,
    "gastropub": CATEGORY_FOOD,

    # Cafes & Coffee
    "cafe": CATEGORY_CAFE,
    "cafes": CATEGORY_CAFE,
    "coffee": CATEGORY_CAFE,
    "cafes & coffee": CATEGORY_CAFE,
    "cafes and coffee": CATEGORY_CAFE,
    "coffee & cafe": CATEGORY_CAFE,
    "bakery": CATEGORY_CAFE,
    "bakeries": CATEGORY_CAFE,
    "coffee_shop": CATEGORY_CAFE,
    "coffee shop": CATEGORY_CAFE,
    "roastery": CATEGORY_CAFE,
    "tea": CATEGORY_CAFE,
    "tea_house": CATEGORY_CAFE,
    "tea house": CATEGORY_CAFE,
    "espresso_bar": CATEGORY_CAFE,

    # Culture & Art
    "culture": CATEGORY_CULTURE,
    "art": CATEGORY_CULTURE,
    "art & culture": CATEGORY_CULTURE,
    "art and culture": CATEGORY_CULTURE,
    "culture & art": CATEGORY_CULTURE,
    "museum": CATEGORY_CULTURE,
    "museums": CATEGORY_CULTURE,
    "art_gallery": CATEGORY_CULTURE,
    "art gallery": CATEGORY_CULTURE,
    "gallery": CATEGORY_CULTURE,
    "monument": CATEGORY_CULTURE,
    "monuments": CATEGORY_CULTURE,
    "historic": CATEGORY_CULTURE,
    "historical": CATEGORY_CULTURE,
    "historical_site": CATEGORY_CULTURE,
    "historical site": CATEGORY_CULTURE,
    "historical_landmark": CATEGORY_CULTURE,
    "historical landmark": CATEGORY_CULTURE,
    "heritage": CATEGORY_CULTURE,
    "heritage site": CATEGORY_CULTURE,
    "palace": CATEGORY_CULTURE,
    "fort": CATEGORY_CULTURE,
    "tomb": CATEGORY_CULTURE,
    "temple": CATEGORY_CULTURE,
    "shrine": CATEGORY_CULTURE,
    "church": CATEGORY_CULTURE,
    "mosque": CATEGORY_CULTURE,
    "cultural_center": CATEGORY_CULTURE,
    "castle": CATEGORY_CULTURE,
    "ruins": CATEGORY_CULTURE,

    # Viewpoints & Scenic Views
    "viewpoint": CATEGORY_VIEWPOINT,
    "viewpoints": CATEGORY_VIEWPOINT,
    "scenic": CATEGORY_VIEWPOINT,
    "scenic views": CATEGORY_VIEWPOINT,
    "scenic view": CATEGORY_VIEWPOINT,
    "scenic_views": CATEGORY_VIEWPOINT,
    "scenic_point": CATEGORY_VIEWPOINT,
    "scenic point": CATEGORY_VIEWPOINT,
    "view": CATEGORY_VIEWPOINT,
    "views": CATEGORY_VIEWPOINT,
    "overlook": CATEGORY_VIEWPOINT,
    "lookout": CATEGORY_VIEWPOINT,
    "observation_deck": CATEGORY_VIEWPOINT,
    "observation deck": CATEGORY_VIEWPOINT,
    "skydeck": CATEGORY_VIEWPOINT,

    # Waterfront
    "waterfront": CATEGORY_WATERFRONT,
    "water": CATEGORY_WATERFRONT,
    "beach": CATEGORY_WATERFRONT,
    "beaches": CATEGORY_WATERFRONT,
    "pier": CATEGORY_WATERFRONT,
    "wharf": CATEGORY_WATERFRONT,
    "marina": CATEGORY_WATERFRONT,
    "lake": CATEGORY_WATERFRONT,
    "lakefront": CATEGORY_WATERFRONT,
    "bay": CATEGORY_WATERFRONT,
    "promenade": CATEGORY_WATERFRONT,
    "riverfront": CATEGORY_WATERFRONT,
    "harbor": CATEGORY_WATERFRONT,
    "coast": CATEGORY_WATERFRONT,

    # Shopping
    "shopping": CATEGORY_SHOPPING,
    "market": CATEGORY_SHOPPING,
    "bazaar": CATEGORY_SHOPPING,
    "mall": CATEGORY_SHOPPING,
    "shopping_mall": CATEGORY_SHOPPING,
    "store": CATEGORY_SHOPPING,
    "flea_market": CATEGORY_SHOPPING,

    # Landmark / Iconic
    "landmark": CATEGORY_LANDMARK,
    "landmarks": CATEGORY_LANDMARK,
    "iconic attraction": CATEGORY_LANDMARK,
    "iconic attractions": CATEGORY_LANDMARK,
    "iconic_attraction": CATEGORY_LANDMARK,
    "major tourist attraction": CATEGORY_LANDMARK,
    "major_attraction": CATEGORY_LANDMARK,
    "major attraction": CATEGORY_LANDMARK,
}


def normalize_category(cat: Optional[str]) -> Optional[str]:
    """
    Normalizes any category identifier, label, or string into its canonical category key.
    Examples:
        'PARK' -> 'nature'
        'Parks & Gardens' -> 'nature'
        'Dining & Food' -> 'food'
        'museum' -> 'culture'
    Returns None if the string cannot be mapped to a known category.
    """
    if not cat or not isinstance(cat, str):
        return None

    cleaned = cat.strip().lower()
    # Strip emojis, punctuation and leading/trailing quotes
    cleaned = re.sub(r'[\U00010000-\U0010ffff]', '', cleaned)
    cleaned = re.sub(r'[^\w\s&]', ' ', cleaned).strip()
    cleaned = re.sub(r'\s+', ' ', cleaned)

    if cleaned in CATEGORY_ALIAS_MAP:
        return CATEGORY_ALIAS_MAP[cleaned]

    # Substring / keyword fallback
    for alias, canonical in CATEGORY_ALIAS_MAP.items():
        if alias == cleaned:
            return canonical

    if any(k in cleaned for k in ["park", "garden", "nature", "botanical"]):
        return CATEGORY_NATURE
    if any(k in cleaned for k in ["restaurant", "dining", "food", "eat"]):
        return CATEGORY_FOOD
    if any(k in cleaned for k in ["cafe", "coffee", "bakery"]):
        return CATEGORY_CAFE
    if any(k in cleaned for k in ["museum", "culture", "art", "monument", "historic", "palace", "fort"]):
        return CATEGORY_CULTURE
    if any(k in cleaned for k in ["view", "scenic", "overlook"]):
        return CATEGORY_VIEWPOINT
    if any(k in cleaned for k in ["water", "beach", "pier", "lake", "marina", "wharf"]):
        return CATEGORY_WATERFRONT
    if any(k in cleaned for k in ["shopping", "bazaar", "market", "mall"]):
        return CATEGORY_SHOPPING
    if any(k in cleaned for k in ["landmark", "iconic"]):
        return CATEGORY_LANDMARK

    return None


def get_venue_canonical_categories(place: Dict[str, Any]) -> Set[str]:
    """
    Determines all canonical categories applicable to a venue by inspecting:
    1. place['category']
    2. place['type']
    3. place['types'] (list of Google Places types)
    4. place['name']
    Returns a set of canonical category keys (e.g. {'nature'}, {'food'}, {'culture'}).
    """
    cats: Set[str] = set()
    if not isinstance(place, dict):
        return cats

    # Check explicit category & type fields
    raw_cat = place.get("category")
    if raw_cat:
        norm = normalize_category(str(raw_cat))
        if norm:
            cats.add(norm)

    raw_type = place.get("type")
    if raw_type:
        norm = normalize_category(str(raw_type))
        if norm:
            cats.add(norm)

    # Check types array
    raw_types = place.get("types")
    if isinstance(raw_types, (list, tuple, set)):
        for t in raw_types:
            norm = normalize_category(str(t))
            if norm:
                cats.add(norm)

    # Check name heuristics if still empty or to supplement
    name = str(place.get("name") or "").lower()
    if any(w in name for w in ["park", "garden", "nursery", "forest", "botanical"]):
        cats.add(CATEGORY_NATURE)
    if any(w in name for w in ["museum", "gallery", "monument", "fort", "palace", "tomb", "temple", "gate"]):
        cats.add(CATEGORY_CULTURE)
    if any(w in name for w in ["restaurant", "bistro", "diner", "dhaba", "kitchen", "grill", "eatery"]):
        cats.add(CATEGORY_FOOD)
    if any(w in name for w in ["cafe", "coffee", "bakery", "roastery"]):
        cats.add(CATEGORY_CAFE)
    if any(w in name for w in ["viewpoint", "overlook", "observation deck", "lookout"]):
        cats.add(CATEGORY_VIEWPOINT)
    if any(w in name for w in ["beach", "pier", "wharf", "marina", "waterfront", "lake"]):
        cats.add(CATEGORY_WATERFRONT)
    if any(w in name for w in ["bazaar", "market", "mall"]):
        cats.add(CATEGORY_SHOPPING)

    # If venue is marked as landmark
    if is_iconic_landmark(place):
        cats.add(CATEGORY_LANDMARK)

    return cats


def is_iconic_landmark(place: Dict[str, Any]) -> bool:
    """
    Deterministically evaluates whether a venue is a recognized major/iconic landmark.
    Major landmarks are distinguished by:
    1. High review volume (e.g. >= 10,000 reviews, or >= 3,000 with landmark tags)
    2. Recognizable monument/heritage name or category keywords
    Generic neighborhood parks, local diners, or small cafes return False.
    """
    if not isinstance(place, dict):
        return False

    name = str(place.get("name") or "").lower()
    raw_cat = str(place.get("category") or place.get("type") or "").lower()
    types_raw = place.get("types")
    types = [str(t).lower() for t in types_raw] if isinstance(types_raw, (list, tuple, set)) else []

    # Check reviews count
    raw_rc = place.get("user_rating_count") or place.get("review_count") or place.get("userRatingCount")
    review_count = 0
    if raw_rc is not None:
        try:
            review_count = int(raw_rc)
        except (ValueError, TypeError):
            review_count = 0

    # Key iconic landmark keywords
    landmark_keywords = [
        "gate", "fort", "palace", "tomb", "akshardham", "taj", "colosseum", "eiffel",
        "red fort", "india gate", "qutub", "humayun", "lotus temple", "statue", "monument",
        "memorial", "historical_landmark", "world_heritage", "unesco", "pyramid",
        "golden gate", "space needle", "louvre", "sagrada", "acropolis", "coit tower"
    ]

    has_keyword = any(kw in name for kw in landmark_keywords)
    has_landmark_type = any(t in ["historical_landmark", "monument"] for t in types)
    has_landmark_cat = raw_cat in ["monument", "historic", "major_attraction", "landmark"]

    # Explicit iconic tag
    if place.get("is_landmark") is True or place.get("is_iconic") is True:
        return True

    # Generic parks, gardens, restaurants, and cafes should not become iconic landmark exceptions
    if raw_cat in ["park", "garden", "restaurant", "cafe", "dining", "bar"] and not has_landmark_cat:
        if not any(kw in name for kw in ["red fort", "india gate", "qutub minar", "humayun's tomb", "taj", "colosseum", "eiffel", "acropolis", "pyramid", "versailles"]):
            return False

    # High review threshold + landmark signal
    if review_count >= 15000:
        if (has_keyword and (has_landmark_cat or has_landmark_type)) or has_landmark_cat:
            return True

    if review_count >= 3000:
        if has_keyword and (has_landmark_cat or has_landmark_type):
            return True

    # Explicit iconic monument name hit with decent review confidence
    if has_keyword and review_count >= 800:
        if any(kw in name for kw in ["red fort", "india gate", "qutub minar", "humayun's tomb", "coit tower", "eiffel", "colosseum", "taj"]):
            return True
        if has_landmark_cat or "monument" in types or "historical_landmark" in types:
            return True

    return False


def calculate_tourism_significance(place: Dict[str, Any]) -> float:
    """
    Computes a generalized, continuous tourism significance score (0.0 to 100.0)
    for any destination worldwide based on:
    - Review volume (log-scaled indicator of global/city-wide prominence)
    - Rating quality
    - Historical/heritage/monument category and type signals
    - Iconic landmark detection
    Generic neighborhood parks, local diners, and small cafes receive low scores (10-35),
    while world-class landmarks, monuments, and UNESCO sites receive high scores (75-100).
    """
    if not isinstance(place, dict):
        return 20.0

    name = str(place.get("name") or "").lower()
    raw_cat = str(place.get("category") or place.get("type") or "").lower()
    types_raw = place.get("types")
    types = [str(t).lower() for t in types_raw] if isinstance(types_raw, (list, tuple, set)) else []

    # Rating
    raw_rating = place.get("rating")
    try:
        rating = float(raw_rating) if raw_rating is not None else 4.0
    except (ValueError, TypeError):
        rating = 4.0

    # Review count
    raw_rc = place.get("user_rating_count") or place.get("review_count") or place.get("userRatingCount")
    review_count = 0
    if raw_rc is not None:
        try:
            review_count = int(raw_rc)
        except (ValueError, TypeError):
            review_count = 0

    score = 20.0  # Baseline

    # 1. Iconic landmark status
    if is_iconic_landmark(place) or place.get("is_landmark") is True or place.get("is_iconic") is True:
        score += 35.0

    # 2. Review volume prominence (log curve up to 50,000 reviews)
    if review_count >= 25000:
        score += 30.0
    elif review_count >= 10000:
        score += 24.0
    elif review_count >= 3000:
        score += 18.0
    elif review_count >= 1000:
        score += 12.0
    elif review_count >= 300:
        score += 6.0

    # 3. Monument / Heritage / Culture type signals
    heritage_keywords = [
        "gate", "fort", "palace", "tomb", "monument", "memorial", "temple",
        "heritage", "unesco", "castle", "historic", "ruins", "tower", "cathedral"
    ]
    has_heritage_kw = any(kw in name for kw in heritage_keywords)
    if has_heritage_kw:
        score += 12.0

    if any(t in types for t in ["historical_landmark", "monument", "tourist_attraction", "museum"]):
        score += 10.0
    elif raw_cat in ["monument", "historic", "culture", "museum", "landmark"]:
        score += 10.0

    # 4. Rating boost
    if rating >= 4.7:
        score += 8.0
    elif rating >= 4.4:
        score += 4.0

    # 5. Penalties for purely commercial / neighborhood venues
    is_food = any(fc in raw_cat for fc in ["restaurant", "cafe", "food", "dining", "bakery", "bar", "pub"]) or any(t in types for t in ["restaurant", "cafe", "food"])
    if is_food and not (place.get("is_landmark") is True or place.get("is_iconic") is True):
        score = min(score, 35.0)

    is_generic_park = raw_cat in ["park", "garden"] and not has_heritage_kw and not is_iconic_landmark(place) and review_count < 5000
    if is_generic_park:
        score = min(score, 45.0)

    return round(max(5.0, min(100.0, score)), 1)

