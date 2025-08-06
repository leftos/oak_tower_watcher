#!/usr/bin/env python3
"""
Quick script to check the production database contents
"""
import sqlite3
import sys
import os

def check_database():
    db_path = 'prod_data/users.db'
    
    if not os.path.exists(db_path):
        print(f"ERROR: Database file {db_path} does not exist!")
        return
    
    print(f"Database file: {db_path}")
    print(f"File size: {os.path.getsize(db_path)} bytes")
    print(f"File permissions: {oct(os.stat(db_path).st_mode)[-3:]}")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        print(f"\nTables in database: {[table[0] for table in tables]}")
        
        if tables:
            for table in tables:
                table_name = table[0]
                cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
                count = cursor.fetchone()[0]
                print(f"  {table_name}: {count} records")
                
                # Show some sample data for users table
                if table_name == 'users':
                    cursor.execute("SELECT id, email, email_verified, created_at FROM users LIMIT 5;")
                    users = cursor.fetchall()
                    print(f"  Sample users:")
                    for user in users:
                        print(f"    ID: {user[0]}, Email: {user[1]}, Verified: {user[2]}, Created: {user[3]}")
        else:
            print("No tables found in database!")
            
        conn.close()
        
    except Exception as e:
        print(f"ERROR querying database: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_database()