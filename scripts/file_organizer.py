# file_organizer.py
# Version 0.9.4
# Change Log:
# - Restored version with NFO writing only (no move/delete)
# - Uses paths.txt
# - Filters broken files
# - Groups by subtitle
# - Picks best file
# - Writes .nfo files to TV_LIBRARY_PATH
# - Logs KEEP/RENAME/NFO/DELETE candidates in file_organizer_actions_<series>.log
# - Cleans subtitle for use in filename
# - Fixes issue where titles list was not parsed correctly
# - 2025-04-18: Logging format restored with full traceability for each action
# - 2025-04-19: Normalize log file output to use / without a mix, which is unix style file address
# - 2025-04-22: Fixed AttributeError in group_and_write to handle new JSON structure with matches and unmatched sections
# - 2025-04-22: Updated write_nfo to place unmatched episodes in 'Unmatched Episodes' folder

import os
import json
import re
import sys
from datetime import datetime

SERIES_NAME = None
SERIES_FOLDER_PATH = None
SERIES_METADATA_JSON = None
TV_LIBRARY_PATH = None
KODI_JSON = None
LOG_PATH = None

def log_event(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_file = os.path.join(LOG_PATH, f"file_organizer_{SERIES_NAME.replace(' ', '_')}.log")
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")

def log_action(message):
    # Normalize paths in message to use forward slashes
    normalized = message.replace("\\", "/")
    action_file = os.path.join(LOG_PATH, f"file_organizer_actions_{SERIES_NAME.replace(' ', '_')}.log")
    with open(action_file, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [{SERIES_NAME}] {normalized}\n")

def load_paths():
    global SERIES_FOLDER_PATH, SERIES_METADATA_JSON, TV_LIBRARY_PATH, KODI_JSON, LOG_PATH
    config = {}
    with open("paths.txt", "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            config[key.strip()] = value.strip().strip('"')

    for i in range(1, 50):
        if config.get(f"series_name_{i}", "").strip('"') == SERIES_NAME:
            SERIES_FOLDER_PATH = config.get(f"series_path_{i}", "").strip('"')
            break

    JSON_FOLDER = config.get("JSON_FOLDER", ".")
    LOG_PATH = config.get("LOG_PATH", ".")
    KODI_JSON = config.get("KODI_METADATA_TEMPLATE", "")
    TV_LIBRARY_PATH = config.get("TV_LIBRARY_PATH", ".")

    SERIES_METADATA_JSON = os.path.join(JSON_FOLDER, f"{SERIES_NAME}.json")
    PROCESSED_JSON = os.path.join(JSON_FOLDER, f"{SERIES_NAME.replace(' ', '_')}_Processed.json")
    return PROCESSED_JSON

def load_processed(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def load_kodi_data():
    if not os.path.exists(KODI_JSON):
        return set()
    with open(KODI_JSON, "r", encoding="utf-8") as f:
        kodi = json.load(f)
    return set(entry.get("file") for entry in kodi if entry.get("playcount", 0) > 0)

def clean_name(s):
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")

def write_nfo(ep_meta, episode_path, watched):
    is_unmatched = "reason" in ep_meta and ep_meta["reason"].startswith("No match")
    season = int(ep_meta["season"]) if "season" in ep_meta else 0
    episode = int(ep_meta["episode"]) if "episode" in ep_meta else 0
    title_list = ep_meta.get("titles", [])
    title = next((t for t in title_list if t.strip()), ep_meta.get("title", ep_meta.get("subtitle", "Unknown")))
    plot = ep_meta.get("overview", ep_meta.get("description", ""))
    airdate = ep_meta.get("air_date", "")
    playcount = "1" if watched else "0"

    if is_unmatched:
        folder = os.path.join(TV_LIBRARY_PATH, SERIES_NAME, "Unmatched Episodes")
        filename = f"{SERIES_NAME.replace(' ', '.')}.{clean_name(title)}.nfo"
    else:
        folder = os.path.join(TV_LIBRARY_PATH, SERIES_NAME, f"Season {season:02d}")
        subtitle_clean = re.sub(r'\W+', '_', title.lower()) if title else "unknown"
        filename = f"{SERIES_NAME.replace(' ', '.')}.S{season:02d}E{episode:02d}.{subtitle_clean}.nfo"
    
    os.makedirs(folder, exist_ok=True)
    fullpath = os.path.join(folder, filename)

    lines = [
        "<?xml version='1.0' encoding='utf-8'?>",
        "<episodedetails>",
        f"  <title>{title}</title>",
        f"  <season>{season}</season>",
        f"  <episode>{episode}</episode>",
        f"  <plot>{plot}</plot>",
        f"  <aired>{airdate}</aired>",
        f"  <playcount>{playcount}</playcount>",
        f"  <showtitle>{SERIES_NAME}</showtitle>",
        "</episodedetails>"
    ]

    with open(fullpath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    log_action(f"NFO CREATED: {fullpath}")

def group_and_write(processed, kodi_watched):
    # Process matches
    for key, entry in processed.get("matches", {}).items():
        originals = entry.get("originals", [])
        broken = [f for f in originals if f.get("broken")]
        clean = [f for f in originals if not f.get("broken")]

        for b in broken:
            log_action(f"TO BE DELETED (broken): {b['path']}")

        if not clean:
            continue

        best = max(clean, key=lambda f: (f.get("timing_exists", False), f["size"]))
        ep_meta = entry.get("episode_meta")
        if not ep_meta:
            log_event(f"No episode_meta for {key}, skipping.")
            continue

        raw_subtitle = best.get("subtitle", "").strip()
        if raw_subtitle:
            log_action(f"Subtitle: {raw_subtitle}")

        dest_file = f"{SERIES_NAME.replace(' ', '.')}.S{ep_meta['season']:02d}E{ep_meta['episode']:02d}.{clean_name(raw_subtitle or ep_meta.get('title', 'unknown'))}.ts"
        dest_path = os.path.join(TV_LIBRARY_PATH, SERIES_NAME, f"Season {ep_meta['season']:02d}", dest_file)

        log_action(f"KEEP AND RENAME: {best['path']} → {dest_path}")

        for f in clean:
            if f["path"] != best["path"]:
                log_action(f"TO BE DELETED (dupe): {f['path']}")

        watched = best["path"] in kodi_watched
        write_nfo(ep_meta, best["path"], watched)

    # Process unmatched
    for entry in processed.get("unmatched", []):
        originals = entry.get("originals", [])
        broken = [f for f in originals if f.get("broken")]
        clean = [f for f in originals if not f.get("broken")]

        for b in broken:
            log_action(f"TO BE DELETED (broken): {b['path']}")

        if not clean:
            continue

        best = max(clean, key=lambda f: (f.get("timing_exists", False), f["size"]))
        ep_meta = entry.get("episode_meta")
        if not ep_meta:
            log_event(f"No episode_meta for unmatched entry, skipping.")
            continue

        raw_subtitle = best.get("subtitle", "").strip()
        if raw_subtitle:
            log_action(f"Subtitle: {raw_subtitle}")

        # Use subtitle for unmatched entries since no season/episode
        dest_file = f"{SERIES_NAME.replace(' ', '.')}.{clean_name(raw_subtitle or 'unknown')}.ts"
        dest_path = os.path.join(TV_LIBRARY_PATH, SERIES_NAME, "Unmatched Episodes", dest_file)

        log_action(f"KEEP AND RENAME: {best['path']} → {dest_path}")

        for f in clean:
            if f["path"] != best["path"]:
                log_action(f"TO BE DELETED (dupe): {f['path']}")

        watched = best["path"] in kodi_watched
        write_nfo(ep_meta, best["path"], watched)

def main():
    global SERIES_NAME
    if len(sys.argv) < 2:
        print("Usage: file_organizer.py \"Series Name\"")
        return
    SERIES_NAME = sys.argv[1]
    print("Starting File Organizer...")
    processed_path = load_paths()
    log_event(f"=== File Organizer v0.9.3 Started for '{SERIES_NAME}' ===")
    log_event(f"Using SERIES_FOLDER_PATH = {SERIES_FOLDER_PATH}")
    data = load_processed(processed_path)
    kodi_watched = load_kodi_data()
    log_event(f"Loaded {len(data.get('matches', {}))} matched and {len(data.get('unmatched', []))} unmatched episode groups from Processed.json")
    group_and_write(data, kodi_watched)
    log_event("NFO generation complete. No destructive operations performed.")

if __name__ == "__main__":
    main()