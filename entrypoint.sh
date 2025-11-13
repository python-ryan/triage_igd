#!/usr/bin/env bash
set -e

: "Waiting for MongoDB to be available..."


host="${MONGO_HOST:-mongo}"
port="${MONGO_PORT:-27017}"


until nc -z "$host" "$port"; do
echo "Waiting for MongoDB at $host:$port..."
sleep 1
done


# Gunakan --workers 1 diproduction
exec uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1
