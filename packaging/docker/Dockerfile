FROM python:3.11-slim

WORKDIR /app

COPY packaging/docker/requirements-plugin.txt /tmp/requirements-plugin.txt
RUN pip install --no-cache-dir -r /tmp/requirements-plugin.txt

# Copy full repo to staging context
COPY . /repo

# Build staged runtime and copy into /app
RUN chmod +x /repo/packaging/stage-runtime.sh && \
    STAGE_DIR=$(/repo/packaging/stage-runtime.sh) && \
    cp -r "$STAGE_DIR"/* /app/

EXPOSE 8080

CMD ["python", "bin/ultimate-kea-dashboard-plugin"]
