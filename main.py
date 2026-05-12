import os
import json
import getpass
import importlib
import base64
import time
import argparse  # <--- Added for command-line arguments
from http.cookiejar import Cookie

import vrchatapi
from vrchatapi.api import authentication_api
from vrchatapi.exceptions import UnauthorizedException
from vrchatapi.models.two_factor_auth_code import TwoFactorAuthCode
from vrchatapi.models.two_factor_email_code import TwoFactorEmailCode
from vrchatapi.models.limited_world import LimitedWorld
from vrchatapi.models.world import World

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

def save_settings(settings_path, data):
    with open(settings_path, 'w') as f:
        json.dump(data, f, indent=4)

def main():
    # --- Command Line Argument Setup ---
    parser = argparse.ArgumentParser(description="VRChat Toolbox")
    parser.add_argument('--run', type=str, help='Directly run a tool module by name (e.g., --run export_calendar)')
    args = parser.parse_args()
    is_automated = bool(args.run)

    script_dir = os.path.dirname(os.path.abspath(__file__))
    settings_path = os.path.join(script_dir, 'settings.json')

    with open(settings_path, 'r') as f:
        settingsdata = json.load(f)

    cookie_file_path = settingsdata['files']['cookie_path']
    cred_file_path = settingsdata['files'].get('cred_path', 'nope/cred.json')

    lifetime_days = settingsdata['files'].get('cookie_lifetime_days', 30)

    if lifetime_days is None:
        expire_time = None
    else:
        expire_time = int(time.time()) + (lifetime_days * 86400)

    # --- Ensure Credentials File & Folder Exist ---
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
            print("Automated Run Error: Missing credentials in cred.json. Run manually first.")
            return

        print("\n--- Authentication Setup ---")
        if not vrc_user:
            vrc_user = input("Enter VRChat Username: ")
            manual_login = True
        if not vrc_pass:
            vrc_pass = getpass.getpass("Enter VRChat Password: ")
            manual_login = True
        print("----------------------------\n")

    configuration = vrchatapi.Configuration(username=vrc_user, password=vrc_pass)

    with vrchatapi.ApiClient(configuration) as api_client:
        api_client.user_agent = "VRChatToolbox/0.1.0 akoj93@gmail.com"
        auth_api = authentication_api.AuthenticationApi(api_client)

        # --- Cookie / Login Handling ---
        if os.path.exists(cookie_file_path):
            with open(cookie_file_path, 'r') as f:
                cookiedata = json.load(f)
            api_client.rest_client.cookie_jar.set_cookie(make_cookie("auth", cookiedata['auth'], expire_time))
            api_client.rest_client.cookie_jar.set_cookie(make_cookie("twoFactorAuth", cookiedata['twoFactorAuth'], expire_time))

            try:
                current_user = auth_api.get_current_user()
                if not is_automated:
                    print(f"Logged in via cookie as: {current_user.display_name} ({current_user.id})")
            except UnauthorizedException:
                if is_automated:
                    print("Automated Run Error: Session expired. Run manually to log in again.")
                    return
                print("Session expired. Please log in again.")
                os.remove(cookie_file_path)
                return
        else:
            try:
                current_user = auth_api.get_current_user()
            except UnauthorizedException as e:
                if is_automated:
                    print("Automated Run Error: 2FA required. Run manually to log in.")
                    return

                if e.status == 200:
                    if "Email" in e.reason:
                        auth_api.verify2_fa_email_code(two_factor_email_code=TwoFactorEmailCode(input("Email 2FA Code: ")))
                    else:
                        auth_api.verify2_fa(two_factor_auth_code=TwoFactorAuthCode(input("2FA Code: ")))
                    current_user = auth_api.get_current_user()

            cookie_jar = api_client.rest_client.cookie_jar._cookies["api.vrchat.cloud"]["/"]
            cookie_dir = os.path.dirname(cookie_file_path)
            if cookie_dir:
                os.makedirs(cookie_dir, exist_ok=True)

            with open(cookie_file_path, 'w') as f:
                json.dump({"auth": cookie_jar["auth"].value, "twoFactorAuth": cookie_jar["twoFactorAuth"].value}, f)
            print(f"Logged in as: {current_user.display_name} ({current_user.id})")

        if manual_login:
            save_choice = input("Do you want to save your username and password for next time? (Y/N): ").strip().lower()
            if save_choice == 'y':
                cred_data['username'] = scramble(vrc_user)
                cred_data['password'] = scramble(vrc_pass)
                with open(cred_file_path, 'w') as f:
                    json.dump(cred_data, f, indent=4)
                print(f"Credentials scrambled and saved to {cred_file_path}.")

        # --- Direct Run Execution (Bypasses Menu) ---
        if is_automated:
            target_tool = next((tool for tool in REGISTERED_TOOLS if tool['module'] == args.run), None)
            if target_tool:
                try:
                    module = importlib.import_module(target_tool['module'])
                    module.run(api_client, current_user, settingsdata)
                except Exception as e:
                    print(f"Failed to execute tool '{args.run}': {e}")
            else:
                print(f"Error: Tool '{args.run}' not found in registered tools.")
            return # Exits the script immediately after running

        # --- Menu System Loop ---
        while True:
            print("\n--- Available Tools ---")
            for idx, tool in enumerate(REGISTERED_TOOLS):
                print(f"[{idx}] {tool['name']}")
            print("[l] Logout (Clear credentials & cookies)")
            print("[q] Quit")

            choice = input("\nSelect an option: ").strip()

            if choice.lower() == 'q':
                break

            if choice.lower() == 'l':
                print("Logging out...")
                if os.path.exists(cookie_file_path):
                    os.remove(cookie_file_path)
                with open(cred_file_path, 'w') as f:
                    json.dump({"username": "", "password": ""}, f, indent=4)
                api_client.rest_client.cookie_jar.clear()
                print("Logged out. Credentials and cookies have been cleared from disk.")
                break

            try:
                choice_idx = int(choice)
                selected_tool = REGISTERED_TOOLS[choice_idx]
            except (ValueError, IndexError):
                print("Invalid selection. Try again.")
                continue

            print(f"\nLoading module: {selected_tool['module']}...")
            try:
                module = importlib.import_module(selected_tool['module'])
                if hasattr(module, 'run'):
                    module.run(api_client, current_user, settingsdata)
                else:
                    print(f"Error: The module '{selected_tool['module']}' must have a 'run' function.")
            except Exception as e:
                print(f"Failed to execute tool: {e}")

if __name__ == "__main__":
    main()