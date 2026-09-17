# pyproject.toml pins numpy==2.5.3, which has no build for Python 3.11 (requires >=3.12) —
# this image must match, not the "3.11+" in MASTER_PROMPT.md's original stack description.
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY pyproject.toml ./
RUN pip install --no-cache-dir -e ".[dev]"

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
