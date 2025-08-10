# VectorShift Backend - Integrations Technical Assessment

## Setup

1. Navigate to `/backend` folder.
2. Install dependencies in virtual env ( python3 -m venv environment name )
3. Start Redis server - setup using docker
   1. docker pull redis
   2. docker run --name my-redis -p 6379:6379 -d redis
   3. docker exec -it my-redis redis-cli -h 127.0.0.1 -p 6379 ( to check if the server is alive )

4. Run FastAPI backend - uvicorn main:app --reload



## What It Does

- Handles OAuth flows for HubSpot (authorize, callback, token storage).
- Fetches HubSpot integration items from HubSpot API.
- Uses FastAPI and Redis for async task management.
- Follows the same pattern as Notion and Airtable integrations.

