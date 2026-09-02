import os
import json
import time
import datetime
import re
import webbrowser
import random

import vrchatapi
import vrcx_utils
from vrcx_utils import add_favorite_world
from vrchatapi import InstanceType, InstanceRegion, CreateInstanceRequest
from vrchatapi.rest import ApiException
from vrchatapi.api import AuthenticationApi

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, BarColumn, TextColumn

console = Console()

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

def get_unity_version(data):
    world_data = data.get('world', data)
    ups = world_data.get('unity_packages', [])
    return ups[-1].get('unity_version') if ups else 'unknown'

def load_co_explorers(file_path):
    if not os.path.exists(file_path):
        return []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except (json.JSONDecodeError, IOError):
        return []

def save_co_explorers(file_path, explorers):
    dir_path = os.path.dirname(file_path)
    if dir_path and not os.path.exists(dir_path):
        os.makedirs(dir_path, exist_ok=True)
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(explorers, f, indent=2, ensure_ascii=False)

def get_instance_users(api_client, world_id, instance_id):
    try:
        api_instance = vrchatapi.InstancesApi(api_client)
        instance = api_instance.get_instance(world_id, instance_id)
        if not hasattr(instance, 'users') or instance.users is None:
            return []
        return [{'uid': user.id, 'name': user.display_name} for user in instance.users]
    except ApiException:
        return []

def get_user_by_id(api_client, user_id):
    try:
        api_users = vrchatapi.UsersApi(api_client)
        user = api_users.get_user(user_id)
        return {'uid': user.id, 'name': user.display_name}
    except ApiException:
        return None

def get_current_presence_world_id(api_client):
    try:
        api_auth = AuthenticationApi(api_client)
        user = api_auth.get_current_user()
        if user and user.presence and user.presence.world:
            return user.presence.world
        return None
    except Exception:
        return None

def render_dashboard(active_idx, total_worlds, current_world_info, next_worlds, settings, co_explorers):
    term_height = console.size.height

    if current_world_info:
        header_text = f"[bold green]{current_world_info.get('name', 'Unknown')}[/bold green] by [bold cyan]{current_world_info.get('author', 'Unknown')}[/bold cyan]\n"
        header_text += f"ID: {current_world_info.get('id', 'Unknown')}\n"
        header_text += f"Unity: {current_world_info.get('unity', 'Unknown')}"
    else:
        header_text = "No active world selected yet."
    header_panel = Panel(header_text, title="Current World Info", border_style="red", height=6)

    progress = Progress(TextColumn("[progress.description]{task.description}"), BarColumn(), TextColumn("[progress.percentage]{task.percentage:>3.0f}%"))
    progress.add_task("Queue", total=total_worlds, completed=active_idx + 1)
    progress_panel = Panel(progress, border_style="none", height=3)

    bottom_height = max(10, term_height - 12)

    next_table = Table(show_header=False, box=None)
    for i, w in enumerate(next_worlds):
        next_table.add_row(f"{active_idx + 2 + i}.", f"{w.get('name')} (by {w.get('author_name')})")
    next_panel = Panel(next_table, title="Coming Next", border_style="blue", height=bottom_height)

    settings_text = f"Instance Type: [bold]{settings['instance_type']}[/bold]\nLaunch Mode: [bold]{settings['launch_mode'].upper()}[/bold]"
    settings_panel = Panel(settings_text, title="Settings", border_style="yellow", height=6)

    party_table = Table(show_header=False, box=None)
    for i, explorer in enumerate(co_explorers[:5]):
        party_table.add_row(str(i+1), explorer['name'])
    if len(co_explorers) > 5:
        party_table.add_row("", f"...and {len(co_explorers) - 5} more")
    party_panel = Panel(party_table, title="Hopping Party", border_style="white", height=bottom_height - 6)

    sidebar_grid = Table.grid(expand=True)
    sidebar_grid.add_column()
    sidebar_grid.add_row(settings_panel)
    sidebar_grid.add_row(party_panel)

    bottom_grid = Table.grid(expand=True)
    bottom_grid.add_column(ratio=1)
    bottom_grid.add_column(ratio=1)
    bottom_grid.add_row(next_panel, sidebar_grid)

    main_grid = Table.grid(expand=True)
    main_grid.add_column()
    main_grid.add_row(header_panel)
    main_grid.add_row(progress_panel)
    main_grid.add_row(bottom_grid)

    console.clear()
    console.print(main_grid)

