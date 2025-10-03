#############################################
# Install uv
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
# Change the working directory to the `app` directory
WORKDIR /app
COPY webscenarios_perfcheck.py .
RUN uv sync --script webscenarios_perfcheck.py
CMD ["uv", "run", "--script", "webscenarios_perfcheck.py"]