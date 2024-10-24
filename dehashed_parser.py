import json
import sqlite3
import argparse
import os
from datetime import datetime
from tqdm import tqdm
import logging

# Configure logging
logging.basicConfig(filename='dehashed_parser.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Maximum file size (in bytes) for which the script is designed
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB

# Function to validate and infer data type
def infer_data_type(value):
    if isinstance(value, int):
        return "INTEGER"
    elif isinstance(value, float):
        return "REAL"
    elif isinstance(value, (str, bytes)):
        if isinstance(value, str):
            return "TEXT"
        elif isinstance(value, bytes):
            return "BLOB"
    else:
        return "TEXT"

# Function to handle renaming the 'id' field if present in JSON
def rename_id_field(record):
    if 'id' in record:
        record['json_id'] = record.pop('id')
    return record

# Function to infer the schema from the first record
def infer_schema(data):
    if isinstance(data, list):
        if not data:
            raise ValueError("No data available to infer schema from the list.")
        first_record = rename_id_field(data[0])  # Rename 'id' to 'json_id' if necessary
    elif isinstance(data, dict):
        first_record = rename_id_field(data)
    else:
        raise ValueError("Unsupported JSON structure. Expected a list or dictionary.")
    
    schema = {key: infer_data_type(value) for key, value in first_record.items()}
    
    return schema

# Function to handle indexing of specific columns
def create_indexes(cursor, table_name):
    index_columns = ['username', 'name', 'email', 'database_name', 'password']  # Added 'password'
    for column in index_columns:
        index_sql = f"CREATE INDEX IF NOT EXISTS idx_{table_name}_{column} ON {table_name}({column})"
        cursor.execute(index_sql)

# Function to create the table schema
def create_table(cursor, table_name, schema, drop_existing):
    if drop_existing:
        cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
    
    create_table_sql = f"""
    CREATE TABLE IF NOT EXISTS {table_name} (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        {', '.join([f'{col} {col_type}' for col, col_type in schema.items()])}
    );
    """
    cursor.execute(create_table_sql)

# Function to insert records
def insert_records(conn, table_name, columns, values):
    cursor = conn.cursor()
    try:
        # Insert data into the table
        insert_sql = f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({', '.join(['?' for _ in values])});"
        cursor.execute(insert_sql, tuple(values))

        row_id = cursor.lastrowid  # Get the last inserted ID
        create_indexes(cursor, table_name)  # Create indexes on important columns

    except sqlite3.Error as e:
        logging.error(f"SQLite error: {e}")
        conn.rollback()
        raise e
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        conn.rollback()
        raise e
    finally:
        conn.commit()

# Function to analyze the data in the database and output results
def analyze_data(conn, table_name):
    cursor = conn.cursor()
    
    # Total number of records
    total_records_query = f"SELECT COUNT(*) AS total_records FROM {table_name};"
    cursor.execute(total_records_query)
    total_records = cursor.fetchone()[0]
    
    # Total number of records with cleartext passwords
    cleartext_passwords_query = f"""
    SELECT COUNT(*) AS total_cleartext_passwords
    FROM {table_name}
    WHERE password IS NOT NULL AND password != '';
    """
    cursor.execute(cleartext_passwords_query)
    total_cleartext_passwords = cursor.fetchone()[0]
    
    # Total number of records with hashed passwords but no cleartext passwords
    hashed_passwords_query = f"""
    SELECT COUNT(*) AS total_hashed_passwords
    FROM {table_name}
    WHERE (password IS NULL OR password = '')
    AND hashed_password IS NOT NULL AND hashed_password != '';
    """
    cursor.execute(hashed_passwords_query)
    total_hashed_passwords = cursor.fetchone()[0]
    
    # Total number of records with no passwords
    no_passwords_query = f"""
    SELECT COUNT(*) AS no_passwords
    FROM {table_name}
    WHERE (password IS NULL OR password = '')
    AND (hashed_password IS NULL OR hashed_password = '');
    """
    cursor.execute(no_passwords_query)
    total_no_passwords = cursor.fetchone()[0]
    
    # Output results
    print("\n--- Data Analysis Results ---")
    print(f"Total number of records: {total_records}")
    print(f"Total number of records with cleartext passwords: {total_cleartext_passwords}")
    print(f"Total number of records with hashed passwords but no cleartext passwords: {total_hashed_passwords}")
    print(f"Total number of records with no passwords: {total_no_passwords}")
    print("------------------------------\n")

# Function to generate user:pass file for records with cleartext passwords
def generate_userpass_file(conn, table_name, userpass_file):
    cursor = conn.cursor()
    
    # Query to fetch records with cleartext passwords
    userpass_query = f"""
    SELECT email, name, username, password
    FROM {table_name}
    WHERE password IS NOT NULL AND password != '';
    """
    cursor.execute(userpass_query)
    records = cursor.fetchall()
    
    with open(userpass_file, 'w') as f:
        for record in records:
            email, name, username, password = record
            entries = set()
            
            if email and email.strip():
                entries.add(email.replace(" ", "_"))
            if name and name.strip():
                entries.add(name.replace(" ", "_"))
            if username and username.strip():
                entries.add(username.replace(" ", "_"))
            
            for entry in entries:
                f.write(f"{entry}:{password}\n")
    
    print(f"Userpass file '{userpass_file}' generated successfully!")

# Parse JSON data
def parse_json(json_file, conn, table_name, drop_existing=True, filter_key=None):
    with open(json_file, 'r') as f:
        data = json.load(f)

        if 'balance' in data:
            balance = data['balance']
            print(f"Starting Balance: {balance}")

        entries = data.get('entries', [])
        if not entries:
            raise ValueError("No entries available to parse.")

        schema = infer_schema(entries)

        cursor = conn.cursor()
        create_table(cursor, table_name, schema, drop_existing)

        for item in tqdm(entries, desc="Inserting records"):
            item = rename_id_field(item)
            columns = list(item.keys())
            values = list(item.values())
            if filter_key and filter_key not in item:
                continue
            insert_records(conn, table_name, columns, values)

# Confirm before dropping tables
def confirm_deletion(db_file):
    if os.path.exists(db_file):
        while True:
            response = input(f"The database {db_file} already exists. Dropping the tables will delete existing data. Proceed? (Y/N): ")
            if response.strip().lower() == 'y':
                return True
            elif response.strip().lower() == 'n':
                print("You chose not to drop the existing tables.")
                response_t = input("Would you like to create new tables with the -t option? (Y/N): ")
                if response_t.strip().lower() == 'y':
                    return 'timestamp'
                elif response_t.strip().lower() == 'n':
                    print("Operation canceled.")
                    return False
                else:
                    print("Invalid input. Please enter 'Y' or 'N'.")
            else:
                print("Invalid input. Please enter 'Y' or 'N'.")
    return True

# Function to check file size before processing
def check_file_size(file_path):
    file_size = os.path.getsize(file_path)
    if file_size > MAX_FILE_SIZE:
        print(f"Warning: The file size is {file_size / (1024 * 1024):.2f} MB, which exceeds the 100 MB limit for this script.")
        print("Please use a different script and database to handle larger datasets.")
        return False
    return True

# Main function to handle command-line arguments and process
def main():
    parser = argparse.ArgumentParser(description="Parse DeHashed JSON output and insert data into an SQLite database.")
    parser.add_argument('-f', '--file', required=True, help="Path to the DeHashed JSON file")
    parser.add_argument('-d', '--db', default="dehashed_results.db", help="Path to the SQLite database file (default is 'dehashed_results.db')")
    parser.add_argument('-t', '--timestamp', action='store_true', help="Create new tables with a datetime stamp instead of dropping and recreating existing tables")
    parser.add_argument('-u', '--userpass', nargs='?', const='userpass.txt', help="Generate user:pass file (default: 'userpass.txt')")
    parser.add_argument('--filter', help="Only import data that matches the given key")
    parser.add_argument('--name', help="Custom name for the target table", default="dehashed_results")

    args = parser.parse_args()

    if not check_file_size(args.file):
        return

    if not args.timestamp:
        deletion_result = confirm_deletion(args.db)
        if deletion_result == 'timestamp':
            args.timestamp = True
        elif not deletion_result:
            return

    conn = sqlite3.connect(args.db)

    if args.timestamp:
        table_name = f"{args.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    else:
        table_name = args.name

    parse_json(args.file, conn, table_name, drop_existing=not args.timestamp, filter_key=args.filter)

    # Run data analysis after processing
    analyze_data(conn, table_name)

    # Generate userpass file if -u option is specified
    if args.userpass:
        generate_userpass_file(conn, table_name, args.userpass)

    try:
        conn.close()
    except sqlite3.Error as e:
        logging.error(f"SQLite close error: {e}")

if __name__ == "__main__":
    main()
