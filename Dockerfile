FROM python:3-slim

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock ./
RUN uv export --frozen --no-dev -o requirements.txt && \
    uv pip install --system --no-cache -r requirements.txt

COPY src ./src

CMD ["python", "-m", "src.main"]
