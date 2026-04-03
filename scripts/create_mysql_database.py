"""
Create MySQL database for eRepairing.com
"""
import pymysql
from pymysql import Error

# MySQL connection details
MYSQL_HOST = "localhost"
MYSQL_PORT = 3306
MYSQL_USER = "root"
MYSQL_PASSWORD = "Ak18070406@"
DATABASE_NAME = "erepairingnew"


def create_database():
    """Create the database if it doesn't exist"""
    try:
        # Connect to MySQL server (without specifying database)
        connection = pymysql.connect(
            host=MYSQL_HOST,
            port=MYSQL_PORT,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            charset='utf8mb4'
        )
        
        cursor = connection.cursor()
        
        # Create database if it doesn't exist
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DATABASE_NAME} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        print(f"[OK] Database '{DATABASE_NAME}' created or already exists")
        
        # Select the database
        cursor.execute(f"USE {DATABASE_NAME}")
        
        # Set SQL mode for better compatibility
        cursor.execute("SET sql_mode = 'STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION'")
        
        connection.commit()
        print("[OK] Database configured successfully")
        
        cursor.close()
        connection.close()
        
        return True
        
    except Error as e:
        print(f"[ERROR] Error creating database: {e}")
        return False


def verify_connection():
    """Verify connection to the database"""
    try:
        connection = pymysql.connect(
            host=MYSQL_HOST,
            port=MYSQL_PORT,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            database=DATABASE_NAME,
            charset='utf8mb4'
        )
        
        cursor = connection.cursor()
        cursor.execute("SELECT VERSION()")
        version = cursor.fetchone()
        print(f"[OK] Connected to MySQL Server version: {version[0]}")
        
        cursor.execute("SELECT DATABASE()")
        db_name = cursor.fetchone()
        print(f"[OK] Current database: {db_name[0]}")
        
        cursor.close()
        connection.close()
        
        return True
        
    except Error as e:
        print(f"[ERROR] Error connecting to database: {e}")
        return False


if __name__ == "__main__":
    print("Creating MySQL database for eRepairing.com...")
    print()
    
    if create_database():
        print()
        if verify_connection():
            print()
            print("[OK] Database setup complete!")
            print()
            print("Next steps:")
            print("1. Run: alembic upgrade head")
            print("2. Run: python scripts/init_db.py")
        else:
            print("[ERROR] Database verification failed")
    else:
        print("[ERROR] Database creation failed")

