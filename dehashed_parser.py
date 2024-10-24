import json
import sqlite3
import argparse
import os
from datetime import datetime
from tqdm import tqdm
import logging
import re

# Configure logging
logging.basicConfig(filename='dehashed_parser.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Maximum file size (in bytes) for which the script is designed
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB

# Function to parse the JSON file, create the table, and insert the records
def parse_json(json_file, conn, table_name, drop_existing=True, filter_key=None):
    print(f"Parsing data from {json_file}...")

    with open(json_file, 'r') as f:
        data = json.load(f)
    
        # If there are specific entries in the data (e.g., DeHashed API response)
        entries = data.get('entries', [])
        if not entries:
            raise ValueError("No entries found in the provided JSON file.")
        
        # Filter the entries based on a specific key if provided
        if filter_key:
            entries = [entry for entry in entries if filter_key in entry]
        
        # Infer the schema from the first entry
        schema = infer_schema(entries)

        # Create the table in the database
        cursor = conn.cursor()
        create_table(cursor, table_name, schema, drop_existing)

        # Insert records in batches
        for item in tqdm(entries, desc="Inserting records"):
            item = rename_id_field(item)  # Ensure 'id' field is renamed if necessary
            columns = list(item.keys())
            values = list(item.values())
            insert_records(conn, table_name, columns, values)

        print("Data inserted successfully.")

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

# Function to insert records in batches and create indexes after insertion
def insert_records_batch(conn, table_name, records):
    cursor = conn.cursor()
    try:
        conn.execute("BEGIN TRANSACTION;")
        # Insert data into the table in batches
        insert_sql = f"INSERT INTO {table_name} ({', '.join(records[0]['columns'])}) VALUES ({', '.join(['?' for _ in records[0]['values']])})"
        values = [record['values'] for record in records]
        cursor.executemany(insert_sql, values)
        conn.execute("COMMIT;")
    except sqlite3.Error as e:
        logging.error(f"SQLite error: {e}")
        conn.rollback()
        raise e

    # Create indexes after all data has been inserted
    create_indexes(cursor, table_name)

# Function to insert records
def insert_records(conn, table_name, columns, values):
    cursor = conn.cursor()
    try:
        # Insert data into the table
        insert_sql = f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({', '.join(['?' for _ in values])});"
        cursor.execute(insert_sql, tuple(values))

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
    
    # ANSI color codes
    CYAN = "\033[36m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    MAGENTA = "\033[35m"
    RED = "\033[31m"
    BLUE = "\033[34m"
    RESET = "\033[0m"    

    # Output results with counts in the same color
    print(f"\n--- {CYAN}Data Analysis Results{RESET} ---")
    print(f"{BLUE}Total number of records: {GREEN}{total_records}{RESET}")
    print(f"{BLUE}Total number of records {YELLOW}with cleartext passwords: {GREEN}{total_cleartext_passwords}{RESET}")
    print(f"{BLUE}Total number of records {MAGENTA}with hashed passwords but no cleartext passwords: {GREEN}{total_hashed_passwords}{RESET}")
    print(f"{BLUE}Total number of records {RED}with no passwords: {GREEN}{total_no_passwords}{RESET}")
    print(f"------------------------------{RESET}\n")

# Function to append data from additional JSON file with enhanced duplication check
def append_json(json_file, conn, table_name):
    print(f"Appending data from {json_file} into the existing table {table_name}...")

    with open(json_file, 'r') as f:
        data = json.load(f)
    
        entries = data.get('entries', [])
        if not entries:
            raise ValueError("No entries available to append.")

        duplicate_count = 0  # Initialize a counter for duplicates

        for item in tqdm(entries, desc="Appending records"):
            item = rename_id_field(item)
            columns = list(item.keys())
            values = list(item.values())
            
            # Construct a dynamic query based on non-null fields
            query_conditions = []
            query_values = []
            
            if item.get('email'):
                query_conditions.append("email = ?")
                query_values.append(item.get('email'))
            if item.get('username'):
                query_conditions.append("username = ?")
                query_values.append(item.get('username'))
            if item.get('name'):
                query_conditions.append("name = ?")
                query_values.append(item.get('name'))
            if item.get('password'):
                query_conditions.append("password = ?")
                query_values.append(item.get('password'))
            if item.get('hashed_password'):
                query_conditions.append("hashed_password = ?")
                query_values.append(item.get('hashed_password'))

            # If there are conditions to check, perform the query
            if query_conditions:
                check_query = f"SELECT COUNT(*) FROM {table_name} WHERE {' AND '.join(query_conditions)}"
                cursor = conn.cursor()
                cursor.execute(check_query, query_values)
                if cursor.fetchone()[0] > 0:
                    duplicate_count += 1  # Increment the duplicate counter
                    continue  # Skip this record as it's a duplicate

            # Insert the unique record
            insert_records(conn, table_name, columns, values)

        # Output the total number of duplicates skipped
        if duplicate_count > 0:
            print(f"{duplicate_count} duplicate records were skipped.")

# Function to determine if the password is likely a hash (basic check)
def is_likely_hash(password):
    # Common hash lengths (MD5: 32, SHA-1: 40, SHA-256: 64, etc.)
    common_hash_lengths = [32, 40, 64]
    
    # Check if the password length matches a common hash length and is hex-like or base64
    if len(password) in common_hash_lengths:
        if re.match(r'^[a-fA-F0-9]+$', password) or re.match(r'^[A-Za-z0-9+/=]+$', password):
            return True
    return False

# Function to validate if the email looks legitimate
def is_valid_email(email):
    # Basic regex for validating an email address
    email_regex = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    return re.match(email_regex, email)

# Function to check if a string contains only ASCII characters
def is_ascii(s):
    try:
        s.encode('ascii')
    except UnicodeEncodeError:
        return False
    return True

# Updated generate_userpass_file function with non-ASCII check and sorting
def generate_userpass_file(conn, table_name, userpass_file, nohashcheck):
    cursor = conn.cursor()
    
    # Query to fetch records with cleartext passwords
    userpass_query = f"""
    SELECT email, name, username, password
    FROM {table_name}
    WHERE password IS NOT NULL AND password != '';
    """
    cursor.execute(userpass_query)
    records = cursor.fetchall()
    
    unique_entries = set()  # Use a set to avoid duplicates before writing

    for record in records:
        email, name, username, password = record
        
        # Skip if any field is longer than 100 characters
        if (email and len(email) > 100) or (name and len(name) > 100) or (username and len(username) > 100) or (password and len(password) > 100):
            continue

        # Skip if the password is likely a hash, unless --nohashcheck is specified
        if not nohashcheck and is_likely_hash(password):
            continue

        # Skip if the email doesn't look valid
        if email and not is_valid_email(email):
            continue

        # Skip if any field contains non-ASCII characters
        if (email and not is_ascii(email)) or (name and not is_ascii(name)) or (username and not is_ascii(username)) or (password and not is_ascii(password)):
            continue

        # Generate unique user identifiers by replacing spaces with underscores
        if email and email.strip():
            unique_entries.add(f"{email.replace(' ', '_')}:{password}")
        if name and name.strip():
            unique_entries.add(f"{name.replace(' ', '_')}:{password}")
        if username and username.strip():
            unique_entries.add(f"{username.replace(' ', '_')}:{password}")

    # Sort the unique entries alphabetically
    sorted_entries = sorted(unique_entries)

    # Write the sorted entries to the file
    with open(userpass_file, 'w') as f:
        for entry in sorted_entries:
            f.write(entry + '\n')
    
    print(f"Userpass file '{userpass_file}' generated and sorted alphabetically.")


# Confirm before dropping or appending to tables
def confirm_deletion_or_append(db_file, append=False, force_drop=False):
    if force_drop:
        return True
    if os.path.exists(db_file):
        while True:
            if append:
                response = input(f"The database {db_file} already exists. Would you like to append data to the existing table? (Y/N): ")
            else:
                response = input(f"The database {db_file} already exists. Dropping the tables will delete existing data. Proceed? (Y/N): ")
            if response.strip().lower() == 'y':
                return True
            elif response.strip().lower() == 'n':
                if append:
                    print("Appending data was canceled.")
                    return False
                else:
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
    parser.add_argument('-a', '--append', help="Append data from an additional JSON file to the existing table", action='store_true')
    parser.add_argument('-d', '--db', default="dehashed_results.db", help="Path to the SQLite database file (default is 'dehashed_results.db')")
    parser.add_argument('-t', '--timestamp', action='store_true', help="Create new tables with a datetime stamp instead of dropping and recreating existing tables")
    parser.add_argument('-y', '--yes', action='store_true', help="Skip confirmation and force drop the table")
    parser.add_argument('-u', '--userpass', nargs='?', const='userpass.txt', help="Generate user:pass file (default: 'userpass.txt')")
    parser.add_argument('--nohashcheck', action='store_true', help="Skip the check to detect if passwords are likely hashes")  # Optional flag
    parser.add_argument('--filter', help="Only import data that matches the given key")
    parser.add_argument('--name', help="Custom name for the target table", default="dehashed_results")

    args = parser.parse_args()

    if not check_file_size(args.file):
        return

    if args.append:
        # If appending, skip confirmation and proceed
        conn = sqlite3.connect(args.db)
        table_name = args.name
        append_json(args.file, conn, table_name)
    else:
        # Dropping and recreating the table with sanity check or -y to skip
        if not confirm_deletion_or_append(args.db, force_drop=args.yes):
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
        generate_userpass_file(conn, table_name, args.userpass, args.nohashcheck)  # Pass nohashcheck argument

    try:
        conn.close()
    except sqlite3.Error as e:
        logging.error(f"SQLite close error: {e}")


if __name__ == "__main__":
    main()
