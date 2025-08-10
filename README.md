# VectorShift Backend - Integrations Technical Assessment

## Setup

1. Navigate to `/backend` folder.
2. Ideally its better to setup a virtual env ( python3 -m venv 'environment name' )
3. Sensitive credentials (like client IDs, secrets, tokens) are **not included** in the repo for security reasons. Please create a `.env` file in the backend root directories based on `.env.example` file provided (or create your own) with the following variables: 

   ### Backend example (`.env`):

   # notion integration credentials
   NOTION_CLIENT_ID={your_notion_client_id}
   NOTION_CLIENT_SECRET={your_notion_client_secret}

   # hubspot integration credentials
   HUBSPOT_CLIENT_ID={your_hubspot_client_id}
   HUBSPOT_CLIENT_SECRET={your_hubspot_client_secret}

   # airtable integration credentials
   AIRTABLE_CLIENT_ID={your_airtable_client_id}
   AIRTABLE_CLIENT_SECRET={your_airtable_client_secret}

   ### ### ### 

4. Start Redis server - setup using docker
   1. docker pull redis
   2. docker run --name my-redis -p 6379:6379 -d redis
   3. docker exec -it my-redis redis-cli -h 127.0.0.1 -p 6379 ( to check if the server is alive )

5. Run FastAPI backend - uvicorn main:app --reload



## What It Does

- Handles OAuth flows for HubSpot (authorize, callback, token storage).
- Fetches HubSpot integration items from HubSpot API.
- Uses FastAPI and Redis for async task management.
- Follows the same pattern as Notion and Airtable integrations.

