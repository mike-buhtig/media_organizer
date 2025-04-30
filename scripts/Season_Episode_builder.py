# Season_Episode_builder.py v2.8.7
# Change 1: CLI, paths.txt support, TMDB API call, media type resolution, logging
# Change 2: Fetch full metadata from TMDB and write to .json file in JSON_FOLDER
# Change 3: Added fallback to alternate paths file (e.g., VLC-paths.txt)
# Change 4: Added optional support for password (for future plugins)
# Change 5: Improved robustness and file-saving feedback in logs
# Change 6: Switched primary metadata provider to TVmaze; TMDB is now fallback
# Change 7: For each episode, add matching metadata from TMDB using season/episode match
# Change 8: Strip HTML tags and unescape HTML entities in TVmaze overviews
# Change 9: Add the search for Season 0 with TV Maze.  TMDB  will follow suite.
# Change 10: Unfortunately TMDB returned 'NULL' so we are calling for season 0
# Change 11: Assign synthetic episode numbers if TVmaze number is missing or 0
# Change 12: Add Trakt as tertiary metadata provider if TMDB fails
# Change 13: Always include Trakt metadata (if available) and include specials from Trakt
# Change 14: Switched paths.txt to INI-style format using configparser with [blocks]
# Change 15: Split TVMaze, TMDB, and Trakt logic into independent provider modules in ./providers
# Change 16: Wrapper loads active providers from [meta_providers] and merges their temp .json files
# Change 17: Each provider writes to tmp/provider_[name].json; wrapper merges and saves final output
# Change 18: Output now matches desired nested format (season_number, episodes[])
# Change 19: Properly groups all provider metadata (titles, overviews, ids) under each episode
# Change 20: Adds synthetic_number field when episode_number is missing

import requests
import sys
import os
import json
import re
import html
from configparser import ConfigParser
from datetime import datetime

# Trakt constants for episode pull
TRAKT_API = "https://api.trakt.tv"
TRAKT_HEADERS = {}

# ----------------------------
# Load paths.txt
# ----------------------------
def setup_trakt_headers(paths):
    global TRAKT_HEADERS
    TRAKT_HEADERS = {
        "Content-Type": "application/json",
        "trakt-api-version": "2",
        "trakt-api-key": paths['trakt'].get('TRAKT_CLIENT_ID', '')
    }

def load_paths():
    base_path = os.path.dirname(__file__)
    config = ConfigParser()
    paths_file = os.path.join(base_path, "paths.txt")
    if not os.path.exists(paths_file):
        print("paths.txt not found.", file=sys.stderr)
        sys.exit(1)
    config.read(paths_file)
    try:
        config.read(paths_file)
        return config
    except Exception as e:
        print(f"Error reading paths.txt: {e}", file=sys.stderr)
        sys.exit(1)

# Data below this line is unchanged and only a few lines are included to show where the changes end

# ----------------------------
# Wrapper Loader for Providers
# ----------------------------
def load_metadata_from_providers(title, config):
    import importlib
    temp_dir = config["general"]["TEMP_FOLDER"]
    active = config["meta_providers"]
    merged = {
        "title": title,
        "id": None,
        "type": "tv",
        "overview": "",
        "first_air_date": "",
        "seasons": []
    }

    for name, enabled in active.items():
        if enabled.strip().lower() != "enabled":
            continue
        try:
            mod = importlib.import_module(f"providers.{name}_provider")
            mod.get_metadata(title, config)
            temp_file = os.path.join(temp_dir, f"provider_{name}.json")
            if os.path.exists(temp_file):
                with open(temp_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for s, eps in data.get("seasons", {}).items():
                    s = int(s)
                    existing_season = next((season for season in merged["seasons"] if season["season_number"] == s), None)
                    if not existing_season:
                        existing_season = {"season_number": s, "episodes": []}
                        merged["seasons"].append(existing_season)
                    for ep in eps:
                        ep_num = ep.get("episode_number")
                        match = next((e for e in existing_season["episodes"] if e.get("episode_number") == ep_num), None)
                        if not match:
                            match = {
                                "episode_number": ep_num,
                                "air_date": ep.get("air_date"),
                                "titles": {},
                                "overviews": {},
                                "ids": {},
                                "synthetic_number": not isinstance(ep_num, int) or ep_num is None
                            }
                            existing_season["episodes"].append(match)
                        for field in ["titles", "overviews", "ids"]:
                            if field in ep and isinstance(ep[field], dict):
                                match[field].update(ep[field])
        except Exception as e:
            print(f"[WRAPPER ERROR - {name}] {e}")

    for season in merged["seasons"]:
        season["episodes"] = sorted(season["episodes"], key=lambda x: x.get("episode_number") or 0)
    merged["seasons"] = sorted(merged["seasons"], key=lambda x: x["season_number"])

    json_path = os.path.join(config["general"]["JSON_FOLDER"], f"{title}.json")
    with open(json_path, "w", encoding="utf-8") as out:
        json.dump(merged, out, indent=2)
    print(f"[WRAPPER] Final merged metadata saved to {json_path}")

# ----------------------------
# CLI Interface for Direct Calls
# ----------------------------
if __name__ == "__main__":
    if len(sys.argv) > 1:
        show_title = sys.argv[1]
        config = load_paths()
        load_metadata_from_providers(show_title, config)
    else:
        print("Usage: python season_episode_builder.py \"Show Title\"")

# ----------------------------
# Logging Function
# ----------------------------
def log_message(message, log_dir, max_lines=500):
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "builder.log")
    timestamped = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {message}"
    try:
        if os.path.exists(log_file):
            with open(log_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
            lines = lines[-max_lines+1:]
        else:
            lines = []
        lines.append(timestamped + "\\n")
        with open(log_file, "w", encoding="utf-8") as f:
            f.writelines(lines)
    except Exception as e:
        print(f"[LOGGING ERROR] {e}", file=sys.stderr)
