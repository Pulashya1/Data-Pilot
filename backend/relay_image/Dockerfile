# Minimal, trusted TCP relay (MASTER_PROMPT.md §9: "no outbound network" for the kernel).
#
# The kernel container is attached only to an internal (no-internet) Docker network, so
# nothing it runs can reach the outside world. This relay is the only thing that bridges
# it back to the host: it sits on both the internal network and a public one, and blindly
# forwards the 5 Jupyter ZMQ ports. It never executes user code or interprets the traffic
# it forwards, so it never needs to reach the internet or run as an untrusted process.
FROM alpine:3.20

RUN apk add --no-cache socat

COPY relay.sh /usr/local/bin/relay.sh
RUN chmod +x /usr/local/bin/relay.sh

USER nobody
ENTRYPOINT ["/usr/local/bin/relay.sh"]
