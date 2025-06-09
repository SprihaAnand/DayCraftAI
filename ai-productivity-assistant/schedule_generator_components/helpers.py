from datetime import datetime

def parse_time_input(time_str):
    if not time_str:
        return None
    time_str = time_str.strip().upper()
    try:
        if 'AM' in time_str or 'PM' in time_str:
            return datetime.strptime(time_str, "%I:%M %p").time()
        elif ':' in time_str:
            return datetime.strptime(time_str, "%H:%M").time()
        else:
            hour = int(time_str)
            if 0 <= hour <= 23:
                return datetime.strptime(f"{hour}:00", "%H:%M").time()
    except ValueError:
        return None

def format_time_display(time_obj):
    return time_obj.strftime("%I:%M %p")

def format_time_slot(start_time, end_time, title, location=""):
    location_str = f" at {location}" if location else ""
    return f"- {start_time} to {end_time}: {title}{location_str}"
