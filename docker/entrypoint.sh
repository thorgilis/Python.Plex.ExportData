#!/bin/sh
set -eu

# If no schedule is provided, run once and exit
if [ "${CRON_SCHEDULE:-}" = "" ]; then
    cd /app
    exec /usr/local/bin/python /app/app/main.py
fi

CRON_FILE=/etc/cron.d/plex-export
# Export current container environment to a file that cron can source
# Use single-quoted, shell-safe values to preserve spaces and special chars
printenv | sed -E "s/'/'\\''/g; s/^(.*)=(.*)$/export \1='\2'/" > /etc/container_env.sh

# Ensure cron has a sane environment
{
    echo "SHELL=/bin/sh"
    echo "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
    echo "${CRON_SCHEDULE} root . /etc/container_env.sh; /usr/local/bin/run-etl.sh >> /var/log/cron.log 2>&1"
} > "$CRON_FILE"
chmod 0644 "$CRON_FILE"

touch /var/log/cron.log
echo "Starting cron with CRON_SCHEDULE='${CRON_SCHEDULE}'"
cron
tail -F /var/log/cron.log


