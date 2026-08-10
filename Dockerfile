FROM python:3.14-slim

WORKDIR /app

COPY . .

RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir .

RUN mkdir -p /app/data/database /app/data/logs

CMD ["kase-pilot", "--version"]