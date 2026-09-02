import time
import vrchatapi
from vrchatapi.rest import ApiException
from rich.console import Console
from rich.table import Table
from rich.progress import track

console = Console()
SCRIPT_VERSION = "0.6.0"

def parse_version(version_string):
    try: return tuple(map(int, version_string.split('.')))
    except: return (0, 0, 0)

def get_latest_impostor_version(avatar_obj):
    unity_packages = getattr(avatar_obj, 'unity_packages', [])
    impostor_versions = []
    for package in unity_packages:
        variant = package.get('variant') if isinstance(package, dict) else getattr(package, 'variant', None)
        version = package.get('impostorizer_version') if isinstance(package, dict) else getattr(package, 'impostorizer_version', None)
        if variant == 'impostor' and version and version != 'None':
            impostor_versions.append(version)
    return impostor_versions[-1] if impostor_versions else 'unknown'

def should_regenerate(avatar_obj, target_version):
    impostor_version = get_latest_impostor_version(avatar_obj)
    if impostor_version == 'unknown': return True
    return parse_version(impostor_version) < parse_version(target_version)

def run(api_client, current_user, settingsdata):
    console.print(f"\n[bold magenta]Impostor Regenerator v{SCRIPT_VERSION}[/bold magenta]")
    target_version_input = console.input("Target impostor version (or blank for auto): ").strip()
    api_avatar_instance = vrchatapi.AvatarsApi(api_client)

    all_avatars = []
    offset = 0
    batch_size = 100

    with console.status("[bold green]Fetching avatars..."):
        while offset < 2000:
            try:
                batch = api_avatar_instance.search_avatars(user="me", n=batch_size, offset=offset, release_status="all")
                if not batch: break
                all_avatars.extend(batch)
                offset += batch_size
            except Exception as e:
                console.print(f"[red]Error fetching: {e}[/red]")
                break

    if not all_avatars:
        console.print("[yellow]No avatars found.[/yellow]")
        return

    if not target_version_input:
        highest_version_str = None
        highest_version_tuple = (0, 0, 0)
        for avatar in all_avatars:
            ver_str = get_latest_impostor_version(avatar)
            if ver_str != 'unknown' and parse_version(ver_str) > highest_version_tuple:
                highest_version_tuple = parse_version(ver_str)
                highest_version_str = ver_str
        target_version_input = highest_version_str
        console.print(f"Auto-detected target version: [cyan]{target_version_input}[/cyan]")

    avatars_to_regenerate = []
    table = Table(title="Avatar Filter Status")
    table.add_column("Status", justify="center")
    table.add_column("Avatar Name")
    table.add_column("Version", justify="right")

    for avatar in all_avatars:
        avatar_name = getattr(avatar, 'name', 'Unknown')
        ver = get_latest_impostor_version(avatar)

        if not target_version_input or should_regenerate(avatar, target_version_input):
            avatars_to_regenerate.append(avatar)
            table.add_row("[green]REGENERATE[/green]", avatar_name, ver)
        else:
            table.add_row("[yellow]SKIP[/yellow]", avatar_name, ver)

    console.print(table)

    if not avatars_to_regenerate:
        console.print("[green]All avatars are up to date.[/green]")
        return

    successful, failed = 0, 0

    for avatar in track(avatars_to_regenerate, description="Regenerating..."):
        try:
            api_avatar_instance.enqueue_impostor(getattr(avatar, 'id', None))
            successful += 1
        except ApiException as e:
            if e.status == 429:
                console.print("\n[bold red]API Rate Limit Reached (50 per day). Try again tomorrow.[/bold red]")
                break
            failed += 1

    console.print(f"\n[bold]Completed:[/bold] [green]{successful} Success[/green] | [red]{failed} Failed[/red]")