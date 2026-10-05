FROM python:3.11-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.7 /uv /usr/local/bin/uv

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Dependencies first (better layer caching); --system: no venv inside the container
COPY pyproject.toml .
RUN uv pip install --system -r pyproject.toml

# Unprivileged user (uid 1000 so bind-mounted logs are not created as root)
RUN useradd --create-home --uid 1000 lab

COPY src ./src
COPY data ./data

USER lab

ENTRYPOINT ["python", "src/app.py"]
CMD ["--scenario", "tools", "--server", "secure"]
