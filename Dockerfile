FROM python:3.12-slim

WORKDIR /app
COPY . .

RUN pip install --no-cache-dir .

# Render sets $PORT; fall back to 8765 for local Docker runs
ENV PORT=8765

# --http starts the SSE/HTTP transport so Render (and Copilot) can reach it
CMD ["sh", "-c", "python -m liteparse_mcp --http --port ${PORT}"]
