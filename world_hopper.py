import os
import json
import math
import time
import re
import webbrowser
import random

import vrchatapi
from vrcx_utils import add_favorite_world
from json_utils import clean_for_json, load_json_list, save_json_list
from vrchatapi import InstanceType, InstanceRegion, CreateInstanceRequest
from vrchatapi.rest import ApiException
from vrchatapi.api import AuthenticationApi

from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.progress_bar import ProgressBar
from rich.table import Table
from rich.text import Text

console = Console()

# Names shown in the UI, matching what you type for the 'type' command
INSTANCE_TYPE_NAMES = {
    InstanceType.FRIENDS: "Friends",
    InstanceType.HIDDEN: "Friends+",
    InstanceType.PRIVATE: "Invite",
    InstanceType.PUBLIC: "Public",
}
INSTANCE_TYPE_ALIASES = {
    'friends': InstanceType.FRIENDS,
    'friends+': InstanceType.HIDDEN, 'hidden': InstanceType.HIDDEN,
    'invite': InstanceType.PRIVATE, 'invite+': InstanceType.PRIVATE, 'private': InstanceType.PRIVATE,
    'public': InstanceType.PUBLIC,
}
LAUNCH_MODES = ('invite', 'launch', 'both')

KEY_HINTS = ("[bold]Enter[/bold] next · [bold]#[/bold] jump to · [bold]type[/bold] · [bold]mode[/bold] · "
             "[bold]update[/bold]/[bold]add[/bold]/[bold]remove[/bold]/[bold]clear[/bold] party · "
             "[bold]fav[/bold] · [bold]help[/bold] · [bold]quit[/bold]")
HELP_ROWS = [
    ("Enter", "Jump to the next world"),
    ("<number>", "Jump to that world in the queue"),
    ("type <t>", "Instance type: friends, friends+, invite, public"),
    ("mode <m>", "invite (invite yourself), launch (open VRChat), both"),
    ("update", "Set the party to everyone in your current instance"),
    ("add", "Add a party member by user ID"),
    ("remove", "Remove a party member by number"),
    ("clear", "Remove everyone from the party"),
    ("fav", "Add the world you're in to your VRCX favorites"),
    ("quit", "Exit. The session is kept so you can resume it"),
]

# Lines used outside the bottom panels: header (5), progress (1), hints (1), status (1), prompt (1), slack (1)
RESERVED_LINES = 10
MIN_PANEL_HEIGHT = 8

def get_unity_version(data):
    world_data = data.get('world', data)
    ups = world_data.get('unity_packages', [])
    return ups[-1].get('unity_version') if ups else 'unknown'

def save_session_index(settings_path, settingsdata, index):
    settingsdata['currentworld'] = "" if index is None else str(index)
    with open(settings_path, 'w', encoding='utf-8') as f:
        json.dump(settingsdata, f, indent=4, ensure_ascii=False)

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

def list_table():
    table = Table(show_header=False, box=None, padding=(0, 1), expand=True)
    table.add_column(justify="right", no_wrap=True, style="dim")
    table.add_column(no_wrap=True, overflow="ellipsis", ratio=1)
    return table

def build_header(world, visited):
    if not world:
        return Panel("No worlds in the queue.", title="Current World", border_style="cyan", height=5)
    text = Text.assemble((world['name'], "bold green"), " by ", (world['author'], "bold cyan"),
                         f"\nID: {world['id']}\nUnity: {world['unity']}", no_wrap=True, overflow="ellipsis")
    if visited:
        return Panel(text, title="Current World", border_style="cyan", height=5)
    return Panel(text, title="Up Next (press Enter to jump)", border_style="yellow", height=5)

def build_progress(done, total):
    grid = Table.grid(expand=True, padding=(0, 1))
    grid.add_column(no_wrap=True)
    grid.add_column(ratio=1)
    grid.add_column(no_wrap=True, justify="right")
    percent = done * 100 // total if total else 0
    grid.add_row(f"World {done} / {total}", ProgressBar(total=max(total, 1), completed=done), f"{percent:>3}%")
    return grid

def build_coming_next(next_worlds, first_number, rows):
    table = list_table()
    for i, w in enumerate(next_worlds[:rows]):
        table.add_row(f"{first_number + i}.", Text.assemble(w.get('name') or 'Unknown', (f" by {w.get('author_name') or 'Unknown'}", "dim")))
    if not next_worlds:
        table.add_row("", Text("End of queue", style="dim"))
    return table

