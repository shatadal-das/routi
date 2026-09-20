def calculate_activities(time_hours: float) -> dict:
    """
    Calculate realistic activity pacing for the user's available time.
    Uses a proportional, rational safety buffer (10-15 mins) rather than
    excessively consuming user exploration time.
    """
    hrs = max(0.75, float(time_hours))
    # Proportional, modest buffer: 10-15 minutes max
    buffer_hours = min(0.25, round(hrs * 0.08, 2))
    dinner_hours = 1.25  # Standard 75 mins meal
    attraction_duration = 1.0  # 60 mins typical attraction

    available_time = max(0.5, hrs - buffer_hours)

    if available_time >= 3.0:
        has_dinner = True
        remaining_time = max(0.0, available_time - dinner_hours)
        num_attractions = max(1, int(remaining_time // attraction_duration))
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
