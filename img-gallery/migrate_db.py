#!/usr/bin/env python3
"""
Database migration script to add missing columns to existing databases.
Run this script to update your database schema.
"""

import sqlite3
import os
from pathlib import Path

def migrate_database():
    """Migrate the database to add missing columns."""
    db_path = Path("gallery_metadata.db")
    
    if not db_path.exists():
        print("Database file not found. Creating new database...")
        return
    
    print(f"Migrating database: {db_path}")
    
    # Connect to the database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if drawings_count column exists
        cursor.execute("PRAGMA table_info(images)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'drawings_count' not in columns:
            print("Adding drawings_count column...")
            cursor.execute("ALTER TABLE images ADD COLUMN drawings_count INTEGER DEFAULT 1")
            print("✓ Added drawings_count column")
        else:
            print("✓ drawings_count column already exists")
        
        if 'created_at' not in columns:
            print("Adding created_at column...")
            cursor.execute("ALTER TABLE images ADD COLUMN created_at DATETIME")
            print("✓ Added created_at column")
        else:
            print("✓ created_at column already exists")
            
        if 'updated_at' not in columns:
            print("Adding updated_at column...")
            cursor.execute("ALTER TABLE images ADD COLUMN updated_at DATETIME")
            print("✓ Added updated_at column")
        else:
            print("✓ updated_at column already exists")
        
        # Commit the changes
        conn.commit()
        print("✓ Database migration completed successfully!")
        
    except Exception as e:
        print(f"Error during migration: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_database() 