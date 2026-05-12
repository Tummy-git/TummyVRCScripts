import os
import json
import getpass
import importlib
import base64
import time
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
    # Skips the >= 0 validation check
    self._favorites = favorites

LimitedWorld.name = property(fget=LimitedWorld.name.fget, fset=patched_name_setter)
LimitedWorld.favorites = property(fget=LimitedWorld.favorites.fget, fset=patched_favorites_setter)
World.favorites = property(fget=World.favorites.fget, fset=patched_favorites_setter)
# ------------------------------------------------

REGISTERED_TOOLS = [
    {"module": "world_hopper", "name": "VRChat World Hopper"},
    {"module": "regenerate_impostors", "name": "Impostor Regenerator"},
]

def scramble(text):
    """Obfuscates text to prevent casual reading. THIS IS NOT SECURE ENCRYPTION."""
    if not text: return ""
    return base64.b64encode(text.encode('utf-8')).decode('utf-8')

def unscramble(text):
    """Reverses the Base64 obfuscation."""
    if not text: return ""
    try:
        return base64.b64decode(text.encode('utf-8')).decode('utf-8')
    except Exception:
        # Fallback in case the user has legacy plaintext in their settings file
        return text

def make_cookie(name, value, expire_time):
    return Cookie(0, name, value, None, False, "api.vrchat.cloud", True, False, "/", False, False, expire_time, False, None, None, {})

def save_settings(settings_path, data):
    with open(settings_path, 'w') as f:
        json.dump(data, f, indent=4)

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    settings_path = os.path.join(script_dir, 'settings.json')

    with open(settings_path, 'r') as f:
        settingsdata = json.load(f)

    cookie_file_path = settingsdata['files']['cookie_path']
    cred_file_path = settingsdata['files'].get('cred_path', 'nope/cred.json')
    cookie_lifetime_seconds = settingsdata['files'].get('cookie_lifetime_days', 30) * 86400
    expire_time = int(time.time()) + cookie_lifetime_seconds

    # --- Ensure Credentials File & Folder Exist ---
    cred_dir = os.path.dirname(cred_file_path)
    if cred_dir:
        os.makedirs(cred_dir, exist_ok=True)

    if not os.path.exists(cred_file_path):
        with open(cred_file_path, 'w') as f:
            json.dump({"username": "", "password": ""}, f, indent=4)

    # Attempt to load and unscramble saved credentials from cred.json
    with open(cred_file_path, 'r') as f:
        cred_data = json.load(f)

    vrc_user = unscramble(cred_data.get('username', ''))
    vrc_pass = unscramble(cred_data.get('password', ''))

    manual_login = False

    if not vrc_user or not vrc_pass:
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
                print(f"Logged in via cookie as: {current_user.display_name} ({current_user.id})")
            except UnauthorizedException:
                print("Session expired. Please log in again.")
                os.remove(cookie_file_path)
                return
        else:
            try:
                current_user = auth_api.get_current_user()
            except UnauthorizedException as e:
                if e.status == 200:
                    if "Email" in e.reason:
                        auth_api.verify2_fa_email_code(two_factor_email_code=TwoFactorEmailCode(input("Email 2FA Code: ")))
                    else:
                        auth_api.verify2_fa(two_factor_auth_code=TwoFactorAuthCode(input("2FA Code: ")))
                    current_user = auth_api.get_current_user()

            # Save the new auth cookies
            cookie_jar = api_client.rest_client.cookie_jar._cookies["api.vrchat.cloud"]["/"]

            # Ensure cookie folder exists before saving
            cookie_dir = os.path.dirname(cookie_file_path)
            if cookie_dir:
                os.makedirs(cookie_dir, exist_ok=True)

            with open(cookie_file_path, 'w') as f:
                json.dump({"auth": cookie_jar["auth"].value, "twoFactorAuth": cookie_jar["twoFactorAuth"].value}, f)
            print(f"Logged in as: {current_user.display_name} ({current_user.id})")

        # --- Save Credentials Prompt ---
        if manual_login:
            save_choice = input("Do you want to save your username and password for next time? (Y/N): ").strip().lower()
            if save_choice == 'y':
                cred_data['username'] = scramble(vrc_user)
                cred_data['password'] = scramble(vrc_pass)
                with open(cred_file_path, 'w') as f:
                    json.dump(cred_data, f, indent=4)
                print(f"Credentials scrambled and saved to {cred_file_path}.")

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

                # Clear credentials from cred.json instead of settings.json
                with open(cred_file_path, 'w') as f:
                    json.dump({"username": "", "password": ""}, f, indent=4)

                # Clear active client cookies
                api_client.rest_client.cookie_jar.clear()
                print("Logged out. Credentials and cookies have been cleared from disk.")
                break

            try:
                choice_idx = int(choice)
                selected_tool = REGISTERED_TOOLS[choice_idx]
            except (ValueError, IndexError):
                print("Invalid selection. Try again.")
                continue

            # Dynamically import and run the selected script
            print(f"\nLoading module: {selected_tool['module']}...")
            try:
                module = importlib.import_module(selected_tool['module'])
                if hasattr(module, 'run'):
                    module.run(api_client, current_user, settingsdata)
                else:
                    print(f"Error: The module '{selected_tool['module']}' must have a 'run(api_client, current_user, settingsdata)' function.")
            except Exception as e:
                print(f"Failed to execute tool: {e}")

if __name__ == "__main__":
    main()