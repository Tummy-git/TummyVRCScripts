import time
import vrchatapi
from vrchatapi.rest import ApiException

SCRIPT_VERSION = "0.6.0"

def parse_version(version_string):
    """Convert version string like '1.4.0' to tuple (1, 4, 0) for comparison"""
    try:
        return tuple(map(int, version_string.split('.')))
    except (ValueError, AttributeError, TypeError):
        return (0, 0, 0)

def get_latest_impostor_version(avatar_obj):
    """Extract the latest impostor version from unity_packages array"""
    unity_packages = getattr(avatar_obj, 'unity_packages', [])

    if not unity_packages:
        return 'unknown'

    # Find all impostor variants and get the one with the highest version
    impostor_versions = []
    for package in unity_packages:
        # Handle both object attributes and dict keys
        if isinstance(package, dict):
            variant = package.get('variant')
            version = package.get('impostorizer_version')
        else:
            variant = getattr(package, 'variant', None)
            version = getattr(package, 'impostorizer_version', None)

        if variant == 'impostor' and version and version != 'None':
            impostor_versions.append(version)

    if impostor_versions:
        # Return the latest version (last one in list, as they seem to be added chronologically)
        return impostor_versions[-1]

    return 'unknown'

def should_regenerate(avatar_obj, target_version):
    """Check if avatar's impostor version is older than target version"""
    impostor_version = get_latest_impostor_version(avatar_obj)

    if impostor_version == 'unknown':
        # No impostor version found, regenerate it
        return True

    current_version = parse_version(impostor_version)
    target = parse_version(target_version)

    return current_version < target

def run(api_client, current_user, settingsdata):
    print(f"\nImpostor Regenerator v{SCRIPT_VERSION}")
    print("=" * 80)

    print("\n--- Impostor Version Filter ---")
    print("If you want to skip avatars with a certain impostor version or newer,")
    print("enter the minimum version (e.g., 1.4.2)")
    print("Leave blank to auto-detect the highest version among your avatars.")
    target_version_input = input("Target impostor version (or blank for auto): ").strip()

    # --- Initialize Avatar API ---
    api_avatar_instance = vrchatapi.AvatarsApi(api_client)

    # --- Fetch all avatars (public + private) with release_status="all" ---
    print("\nFetching all your avatars (public + private)...")
    all_avatars = []
    offset = 0
    batch_size = 100
    max_attempts = 20

    while offset < (batch_size * max_attempts):

        try:
            print(f"Fetching batch at offset {offset}...")
            # Use the SDK with release_status="all" to get both public and private avatars
            batch = api_avatar_instance.search_avatars(
                user="me",
                n=batch_size,
                offset=offset,
                release_status="all"
            )

            if not batch or len(batch) == 0:
                print(f"No more avatars found at offset {offset}")
                break

            all_avatars.extend(batch)
            print(f"Fetched {len(batch)} avatars (total: {len(all_avatars)})")

            lastFetchTime = int(time.time())
            offset += batch_size

        except Exception as e:
            print(f"Error fetching avatars at offset {offset}: {e}")
            break

    print(f"\nTotal avatars found: {len(all_avatars)}")

    if not all_avatars:
        print("No avatars found.")
        return

    # --- Auto-detect highest version if input was blank ---
    if not target_version_input:
        print("\nAuto-detecting the highest impostor version among your avatars...")
        highest_version_str = None
        highest_version_tuple = (0, 0, 0)

        for avatar in all_avatars:
            ver_str = get_latest_impostor_version(avatar)
            if ver_str != 'unknown':
                ver_tuple = parse_version(ver_str)
                if ver_tuple > highest_version_tuple:
                    highest_version_tuple = ver_tuple
                    highest_version_str = ver_str

        if highest_version_str:
            print(f"Detected highest version: {highest_version_str}")
            target_version_input = highest_version_str
        else:
            print("Could not find any existing impostor versions to use as a baseline.")

    # --- Filter avatars based on version ---
    avatars_to_regenerate = []
    avatars_to_skip = []

    if target_version_input:
        print(f"\nFiltering avatars by impostor version...")
        print(f"Will regenerate impostors for avatars with version < {target_version_input}")
        print("-" * 100)

        for avatar in all_avatars:
            avatar_name = getattr(avatar, 'name', 'Unknown')
            impostor_version = get_latest_impostor_version(avatar)
            release_status = getattr(avatar, 'release_status', 'unknown')

            if should_regenerate(avatar, target_version_input):
                avatars_to_regenerate.append(avatar)
                status = "REGENERATE" if impostor_version != 'unknown' else "NO IMPOSTOR"
                print(f"  O {avatar_name:<40} (version: {impostor_version:<10}) [{release_status}] - {status}")
            else:
                avatars_to_skip.append(avatar)
                print(f"  X {avatar_name:<40} (version: {impostor_version:<10}) [{release_status}] - SKIP (up to date)")

        print("-" * 100)
        print(f"\nAvatars to regenerate: {len(avatars_to_regenerate)}")
        print(f"Avatars to skip: {len(avatars_to_skip)}")
    else:
        # This fallback only triggers if input was blank AND no avatars had any impostors at all
        avatars_to_regenerate = all_avatars
        print(f"\nWill regenerate impostors for all {len(all_avatars)} avatars.")
        print("-" * 100)
        for avatar in all_avatars:
            avatar_name = getattr(avatar, 'name', 'Unknown')
            impostor_version = get_latest_impostor_version(avatar)
            release_status = getattr(avatar, 'release_status', 'unknown')
            print(f"  {avatar_name:<40} (version: {impostor_version:<10}) [{release_status}]")
        print("-" * 100)

    if not avatars_to_regenerate:
        print(f"\nNo avatars need impostor regeneration.")
        return

    print(f"\nStarting impostor regeneration for {len(avatars_to_regenerate)} avatars...")
    print("=" * 100)

    successful = 0
    failed = 0

    for i, avatar in enumerate(avatars_to_regenerate, 1):

        try:
            avatar_id = getattr(avatar, 'id', None)
            avatar_name = getattr(avatar, 'name', 'Unknown')
            impostor_version = get_latest_impostor_version(avatar)

            api_avatar_instance.enqueue_impostor(avatar_id)
            print(f"[{i}/{len(avatars_to_regenerate)}] ✓ {avatar_name:<40} (old version: {impostor_version})")
            successful += 1

        except ApiException as e:
            if e.status == 429:
                print(f"[{i}/{len(avatars_to_regenerate)}] ✗ {avatar_name:<40} - ERROR: Rate Limited")
                print("\n[!] API Limit Reached.")
                print("VRChat limits impostor generations to 50 per day.")
                print("Please wait 24 hours before running the script again to process the remaining avatars.")
                failed += 1
                break
            else:
                print(f"[{i}/{len(avatars_to_regenerate)}] ✗ {avatar_name:<40} - ERROR: {e.status} {e.reason}")
                failed += 1

    print("=" * 100)
    print(f"\nCompleted!")
    print(f"  Successful: {successful}")
    print(f"  Failed: {failed}")
    print("Session finished.")