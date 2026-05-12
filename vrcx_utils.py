import sqlite3
import os
import time
from datetime import datetime, timezone

def add_favorite_world(db_path, world_id, group_name, max_retries=5):
    """
    Adds a new world to the favorite_world table with retry logic to handle
    database locks caused by VRCX.
    
    :param db_path: Path to the VRCX sqlite database file (supports %appdata% or ~).
    :param world_id: The unique ID of the world (e.g., 'wrld_...').
    :param group_name: The name of the group/collection.
    :param max_retries: Number of times to attempt the write if the DB is locked.
    :return: A string status: "added", "duplicate", or "error".
    """
    # Expand %appdata% or ~ to a real system path
    actual_db_path = os.path.expanduser(os.path.expandvars(db_path))

    # Ensure group_name is a string for SQLite compatibility
    group_name = group_name if group_name else ""

    for attempt in range(max_retries):
        conn = None
        try:
            # timeout=30 tells SQLite to wait internally for 30s before throwing an error
            conn = sqlite3.connect(actual_db_path, timeout=30)
            cursor = conn.cursor()

            # 1. CHECK FOR DUPLICATE
            check_query = "SELECT 1 FROM favorite_world WHERE world_id = ? AND group_name = ? LIMIT 1"
            cursor.execute(check_query, (world_id, group_name))
            if cursor.fetchone():
                return "duplicate"

            # 2. INSERT
            created_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            insert_query = "INSERT INTO favorite_world (world_id, group_name, created_at) VALUES (?, ?, ?)"
            cursor.execute(insert_query, (world_id, group_name, created_at))
            conn.commit()

            return "added"

        except sqlite3.OperationalError as e:
            # Specifically catch 'database is locked' errors
            if "locked" in str(e).lower():
                wait_time = attempt + 2  # Wait 2s, then 3s, then 4s...
                time.sleep(wait_time)
            else:
                return "error"
        except Exception:
            return "error"
        finally:
            if conn:
                conn.close()

    return "error" # Failed after max retries
