# providers/tvmaze_provider.py v 1.0.1
# Fetches metadata from TVmaze and writes standardized output to a temp file
# Change 1: Added clean_title function to strip quotes and backslashes from episode titles
# Change 2: Applied title cleaning to ep.get("name") to prevent malformed titles (e.g., "\"By Air, Land and Sea\"")

import os
import requests
import json
import re
import html
from configparser import ConfigParser

def normalize_title(title):
    return re.sub(r"[`‘’´]", "'", title.strip().lower()) if title else ""

def clean_title(title):
    if not title:
        return ""
    cleaned = re.sub(r'^"|"$|\\', '', title.strip())
    if cleaned != title:
        print(f"[TVMAZE] Cleaned title: '{title}' -> '{cleaned}'")
    return cleaned

def get_metadata(title, config: ConfigParser):
    base_temp = config["general"]["TEMP_FOLDER"]
    os.makedirs(base_temp, exist_ok=True)

    search_url = f"https://api.tvmaze.com/singlesearch/shows?q={requests.utils.quote(title)}"
    episodes_url_template = "https://api.tvmaze.com/shows/{id}/episodes?specials=1"

    try:
        show_resp = requests.get(search_url)
        if show_resp.status_code != 200:
            print("[TVMAZE] Show not found.")
            return

        show_data = show_resp.json()
        show_id = show_data.get("id")
        episodes_url = episodes_url_template.format(id=show_id)
        ep_resp = requests.get(episodes_url)
        episodes = ep_resp.json() if ep_resp.status_code == 200 else []

        output = {
            "title": show_data.get("name"),
            "id": show_id,
            "type": "tv",
            "overview": html.unescape(re.sub("<[^>]+>", "", show_data.get("summary", ""))),
            "first_air_date": show_data.get("premiered"),
            "seasons": {}
        }

        for ep in episodes:
            s = ep.get("season", 0)
            e = ep.get("number")
            if e is None or e == 0:
                continue

            ep_title = clean_title(ep.get("name"))
            ep_data = {
                "episode_number": e,
                "air_date": ep.get("airdate"),
                "titles": {"tvmaze": ep_title},
                "overviews": {"tvmaze": html.unescape(re.sub("<[^>]+>", "", ep.get("summary") or ""))},
                "ids": {"tvmaze": ep.get("id")}
            }

            output["seasons"].setdefault(s, []).append(ep_data)

        output_path = os.path.join(base_temp, "provider_tvmaze.json")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2)

        print(f"[TVMAZE] Metadata written to {output_path}")

    except Exception as e:
        print(f"[TVMAZE ERROR] {e}")