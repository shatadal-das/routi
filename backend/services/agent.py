"""
RoamAround / Routi - AI Agent & Tool Calling Engine

Integrates OpenAI Python client (AWS Bedrock / google.gemma-3-27b-it) as an autonomous travel concierge.
The agent uses tools (place scoring, loop optimization, timetable generation)
to curate personalized itineraries with rich day-flow narratives.
"""

import os
import json
import re
from typing import List, Dict, Any, Optional, Tuple
from dotenv import load_dotenv

from services.llm_client import (
    get_openai_client,
    call_llm_json,
    DEFAULT_MODEL
)
from services.scorer import score_and_rank_candidates, ScoringConfig
from services.optimizer import optimize_day_itinerary, OptimizedItineraryPlan, calculate_safety_buffer_mins
from services.itinerary_generator import generate_user_friendly_itinerary
from services.tools import search_places, get_place_details, get_route, optimize_trip, geocode_location

load_dotenv()


class RoamAroundAgent:
    """
    Autonomous Concierge Agent that combines algorithmic optimization tools
    with LLM generative intelligence (AWS Bedrock / google.gemma-3-27b-it) to produce personalized day trips.
    """

    def __init__(self, model_name: str = DEFAULT_MODEL):
        self.model_name = model_name
        self.client = get_openai_client()
        self.model = self.client

    def plan_itinerary(
        self,
        origin_lat: float,
        origin_lng: float,
        origin_name: str,
        candidates: List[Dict[str, Any]],
        total_hours: float,
        user_vibe: Optional[str] = None,
        cuisine_preference: Optional[str] = None,
        price_level: Optional[str] = None,
        travel_mode: str = "DRIVE",
        start_time_clock: str = "09:30 AM",
        selected_categories: Optional[List[str]] = None,
        allow_iconic_landmarks: bool = False
    ) -> Dict[str, Any]:
        """
        Executes the agentic workflow:
        1. Tool Execution: Runs mathematical optimizer (greedy insertion + 2-opt).
        2. Generative Enrichment: Uses Gemini to craft day narratives and tailor stop rationales.
        3. Fallback Safety: Always yields a valid result even if LLM is unavailable.
        """
        # Step 1: Run algorithmic optimization tool
        plan: OptimizedItineraryPlan = optimize_day_itinerary(
            origin_lat=origin_lat,
            origin_lng=origin_lng,
            origin_name=origin_name,
            candidates=candidates,
            total_hours=total_hours,
            user_vibe=user_vibe,
            cuisine_preference=cuisine_preference,
            travel_mode=travel_mode,
            start_time_clock=start_time_clock,
            selected_categories=selected_categories,
            allow_iconic_landmarks=allow_iconic_landmarks
        )

        # Step 2: Generative narrative synthesis using Gemini
        narrative, stop_refinements = self._generate_ai_enrichments(
            plan=plan,
            user_vibe=user_vibe,
            cuisine_preference=cuisine_preference,
            price_level=price_level,
            total_hours=total_hours
        )

        # Step 3: Compile enriched result
        enriched_places = []
        for stop in plan.stops:
            refinement = stop_refinements.get(stop.place_id, {})
            ai_reason = refinement.get("ai_reasoning") or stop.ai_reasoning
            time_reason = refinement.get("time_estimate_reason") or stop.time_estimate_reason

            v_dur = getattr(stop, "visit_duration", stop.duration_mins)
            t_prev = getattr(stop, "travel_time_from_previous", getattr(stop, "transit_from_prev_mins", 0))
            enriched_places.append({
                "place_id": stop.place_id,
                "place": stop.name,
                "name": stop.name,
                "selection_reasons": getattr(stop, "selection_reasons", []),
                "category": stop.category,
                "lat": stop.lat,
                "lng": stop.lng,
                "coordinates": {"lat": stop.lat, "lng": stop.lng},
                "address": stop.address,
                "rating": stop.rating,
                "review_count": stop.review_count,
                "price_level": stop.price_level,
                "duration_mins": v_dur,
                "duration_hours": round(v_dur / 60.0, 2),
                "visit_duration": v_dur,
                "travel_time_from_previous": t_prev,
                "transit_from_prev_mins": t_prev,
                "arrival_time": stop.arrival_clock,
                "departure_time": stop.departure_clock,
                "arrival_rel_mins": stop.arrival_rel_mins,
                "departure_rel_mins": stop.departure_rel_mins,
                "time_estimate_reason": time_reason,
                "ai_reasoning": ai_reason,
                "score_breakdown": stop.score_breakdown or {},
                "meal_type": getattr(stop, "meal_type", None),
                "is_meal_stop": bool(getattr(stop, "meal_type", None)),
                "type": "restaurant" if getattr(stop, "meal_type", None) or stop.category in ["restaurant", "cafe", "food", "bakery"] else "attraction"
            })

        # Step 4: Generate user-friendly 10-point JSON itinerary
        actual_buffer = getattr(plan, "safety_buffer_mins", calculate_safety_buffer_mins(plan.total_travel_mins))
        user_itinerary_input = {
            "status": "success",
            "starting_location": {
                "name": origin_name,
                "lat": origin_lat,
                "lng": origin_lng,
                "address": origin_name
            },
            "ordered_itinerary": enriched_places,
            "rejected_destinations": getattr(plan, "rejected_destinations", []),
            "return_to_start": {
                "destination": plan.return_leg.get("destination", origin_name),
                "duration_minutes": plan.return_leg.get("duration_mins", 0),
                "distance_km": plan.return_leg.get("distance_km", 0.0),
                "arrival_clock": plan.return_leg.get("final_return_clock", plan.end_clock),
                "buffered_arrival_clock": plan.return_leg.get("buffered_arrival_clock", getattr(plan, "buffered_end_clock", plan.end_clock))
            },
            "total_travel_time": plan.total_travel_mins,
            "travel_time_minutes": plan.total_travel_mins,
            "total_visit_time": plan.total_dwell_mins,
            "visit_time_minutes": plan.total_dwell_mins,
            "safety_buffer": actual_buffer,
            "safety_buffer_minutes": actual_buffer,
            "total_duration": plan.total_trip_mins,
            "total_duration_minutes": plan.total_travel_mins + plan.total_dwell_mins + actual_buffer,
            "total_distance": plan.total_distance_km,
            "transportation_mode": travel_mode,
            "available_time_minutes": int(round(total_hours * 60)),
            "score": plan.route_score
        }
        user_itinerary = self.generate_user_itinerary(
            optimizer_output=user_itinerary_input,
            user_preferences=user_vibe,
            transportation_mode=travel_mode
        )

        return {
            "status": "success",
            "curator_model": self.model_name if self.model else "algorithmic-optimizer",
            "start_location": {
                "name": origin_name,
                "lat": origin_lat,
                "lng": origin_lng
            },
            "optimized_places": enriched_places,
            "rejected_destinations": getattr(plan, "rejected_destinations", []),
            "total_trip_mins": plan.total_trip_mins,
            "total_trip_hours": plan.total_trip_hours,
            "total_travel_mins": plan.total_travel_mins,
            "travel_time_minutes": plan.total_travel_mins,
            "total_dwell_mins": plan.total_dwell_mins,
            "visit_time_minutes": plan.total_dwell_mins,
            "total_distance_km": plan.total_distance_km,
            "slack_remaining_mins": plan.slack_remaining_mins,
            "safety_buffer": actual_buffer,
            "safety_buffer_mins": actual_buffer,
            "safety_buffer_minutes": actual_buffer,
            "total_duration_minutes": plan.total_travel_mins + plan.total_dwell_mins + actual_buffer,
            "available_time_minutes": int(round(total_hours * 60)),
            "start_clock": plan.start_clock,
            "end_clock": plan.end_clock,
            "buffered_end_clock": getattr(plan, "buffered_end_clock", plan.return_leg.get("buffered_arrival_clock", plan.end_clock)),
            "start_time": plan.start_clock,
            "actual_return_time": plan.end_clock,
            "actual_elapsed_minutes": plan.total_travel_mins + plan.total_dwell_mins,
            "travel_minutes": plan.total_travel_mins,
            "visit_minutes": plan.total_dwell_mins,
            "safety_buffer_minutes": actual_buffer,
            "planning_budget_minutes": plan.total_travel_mins + plan.total_dwell_mins + actual_buffer,
            "available_minutes": int(round(total_hours * 60)),
            "unused_minutes": max(0, int(round(total_hours * 60)) - (plan.total_travel_mins + plan.total_dwell_mins + actual_buffer)),
            "unused_available_minutes": max(0, int(round(total_hours * 60)) - (plan.total_travel_mins + plan.total_dwell_mins)),
            "time_accounting": {
                "start_time": plan.start_clock,
                "actual_return_time": plan.end_clock,
                "actual_elapsed_minutes": plan.total_travel_mins + plan.total_dwell_mins,
                "travel_minutes": plan.total_travel_mins,
                "visit_minutes": plan.total_dwell_mins,
                "safety_buffer_minutes": actual_buffer,
                "planning_budget_minutes": plan.total_travel_mins + plan.total_dwell_mins + actual_buffer,
                "available_minutes": int(round(total_hours * 60)),
                "unused_minutes": max(0, int(round(total_hours * 60)) - (plan.total_travel_mins + plan.total_dwell_mins + actual_buffer)),
                "unused_available_minutes": max(0, int(round(total_hours * 60)) - (plan.total_travel_mins + plan.total_dwell_mins))
            },
            "narrative": narrative,
            "user_itinerary": user_itinerary,
            "legs": plan.legs_data,
            "return_leg": plan.return_leg
        }

    def generate_user_itinerary(
        self,
        optimizer_output: Dict[str, Any],
        user_preferences: Optional[str] = None,
        transportation_mode: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        AI Itinerary-Generation Layer:
        Transforms structured optimizer output into a concise, user-friendly 10-point JSON itinerary.
        Guarantees zero factual fabrication (all numbers, times, ratings, and distances are 100% grounded).
        """
        return generate_user_friendly_itinerary(
            optimizer_data=optimizer_output,
            user_preferences=user_preferences,
            transportation_mode=transportation_mode,
            model=self.model_name
        )


    def _generate_ai_enrichments(
        self,
        plan: OptimizedItineraryPlan,
        user_vibe: Optional[str],
        cuisine_preference: Optional[str],
        price_level: Optional[str],
        total_hours: float
    ) -> Tuple[str, Dict[str, Dict[str, str]]]:
        """
        Prompts LLM (AWS Bedrock / google.gemma-3-27b-it) to generate a cohesive day-flow narrative and stop-by-stop rationales.
        Falls back to deterministic text if LLM fails or is unconfigured.
        """
        vibe_str = user_vibe or "Balanced sightseeing and local dining"
        stops_summary = [
            {
                "place_id": s.place_id,
                "name": s.name,
                "category": s.category,
                "arrival": s.arrival_clock,
                "departure": s.departure_clock,
                "dwell_mins": s.duration_mins,
                "rating": s.rating
            }
            for s in plan.stops
        ]

        default_narrative = (
            f"A curated {plan.total_trip_hours}-hour loop itinerary starting and ending at "
            f"{plan.start_location.get('name')}. Balanced with {plan.total_dwell_mins} minutes spent enjoying "
            f"{len(plan.stops)} distinct stops and only {plan.total_travel_mins} minutes in transit."
        )

        if not self.client:
            return default_narrative, {}

        prompt = f"""You are RoamAround's AI concierge.
The user requested a day trip with:
- Total Time: {total_hours} hours ({plan.start_clock} to {plan.end_clock})
- Desired Vibe: "{vibe_str}"
- Budget Tier: "{price_level or 'Moderate'}"
- Cuisine: "{cuisine_preference or 'Any'}"

The route optimization engine has sequenced these stops in optimal physical order:
{json.dumps(stops_summary, indent=2)}

Please provide:
1. "narrative": A 2-sentence summary explaining how this sequence flows naturally from morning to conclusion.
2. "refinements": A dictionary mapping each place_id to:
   - "ai_reasoning": Exactly 1 punchy sentence explaining why this venue fits the requested vibe and its place in the day.
   - "time_estimate_reason": Exactly 1 sentence explaining why the allocated dwell time works.

Return JSON with this schema:
{{
  "narrative": "string",
  "refinements": {{
    "place_id_1": {{
      "ai_reasoning": "string",
      "time_estimate_reason": "string"
    }}
  }}
}}
"""
        try:
            data = call_llm_json(prompt=prompt, model=self.model_name, client=self.client)
            if isinstance(data, dict):
                narrative = data.get("narrative") or default_narrative
                refinements = data.get("refinements") or {}
                return narrative, refinements
            return default_narrative, {}
        except Exception as e:
            print(f"Agent narrative enrichment fallback ({e})")
            return default_narrative, {}


    # -----------------------------------------------------------------------
    # Conversational Itinerary Modification Engine
    # -----------------------------------------------------------------------

    def _extract_itinerary_state(
        self,
        itinerary: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]], int, str, str, str]:
        """Extracts normalized (start_location, stops, avail_mins, mode, vibe, start_clock) from any itinerary schema."""
        start_loc = (
            itinerary.get("start_location")
            or itinerary.get("starting_location")
            or {}
        )
        if not start_loc.get("lat") and "return_to_start_confirmation" in itinerary:
            ret = itinerary["return_to_start_confirmation"]
            start_loc = {
                "name": ret.get("origin_name", "Departure Point"),
                "address": ret.get("origin_address", ret.get("origin_name", "")),
                "lat": 37.7955,
                "lng": -122.3937
            }

        stops = (
            itinerary.get("ordered_destinations")
            or itinerary.get("ordered_itinerary")
            or itinerary.get("optimized_places")
            or []
        )

        avail_mins = 240
        if "available_time_minutes" in itinerary:
            avail_mins = int(itinerary["available_time_minutes"])
        elif isinstance(itinerary.get("total_duration"), dict):
            avail_mins = int(
                itinerary["total_duration"].get("available_budget_minutes")
                or itinerary["total_duration"].get("minutes")
                or 240
            )
        elif "total_trip_mins" in itinerary:
            avail_mins = int(itinerary["total_trip_mins"])

        mode = itinerary.get("transportation_mode") or "DRIVE"
        vibe = (
            itinerary.get("vibe")
            or itinerary.get("vibe_preference")
            or itinerary.get("user_preferences")
            or "Balanced sightseeing and dining"
        )

        start_clock = (
            itinerary.get("start_clock")
            or itinerary.get("start_time")
            or (itinerary.get("time_accounting", {}).get("start_time") if isinstance(itinerary.get("time_accounting"), dict) else None)
            or "09:30 AM"
        )

        return start_loc, stops, avail_mins, mode, vibe, start_clock

    def _parse_modification_intent(
        self,
        request_message: str,
        current_stops: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Extracts structured modification intent from natural language.
        Combines Gemini structured extraction with an intelligent deterministic rule-based parser.
        """
        msg_low = request_message.lower().strip()
        excluded_categories = []
        excluded_place_ids = []
        desired_categories = []
        search_query = None
        max_destinations = None
        time_adjustment = None
        dwell_multiplier = 1.0
        summary_actions = []

        # 1. Restaurant / Dining removal ("Remove the restaurant", "no restaurants")
        if any(w in msg_low for w in ["remove the restaurant", "remove restaurant", "no restaurant", "no restaurants", "drop restaurant", "delete restaurant"]):
            excluded_categories.extend(["restaurant", "food", "dining"])
            summary_actions.append("Removed restaurant")
            for s in current_stops:
                cat = str(s.get("category") or s.get("type") or "").lower()
                if cat in ["restaurant", "food", "cafe"] or s.get("type") == "restaurant":
                    excluded_place_ids.append(str(s.get("place_id") or ""))

        # 2. Museum exclusion ("I don't want museums", "no museums")
        if any(w in msg_low for w in ["museum", "museums"]) and any(w in msg_low for w in ["no", "don't want", "dont want", "remove", "exclude", "drop"]):
            excluded_categories.extend(["museum", "art_gallery"])
            summary_actions.append("Excluded museums")
            for s in current_stops:
                cat = str(s.get("category") or "").lower()
                if "museum" in cat or "art_gallery" in cat:
                    excluded_place_ids.append(str(s.get("place_id") or ""))

        # 3. Replace stop ("Replace the last stop with something outdoors")
        if "replace" in msg_low and any(w in msg_low for w in ["last", "first", "stop"]):
            target = "last" if "last" in msg_low else ("first" if "first" in msg_low else "last")
            if target == "last" and current_stops:
                last_stop = current_stops[-1]
                excluded_place_ids.append(str(last_stop.get("place_id") or ""))
                summary_actions.append(f"Replacing last stop ({last_stop.get('name')})")
            elif target == "first" and current_stops:
                first_stop = current_stops[0]
                excluded_place_ids.append(str(first_stop.get("place_id") or ""))
                summary_actions.append(f"Replacing first stop ({first_stop.get('name')})")

            if any(w in msg_low for w in ["outdoors", "outdoor", "nature", "park", "viewpoint", "scenic"]):
                desired_categories.extend(["park", "nature", "viewpoint"])
                search_query = "outdoors nature park scenic viewpoint"
                summary_actions.append("with outdoor/nature destination")
            elif any(w in msg_low for w in ["cafe", "coffee", "bakery"]):
                desired_categories.append("cafe")
                search_query = "coffee cafe bakery"
                summary_actions.append("with a cafe")

        # 4. Limit destination count ("I want only two destinations", "limit to 2 places", "fewer destinations")
        count_match = re.search(r"(?:only|just|limit to|maximum of)\s+(\d+|one|two|three|four|five|six)\s+(?:destinations|places|stops|venues)?", msg_low)
        if count_match:
            val_str = count_match.group(1)
            word_map = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6}
            num = word_map.get(val_str) or (int(val_str) if val_str.isdigit() else None)
            if num:
                max_destinations = num
                summary_actions.append(f"Limited to {num} destinations")
        elif any(w in msg_low for w in ["fewer destinations", "fewer places", "fewer stops", "less places", "less destinations", "reduce stops"]):
            if current_stops and len(current_stops) > 1:
                max_destinations = max(1, len(current_stops) - 1)
                summary_actions.append(f"Reduced to {max_destinations} destinations")
            else:
                max_destinations = 1
                summary_actions.append("Reduced to 1 destination")
            dwell_multiplier = 1.5

        # 5. Add a venue or category ("Add a cafe if there is enough time", "add another nature place")
        add_match = re.search(r"(?:add|include)\s+(?:another\s+)?(nature|park|outdoors?|viewpoint|cafe|coffee|restaurant|museum)\s*(?:place|stop|destination|venue)?", msg_low)
        if add_match:
            add_term = add_match.group(1)
            if add_term in ["nature", "park", "outdoor", "outdoors", "viewpoint"]:
                desired_categories.extend(["park", "nature", "viewpoint"])
                search_query = "nature park scenic viewpoint outdoors"
                summary_actions.append("Added another nature/outdoor destination")
            elif add_term in ["cafe", "coffee"]:
                desired_categories.append("cafe")
                search_query = "coffee cafe bakery"
                summary_actions.append("Added a cafe if time permits")
        elif any(w in msg_low for w in ["add a cafe", "include a cafe", "add cafe"]):
            desired_categories.append("cafe")
            search_query = "coffee cafe bakery"
            summary_actions.append("Added cafe opportunity if time permits")

        # 6. Make route shorter ("Make this route shorter")
        if any(w in msg_low for w in ["shorter", "shorten", "less time", "reduce duration"]):
            time_adjustment = "shorter"
            summary_actions.append("Shortened route duration")

        # 7. Relaxed pacing ("Give me a more relaxed itinerary", "relaxed trip with fewer destinations")
        if any(w in msg_low for w in ["relaxed", "relax", "more time at each", "leisurely", "slower pace"]):
            dwell_multiplier = max(dwell_multiplier, 1.4)
            summary_actions.append("Relaxed pacing with longer dwell times")


        summary = "; ".join(summary_actions) if summary_actions else "Refining itinerary based on your preferences"

        # Optional LLM structured refinement if configured
        if self.client:
            try:
                stops_context = [{"place_id": s.get("place_id"), "name": s.get("name"), "category": s.get("category")} for s in current_stops]
                ai_prompt = f"""You are RoamAround's itinerary modification parser.
User Request: "{request_message}"
Current Stops: {json.dumps(stops_context)}

Extract structured modification intent matching this JSON schema:
{{
  "excluded_categories": ["list of lowercase categories to remove, e.g. restaurant, museum"],
  "excluded_place_ids": ["list of place_ids to remove"],
  "desired_categories": ["list of categories to add or prioritize, e.g. park, cafe"],
  "search_query": "search query text if new venues needed or null",
  "max_destinations": integer or null,
  "time_adjustment": "shorter" or "longer" or null,
  "dwell_multiplier": float (e.g. 1.0 or 1.4),
  "summary": "1 sentence describing the change"
}}
"""
                ai_data = call_llm_json(prompt=ai_prompt, model=self.model_name, client=self.client)
                if isinstance(ai_data, dict):
                    if ai_data.get("excluded_categories"):
                        for c in ai_data["excluded_categories"]:
                            if c.lower() not in excluded_categories:
                                excluded_categories.append(c.lower())
                    if ai_data.get("excluded_place_ids"):
                        for pid in ai_data["excluded_place_ids"]:
                            if pid not in excluded_place_ids:
                                excluded_place_ids.append(pid)
                    if ai_data.get("desired_categories"):
                        for dc in ai_data["desired_categories"]:
                            if dc.lower() not in desired_categories:
                                desired_categories.append(dc.lower())
                    if ai_data.get("search_query"):
                        search_query = ai_data["search_query"]
                    if ai_data.get("max_destinations") and not max_destinations:
                        max_destinations = int(ai_data["max_destinations"])
                    if ai_data.get("time_adjustment") and not time_adjustment:
                        time_adjustment = ai_data["time_adjustment"]
                    if ai_data.get("dwell_multiplier") and dwell_multiplier == 1.0:
                        dwell_multiplier = float(ai_data["dwell_multiplier"])
                    if ai_data.get("summary"):
                        summary = ai_data["summary"]
            except Exception as e:
                pass  # Fallback to robust deterministic rules

        # 6. Explicit destination recognition & place locking
        explicit_destination = None
        generic_words = {
            "cafe", "coffee", "restaurant", "museum", "park", "nature", "stop", "place",
            "venue", "destination", "itinerary", "trip", "food", "lunch", "dinner", "breakfast",
            "something", "another", "more"
        }
        place_req_match = re.search(
            r"(?:i\s+want\s+to\s+(?:go\s+to|visit|see)|can\s+we\s+(?:go\s+to|visit|add|see)|please\s+add|add|include|take\s+me\s+to|must\s+visit)\s+([A-Z0-9][A-Za-z0-9\s'&.-]+?)(?:\s+(?:to\s+(?:the|my)\s+itinerary|to\s+the\s+trip|please|today|if\s+possible))?$",
            request_message,
            re.IGNORECASE
        )
        if place_req_match:
            candidate_place_str = place_req_match.group(1).strip()
            if candidate_place_str.lower() not in generic_words and len(candidate_place_str) > 2:
                explicit_destination = candidate_place_str

        return {
            "excluded_categories": excluded_categories,
            "excluded_place_ids": excluded_place_ids,
            "desired_categories": desired_categories,
            "search_query": search_query,
            "max_destinations": max_destinations,
            "time_adjustment": time_adjustment,
            "dwell_multiplier": dwell_multiplier,
            "summary": summary,
            "explicit_destination": explicit_destination
        }

    def modify_itinerary(
        self,
        request_message: str,
        current_itinerary: Dict[str, Any],
        candidate_pool: Optional[List[Dict[str, Any]]] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        Modifies an existing itinerary based on natural-language user requests.

        The process:
        1. Agent understands requested change (intent parsing)
        2. Update itinerary constraints / preferences
        3. Search / filter candidates if necessary
        4. Call deterministic optimizer again
        5. Validate time constraint & loop invariants
        6. Return updated user-friendly itinerary

        CRITICAL: Does NOT manually edit the route inside the LLM.
        The optimizer is strictly responsible for producing the valid route.
        """
        # Step 1: Extract normalized state from current itinerary
        start_loc, current_stops, avail_mins, mode, vibe, start_clock = self._extract_itinerary_state(current_itinerary)
        origin_lat = float(start_loc.get("lat", 37.7955))
        origin_lng = float(start_loc.get("lng", -122.3937))

        # Step 2: Understand requested change
        intent = self._parse_modification_intent(request_message, current_stops)

        # Step 3: Update constraints & preferences
        new_avail_mins = avail_mins
        if intent.get("time_adjustment") == "shorter":
            # Reduce time by ~25% or down to fit a tighter schedule
            curr_dur = avail_mins
            if isinstance(current_itinerary.get("total_duration"), dict):
                curr_dur = current_itinerary["total_duration"].get("minutes", avail_mins)
            new_avail_mins = max(60, min(int(avail_mins * 0.75), int(curr_dur * 0.85)))

        max_dest = intent.get("max_destinations")
        dwell_mult = intent.get("dwell_multiplier", 1.0)
        excluded_ids = set(intent.get("excluded_place_ids") or [])
        excluded_cats = set((c.lower() for c in (intent.get("excluded_categories") or [])))

        # Step 4: Search / filter candidates
        pool: List[Dict[str, Any]] = []
        if candidate_pool and isinstance(candidate_pool, list):
            pool.extend([dict(c) for c in candidate_pool])
        # Always add existing stops as candidates
        for s in current_stops:
            pool.append(dict(s))

        filtered_pool: List[Dict[str, Any]] = []
        seen_pids = set()
        for c in pool:
            pid = str(c.get("place_id") or c.get("id") or "")
            cat = str(c.get("category") or c.get("type") or "").lower()
            if pid in excluded_ids:
                continue
            if any(ex in cat for ex in excluded_cats):
                continue
            if pid not in seen_pids:
                seen_pids.add(pid)
                filtered_pool.append(c)

        # Search new candidates if search_query or desired_categories are present
        search_q = intent.get("search_query")
        desired_cats = intent.get("desired_categories") or []
        if search_q or desired_cats:
            res = search_places(
                lat=origin_lat,
                lng=origin_lng,
                query=search_q or " ".join(desired_cats),
                category=desired_cats[0] if desired_cats else None,
                radius_meters=5000,
                max_results=15
            )
            for p in res.get("places", []):
                pid = str(p.get("place_id") or "")
                cat = str(p.get("category") or "").lower()
                if pid in excluded_ids or any(ex in cat for ex in excluded_cats):
                    continue
                if pid not in seen_pids:
                    seen_pids.add(pid)
                    filtered_pool.append(p)

        # If candidate pool is small, replenish with general attractions
        if len(filtered_pool) < 5:
            extra = search_places(lat=origin_lat, lng=origin_lng, radius_meters=5000, max_results=15)
            for p in extra.get("places", []):
                pid = str(p.get("place_id") or "")
                cat = str(p.get("category") or "").lower()
                if pid in excluded_ids or any(ex in cat for ex in excluded_cats):
                    continue
                if pid not in seen_pids:
                    seen_pids.add(pid)
                    filtered_pool.append(p)

        # Update user interests
        updated_interests = vibe
        if desired_cats:
            updated_interests = f"{vibe}, {' '.join(desired_cats)}"

        explicit_dest_name = intent.get("explicit_destination")
        required_pids: List[str] = []
        if explicit_dest_name:
            found_place = None
            for p in current_stops + (candidate_pool or []):
                p_name = str(p.get("name") or p.get("place") or "").lower()
                if explicit_dest_name.lower() in p_name or p_name in explicit_dest_name.lower():
                    found_place = dict(p)
                    break

            if not found_place:
                search_res = search_places(lat=origin_lat, lng=origin_lng, query=explicit_dest_name, max_results=5)
                cand_list = search_res.get("places", [])
                if cand_list:
                    found_place = dict(cand_list[0])

            if found_place:
                found_place["is_locked"] = True
                f_pid = str(found_place.get("place_id") or found_place.get("id") or "")
                if f_pid:
                    required_pids.append(f_pid)
                    excluded_ids.discard(f_pid)
                    filtered_pool = [c for c in filtered_pool if str(c.get("place_id") or c.get("id") or "") != f_pid]
                    filtered_pool.insert(0, found_place)

        # Step 5: Call deterministic optimizer again
        optimizer_res = optimize_trip(
            start_location=start_loc,
            available_time_minutes=new_avail_mins,
            transportation_mode=mode,
            user_interests=updated_interests,
            candidate_places=filtered_pool,
            dwell_multiplier=dwell_mult,
            max_destinations=max_dest,
            start_time_clock=start_clock,
            required_place_ids=required_pids
        )

        # Step 6: Validate time constraint & loop invariants
        time_ok = optimizer_res.get("constraints_satisfied", {}).get("within_time_budget", True)
        assert optimizer_res.get("total_duration", 0) <= new_avail_mins, "Time constraint violated by optimizer"

        # Step 7: Generate concise user-friendly itinerary
        user_itinerary = self.generate_user_itinerary(
            optimizer_output=optimizer_res,
            user_preferences=updated_interests,
            transportation_mode=mode
        )

        # Compute delta for transparency
        prev_pids = {s.get("place_id") for s in current_stops}
        new_pids = {s.get("place_id") for s in user_itinerary.get("ordered_destinations", [])}
        prev_names = {s.get("place_id"): s.get("name") for s in current_stops}
        new_names = {s.get("place_id"): s.get("name") for s in user_itinerary.get("ordered_destinations", [])}

        stops_removed = [prev_names[pid] for pid in prev_pids - new_pids if pid in prev_names]
        stops_added = [new_names[pid] for pid in new_pids - prev_pids if pid in new_names]

        return {
            "status": "success",
            "message": "Itinerary updated successfully",
            "modification_applied": intent.get("summary"),
            "delta": {
                "stops_removed": stops_removed,
                "stops_added": stops_added,
                "previous_duration_minutes": avail_mins,
                "new_duration_minutes": optimizer_res.get("total_duration"),
                "time_constraint_satisfied": time_ok
            },
            "itinerary": user_itinerary,
            "raw_optimizer_output": optimizer_res
        }

    def chat(
        self,
        message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        current_itinerary: Optional[Dict[str, Any]] = None,
        default_location: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Conversational entrypoint for the RoamAround AI Agent.
        - If current_itinerary is present -> executes deterministic modification workflow.
        - If current_itinerary is not present -> executes fresh generation workflow.
        """
        msg_low = message.lower().strip()

        # Handle advisory & troubleshooting questions (e.g. "There aren't enough places. What can I do?")
        if any(phrase in msg_low for phrase in ["aren't enough places", "not enough places", "too few places", "no places found", "cannot find places", "what can i do"]):
            return {
                "status": "advisory",
                "message": (
                    "If there aren't enough places found, here are 4 practical ways to expand your options:\n"
                    "1. **Expand search radius**: Increase distance from 5 km to 10–15 km to discover spots in neighboring areas.\n"
                    "2. **Broaden your interests**: Include popular local highlights, viewpoints, or cafes alongside specific categories.\n"
                    "3. **Extend available time**: A longer time budget allows our optimizer to consider farther destinations while safely reserving return travel.\n"
                    "4. **Change starting location**: Relocating your departure point to a more central hub (such as downtown or a waterfront terminal) provides higher venue density.\n\n"
                    "Would you like me to broaden the search radius or suggest top highlights around your departure point?"
                ),
                "advice_actions": [
                    "increase_radius",
                    "broaden_categories",
                    "extend_time",
                    "change_location"
                ]
            }

        if current_itinerary:
            return self.modify_itinerary(
                request_message=message,
                current_itinerary=current_itinerary,
                conversation_history=conversation_history
            )

        # Check missing location
        start_loc = default_location
        if not start_loc:
            # Check if location is mentioned in message
            geo = geocode_location(message)
            if geo.get("status") == "success":
                start_loc = {"name": geo.get("name"), "lat": geo.get("lat"), "lng": geo.get("lng"), "address": geo.get("address")}

        if not start_loc:
            return {
                "status": "clarification_needed",
                "message": "Where will you be starting your trip? Please provide your starting city, neighborhood, or address.",
                "missing_fields": ["start_location"]
            }

        # Parse available hours
        hours = 4.0
        h_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:hours|hrs|hour)", msg_low)
        if h_match:
            hours = float(h_match.group(1))

        # Check distance constraint ("don't want to travel far", "nearby")
        radius_meters = 5000.0
        if any(w in msg_low for w in ["don't want to travel far", "dont want to travel far", "not far", "not too far", "nearby", "close by", "tight radius"]):
            radius_meters = 2500.0

        # Fresh discovery with vibe query
        places_res = search_places(
            lat=start_loc["lat"],
            lng=start_loc["lng"],
            query=message,
            radius_meters=radius_meters,
            max_results=20
        )
        cands = places_res.get("places", [])

        plan = self.plan_itinerary(
            origin_lat=start_loc["lat"],
            origin_lng=start_loc["lng"],
            origin_name=start_loc.get("name", "Departure Point"),
            candidates=cands,
            total_hours=hours,
            user_vibe=message
        )

        return {
            "status": "success",
            "message": "Generated new curated itinerary",
            "itinerary": plan.get("user_itinerary"),
            "raw_output": plan
        }

