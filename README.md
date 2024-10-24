# DeHashed Parser

`dehashed_parser` is a Python script designed to parse JSON output from the DeHashed API and store the entries into a SQLite database. It ensures proper handling of ID fields, prevents conflicts, and allows flexible table creation options. The script includes functionality for filtering, data analysis, and generating userpass files.

## Features

- Parses DeHashed API JSON output and inserts parsed entries into a SQLite database
- Supports filtering of data by a specific key
- Supports appending data from additional JSON files without duplicating existing records
- Option to generate an alphabetically sorted `user:pass` file for records with cleartext passwords

## Prerequisites

- Python 3.x
- SQLite

### Required Python libraries:
- `tqdm`
- Install the required libraries via pip:

   ```bash
   pip install tqdm
   ```

## Installation

1. Clone the repository:

   ```bash
   git clone https://github.com/Sir-CussFreq/Dehashed_Parser.git
   ```

2. Navigate to the project directory:

   ```bash
   cd DeHashed_Parser
   ```

## Usage

### Basic Usage

To parse a JSON file from DeHashed API and insert the data into the database:

```bash
python3 ./dehashed_parser.py -f data.json
```

By default, the database will be saved as `dehashed_results.db` in the current directory.

### Optional Arguments

- `-d`, `--db`: Specify a custom SQLite database name (default is `dehashed_results.db`).
- `-t`, `--timestamp`: Create a new table with a timestamp instead of dropping the existing table.
- `-a`, `--append`: Append data from an additional JSON file to the existing table.
- `-y`, `--yes`: Skip confirmation and force drop the table.
- `-u`, `--userpass`: Generate a `user:pass` file for records with cleartext passwords (default is `userpass.txt`).
- `--nohashcheck`: Skip the check for hashed passwords when generating the userpass file.
- `--filter`: Only import data that matches the specified key.
- `--name`: Custom name for the target table.

### Example Commands

1. **Create a new table with a timestamp**:
   ```bash
   python3 ./dehashed_parser.py -f data.json -t
   ```

2. **Append data from another JSON file**:
   ```bash
   python3 ./dehashed_parser.py -f data.json -a
   ```

3. **Generate a `user:pass` file without hash checks**:
   ```bash
   python3 ./dehashed_parser.py -f data.json -u userpass.txt --nohashcheck
   ```

### Data Analysis

After processing, the script will provide analysis of the records, including:

- Total number of records
- Total number of records with cleartext passwords
- Total number of records with hashed passwords but no cleartext passwords
- Total number of records with no passwords

The results are displayed in color for easy readability.

### Output Example:

```bash
--- Data Analysis Results ---
Total number of records: 1000
Total number of records with cleartext passwords: 500
Total number of records with hashed passwords but no cleartext passwords: 300
Total number of records with no passwords: 200
------------------------------
```

## License

This project is licensed under the MIT License.