def run(api_client, current_user, settingsdata):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    world_json_output_path = settingsdata['files']['world_list_path']
    worldhoppers_file_path = settingsdata['files']['co_explorers_path']
    apiHappyTime = settingsdata['files']['api_delay_seconds']
    manual_world_list_path = os.path.join(script_dir, settingsdata['files']['manual_world_list'])
    instance_name = settingsdata['instanceid']
    current_world = settingsdata['currentworld']
    vrcx_db_path = settingsdata['files']['vrcx_db_path']
    vrcx_allowed = settingsdata['allowvrcx']
    vrcx_fav_group = settingsdata['vrcxfavgroup']

    has_vrcplus = hasattr(current_user, 'tags') and current_user.tags and 'system_supporter' in current_user.tags

    offset = 0
    current_instance_type = InstanceType.FRIENDS
    action_mode = "invite"

    api_instance_instance = vrchatapi.InstancesApi(api_client)
    api_invite_instance = vrchatapi.InviteApi(api_client)
    api_world_instance = vrchatapi.WorldsApi(api_client)

    newsession = True
    if current_world:
        console.print(f"\n[bold yellow]You have an ongoing jump session stored (Index: {current_world}).[/bold yellow]")
        if console.input("Continue last session? (y/n): ").strip().lower() == "y":
            newsession = False

    if newsession:
        api_response = []
        queue_table = Table(title="World Queue Selection", show_lines=True)
        queue_table.add_column("Option", justify="center", style="cyan")
        queue_table.add_column("Queue Type")
        queue_table.add_row("1", "File (Load from manual list)")
        queue_table.add_row("2", "Community Labs (Newest)")
        queue_table.add_row("3", "Public (Recently Published)")
        queue_table.add_row("4", "Public (Hot / Popular)")
        queue_table.add_row("5", "Public (Random / Shuffle)")

        console.print(queue_table)
        q_choice = console.input("Select a queue to load (1-5): ").strip()

        if q_choice == '1':
            if os.path.exists(manual_world_list_path):
                with open(manual_world_list_path, 'r') as f:
                    ids = [line.strip() for line in f if line.strip()]
                console.print(f"Found {len(ids)} IDs. Fetching data...")
                for i, wid in enumerate(ids):
                    try:
                        w_data = api_world_instance.get_world(wid)
                        api_response.append(w_data)
                        time.sleep(0.5)
                    except ApiException:
                        pass
            use_api_search = False if api_response else True
        else:
            use_api_search = True

        if use_api_search:
            offset_input = console.input("Enter offset (0-999): ").strip()
            offset = int(offset_input) if offset_input.isdigit() else 0

            with console.status("[bold green]Fetching world list from API..."):
                try:
                    if q_choice == '2': api_response = api_world_instance.search_worlds(sort=vrchatapi.SortOption().LABSPUBLICATIONDATE, n=100, offset=offset, order=vrchatapi.OrderOption().DESCENDING)
                    elif q_choice == '3': api_response = api_world_instance.search_worlds(release_status="public", sort=vrchatapi.SortOption().PUBLICATIONDATE, n=100, offset=offset, order=vrchatapi.OrderOption().DESCENDING)
                    elif q_choice == '4': api_response = api_world_instance.search_worlds(release_status="public", sort=vrchatapi.SortOption().HEAT, n=100, offset=offset, order=vrchatapi.OrderOption().DESCENDING)
                    elif q_choice == '5': api_response = api_world_instance.search_worlds(release_status="public", sort=vrchatapi.SortOption().SHUFFLE, n=100, offset=offset)
                    else: api_response = api_world_instance.search_worlds(sort=vrchatapi.SortOption().LABSPUBLICATIONDATE, n=100, offset=offset, order=vrchatapi.OrderOption().DESCENDING)
                except ApiException as e:
                    console.print(f"[red]Error fetching queue: {e}[/red]")

        with open(world_json_output_path, "w", encoding="utf-8") as f:
            json.dump(clean_for_json(api_response), f, indent=2, ensure_ascii=False)

    co_explorers = load_co_explorers(worldhoppers_file_path)

    with open(world_json_output_path, 'r', encoding='utf-8') as f:
        json_list = json.load(f)

    lastInviteTime = 0
    activeJumpIndex = int(current_world) if current_world != "" else 0
    last_index = activeJumpIndex
    status_msg = ""
    current_world_info = {}

    while True:
        if 0 <= activeJumpIndex < len(json_list):
            cw_static = json_list[activeJumpIndex]
            if not current_world_info or current_world_info.get('id') != cw_static.get('id'):
                current_world_info = {
                    'name': cw_static.get('name', 'Unknown'),
                    'author': cw_static.get('author_name', 'Unknown'),
                    'id': cw_static.get('id', 'Unknown'),
                    'unity': get_unity_version(cw_static)
                }

        next_worlds = json_list[activeJumpIndex + 1 : activeJumpIndex + 6]
        settings_info = {'instance_type': str(current_instance_type), 'launch_mode': action_mode}

        render_dashboard(activeJumpIndex, len(json_list), current_world_info, next_worlds, settings_info, co_explorers)

        display_status = status_msg if status_msg else "Ready."
        console.print(f"[bold]System:[/bold] {display_status}")
        status_msg = ""

        user_input = console.input("[bold]Command[/bold] (goto#, type, mode, update, add, remove, clear, fav, help): ").strip()

        if user_input.lower() == 'help':
            status_msg = "[empty]: Next world | [number]: Jump to index | type/mode: Settings | update/add/remove/clear: Party Mgmt | fav: Add to VRCX"
            continue

        elif user_input.lower().startswith('type'):
            val = user_input.lower().replace('type', '').strip()
            if not val:
                val = console.input("Type (friends, friends+, invite, public): ").strip().lower()
            if val in ['friends']: current_instance_type = InstanceType.FRIENDS
            elif val in ['friends+', 'hidden']: current_instance_type = InstanceType.HIDDEN
            elif val in ['invite', 'invite+', 'private']: current_instance_type = InstanceType.PRIVATE
            elif val in ['public']: current_instance_type = InstanceType.PUBLIC
            status_msg = f"Instance type set to {current_instance_type}"
            continue

        elif user_input.lower().startswith('mode'):
            val = user_input.lower().replace('mode', '').strip()
            if not val:
                val = console.input("Mode (invite, launch, both): ").strip().lower()
            if val in ['invite', 'launch', 'both']:
                action_mode = val
                status_msg = f"Mode set to {action_mode.upper()}"
            continue

        elif user_input.lower() == 'update':
            api_auth = AuthenticationApi(api_client)
            user = api_auth.get_current_user()
            if getattr(user, 'presence', None):
                w_id = getattr(user.presence, 'world', None)
                i_id = getattr(user.presence, 'instance', None)
                if w_id and i_id:
                    users = get_instance_users(api_client, w_id, i_id)
                    co_explorers = [u for u in users if u['uid'] != current_user.id]
                    save_co_explorers(worldhoppers_file_path, co_explorers)
                    status_msg = f"Updated party with {len(co_explorers)} users from current instance."
                else:
                    status_msg = "[red]Not in a valid instance.[/red]"
            continue

        elif user_input.lower() == 'clear':
            co_explorers = []
            save_co_explorers(worldhoppers_file_path, co_explorers)
            status_msg = "Party cleared."
            continue

        elif user_input.lower() == 'add':
            uid = console.input("Enter user ID: ").strip()
            if re.match(r"^usr_[0-9a-fA-F-]{36}$", uid):
                user_info = get_user_by_id(api_client, uid)
                if user_info:
                    co_explorers.append(user_info)
                    save_co_explorers(worldhoppers_file_path, co_explorers)
                    status_msg = f"Added {user_info['name']}."
            continue

        elif user_input.lower() == 'remove':
            try:
                idx = int(console.input("Enter number to remove: ").strip()) - 1
                if 0 <= idx < len(co_explorers):
                    removed = co_explorers.pop(idx)
                    save_co_explorers(worldhoppers_file_path, co_explorers)
                    status_msg = f"Removed {removed['name']}."
            except ValueError:
                pass
            continue

        elif user_input.lower() == 'fav':
            if vrcx_allowed:
                cid = get_current_presence_world_id(api_client)
                status = add_favorite_world(vrcx_db_path, cid, vrcx_fav_group)
                if status == "added": status_msg = f"[green]Added {cid} to {vrcx_fav_group}[/green]"
                elif status == "duplicate": status_msg = f"[yellow]World already in {vrcx_fav_group}[/yellow]"
                else: status_msg = "[red]Database locked/Error.[/red]"
            else:
                status_msg = "[red]VRCX interaction disabled in settings.[/red]"
            continue

        elif user_input == "":
            if activeJumpIndex == 0 and last_index == 0 and newsession:
                activeJumpIndex = 0
                newsession = False
            else:
                activeJumpIndex = last_index + 1
        else:
            try:
                # Interpret user numerical input based on the 1-based index shown in the UI
                activeJumpIndex = int(user_input) - 1
            except ValueError:
                continue

        if not (0 <= activeJumpIndex < len(json_list)) or activeJumpIndex == 500:
            break

        elapsed = int(time.time()) - lastInviteTime
        if elapsed < apiHappyTime:
            time.sleep(apiHappyTime - elapsed)

        last_index = activeJumpIndex
        target_world_id = json_list[activeJumpIndex]['id']

        try:
            joined_existing = False
            world_location = ""

            with console.status(f"[cyan]Initializing jump to index {activeJumpIndex + 1}...[/cyan]"):
                if current_instance_type == InstanceType.PUBLIC:
                    world_info = api_world_instance.get_world(target_world_id)
                    capacity = getattr(world_info, 'capacity', 16)
                    if hasattr(world_info, 'instances') and world_info.instances:
                        best = next((inst[0] for inst in world_info.instances if len(inst) >= 2 and inst[1] < capacity), world_info.instances[0][0])
                        world_location = f"{world_info.id}:{best}"
                    else:
                        world_location = f"{world_info.id}:{random.randint(10000, 99999)}~region(eu)"
                    joined_existing = True
                    current_world_info['unity'] = get_unity_version(clean_for_json(world_info))

                if not joined_existing:
                    instance_args = {"world_id": target_world_id, "type": current_instance_type, "region": InstanceRegion.EU}
                    if current_instance_type != InstanceType.PUBLIC:
                        instance_args["owner_id"] = current_user.id
                    if has_vrcplus and instance_name and current_instance_type != InstanceType.PUBLIC:
                        instance_args["display_name"] = instance_name

                    created_instance = api_instance_instance.create_instance(create_instance_request=CreateInstanceRequest(**instance_args))
                    created = clean_for_json(created_instance)
                    world_location = created.get('location') or created.get('id')
                    current_world_info['unity'] = get_unity_version(created)

                if action_mode == "invite":
                    parts = world_location.split(':')
                    api_invite_instance.invite_myself_to(parts[0], parts[1] if len(parts) > 1 else "")
                elif action_mode in ["launch", "both"]:
                    webbrowser.open(f"vrchat://launch/?ref=vrchat.com&id={world_location}&attach=1")

                invites_sent = 0
                if action_mode in ["invite", "both"] and co_explorers:
                    for explorer in co_explorers:
                        try:
                            api_invite_instance.invite_user(explorer['uid'], vrchatapi.InviteRequest(instance_id=world_location))
                            invites_sent += 1
                        except Exception:
                            pass

                status_msg = f"[green]Jump successful.[/green] Invited self. Sent {invites_sent} party invites."
                lastInviteTime = int(time.time())

        except Exception as e:
            status_msg = f"[red]Error during jump: {e}[/red]"

    console.print("Session finished.")