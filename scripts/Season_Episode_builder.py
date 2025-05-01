```python
import os
import json
import argparse
import logging
from datetime import datetime
import importlib
import sys
from pathlib import Path

__version__ = "1.0.7"

CHANGELOG = """
1.0.7 (2025-05-01):
- Updated load_providers() to use correct class names (TvMazeProvider, TmdbProvider, TraktProvider, RottenTomatoesProvider)
- Kept sys.path and providers.<provider_name>_provider imports
1.0.6 (2025-04-30):
- Fixed provider imports by adding scripts/ to sys.path and using absolute paths
- Added __init__.py to scripts/ for package recognition
1.0.5 (2025-04-30):
- Fixed load_paths() to skip comments and blank lines in paths.txt
- Added logging for invalid provider entries
1.0.4 (2025-04-30):
- Updated to read [meta_providers] from paths.txt, supporting enabled/disabled status
1.0.3 (2025-04-30):
- Improved provider loading with detailed error logging
- Added support for flexible provider class names
- Ensured scripts/providers/ is a module with __init__.py
1.0.2 (2025-04-30):
- Updated provider imports to use scripts.providers.<provider_name>_provider
1.0.1 (2025-04-30):
- Updated to load paths.txt from config/ directory
1.0.0 (2025-04-30):
- Updated to use new folder structure: data/<series_slug>/ for JSON, logs/<series_slug>/ for logs
- Read JSON_FOLDER and LOG_PATH from paths.txt
- Added --series argument for specific series
- Standardized series slug (lowercase, underscore)
- Dynamically load providers from paths.txt [providers] section
0.9.2 (2025-04-01):
- Improved provider metadata fetching
- Initial version
"""

def setup_logging(series_name):
    series_slug = series_name.lower().replace(" ", "_")
    log_dir = os.path.join("logs", series_slug)
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "season_episode_builder.log")
    
    logging.basicConfig(
        filename=log_file,
        level=logging.INFO,
        format="[%(asctime)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    return series_slug

def load_paths():
    paths = {}
    providers = []
    paths_file = os.path.join("config", "paths.txt")
    try:
        with open(paths_file, "r") as f:
            current_section = None
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("[") and line.endswith("]"):
                    current_section = line[1:-1]
                elif "=" in line:
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip()
                    if current_section == "library_paths" or current_section == "general":
                        paths[key] = value
                    elif current_section == "meta_providers" and value.lower() == "enabled":
                        providers.append((f"provider_{key}", len(providers) + 1))
                        logging.info(f"Added provider: {key} (priority {len(providers)})")
                    elif current_section == "meta_providers":
                        logging.warning(f"Skipping invalid provider entry: {key} = {value}")
    except FileNotFoundError:
        logging.error(f"paths.txt not found at {paths_file}")
        raise
    paths["JSON_FOLDER"] = paths.get("JSON_FOLDER", "data")
    paths["LOG_PATH"] = paths.get("LOG_PATH", "logs")
    logging.info(f"Loaded {len(providers)} provider configs from paths.txt")
    return paths, providers

def load_providers(provider_configs):
    provider_instances = []
    # Add scripts/ to sys.path
    script_dir = Path(__file__).parent
    sys.path.append(str(script_dir))
    
    for provider_key, priority in provider_configs:
        provider_name = provider_key.replace("provider_", "")
        try:
            module_path = f"providers.{provider_name}_provider"
            logging.info(f"Attempting to import {module_path}")
            module = importlib.import_module(module_path)
            
            # Try specific class names based on provider
            class_names = []
            if provider_name == "tvmaze":
                class_names = ["TvMazeProvider", "TvmazeProvider", "TVmazeProvider", "TVMAZEProvider"]
            elif provider_name == "tmdb":
                class_names = ["TmdbProvider", "TMdbProvider", "TMDBProvider"]
            elif provider_name == "trakt":
                class_names = ["TraktProvider", "TRaktProvider", "TRAKTProvider"]
            elif provider_name == "rotten_tomatoes":
                class_names = ["RottenTomatoesProvider", "Rotten_tomatoesProvider", "ROTTEN_TOMATOESProvider"]
            else:
                class_names = [
                    f"{provider_name.capitalize()}Provider",
                    f"T{provider_name[1:].capitalize()}Provider",
                    f"{provider_name.upper()}Provider"
                ]
                
            provider_class = None
            for class_name in class_names:
                try:
                    provider_class = getattr(module, class_name)
                    logging.info(f"Found class {class_name} in {module_path}")
                    break
                except AttributeError:
                    continue
            
            if not provider_class:
                logging.error(f"No valid provider class found in {module_path}. Tried: {', '.join(class_names)}")
                continue
            
            provider_instances.append(provider_class())
            logging.info(f"Successfully loaded provider: {provider_name} (priority {priority})")
        except Exception as e:
            logging.error(f"Failed to load provider {provider_name}: {str(e)}")
    return provider_instances

def fetch_metadata(series_name, providers):
    metadata = {"series_name": series_name, "seasons": []}
    for provider in providers:
        logging.info(f"Fetching metadata from {provider.__class__.__name__}")
        try:
            provider_data = provider.get_series_metadata(series_name)
            for season in provider_data.get("seasons", []):
                existing_season = next((s for s in metadata["seasons"] if s["season_number"] == season["season_number"]), None)
                if not existing_season:
                    metadata["seasons"].append(season)
                else:
                    existing_season["episodes"].extend(season.get("episodes", []))
        except Exception as e:
            logging.error(f"Error fetching from {provider.__class__.__name__}: {str(e)}")
    return metadata

def save_metadata(series_name, metadata, json_folder):
    series_slug = series_name.lower().replace(" ", "_")
    output_dir = os.path.join(json_folder, series_slug)
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"{series_name}.json")
    
    with open(output_path, "w") as f:
        json.dump(metadata, f, indent=2)
    logging.info(f"Saved metadata to {output_path}")

def main():
    parser = argparse.ArgumentParser(description="Build episode metadata for a series")
    parser.add_argument("--series", required=True, help="Name of the series (e.g., The A-Team)")
    args = parser.parse_args()
    
    series_slug = setup_logging(args.series)
    logging.info(f"=== Season Episode Builder v{__version__} Started for '{args.series}' ===")
    
    paths, provider_configs = load_paths()
    json_folder = paths["JSON_FOLDER"]
    logging.info(f"Using JSON_FOLDER = {json_folder}")
    
    providers = load_providers(provider_configs)
    if not providers:
        logging.error("No providers loaded. Exiting.")
        return
    
    metadata = fetch_metadata(args.series, providers)
    save_metadata(args.series, metadata, json_folder)

if __name__ == "__main__":
    main()