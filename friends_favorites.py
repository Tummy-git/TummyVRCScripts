import os
import json
import time
import datetime

import vrchatapi
from vrchatapi.rest import ApiException
from rich.console import Console
from rich.progress import Progress, BarColumn, TextColumn, MofNCompleteColumn, TimeRemainingColumn

console = Console()

# Seconds between API calls. A full scan is hundreds of requests, so keep it gentle on the API.
REQUEST_DELAY = 1.0
WORLD_GROUP_TYPES = ('world', 'vrcPlusWorld')
SAVE_EVERY = 10

def plural(count, word):
    return f"{count} {word}{'' if count == 1 else 's'}"

def get_cache_path(settingsdata):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(script_dir, settingsdata['files'].get('friends_favorites_path', 'friends_favorites.json'))

def load_cache(path):
    """Cache layout: {"scanned": {friend_id: iso time}, "worlds": {world_id: {..., "favorited_by": [friend_id]}}}"""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, dict):
            return {'scanned': data.get('scanned', {}), 'worlds': data.get('worlds', {})}
    except (OSError, json.JSONDecodeError):
        pass
    return {'scanned': {}, 'worlds': {}}

def save_cache(path, cache):
    # Write to a temp file first so stopping mid-save can't corrupt the cache
    tmp_path = path + '.tmp'
    with open(tmp_path, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False)
    os.replace(tmp_path, path)

def to_queue_entry(world):
    """Converts the API's camelCase world JSON to the snake_case shape the world hopper uses."""
    return {
        'id': world['id'],
        'name': world.get('name') or 'Unknown',
        'author_name': world.get('authorName') or 'Unknown',
        'release_status': world.get('releaseStatus'),
        'unity_packages': [{'platform': p.get('platform'), 'unity_version': p.get('unityVersion')}
                           for p in world.get('unityPackages') or []],
    }

def fetch_friend_worlds(fav_api, friend_id):
    """Returns the public worlds in all favorite world lists the friend shares with you."""
    groups = fav_api.get_favorite_groups(owner_id=friend_id, n=100)
    time.sleep(REQUEST_DELAY)
    worlds = []
    for group in groups:
        if group.type not in WORLD_GROUP_TYPES:
            continue
        # The SDK model rejects worlds without occupants, so read the raw JSON instead
        response = fav_api.get_favorite_group_contents(group.type, group.name, owner_id=friend_id, _preload_content=False)
        time.sleep(REQUEST_DELAY)
        for entry in json.loads(response.data).get('favorites', []):
            world = entry.get('world') or {}
            # Private or deleted worlds can't be joined, so leave them out
            if world.get('id') and world.get('releaseStatus') == 'public':
                worlds.append(to_queue_entry(world))
    return worlds

def forget_friend(cache, friend_id):
    cache['scanned'].pop(friend_id, None)
    for world in cache['worlds'].values():
        if friend_id in world['favorited_by']:
            world['favorited_by'].remove(friend_id)

def load_queue(path):
    """Unique worlds from the cache, the ones most of your friends favorited first."""
    worlds = [w for w in load_cache(path)['worlds'].values() if w.get('favorited_by')]
    worlds.sort(key=lambda w: (-len(w['favorited_by']), (w.get('name') or '').lower()))
    return worlds

def scan_friends(fav_api, cache, cache_path, todo):
    """Scans each friend's shared favorite worlds into the cache. Returns how many friends couldn't be read."""
    errors = 0
    with Progress(TextColumn("{task.description}"), BarColumn(), MofNCompleteColumn(), TimeRemainingColumn(), console=console) as progress:
        task = progress.add_task("Scanning friends", total=len(todo))
        for i, friend_id in enumerate(todo, 1):
            try:
                worlds = fetch_friend_worlds(fav_api, friend_id)
            except ApiException:
                errors += 1
                worlds = None
            if worlds is not None:
                forget_friend(cache, friend_id)
                for world in worlds:
                    entry = cache['worlds'].setdefault(world['id'], {'favorited_by': []})
                    entry.update(world)
                    if friend_id not in entry['favorited_by']:
                        entry['favorited_by'].append(friend_id)
                cache['scanned'][friend_id] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            progress.advance(task)
            if i % SAVE_EVERY == 0:
                save_cache(cache_path, cache)
    return errors

def run(api_client, current_user, settingsdata):
    cache_path = get_cache_path(settingsdata)
    rescan_days = settingsdata.get('friends_favorites_rescan_days', 7)
    cache = load_cache(cache_path)
    fav_api = vrchatapi.FavoritesApi(api_client)

    console.print("\n[bold]--- Friends' Favorite Worlds ---[/bold]")
    friends = list(getattr(current_user, 'friends', None) or [])

    # People you are no longer friends with shouldn't keep worlds in the list
    for friend_id in [f for f in cache['scanned'] if f not in set(friends)]:
        forget_friend(cache, friend_id)

    now = datetime.datetime.now(datetime.timezone.utc)
    cutoff = now - datetime.timedelta(days=rescan_days)
    def scanned_recently(friend_id):
        scanned_at = cache['scanned'].get(friend_id)
        return scanned_at and datetime.datetime.fromisoformat(scanned_at) > cutoff
    todo = [f for f in friends if not scanned_recently(f)]

    console.print(f"{len(friends)} friends. {len(friends) - len(todo)} scanned in the last {rescan_days} days, {len(todo)} to scan.")
    if todo:
        minutes = max(1, round(len(todo) * 2 * REQUEST_DELAY / 60))
        console.print(f"This takes roughly {plural(minutes, 'minute')}. "
                      "Press Ctrl+C to stop; progress is saved and the next run continues from there.")

    errors = 0
    try:
        if todo:
            errors = scan_friends(fav_api, cache, cache_path, todo)
    except KeyboardInterrupt:
        console.print("[yellow]Stopped. Progress is saved; run again to continue.[/yellow]")
    finally:
        cache['worlds'] = {wid: w for wid, w in cache['worlds'].items() if w.get('favorited_by')}
        save_cache(cache_path, cache)

    if errors:
        console.print(f"[yellow]{errors} friend(s) couldn't be read and will be retried next run.[/yellow]")
    queue = load_queue(cache_path)
    sharing = len({f for w in queue for f in w['favorited_by']})
    console.print(f"[green]{plural(len(queue), 'unique world')} from {plural(sharing, 'friend')} who share favorite lists.[/green]")
    for world in queue[:5]:
        console.print(f"  {plural(len(world['favorited_by']), 'friend')}: {world['name']} by {world['author_name']}", markup=False)
    console.print("Use queue option 6 in the World Hopper to hop through them.")
