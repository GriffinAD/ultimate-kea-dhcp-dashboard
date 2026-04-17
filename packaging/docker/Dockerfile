FROM python:3.11-slim

WORKDIR /app

COPY packaging/docker/requirements-plugin.txt /tmp/requirements-plugin.txt
RUN pip install --no-cache-dir -r /tmp/requirements-plugin.txt

# Build context is the repository root. Container assets live under packaging/docker.
COPY . /app

EXPOSE 8080

CMD ["python", "bin/ultimate-kea-dashboard-plugin"]
