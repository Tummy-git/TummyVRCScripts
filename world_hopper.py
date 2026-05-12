import os
import json
import time
import datetime
import re

import vrchatapi

import vrcx_utils
from vrcx_utils import add_favorite_world
from vrchatapi import InstanceType, InstanceRegion, CreateInstanceRequest
from vrchatapi.rest import ApiException
from vrchatapi.api import AuthenticationApi

def clean_for_json(obj):
    if hasattr(obj, "to_dict"):
        return clean_for_json(obj.to_dict())
    elif isinstance(obj, dict):
        return {k: clean_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [clean_for_json(item) for item in obj]
    elif isinstance(obj, (datetime.datetime, datetime.date)):
        return obj.isoformat()
    else:
        return obj

def get_unity_version(created):
    ups = (created.get('world') or {}).get('unity_packages') or []
    return ups[-1].get('unity_version') if ups else 'unknown'

def load_co_explorers(file_path):
    """Load co-explorers from JSON file. Returns list of dicts with 'uid' and 'name'."""
    if not os.path.exists(file_path):
        return []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except (json.JSONDecodeError, IOError):
        return []

def save_co_explorers(file_path, explorers):
    """Save co-explorers to JSON file."""
    # Ensure directory exists
    dir_path = os.path.dirname(file_path)
    if dir_path and not os.path.exists(dir_path):
        os.makedirs(dir_path, exist_ok=True)

    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(explorers, f, indent=2, ensure_ascii=False)
    print(f"Co-explorers list saved. Total: {len(explorers)}")

def get_instance_users(api_client, world_id, instance_id):
    """Fetch users currently in the specified instance."""
    try:
        api_instance = vrchatapi.InstancesApi(api_client)
        instance = api_instance.get_instance(world_id, instance_id)

        if not hasattr(instance, 'users') or instance.users is None:
            print("No users data available for this instance (you may not own it)")
            return []

        users_list = []
        for user in instance.users:
            users_list.append({
                'uid': user.id,
                'name': user.display_name
            })
        return users_list
    except ApiException as e:
        print(f"Error fetching instance users: {e}")
        return []

def get_user_by_id(api_client, user_id):
    """Fetch user information by ID."""
    try:
        api_users = vrchatapi.UsersApi(api_client)
        user = api_users.get_user(user_id)
        return {
            'uid': user.id,
            'name': user.display_name
        }
    except ApiException as e:
        print(f"Error fetching user: {e}")
        return None

def display_co_explorers(explorers):
    """Display current co-explorers list nicely."""
    if not explorers:
        print("No co-explorers in list.")
        return
    print("\n--- Current Co-Explorers List ---")
    for i, explorer in enumerate(explorers, 1):
        print(f"{i}. {explorer['name']} ({explorer['uid']})")
    print("-" * 40)
def get_current_presence_world_id(api_client):
    """Fetches the ID of the world the user is currently physically standing in."""
    try:
        api_auth = AuthenticationApi(api_client) # Note: Ensure api_client name matches your scope
        user = api_auth.get_current_user()
        if user and user.presence and user.presence.world:
            return user.presence.world
        return None
    except Exception as e:
        print(f"Could not fetch presence: {e}")
        return None

def handle_update_command(api_client, explorers, current_user_id):
    """Update list with users from current instance."""
    try:
        api_auth = AuthenticationApi(api_client)
        current_user = api_auth.get_current_user()

        # Get world and instance from presence
        presence = getattr(current_user, 'presence', None)
        if not presence:
            print("No presence data available.")
            return explorers

        world_id = getattr(presence, 'world', None)
        instance_id = getattr(presence, 'instance', None)

        if not world_id or not instance_id:
            print(f"You are not in a valid world instance. world={world_id}, instance={instance_id}")
            return explorers

        instance_users = get_instance_users(api_client, world_id, instance_id)

        if not instance_users:
            print("No users found in your current instance.")
            return explorers

        # Filter out yourself from the list
        instance_users = [user for user in instance_users if user['uid'] != current_user_id]

        # Replace the list with instance users
        explorers = instance_users
        print(f"\nUpdated co-explorers list with {len(explorers)} users from your current instance:")
        display_co_explorers(explorers)
    except Exception as e:
        print(f"Error updating co-explorers: {e}")
        import traceback
        traceback.print_exc()

    return explorers

def handle_add_command(api_client, explorers):
    """Add a user to the co-explorers list."""
    user_input = input("Enter user ID (or 'cancel' to abort): ").strip()

    if user_input.lower() == 'cancel':
        print("Add cancelled.")
        return explorers

    # Validate user ID format
    if not re.match(r"^usr_[0-9a-fA-F-]{36}$", user_input):
        print("Invalid user ID format. Expected format: usr_xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx")
        return explorers

    # Check if already in list
    if any(explorer['uid'] == user_input for explorer in explorers):
        print("User already in co-explorers list.")
        return explorers

    # Fetch user info
    user_info = get_user_by_id(api_client, user_input)
    if not user_info:
        print("User not found or error fetching user data.")
        return explorers

    explorers.append(user_info)
    print(f"Added {user_info['name']} ({user_info['uid']}) to co-explorers list.")
    display_co_explorers(explorers)
    return explorers

def handle_remove_command(explorers):
    """Remove a user from the co-explorers list."""
    if not explorers:
        print("No co-explorers to remove.")
        return explorers

    display_co_explorers(explorers)

    try:
        remove_index = int(input("Enter number to remove (or 0 to cancel): ").strip()) - 1

        if remove_index == -1:
            print("Remove cancelled.")
            return explorers

        if not (0 <= remove_index < len(explorers)):
            print("Invalid selection.")
            return explorers

        removed_user = explorers.pop(remove_index)
        print(f"Removed {removed_user['name']} from co-explorers list.")
        display_co_explorers(explorers)
    except ValueError:
        print("Invalid input.")

    return explorers

def handle_clear_command():
    """Clear the co-explorers list."""
    confirm = input("Are you sure you want to clear the co-explorers list? (y/n): ").lower()
    if confirm == 'y':
        print("Co-explorers list cleared.")
        return []
    else:
        print("Clear cancelled.")
        return None

def run(api_client, current_user, settingsdata):
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Extract settings specific to this script
    world_json_output_path = settingsdata['files']['world_list_path']
    worldhoppers_file_path = settingsdata['files']['co_explorers_path']
    apiHappyTime = settingsdata['files']['api_delay_seconds']
    manual_world_list_path = os.path.join(script_dir, settingsdata['files']['manual_world_list'])
    instance_name = settingsdata['instanceid']
    current_world = settingsdata['currentworld']
    vrcx_db_path = settingsdata['files']['vrcx_db_path']
    vrcx_allowed = settingsdata['allowvrcx']
    vrcx_fav_group = settingsdata['vrcxfavgroup']

    # --- Verify VRC+ Status ---
    has_vrcplus = hasattr(current_user, 'tags') and current_user.tags and 'system_supporter' in current_user.tags
    if not has_vrcplus and instance_name:
        print("\n[!] Notice: VRC+ subscription not detected. Disabling custom instance names to prevent API errors.")

    offset = 0

    api_instance_instance = vrchatapi.InstancesApi(api_client)
    api_invite_instance = vrchatapi.InviteApi(api_client)
    api_world_instance = vrchatapi.WorldsApi(api_client)

    # --- Mode Selection & World Loading ---
    newsession = True
    if current_world:
        print(f"\nYou already have an ongoing jump session stored with number {current_world}.")
        if input("Do you want to continue last session? (y/n): ").lower() == "y":
            newsession = False

    if newsession:
        api_response = []
        if input("\nLoad worlds from IDs file? (y/n): ").lower() == "y":
            if os.path.exists(manual_world_list_path):
                with open(manual_world_list_path, 'r') as f:
                    ids = [line.strip() for line in f if line.strip()]
                print(f"Found {len(ids)} IDs. Fetching world data...")
                for i, wid in enumerate(ids):
                    try:
                        w_data = api_world_instance.get_world(wid)
                        api_response.append(w_data)
                        print(f"[{i+1}/{len(ids)}] Fetched: {w_data.name}")
                        time.sleep(0.5)
                    except ApiException:
                        print(f"Error fetching ID {wid}")
            use_api_search = False if api_response else True
        else:
            use_api_search = True

        if use_api_search:
            offset_input = input("Enter offset (0-999): ").strip()
            offset = int(offset_input) if offset_input.isdigit() else 0
            if input("Load old worlds (Ascending)? (y/n): ").lower() == "y":
                api_response = api_world_instance.search_worlds(sort=vrchatapi.SortOption().CREATED, n=100, offset=offset, order=vrchatapi.OrderOption().ASCENDING)
            else:
                api_response = api_world_instance.search_worlds(sort=vrchatapi.SortOption().LABSPUBLICATIONDATE, n=100, offset=offset, order=vrchatapi.OrderOption().DESCENDING)

        with open(world_json_output_path, "w", encoding="utf-8") as f:
            json.dump(clean_for_json(api_response), f, indent=2, ensure_ascii=False)

    # --- Load co-explorers from JSON ---
    co_explorers = load_co_explorers(worldhoppers_file_path)

    # --- JUMPING LOOP ---
    with open(world_json_output_path, 'r', encoding='utf-8') as f:
        json_list = json.load(f)

    lastInviteTime = 0
    activeJumpIndex = int(current_world) if current_world != "" else 0
    last_index = activeJumpIndex

    while True:
        next_preview_idx = activeJumpIndex + 1
        if 0 <= next_preview_idx < len(json_list):
            print(f"\nNext world will be: {json_list[next_preview_idx]['name']} by {json_list[next_preview_idx]['author_name']}")
        else:
            print("\nNo preview available for next world.")

        user_input = input("goto#?, empty to advance, or 'update/clear/add/remove/fav': ").strip()

        # --- Handle co-explorer management commands ---
        if user_input.lower() == 'update':
            print("Fetching users from your current instance...")
            co_explorers = handle_update_command(api_client, co_explorers, current_user.id)
            save_co_explorers(worldhoppers_file_path, co_explorers)
            continue

        elif user_input.lower() == 'clear':
            result = handle_clear_command()
            if result is not None:
                co_explorers = result
                save_co_explorers(worldhoppers_file_path, co_explorers)
            continue

        elif user_input.lower() == 'add':
            co_explorers = handle_add_command(api_client, co_explorers)
            save_co_explorers(worldhoppers_file_path, co_explorers)
            continue

        elif user_input.lower() == 'remove':
            co_explorers = handle_remove_command(co_explorers)
            save_co_explorers(worldhoppers_file_path, co_explorers)
            continue

        elif user_input.lower() == 'fav':
            if vrcx_allowed:
                print(f"\n[!]Adding {get_current_presence_world_id(api_client)} to {vrcx_fav_group}")
                target_world_id = get_current_presence_world_id(api_client)
                status = vrcx_utils.add_favorite_world(vrcx_db_path, target_world_id, vrcx_fav_group)
                if status == "added":
                    print(f"\n[+] Success! Added {target_world_id} to >{vrcx_fav_group}<")
                elif status == "duplicate":
                    print(f"\n[!] Skip: This world is already in the '{vrcx_fav_group}' group.")
                else:
                    print(f"\n[X] Error: Could not add to database. (Check if VRCX has a heavy lock)")
            else:
                print(f"\nVRCX interactions is set to {vrcx_allowed}. \nIf you want to do this, change from false to true in settings.json and restart the script. \nOn linux, make sure it's pointing at your vrcx database. I take no responsibility over what happens to your vrcx db. \nTake a backup. \nAlso remember that worlds doesn't show up in VRCX immedeately. But does after a restart of VRCX.")
                

        # --- Normal navigation ---
        if user_input == "":
            if activeJumpIndex == 0 and last_index == 0 and newsession:
                activeJumpIndex = 0
                newsession = False
            else:
                activeJumpIndex = last_index + 1
        else:
            try:
                activeJumpIndex = int(user_input)
            except ValueError:
                continue

        if not (0 <= activeJumpIndex < len(json_list)) or activeJumpIndex == 500:
            break

        # Rate limiting
        elapsed = int(time.time()) - lastInviteTime
        if elapsed < apiHappyTime:
            to_sleep = apiHappyTime - elapsed
            print(f"Sleeping for {to_sleep} seconds to keep the servers happy")
            time.sleep(to_sleep)

        last_index = activeJumpIndex

        try:
            # Build the request arguments dynamically to avoid sending empty parameters
            instance_args = {
                "world_id": json_list[activeJumpIndex]['id'],
                "owner_id": current_user.id,
                "type": InstanceType.FRIENDS,
                "region": InstanceRegion.EU
            }

            # Only append the display_name parameter if they have VRC+ and actually set a name
            if has_vrcplus and instance_name:
                instance_args["display_name"] = instance_name

            created_instance = api_instance_instance.create_instance(
                create_instance_request=CreateInstanceRequest(**instance_args)
            )
            created = clean_for_json(created_instance)
            unity_version = get_unity_version(created)
            world_asset_name = (created.get('world') or {}).get('name', 'Unknown World')
            world_author_name = (created.get('world') or {}).get('author_name')
            world_location = created.get('location') or created.get('id')

            print("\n-------------------------------------------------------------------------------------------------------")
            print(f"Sent invite to #{last_index}: {world_asset_name} by {world_author_name}")
            print(f"World id: {world_location}")
            print(f"Unity version: {unity_version}")
            print("-------------------------------------------------------------------------------------------------------")

            # Invite Logic
            parts = world_location.split(':')
            api_invite_instance.invite_myself_to(parts[0], parts[1] if len(parts) > 1 else "")
            print("Invited myself.")

            # Invite all co-explorers
            if co_explorers:
                print(f"Inviting {len(co_explorers)} co-explorers:")
                for explorer in co_explorers:
                    try:
                        api_invite_instance.invite_user(explorer['uid'], vrchatapi.InviteRequest(instance_id=world_location))
                        print(f"  → Invited {explorer['name']}")
                    except Exception as e:
                        print(f"  ✗ Failed to invite {explorer['name']}: {e}")
            else:
                print("No co-explorers in list to invite.")

            lastInviteTime = int(time.time())
            print("\n")

        except Exception as e:
            print(f"Critical error during jump: {e}")

    print("Session finished.")