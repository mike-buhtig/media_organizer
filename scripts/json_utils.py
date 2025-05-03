# json_utils.py
# Standardizes JSON output for provider scripts
#
# Change Log:
# [1.0.0] - 2025-05-03: Initial version with format_provider_json()

import json
import os

def format_provider_json(title, seasons, provider_name, temp_file):
    """
    Format provider data into standardized JSON and write to temp file.
    
    Args:
        title (str): Series title
        seasons (dict): Season data {season_num: [{"number": int, "title": str, "overview": str, "air_date": str, "id": str}, ...]}
        provider_name (str): e.g., 'tvmaze', 'tmdb'
        temp_file (str): Path to tmp/provider_<name>.json
    """
    data = {
        "title": title,
        "seasons": {
            str(season_num): [
                {
                    "episode_number": ep["number"],
                    "air_date": ep.get("air_date", ""),
                    "titles": {provider_name: ep.get("title", "")},
                    "overviews": {provider_name: ep.get("overview", "")},
                    "ids": {provider_name: ep.get("id", None)}
                } for ep in episodes
            ] for season_num, episodes in seasons.items()
        }
    }
    
    try:
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        print(f"[{provider_name}f] Wrote metadata to {temp_file}")
    except Exception as e:
        print(f"[{provider_name}f] Error writing {temp_file}: {e}")

def clean_temp_file(temp_file, provider_name):
    """Delete existing temp file if it exists."""
    if os.path.exists(temp_file):
        os.remove(temp_file)
        print(f"[{provider_name}f] Deleted existing temp file: {temp_file}")