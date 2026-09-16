# Sandboxed Jupyter kernel image (pinned data-science libraries).
# MASTER_PROMPT.md §2, §9: no outbound network (enforced by the Docker network the
# container is attached to at runtime, see app/execution/docker_backend.py), read-only
# root filesystem except a mounted working directory, non-root user, resource limits.
FROM python:3.12-slim

RUN groupadd --gid 1000 kernel \
    && useradd --uid 1000 --gid kernel --create-home --shell /usr/sbin/nologin kernel

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt

# The root filesystem is mounted read-only at runtime, so every place these libraries
# (matplotlib, ipykernel, jupyter, various caches) want to write is redirected under /tmp,
# which is mounted as a writable tmpfs by the execution backend.
ENV MPLCONFIGDIR=/tmp/mplconfig \
    JUPYTER_RUNTIME_DIR=/tmp/jupyter-runtime \
    JUPYTER_DATA_DIR=/tmp/jupyter-data \
    XDG_CACHE_HOME=/tmp/xdg-cache \
    PYTHONUNBUFFERED=1

USER kernel
WORKDIR /home/kernel/work

# The connection file is bind-mounted read-only at this fixed path by the execution
# backend, so `docker run` never needs to override this default command.
CMD ["python", "-m", "ipykernel_launcher", "-f", "/home/kernel/connection.json"]
