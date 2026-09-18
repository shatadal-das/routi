def calculate_activities(time_hours: float) -> dict:
    """
    Calculate how many activities fit into the user's available time.
    Assumptions:
    - Base driving buffer = 1.0 hour
    - Dinner = 1.5 hours
    - 1 Attraction = 1.0 hour
    """
    buffer_hours = 1.0
    dinner_hours = 1.5
    attraction_duration = 1.0

    available_time = max(0.0, float(time_hours) - buffer_hours)

    if available_time >= dinner_hours:
        has_dinner = True
        remaining_time = available_time - dinner_hours
        num_attractions = int(remaining_time // attraction_duration)
    else:
        has_dinner = False
        num_attractions = max(1, int(available_time // attraction_duration))

    return {
        "time_hours": float(time_hours),
        "buffer_hours": buffer_hours,
        "has_dinner": has_dinner,
        "dinner_hours": dinner_hours if has_dinner else 0.0,
        "num_attractions": num_attractions,
        "attraction_duration_hours": attraction_duration,
        "total_stops": (1 if has_dinner else 0) + num_attractions,
    }
