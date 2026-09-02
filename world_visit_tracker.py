import os
from datetime import datetime
import vrchatapi
from vrchatapi.rest import ApiException
from rich.console import Console

# force_terminal=False ensures clean text output without ANSI codes when run via cron
console = Console(force_terminal=False)

def run(api_client, current_user, settingsdata):
    world_id = settingsdata.get('visitors_world_id')

    if not world_id:
        console.print("[red]Error: 'visitors_world_id' not found in settings.json.[/red]")
        return

    # Keep file paths organized alongside your existing file configs
    files_config = settingsdata.get('files', {})
    log_file_path = files_config.get('visitors_log_path', 'world_visits.log')
    script_dir = os.path.dirname(os.path.abspath(__file__))
    full_log_path = os.path.join(script_dir, log_file_path)

    api_world_instance = vrchatapi.WorldsApi(api_client)

    try:
        world_info = api_world_instance.get_world(world_id)
        visits = getattr(world_info, 'visits', 0)

        # Formatted using Swedish standard (YYYY-MM-DD HH:MM:SS)
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"{current_time} {visits}\n"

        with open(full_log_path, 'a', encoding='utf-8') as f:
            f.write(log_entry)

        console.print(f"[green]Logged {visits} visits for '{world_info.name}' at {current_time}[/green]")

    except ApiException as e:
        console.print(f"[red]Failed to fetch world data: {e}[/red]")