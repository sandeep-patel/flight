# Playwright's official image ships Chromium + all OS dependencies,
# matched to the Playwright Python version below.
FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install dependencies first for better layer caching.
COPY pyproject.toml requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy source and install the package.
COPY src ./src
COPY scripts ./scripts
RUN pip install --no-deps .

# Browsers are already installed in the base image; ensure they're present.
RUN python -m playwright install chromium

# Run as the non-root user provided by the base image.
USER pwuser

ENTRYPOINT ["flight-tracker"]
CMD ["--once", "--console"]
