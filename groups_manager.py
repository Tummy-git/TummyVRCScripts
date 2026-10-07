import os
import vrchatapi
from rich.console import Console
from rich.table import Table
from json_utils import load_json_list, save_json_list

console = Console()

def load_groups(file_path):
    return load_json_list(file_path)

def save_groups(file_path, groups):
    save_json_list(file_path, groups)
    console.print(f"[green]Groups file saved. Total: {len(groups)}[/green]")

def display_groups(groups):
    if not groups:
        console.print("[yellow]No followed groups[/yellow]")
        return
    table = Table(title="Followed Groups", show_header=True)
    table.add_column("Index", style="cyan", justify="right")
    table.add_column("Group Name", style="magenta")
    table.add_column("Group ID")
    for i, g in enumerate(groups, 1):
        table.add_row(str(i), g.get('name') or '<unknown>', g.get('id'))
    console.print(table)

def prompt_add_group(api_client, groups, groups_file_path):
    new_id = console.input("Enter group ID to follow (or blank to cancel): ").strip()
    if not new_id: return groups

    fetched_name = ""
    try:
        groups_api = vrchatapi.api.groups_api.GroupsApi(api_client)
        info = groups_api.get_group(new_id)
        fetched_name = getattr(info, 'name', None) or (info.get('name') if isinstance(info, dict) else "")
    except Exception as e:
        console.print(f"[yellow]Warning: Couldn't fetch group name now: {e}[/yellow]")

    groups.append({"id": new_id, "name": fetched_name or ""})
    save_groups(groups_file_path, groups)
    return groups

def prompt_remove_group(groups, groups_file_path):
    display_groups(groups)
    try:
        idx = int(console.input("Enter number to remove (0 cancel): ").strip())
        if idx == 0: return groups
        if not 1 <= idx <= len(groups): raise IndexError(idx)
        removed = groups.pop(idx-1)
        save_groups(groups_file_path, groups)
        console.print(f"[red]Removed {removed.get('name') or removed.get('id')}[/red]")
    except Exception:
        console.print("[red]Invalid selection.[/red]")
    return groups

def fill_missing_names(api_client, groups, groups_file_path):
    if not groups: return groups
    try: groups_api = vrchatapi.api.groups_api.GroupsApi(api_client)
    except Exception: return groups

    changed = False
    for g in groups:
        if not g.get('name') and g.get('id'):
            try:
                info = groups_api.get_group(g['id'])
                fetched_name = getattr(info, 'name', None) or (info.get('name') if isinstance(info, dict) else None)
                if fetched_name:
                    g['name'] = fetched_name
                    console.print(f"[green]Filled name for {g['id']}: {fetched_name}[/green]")
                    changed = True
            except Exception as e:
                pass
    if changed: save_groups(groups_file_path, groups)
    else: console.print("No updates made.")
    return groups

def run(api_client, current_user, settingsdata):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    groups_file_path = os.path.join(script_dir, settingsdata['files'].get('groups_path', 'groups.json'))
    groups = load_groups(groups_file_path)

    while True:
        # Brackets are escaped so Rich doesn't treat [l] etc. as markup tags
        console.print("\n[bold]Groups Manager:[/bold] [cyan]\\[l]ist, \\[a]dd, \\[r]emove, \\[f]ill-names, \\[q]uit[/cyan]")
        cmd = console.input("Select: ").strip().lower()
        if cmd in ('q','quit'): break
        elif cmd in ('l','list'): display_groups(groups)
        elif cmd in ('a','add'): groups = prompt_add_group(api_client, groups, groups_file_path)
        elif cmd in ('r','remove'): groups = prompt_remove_group(groups, groups_file_path)
        elif cmd in ('f','fill','fill-names'): groups = fill_missing_names(api_client, groups, groups_file_path)
        else: console.print("[red]Unknown command.[/red]")