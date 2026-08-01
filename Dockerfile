# Optic Terminal — container image for a hosted deployment.
FROM python:3.12-slim

# gcc/gfortran are needed to build any wheel that isn't published for this
# platform (scipy and pandas usually are, but a version bump shouldn't break the
# build). Removed in the same layer so they don't ship in the final image.
WORKDIR /app
COPY requirements.txt .
RUN apt-get update \
 && apt-get install -y --no-install-recommends gcc g++ gfortran curl \
 && pip install --no-cache-dir -r requirements.txt \
 && apt-get purge -y --auto-remove gcc g++ gfortran \
 && rm -rf /var/lib/apt/lists/*

COPY app ./app
COPY static ./static

# Don't run as root — the app needs no privileges once it's serving.
RUN useradd --create-home --shell /usr/sbin/nologin optic && chown -R optic:optic /app

# Entry point stays root just long enough to fix the disk, then drops privileges.
#
# Render mounts a persistent disk at runtime owned by root, *over* whatever the
# image had at that path — so a build-time chown can't reach it. Running as
# `optic` from the start means the very first write to the ledger fails with a
# permission error on a fresh disk, which surfaces as a tracker that silently
# never records anything. Chowning at startup is the documented way round it.
#
# setpriv comes from util-linux, already in the base image, so this needs no extra
# package. --init-groups gives the process optic's supplementary groups rather
# than inheriting root's.
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]

ENV PYTHONUNBUFFERED=1

# Where the ledger, the symbol directory and the screener cache live. Declared so
# a plain `docker run` behaves like the deploy, and so the entrypoint has one
# place to look.
ENV TRACKER_DATA_DIR=/app/data

# The platform supplies $PORT; 8077 keeps `docker run` working locally.
ENV PORT=8077
EXPOSE 8077

# One worker on purpose: yfinance access is serialised behind an in-process lock
# (see app/providers/yf.py), and a second worker would be a second cache and a
# second lock — doubling upstream requests and risking the rate limiting that
# lock exists to avoid. Scale by making the single worker faster, not by adding
# workers, until the provider layer is process-safe.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8077} --workers 1 --timeout-keep-alive 65"]
