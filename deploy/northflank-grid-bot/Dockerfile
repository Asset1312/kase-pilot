FROM python:3.11-slim

WORKDIR /app

# The bot uses Python standard library only (urllib, hmac, hashlib, json)
# No external pip dependencies needed for ultra-fast builds and zero vulnerabilities!

COPY crypto_grid_lite.py /app/crypto_grid_lite.py

ENV PYTHONUNBUFFERED=1

CMD ["python", "-u", "/app/crypto_grid_lite.py"]
