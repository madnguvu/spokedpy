#!/usr/bin/env python3
"""
Test PostgreSQL connection and create the visual_editor_core database.
"""

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import sys

def test_postgresql_connection():
    """Test PostgreSQL connection and create database if needed."""
    
    # Connection parameters
    host = "localhost"
    port = 5432
    username = "postgres"
    password = "headbutt"
    database_name = "visual_editor_core"
    
    print("=== PostgreSQL Connection Test ===")
    print(f"Host: {host}")
    print(f"Port: {port}")
    print(f"Username: {username}")
    print(f"Target Database: {database_name}")
    print()
    
    try:
        # First, connect to the default postgres database to create our target database
        print("1. Connecting to PostgreSQL server...")
        conn = psycopg2.connect(
            host=host,
            port=port,
            user=username,
            password=password,
            database="postgres"  # Connect to default database first
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        
        cursor = conn.cursor()
        print("✓ Connected to PostgreSQL server successfully")
        
        # Check if our target database exists
        print(f"2. Checking if database '{database_name}' exists...")
        cursor.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s",
            (database_name,)
        )
        
        if cursor.fetchone():
            print(f"✓ Database '{database_name}' already exists")
        else:
            print(f"Database '{database_name}' does not exist. Creating it...")
            cursor.execute(f'CREATE DATABASE "{database_name}"')
            print(f"✓ Database '{database_name}' created successfully")
        
        cursor.close()
        conn.close()
        
        # Now test connection to our target database
        print(f"3. Testing connection to '{database_name}' database...")
        target_conn = psycopg2.connect(
            host=host,
            port=port,
            user=username,
            password=password,
            database=database_name
        )
        
        target_cursor = target_conn.cursor()
        target_cursor.execute("SELECT version()")
        version = target_cursor.fetchone()[0]
        print(f"✓ Connected to '{database_name}' successfully")
        print(f"PostgreSQL Version: {version}")
        
        # Test basic operations
        print("4. Testing basic database operations...")
        target_cursor.execute("""
            CREATE TABLE IF NOT EXISTS connection_test (
                id SERIAL PRIMARY KEY,
                test_data TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        target_cursor.execute(
            "INSERT INTO connection_test (test_data) VALUES (%s)",
            ("Connection test successful",)
        )
        
        target_cursor.execute("SELECT * FROM connection_test ORDER BY id DESC LIMIT 1")
        result = target_cursor.fetchone()
        print(f"✓ Test record created: ID={result[0]}, Data='{result[1]}'")
        
        # Clean up test table
        target_cursor.execute("DROP TABLE IF EXISTS connection_test")
        target_conn.commit()
        
        target_cursor.close()
        target_conn.close()
        
        print("\n=== PostgreSQL Connection Test PASSED ===")
        return True
        
    except psycopg2.OperationalError as e:
        print(f"✗ Connection failed: {e}")
        print("\nPossible issues:")
        print("- PostgreSQL server is not running")
        print("- Incorrect host, port, username, or password")
        print("- PostgreSQL is not accepting connections")
        print("- Firewall blocking the connection")
        return False
        
    except psycopg2.Error as e:
        print(f"✗ PostgreSQL error: {e}")
        return False
        
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False

if __name__ == "__main__":
    success = test_postgresql_connection()
    sys.exit(0 if success else 1)