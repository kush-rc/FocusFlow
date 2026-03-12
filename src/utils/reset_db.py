import sqlite3
import os
from pathlib import Path

def reset_database():
    db_path = Path(__file__).parent.parent.parent / "data" / "focus_flow.db"
    
    if not db_path.exists():
        print(f"Database not found at {db_path}")
        return

    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        for table in tables:
            table_name = table[0]
            if table_name != 'sqlite_sequence':
                print(f"Clearing table: {table_name}")
                cursor.execute(f"DELETE FROM {table_name}")
        
        conn.commit()
        conn.close()
        print("\nSuccessfully cleared all session history.")
        
    except Exception as e:
        print(f"Error resetting database: {e}")

if __name__ == "__main__":
    confirm = input("Are you sure you want to clear ALL session history? (y/n): ")
    if confirm.lower() == 'y':
        reset_database()
    else:
        print("Aborted.")
