FROM python:3.11-slim

WORKDIR /app

# Install dependencies (tradernet-sdk)
RUN pip install --no-cache-dir tradernet-sdk requests websockets

# Copy application files
COPY tradernet_cloud_bot.py /app/

# Environment defaults
ENV PYTHONUNBUFFERED=1
ENV PORT=10000

EXPOSE 10000

CMD ["python", "tradernet_cloud_bot.py"]
