# Use a slim Python image for production
FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Create and set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Create directories for persistent data
RUN mkdir -p data logs

# Use a non-root user for security
RUN useradd -m botuser && chown -R botuser:botuser /app
USER botuser

# Add healthcheck (checks if the bot process is alive)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD pgrep -f "python bot.py" || exit 1

# Command to run the bot
CMD ["python", "bot.py"]
