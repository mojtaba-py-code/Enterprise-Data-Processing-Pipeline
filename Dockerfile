FROM python:3.12-slim

# Keep Python output unbuffered and skip .pyc files.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install dependencies first for better layer caching.
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .

# Bring in example configs and sample data.
COPY configs ./configs
COPY data/sample ./data/sample

ENTRYPOINT ["edp"]
CMD ["run", "--config", "configs/pipeline.example.yaml"]
