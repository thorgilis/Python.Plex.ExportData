# Plex Export Data

A Python-based tool for exporting and managing Plex Media Server data.

## Description

This project provides utilities to export and analyze data from your Plex Media Server, allowing you to backup and analyse your media library information effectively.

## Prerequisites

- Python 3.12 or higher
- Plex Media Server installed and running
- Plex authentication token
- Git (for cloning the repository)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/Python.Plex.ExportData.git
cd Python.Plex.ExportData
```

2. Create a virtual environment (recommended):
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows use: .venv\Scripts\activate
```

3. Install required dependencies:
```bash
pip install -r requirements.txt
```

## Configuration

1. Copy the `.env.example` to `.env`
2. Add your Plex server details and authentication token to `.env`

## Usage

Run the main script:
```bash
python app/main.py
```

## Features

- Export Plex library metadata
- Backup movie and TV show information
- Generate library statistics
- Export watch history

## Contributing

1. Fork the repository
2. Create a new branch (`git checkout -b feature/improvement`)
3. Commit your changes (`git commit -am 'Add new feature'`)
4. Push to the branch (`git push origin feature/improvement`)
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
