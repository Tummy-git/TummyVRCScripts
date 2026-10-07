import os
import json
import datetime

def clean_for_json(obj):
    """Recursively converts SDK models and datetimes into JSON-serializable data."""
    if hasattr(obj, "to_dict"): return clean_for_json(obj.to_dict())
    elif isinstance(obj, dict): return {k: clean_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list): return [clean_for_json(item) for item in obj]
    elif isinstance(obj, (datetime.datetime, datetime.date)): return obj.isoformat()
    return obj

def load_json_list(file_path):
    """Loads a JSON list from disk. Returns [] if the file is missing, unreadable or not a list."""
    if not os.path.exists(file_path): return []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except (json.JSONDecodeError, IOError):
        return []

def save_json_list(file_path, items):
    dir_path = os.path.dirname(file_path)
    if dir_path: os.makedirs(dir_path, exist_ok=True)
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(items, f, indent=2, ensure_ascii=False)
