FROM python:3.11-slim

WORKDIR /app

COPY requirements-plugin.txt /tmp/requirements-plugin.txt
RUN pip install --no-cache-dir -r /tmp/requirements-plugin.txt

# Docker should consume packaged output rather than raw repository source.
# Expected layout: packaging/dist/<artifact>/...
COPY packaging/ /tmp/packaging/

RUN set -eux; \
    if [ ! -d /tmp/packaging/dist ]; then \
      echo "Expected packaged output under packaging/dist but it was not found."; \
      exit 1; \
    fi; \
    PACKAGE_DIR="$(find /tmp/packaging/dist -mindepth 1 -maxdepth 1 -type d | head -n 1)"; \
    if [ -z "$PACKAGE_DIR" ]; then \
      echo "No packaged artifact directory found under packaging/dist."; \
      exit 1; \
    fi; \
    cp -a "$PACKAGE_DIR"/. /app/

EXPOSE 8080

CMD ["python", "bin/ultimate-kea-dashboard-plugin"]
