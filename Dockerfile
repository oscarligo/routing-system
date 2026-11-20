# Official compiler and bundled solvers, without the graphical IDE.
FROM ghcr.io/minizinc/minizinc:2.11.0 AS minizinc

FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/minizinc/bin:${PATH}" \
    LD_LIBRARY_PATH="/opt/minizinc/lib"

COPY --from=minizinc /opt/minizinc /opt/minizinc

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src/ ./src/
COPY models/ ./models/
RUN pip install --no-cache-dir . \
    && minizinc --version \
    && minizinc --solvers

COPY data/raw/ ./data/raw/
COPY data/instances/ ./data/instances/
COPY experiments/ ./experiments/
COPY tests/ ./tests/

# Commands can be overridden with minizinc, python, or routing-system.
CMD ["python", "-m", "src.cli", "--help"]
