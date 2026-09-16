#!/bin/sh
# Forwards each port in $RELAY_PORTS (space-separated) from this container to the same
# port on $RELAY_TARGET. Started by app/execution/docker_backend.py, one relay per kernel.
set -eu

if [ -z "${RELAY_TARGET:-}" ] || [ -z "${RELAY_PORTS:-}" ]; then
    echo "RELAY_TARGET and RELAY_PORTS must be set" >&2
    exit 1
fi

pids=""
for port in $RELAY_PORTS; do
    socat -d TCP-LISTEN:"$port",fork,reuseaddr TCP:"$RELAY_TARGET":"$port" &
    pids="$pids $!"
done

trap 'kill '"$pids"' 2>/dev/null' TERM INT
wait
