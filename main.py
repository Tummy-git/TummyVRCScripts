import os
import sys
import json
import shutil
import getpass
import importlib
import base64
import time
import argparse
from http.cookiejar import Cookie

import vrchatapi
from vrchatapi.api import authentication_api
from vrchatapi.exceptions import UnauthorizedException
from vrchatapi.models.two_factor_auth_code import TwoFactorAuthCode
from vrchatapi.models.two_factor_email_code import TwoFactorEmailCode
from vrchatapi.models.limited_world import LimitedWorld
from vrchatapi.models.world import World

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

def enable_windows_ansi():
    """Lets the classic cmd.exe console understand the escape codes Rich uses to clear and redraw the screen.
    Without this Rich falls back to a legacy mode where clearing the screen does nothing."""
    if os.name != 'nt':
        return
    import ctypes
    kernel32 = ctypes.windll.kernel32
    ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
    for std_handle in (-11, -12):  # stdout, stderr
        handle = kernel32.GetStdHandle(std_handle)
        mode = ctypes.c_uint32()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            kernel32.SetConsoleMode(handle, mode.value | ENABLE_VIRTUAL_TERMINAL_PROCESSING)

# Must run before any Console is created, since Rich picks its mode when the Console is constructed
enable_windows_ansi()
console = Console()

# --- MONKEY PATCH TO FIX SDK VALIDATION ERROR ---
def patched_name_setter(self, name):
    self._name = name

def patched_favorites_setter(self, favorites):
    self._favorites = favorites

LimitedWorld.name = property(fget=LimitedWorld.name.fget, fset=patched_name_setter)
LimitedWorld.favorites = property(fget=LimitedWorld.favorites.fget, fset=patched_favorites_setter)
World.favorites = property(fget=World.favorites.fget, fset=patched_favorites_setter)
# ------------------------------------------------

REGISTERED_TOOLS = [
    {"module": "world_hopper", "name": "VRChat World Hopper"},
    {"module": "regenerate_impostors", "name": "Impostor Regenerator"},
    {"module": "export_calendar", "name": "Export Followed Events to iCal"},
    {"module": "groups_manager", "name": "Manage Followed Groups"},
    {"module": "world_visit_tracker", "name": "World Visit Tracker"},
    {"module": "friends_favorites", "name": "Scrape Friends' Favorite Worlds"},
]

def scramble(text):
    if not text: return ""
    return base64.b64encode(text.encode('utf-8')).decode('utf-8')

def unscramble(text):
    if not text: return ""
    try:
        return base64.b64decode(text.encode('utf-8')).decode('utf-8')
    except Exception:
        return text

def make_cookie(name, value, expire_time):
    return Cookie(0, name, value, None, False, "api.vrchat.cloud", True, False, "/", False, False, expire_time, False, None, None, {})

