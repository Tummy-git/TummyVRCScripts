import os
import json
import vrchatapi

# --- Groups file helpers & interactive manager ---

def load_groups(file_path):
    """Return list of {'id':..., 'name':...}."""
    if not os.path.exists(file_path):
        return []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except (json.JSONDecodeError, IOError):
        return []

def save_groups(file_path, groups):
    # Ensure directory exists
    dir_path = os.path.dirname(file_path)
    if dir_path and not os.path.exists(dir_path):
        os.makedirs(dir_path, exist_ok=True)
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(groups, f, indent=2, ensure_ascii=False)
    print(f"Groups file saved. Total: {len(groups)}")

def display_groups(groups):
    if not groups:
        print("No followed groups")
        return
    print("\n--- Followed Groups ---")
    for i, g in enumerate(groups, 1):
        print(f"{i}. {g.get('name') or '<unknown>'} ({g.get('id')})")

def prompt_add_group(api_client, groups, groups_file_path):
    new_id = input("Enter group ID to follow (or blank to cancel): ").strip()
    if not new_id:
        print("Add cancelled.")
        return groups

    # Try to fetch name immediately
    fetched_name = ""
    try:
        groups_api = vrchatapi.api.groups_api.GroupsApi(api_client)
        info = groups_api.get_group(new_id)
        # info may be a model or dict
        fetched_name = getattr(info, 'name', None) or (info.get('name') if isinstance(info, dict) else "")
    except Exception as e:
        print(f"  - Warning: Couldn't fetch group name now: {e}. Storing with empty name; it will be filled on next export.")

    groups.append({"id": new_id, "name": fetched_name or ""})
    save_groups(groups_file_path, groups)
    print("Group added.")
    return groups

def prompt_remove_group(groups, groups_file_path):
    display_groups(groups)
    try:
        idx = int(input("Enter number to remove (0 cancel): ").strip())
        if idx == 0:
            print("Remove cancelled.")
            return groups
        removed = groups.pop(idx-1)
        save_groups(groups_file_path, groups)
        print(f"Removed {removed.get('name') or removed.get('id')}")
    except Exception:
        print("Invalid selection.")
    return groups

def fill_missing_names(api_client, groups, groups_file_path):
    if not groups:
        print("No groups to fill.")
        return groups
    groups_api = None
    try:
        groups_api = vrchatapi.api.groups_api.GroupsApi(api_client)
    except Exception:
        groups_api = None

    changed = False
    for g in groups:
        if not g.get('name'):
            gid = g.get('id')
            if not gid:
                continue
            fetched_name = None
            if groups_api:
                try:
                    info = groups_api.get_group(gid)
                    fetched_name = getattr(info, 'name', None) or (info.get('name') if isinstance(info, dict) else None)
                except Exception as e:
                    print(f"  - Warning: Couldn't fetch name for {gid}: {e}")
            if fetched_name:
                g['name'] = fetched_name
                print(f"  - Filled name for {gid}: {fetched_name}")
                changed = True

    if changed:
        save_groups(groups_file_path, groups)
    else:
        print("No updates made.")
    return groups

def run(api_client, current_user, settingsdata):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    groups_file_path = os.path.join(script_dir, settingsdata['files'].get('groups_path', 'groups.json'))
    groups = load_groups(groups_file_path)
    while True:
        print("\nGroups Manager: [l]ist, [a]dd, [r]emove, [f]ill-names, [q]uit")
        cmd = input("Select: ").strip().lower()
        if cmd in ('q','quit'):
            break
        elif cmd in ('l','list'):
            display_groups(groups)
        elif cmd in ('a','add'):
            groups = prompt_add_group(api_client, groups, groups_file_path)
        elif cmd in ('r','remove'):
            groups = prompt_remove_group(groups, groups_file_path)
        elif cmd in ('f','fill','fill-names'):
            groups = fill_missing_names(api_client, groups, groups_file_path)
        else:
            print("Unknown command.")