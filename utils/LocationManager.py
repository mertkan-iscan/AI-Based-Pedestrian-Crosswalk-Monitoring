import json
import os
import unicodedata
import re

CONFIG_FILE = "resources/locations.json"
POLYGONS_DIR = os.path.join("resources", "location_regions")


def _ensure_polygons_dir():
    if not os.path.exists(POLYGONS_DIR):
        os.makedirs(POLYGONS_DIR)


def _sanitize_filename(name: str) -> str:
    # 1) Strip accents
    nkfd = unicodedata.normalize("NFKD", name)
    ascii_str = "".join(c for c in nkfd if not unicodedata.combining(c))
    # 2) Lower-case
    ascii_str = ascii_str.lower()
    # 3) Spaces → underscores
    ascii_str = ascii_str.replace(" ", "_")
    # 4) Remove any remaining non-alphanumeric/underscore
    ascii_str = re.sub(r"[^a-z0-9_]", "", ascii_str)
    return ascii_str


def load_locations():

    # 1) Read or initialize the master list
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "w") as f:
            json.dump([], f, indent=4)
        locations = []
    else:
        with open(CONFIG_FILE, "r") as f:
            locations = json.load(f)

    # 2) Ensure the polygons directory exists
    _ensure_polygons_dir()

    # 3) Check each location for a valid polygons_file
    updated = False
    for loc in locations:
        path = loc.get("polygons_file")
        if not path or not os.path.exists(path):
            # Missing file: generate a new one
            base = _sanitize_filename(loc["name"])
            new_fname = f"region_polygons_{base}.json"
            new_path = os.path.join(POLYGONS_DIR, new_fname)

            # If there's already a file by that name, leave it; otherwise create it
            if not os.path.exists(new_path):
                with open(new_path, "w") as pf:
                    pf.write("")  # empty JSON file

            # Update entry and mark for rewrite
            loc["polygons_file"] = new_path
            updated = True

    # 4) If any paths were fixed, persist the updated list
    if updated:
        with open(CONFIG_FILE, "w") as f:
            json.dump(locations, f, indent=4)

    return locations



def add_location(location: dict):
    """
    location must include at least 'name'.
    Raises ValueError if name already exists.
    """
    locations = load_locations()
    # Duplicate‐name check (case-insensitive)
    if any(loc['name'].lower() == location['name'].lower() for loc in locations):
        raise ValueError(f"Location name '{location['name']}' already exists.")

    # Ensure polygons directory
    _ensure_polygons_dir()

    # Compute and assign polygons_file path
    filename = f"region_polygons_{_sanitize_filename(location['name'])}.json"
    file_path = os.path.join(POLYGONS_DIR, filename)
    location['polygons_file'] = file_path

    # Create empty polygons file
    with open(file_path, "w") as pf:
        pf.write("")

    # Persist new location
    locations.append(location)
    with open(CONFIG_FILE, "w") as f:
        json.dump(locations, f, indent=4)

    print(f"Added location: {location['name']}")


def delete_location(location: dict):
    locations = load_locations()
    updated = [loc for loc in locations if loc != location]
    with open(CONFIG_FILE, "w") as f:
        json.dump(updated, f, indent=4)
    print(f"Deleted location: {location['name']}")

    # Remove its polygons file if present
    polygons_file = location.get("polygons_file")
    if polygons_file and os.path.exists(polygons_file):
        os.remove(polygons_file)
        print(f"Deleted polygons file: {polygons_file}")


def update_location(old_location: dict, new_location: dict):
    """
    Rename the JSON file (or recreate it) if the name changed,
    enforce uniqueness by name only, and persist changes.
    Raises ValueError if the new name is already taken.
    """
    locations = load_locations()
    orig_name = old_location['name'].lower()
    new_name  = new_location['name'].lower()

    # 1) Enforce unique names (skip only the entry whose old name matches)
    for loc in locations:
        name = loc['name'].lower()
        if name == new_name and name != orig_name:
            raise ValueError(f"Location name '{new_location['name']}' already exists.")

    # 2) Find and update the entry
    found = False
    for idx, loc in enumerate(locations):
        if loc['name'].lower() == orig_name:
            _ensure_polygons_dir()

            # Compute new filename
            base = _sanitize_filename(new_location['name'])
            new_fname = f"region_polygons_{base}.json"
            new_path = os.path.join(POLYGONS_DIR, new_fname)

            # Rename or recreate
            old_path = loc.get('polygons_file')
            if old_path and os.path.exists(old_path):
                os.rename(old_path, new_path)
            else:
                with open(new_path, 'w') as pf:
                    pf.write("")

            # Update the in-memory entry
            new_location['polygons_file'] = new_path
            locations[idx] = new_location
            found = True
            break

    if not found:
        raise ValueError(f"Original location '{old_location['name']}' not found.")

    # 3) Persist back to disk
    with open(CONFIG_FILE, "w") as f:
        json.dump(locations, f, indent=4)

    print(f"Updated location '{old_location['name']}' → '{new_location['name']}'")