def main():
    # Redirected output (cron, Task Scheduler) can default to a legacy codepage that can't print e.g. Japanese group names
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='replace')

    parser = argparse.ArgumentParser(description="VRChat Toolbox")
    parser.add_argument('--run', type=str, help='Directly run a tool module by name')
    args = parser.parse_args()
    is_automated = bool(args.run)

    script_dir = os.path.dirname(os.path.abspath(__file__))
    settings_path = os.path.join(script_dir, 'settings.json')

    if not os.path.exists(settings_path):
        shutil.copyfile(os.path.join(script_dir, 'settings.example.json'), settings_path)
        console.print("[yellow]Created settings.json from settings.example.json.[/yellow]")

    with open(settings_path, 'r') as f:
        settingsdata = json.load(f)

    cookie_file_path = os.path.join(script_dir, settingsdata['files']['cookie_path'])
    cred_file_path = os.path.join(script_dir, settingsdata['files'].get('cred_path', 'nope/cred.json'))
    lifetime_days = settingsdata['files'].get('cookie_lifetime_days', 30)
    expire_time = int(time.time()) + (lifetime_days * 86400) if lifetime_days else None

    cred_dir = os.path.dirname(cred_file_path)
    if cred_dir:
        os.makedirs(cred_dir, exist_ok=True)

    if not os.path.exists(cred_file_path):
        with open(cred_file_path, 'w') as f:
            json.dump({"username": "", "password": ""}, f, indent=4)

    with open(cred_file_path, 'r') as f:
        cred_data = json.load(f)

    vrc_user = unscramble(cred_data.get('username', ''))
    vrc_pass = unscramble(cred_data.get('password', ''))

    manual_login = False

    if not vrc_user or not vrc_pass:
        if is_automated:
            console.print("[red]Automated Run Error: Missing credentials in cred.json. Run manually first.[/red]")
            return

        console.print(Panel("[bold]Authentication Setup[/bold]", expand=False))
        if not vrc_user:
            vrc_user = console.input("Enter VRChat Username: ")
            manual_login = True
        if not vrc_pass:
            vrc_pass = getpass.getpass("Enter VRChat Password: ")
            manual_login = True

    configuration = vrchatapi.Configuration(username=vrc_user, password=vrc_pass)

    with vrchatapi.ApiClient(configuration) as api_client:
        api_client.user_agent = "VRChatToolbox/0.1.0"
        auth_api = authentication_api.AuthenticationApi(api_client)

        current_user = None

        if os.path.exists(cookie_file_path):
            with open(cookie_file_path, 'r') as f:
                cookiedata = json.load(f)
            api_client.rest_client.cookie_jar.set_cookie(make_cookie("auth", cookiedata['auth'], expire_time))
            api_client.rest_client.cookie_jar.set_cookie(make_cookie("twoFactorAuth", cookiedata['twoFactorAuth'], expire_time))

            try:
                current_user = auth_api.get_current_user()
                if not is_automated:
                    console.print(f"[green]Logged in via cookie as: {current_user.display_name}[/green]")
            except UnauthorizedException:
                console.print("[yellow]Session expired. Logging in again...[/yellow]")
                os.remove(cookie_file_path)
                api_client.rest_client.cookie_jar.clear()

        if current_user is None:
            try:
                current_user = auth_api.get_current_user()
            except UnauthorizedException as e:
                if e.status != 200:
                    console.print(f"[red]Login failed: {e.reason}[/red]")
                    return
                if is_automated:
                    console.print("[red]Automated Run Error: 2FA required. Run manually first.[/red]")
                    return
                if "Email" in e.reason:
                    auth_api.verify2_fa_email_code(two_factor_email_code=TwoFactorEmailCode(input("Email 2FA Code: ")))
                else:
                    auth_api.verify2_fa(two_factor_auth_code=TwoFactorAuthCode(input("2FA Code: ")))
                current_user = auth_api.get_current_user()

            vrc_cookies = api_client.rest_client.cookie_jar._cookies.get("api.vrchat.cloud", {}).get("/", {})
            auth_cookie = vrc_cookies.get("auth")
            tf_cookie = vrc_cookies.get("twoFactorAuth")

            if auth_cookie and tf_cookie:
                cookie_dir = os.path.dirname(cookie_file_path)
                if cookie_dir:
                    os.makedirs(cookie_dir, exist_ok=True)
                with open(cookie_file_path, 'w') as f:
                    json.dump({"auth": auth_cookie.value, "twoFactorAuth": tf_cookie.value}, f)
                console.print(f"[green]Logged in as: {current_user.display_name}[/green]")

        if manual_login:
            save_choice = console.input("Do you want to save your username and password for next time? (Y/N): ").strip().lower()
            if save_choice == 'y':
                cred_data['username'] = scramble(vrc_user)
                cred_data['password'] = scramble(vrc_pass)
                with open(cred_file_path, 'w') as f:
                    json.dump(cred_data, f, indent=4)
                console.print("[green]Credentials securely saved.[/green]")

        if is_automated:
            target_tool = next((tool for tool in REGISTERED_TOOLS if tool['module'] == args.run), None)
            if target_tool:
                try:
                    module = importlib.import_module(target_tool['module'])
                    module.run(api_client, current_user, settingsdata)
                except Exception as e:
                    console.print(f"[red]Failed to execute tool '{args.run}': {e}[/red]")
            return

        while True:
            table = Table(title="Available Tools", show_header=True, header_style="bold magenta")
            table.add_column("Key", justify="center")
            table.add_column("Tool Name")

            for idx, tool in enumerate(REGISTERED_TOOLS):
                table.add_row(str(idx), tool['name'])
            table.add_row("l", "[yellow]Logout (Clear credentials & cookies)[/yellow]")
            table.add_row("q", "[red]Quit[/red]")

            console.print("\n")
            console.print(table)
            choice = console.input("\nSelect an option: ").strip()

            if choice.lower() == 'q':
                break
            if choice.lower() == 'l':
                if os.path.exists(cookie_file_path): os.remove(cookie_file_path)
                with open(cred_file_path, 'w') as f: json.dump({"username": "", "password": ""}, f, indent=4)
                api_client.rest_client.cookie_jar.clear()
                console.print("[green]Logged out completely.[/green]")
                break

            try:
                selected_tool = REGISTERED_TOOLS[int(choice)]
                console.print(f"\n[cyan]Loading module: {selected_tool['module']}...[/cyan]")
                module = importlib.import_module(selected_tool['module'])
                module.run(api_client, current_user, settingsdata)
            except (ValueError, IndexError):
                console.print("[red]Invalid selection.[/red]")
            except Exception as e:
                console.print(f"[red]Failed to execute tool: {e}[/red]")

if __name__ == "__main__":
    main()