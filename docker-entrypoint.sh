#!/bin/sh
# Make the data directory writable by the app user, then drop root.
#
# Render (and Docker volumes generally) mount a disk owned by root over the image's
# own directory, so ownership set at build time doesn't apply. Without this the
# first write to the SQLite ledger fails on a fresh disk — and it fails quietly,
# because the tracker treats a bad scan as "took no positions" rather than
# crashing. That would look like a working deploy with a permanently empty record.
set -e

DATA_DIR="${TRACKER_DATA_DIR:-/app/data}"
mkdir -p "$DATA_DIR"

if [ "$(id -u)" = "0" ]; then
  chown -R optic:optic "$DATA_DIR"
  # setpriv is in util-linux, already present in the slim base image.
  exec setpriv --reuid=optic --regid=optic --init-groups "$@"
fi

# Already unprivileged (e.g. a platform that sets its own user): just run.
exec "$@"