def build_party(co_explorers, rows):
    table = list_table()
    if not co_explorers:
        table.add_row("", Text("Nobody, just you", style="dim"))
        return table
    shown = co_explorers if len(co_explorers) <= rows else co_explorers[:max(rows - 1, 0)]
    for i, explorer in enumerate(shown, 1):
        table.add_row(str(i), Text(explorer.get('name') or explorer.get('uid', '?')))
    if len(shown) < len(co_explorers):
        table.add_row("", Text(f"...and {len(co_explorers) - len(shown)} more", style="dim"))
    return table

def render_dashboard(json_list, active_idx, visited, current_world_info, instance_type, launch_mode, co_explorers, status_msg):
    type_name = INSTANCE_TYPE_NAMES.get(instance_type, str(instance_type))
    next_worlds = json_list[active_idx + 1:]
    done = active_idx + 1 if visited else active_idx
    bottom_height = console.size.height - RESERVED_LINES

    main_grid = Table.grid(expand=True)
    main_grid.add_column()
    main_grid.add_row(build_header(current_world_info, visited))
    main_grid.add_row(build_progress(done, len(json_list)))

    if bottom_height >= MIN_PANEL_HEIGHT:
        next_panel = Panel(build_coming_next(next_worlds, active_idx + 2, bottom_height - 2),
                           title="Coming Next", border_style="blue", height=bottom_height)

        settings_text = Text.assemble("Instance: ", (type_name, "bold"), "\nMode: ", (launch_mode.upper(), "bold"))
        settings_panel = Panel(settings_text, title="Settings", border_style="yellow", height=4)
        party_height = bottom_height - 4
        party_panel = Panel(build_party(co_explorers, party_height - 2), title=f"Hopping Party ({len(co_explorers)})",
                            border_style="white", height=party_height)

        sidebar_grid = Table.grid(expand=True)
        sidebar_grid.add_column()
        sidebar_grid.add_row(settings_panel)
        sidebar_grid.add_row(party_panel)

        bottom_grid = Table.grid(expand=True)
        bottom_grid.add_column(ratio=1)
        bottom_grid.add_column(ratio=1)
        bottom_grid.add_row(next_panel, sidebar_grid)
        main_grid.add_row(bottom_grid)
    else:
        # Small terminal: one summary line instead of the panels
        next_name = next_worlds[0].get('name') or 'Unknown' if next_worlds else "End of queue"
        sep = (" · ", "dim")
        main_grid.add_row(Text.assemble(("Next: ", "dim"), next_name, sep, type_name, sep, launch_mode.upper(), sep,
                                        f"Party: {len(co_explorers)}", no_wrap=True, overflow="ellipsis"))

    console.clear()
    console.print(main_grid)
    console.print(KEY_HINTS, style="dim", no_wrap=True, overflow="ellipsis")
    console.print(f"[bold]System:[/bold] {status_msg or 'Ready.'}")

def show_help():
    table = Table(title="World Hopper Commands", show_header=False)
    table.add_column(style="bold cyan", no_wrap=True)
    table.add_column()
    for command, description in HELP_ROWS:
        table.add_row(Text(command), description)
    console.clear()
    console.print(table)
    console.input("Press Enter to return...")

def load_world_ids(api_world_instance, manual_world_list_path):
    """Fetches every world in the manual list. Returns (worlds, failed) where failed describes skipped lines."""
    worlds, failed = [], []
    if not os.path.exists(manual_world_list_path):
        return worlds, failed
    with open(manual_world_list_path, 'r') as f:
        ids = [line.strip() for line in f if line.strip()]
    with console.status("") as status:
        for i, wid in enumerate(ids, 1):
            status.update(f"[bold green]Fetching world {i}/{len(ids)}...")
            try:
                worlds.append(api_world_instance.get_world(wid))
                time.sleep(0.5)
            except ApiException as e:
                failed.append(f"{wid} ({e.status} {e.reason})")
    return worlds, failed

