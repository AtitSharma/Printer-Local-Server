#!/bin/bash

# Kill any process using port 8000
fuser -k 8000/tcp

# Run the FastAPI application with Uvicorn in the background
nohup uvicorn main:app --host localhost --port 8000 --workers 1 --log-level info > uvicorn.log 2>&1 &

echo "Server started on port 8000. Logs are being written to uvicorn.log."
