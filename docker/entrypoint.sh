#!/bin/sh
set -eu

# If no schedule is provided, run once and exit
if [ "${CRON_SCHEDULE:-}" = "" ]; then
    cd /app
    exec python app/main.py
fi

CRON_FILE=/etc/cron.d/plex-export
echo "${CRON_SCHEDULE} root /usr/local/bin/run-etl.sh >> /var/log/cron.log 2>&1" > "$CRON_FILE"
chmod 0644 "$CRON_FILE"

touch /var/log/cron.log
echo "Starting cron with CRON_SCHEDULE='${CRON_SCHEDULE}'"
cron
tail -F /var/log/cron.log