def run(api_client, current_user, settingsdata):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    settings_path = os.path.join(script_dir, 'settings.json')
    world_json_output_path = os.path.join(script_dir, settingsdata['files']['world_list_path'])
    worldhoppers_file_path = os.path.join(script_dir, settingsdata['files']['co_explorers_path'])
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
    status_msg = ""

    api_instance_instance = vrchatapi.InstancesApi(api_client)
    api_invite_instance = vrchatapi.InviteApi(api_client)
    api_world_instance = vrchatapi.WorldsApi(api_client)

    newsession = True
    if current_world:
        console.print(f"\n[bold yellow]You have an ongoing jump session stored (at world {int(current_world) + 1}).[/bold yellow]")
        if console.input("Continue last session? (y/n): ").strip().lower() == "y":
            if os.path.exists(world_json_output_path):
                newsession = False
            else:
                console.print("[red]Saved world queue not found. Starting a new session.[/red]")

    if newsession:
        current_world = ""
        save_session_index(settings_path, settingsdata, None)
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
            api_response, failed_ids = load_world_ids(api_world_instance, manual_world_list_path)
            if failed_ids:
                shown = ", ".join(failed_ids[:3]) + (f" and {len(failed_ids) - 3} more" if len(failed_ids) > 3 else "")
                status_msg = f"[yellow]Skipped {len(failed_ids)} world ID(s) that couldn't be loaded: {escape(shown)}[/yellow]"
            if not api_response:
                console.print("[yellow]No worlds could be loaded from the file. Falling back to Community Labs (Newest).[/yellow]")
            use_api_search = not api_response
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
                    console.print(f"[red]Error fetching queue: {escape(str(e))}[/red]")

        with open(world_json_output_path, "w", encoding="utf-8") as f:
            json.dump(clean_for_json(api_response), f, indent=2, ensure_ascii=False)

    co_explorers = load_json_list(worldhoppers_file_path)

    with open(world_json_output_path, 'r', encoding='utf-8') as f:
        json_list = json.load(f)

    last_jump_time = 0
    activeJumpIndex = int(current_world) if current_world != "" else 0
    # Index of the last world jumped to successfully. A resumed session has already visited its stored index.
    visited_index = activeJumpIndex if current_world != "" else None
    if not 0 <= activeJumpIndex < len(json_list):
        activeJumpIndex, visited_index = 0, None
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

        render_dashboard(json_list, activeJumpIndex, visited_index == activeJumpIndex, current_world_info,
                         current_instance_type, action_mode, co_explorers, status_msg)
        status_msg = ""

        user_input = console.input("[bold]>[/bold] ").strip()
        command = user_input.lower()

        if command == 'help':
            show_help()
            continue

        elif command in ('q', 'quit'):
            console.print("Session saved. Choose 'Continue last session' next time to resume.")
            return

        elif command.startswith('type'):
            val = command.replace('type', '', 1).strip()
            if not val:
                val = console.input("Type (friends, friends+, invite, public): ").strip().lower()
            if val in INSTANCE_TYPE_ALIASES:
                current_instance_type = INSTANCE_TYPE_ALIASES[val]
                status_msg = f"Instance type set to {INSTANCE_TYPE_NAMES[current_instance_type]}."
            else:
                status_msg = f"[red]Unknown instance type '{escape(val)}'. Use friends, friends+, invite or public.[/red]"
            continue

        elif command.startswith('mode'):
            val = command.replace('mode', '', 1).strip()
            if not val:
                val = console.input("Mode (invite, launch, both): ").strip().lower()
            if val in LAUNCH_MODES:
                action_mode = val
                status_msg = f"Mode set to {action_mode.upper()}."
            else:
                status_msg = f"[red]Unknown mode '{escape(val)}'. Use invite, launch or both.[/red]"
            continue

        elif command == 'update':
            api_auth = AuthenticationApi(api_client)
            user = api_auth.get_current_user()
            w_id = getattr(getattr(user, 'presence', None), 'world', None)
            i_id = getattr(getattr(user, 'presence', None), 'instance', None)
            if w_id and i_id:
                users = get_instance_users(api_client, w_id, i_id)
                co_explorers = [u for u in users if u['uid'] != current_user.id]
                save_json_list(worldhoppers_file_path, co_explorers)
                status_msg = f"Updated party with {len(co_explorers)} users from current instance."
            else:
                status_msg = "[red]Not in a valid instance.[/red]"
            continue

        elif command == 'clear':
            co_explorers = []
            save_json_list(worldhoppers_file_path, co_explorers)
            status_msg = "Party cleared."
            continue

        elif command == 'add':
            uid = console.input("Enter user ID: ").strip()
            if not re.match(r"^usr_[0-9a-fA-F-]{36}$", uid):
                status_msg = "[red]That doesn't look like a user ID (usr_xxxxxxxx-xxxx-...).[/red]"
            elif any(e.get('uid') == uid for e in co_explorers):
                status_msg = "[yellow]That user is already in the party.[/yellow]"
            else:
                user_info = get_user_by_id(api_client, uid)
                if user_info:
                    co_explorers.append(user_info)
                    save_json_list(worldhoppers_file_path, co_explorers)
                    status_msg = f"Added {escape(user_info['name'])}."
                else:
                    status_msg = "[red]User not found.[/red]"
            continue

        elif command == 'remove':
            try:
                idx = int(console.input("Enter number to remove: ").strip()) - 1
            except ValueError:
                idx = -1
            if 0 <= idx < len(co_explorers):
                removed = co_explorers.pop(idx)
                save_json_list(worldhoppers_file_path, co_explorers)
                status_msg = f"Removed {escape(removed['name'])}."
            else:
                status_msg = f"[red]Enter a number between 1 and {len(co_explorers)}.[/red]" if co_explorers else "[red]The party is empty.[/red]"
            continue

        elif command == 'fav':
            if vrcx_allowed:
                cid = get_current_presence_world_id(api_client)
                if not cid:
                    status_msg = "[red]Couldn't determine your current world. Are you in a world?[/red]"
                    continue
                status = add_favorite_world(vrcx_db_path, cid, vrcx_fav_group)
                if status == "added": status_msg = f"[green]Added {cid} to {escape(vrcx_fav_group)}[/green]"
                elif status == "duplicate": status_msg = f"[yellow]World already in {escape(vrcx_fav_group)}[/yellow]"
                else: status_msg = "[red]Database locked/Error.[/red]"
            else:
                status_msg = "[red]VRCX interaction disabled in settings.[/red]"
            continue

        elif user_input == "":
            # Retry the current world if the last jump to it failed, otherwise move on
            target_index = activeJumpIndex + 1 if visited_index == activeJumpIndex else activeJumpIndex
            if target_index >= len(json_list):
                save_session_index(settings_path, settingsdata, None)
                break
        else:
            try:
                # Interpret user numerical input based on the 1-based index shown in the UI
                target_index = int(user_input) - 1
            except ValueError:
                status_msg = f"[red]Unknown command: {escape(user_input)}. Type 'help' for commands.[/red]"
                continue
            if not (0 <= target_index < len(json_list)):
                status_msg = f"[red]Index must be between 1 and {len(json_list)}.[/red]"
                continue

        activeJumpIndex = target_index
        world_number = activeJumpIndex + 1
        target_world_id = json_list[activeJumpIndex]['id']

        try:
            joined_existing = False
            world_location = ""

            with console.status("") as status:
                deadline = last_jump_time + apiHappyTime
                while (remaining := deadline - time.time()) > 0:
                    status.update(f"[cyan]API cooldown: jumping to world {world_number} in {math.ceil(remaining)}s...[/cyan]")
                    time.sleep(min(1, remaining))
                status.update(f"[cyan]Jumping to world {world_number}...[/cyan]")

                if current_instance_type == InstanceType.PUBLIC:
                    world_info = api_world_instance.get_world(target_world_id)
                    capacity = getattr(world_info, 'capacity', None) or 16
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
                    result = "Invited yourself."
                else:
                    webbrowser.open(f"vrchat://launch/?ref=vrchat.com&id={world_location}&attach=1")
                    result = "Launched VRChat."

                if action_mode in ["invite", "both"] and co_explorers:
                    failed_invites = 0
                    for explorer in co_explorers:
                        try:
                            api_invite_instance.invite_user(explorer['uid'], vrchatapi.InviteRequest(instance_id=world_location))
                        except Exception:
                            failed_invites += 1
                    result += f" Sent {len(co_explorers) - failed_invites}/{len(co_explorers)} party invites."
                    if failed_invites:
                        result += f" [red]({failed_invites} failed)[/red]"

                status_msg = f"[green]Jumped to world {world_number}.[/green] {result}"
                visited_index = activeJumpIndex
                save_session_index(settings_path, settingsdata, activeJumpIndex)

        except Exception as e:
            status_msg = f"[red]Error jumping to world {world_number}: {escape(str(e))}[/red] Press Enter to retry or type a number to skip."

        # Failed attempts still made API calls, so they count towards the cooldown too
        last_jump_time = time.time()

    console.print("Session finished.")
