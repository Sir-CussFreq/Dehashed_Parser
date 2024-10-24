# DeHashed Parser

`dehashed_parser` is a Python script designed to parse JSON output from the DeHashed API and store the entries in a SQLite database.

## Features

- Parses DeHashed API JSON output and inserts parsed entries into a SQLite database
- Supports filtering of data by a specific key
- Option to append data from additional JSON files without duplicating existing records
- Option to generate a `user:pass` file for records with cleartext passwords

## Prerequisites

- Python 3.x
- SQLite
- Required Python libraries (listed in `requirements.txt`):
  - `tqdm`

## Installation

1. Clone the repository:

   ```bash
   git clone https://github.com/Sir-CussFreq/Dehashed_Parser.git
   ```

2. Navigate to the project directory:

   ```bash
   cd Dehashed_Parser
   ```

3. Install the required dependencies:

   ```bash
   pip install -r requirements.txt
   ```

## Usage

Run the script with the following options:

   ```bash
   python3 ./dehashed_parser.py -f <path_to_json_file> [options]
   ```

### Required Arguments

- `-f, --file`: Path to the DeHashed JSON file.

### Optional Arguments

- `-d, --db`: Path to the SQLite database file (default is `dehashed_results.db`).
- `-t, --timestamp`: Create new tables with a timestamp instead of dropping existing ones.
- `-a, --append`: Append data from an additional JSON file to the existing table.
- `-y, --yes`: Skip confirmation prompts and force table drop.
- `-u, --userpass`: Generate a `user:pass` file for records with cleartext passwords (default: `userpass.txt`).
- `--filter`: Filter data based on a specific key.
- `--name`: Custom name for the table (default is `dehashed_results`).

### Example

- **Append data to an existing table**:

   ```bash
   python3 ./dehashed_parser.py -f additional_data.json -a
   ```

- **Force table drop without confirmation**:

   ```bash
   python3 ./dehashed_parser.py -f dehashed_data.json -y
   ```

- **Generate user:pass file**:

   ```bash
   python3 ./dehashed_parser.py -f dehashed_data.json -u userpass_output.txt
   ```

### Userpass File Format

If the `-u` option is provided, the script will generate a `user:pass` file for records that contain cleartext passwords. The `email`, `name`, and `username` fields will be processed as follows:
- Spaces will be replaced with underscores (`_`).
- If more than one field contains data, each unique combination will be written to the file on separate lines.

#### Example

For a record with the following fields:
- `email`: `john@doe.com`
- `name`: `John Doe`
- `username`: `jdoe`
- `password`: `asdf1234`

The generated file will contain:
```
john@doe.com:asdf1234
John_Doe:asdf1234
jdoe:asdf1234
```

## License

This project is licensed under the MIT License.

## Contributions

Contributions are welcome! Please feel free to submit a pull request or open an issue to discuss improvements.

## Contact

If you have any questions, feel free to open an issue or contact me via GitHub: [Sir-CussFreq](https://github.com/Sir-CussFreq/Dehashed_Parser).
