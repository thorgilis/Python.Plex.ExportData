# Plex Export Data

Export and analyze Plex Media Server data. Run it once or put it on a schedule. Funky, but not flashy.

## Features ✨
- Export Plex library metadata and watch history
- Generate lightweight library statistics
- Run once or on a cron schedule inside Docker
- Minimal footprint based on `python:3.12-slim`

## How it works
- If `CRON_SCHEDULE` is unset/empty: the app runs `python app/main.py` once, then exits
- If `CRON_SCHEDULE` is set: a cron job runs `/usr/local/bin/run-etl.sh` (calls `python app/main.py`) on schedule and tails logs

## Prerequisites

- Python 3.12 or higher (for local dev)
- Plex Media Server and auth token
- Git (for cloning the repository)

## Installation (Python)

1. Clone the repository:
```bash
git clone https://github.com/thorgilis/Python.Plex.ExportData.git
cd Python.Plex.ExportData
```

2. Create a virtual environment (recommended):
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Configuration

Create a `.env` file with your Plex and database settings. See the example below.

## Usage (Python)

```bash
python app/main.py
```

### Docker

For docker instructions please see the [Docker Hub Page](https://hub.docker.com/r/thorgilis/plex-movie-export)

## Contributing

1. Fork the repository
2. Create a new branch (`git checkout -b feature/improvement`)
3. Commit your changes (`git commit -am 'Add new feature'`)
4. Push to the branch (`git push origin feature/improvement`)
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
