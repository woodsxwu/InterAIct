import os
import sqlite3
import shutil
from database.db_schema import DB_PATH, initialize_database, populate_initial_data


def reset_database():
    """Reset the database to initial state"""
    print("Resetting EmoBuddy database...")

    # Check if database exists
    if os.path.exists(DB_PATH):
        print(f"Removing existing database: {DB_PATH}")
        # Close any open connections
        try:
            conn = sqlite3.connect(DB_PATH)
            conn.close()
        except:
            pass

        # Remove the database file
        os.remove(DB_PATH)

        # Also remove WAL and SHM files if they exist
        wal_file = f"{DB_PATH}-wal"
        shm_file = f"{DB_PATH}-shm"

        if os.path.exists(wal_file):
            os.remove(wal_file)
        if os.path.exists(shm_file):
            os.remove(shm_file)

    # Remove session data directory
    session_dir = "session_data"
    if os.path.exists(session_dir):
        print(f"Removing session data directory: {session_dir}")
        shutil.rmtree(session_dir)

    # Recreate database
    print("Initializing fresh database...")
    initialize_database()
    populate_initial_data()

    print("Database reset complete!")
    print(f"New database created at: {os.path.abspath(DB_PATH)}")


if __name__ == "__main__":
    reset_database()