
import os
from dotenv import load_dotenv

import secrets
import json
import asyncio
import base64
import httpx
from fastapi import Request, HTTPException
from fastapi.responses import HTMLResponse
import urllib.parse
from .integration_item import IntegrationItem
from dateutil import parser


from fastapi import Request

from redis_client import add_key_value_redis, get_value_redis, delete_key_redis

load_dotenv() 

CLIENT_ID = os.getenv('HUBSPOT_CLIENT_ID')
CLIENT_SECRET = os.getenv('HUBSPOT_CLIENT_SECRET')

SCOPES_REQUIRED = ["oauth"]
SCOPES_OPTIONAL = [
    "crm.schemas.contacts.read",
    "crm.objects.contacts.read"
]


encoded_client_id_secret = base64.b64encode(f'{CLIENT_ID}:{CLIENT_SECRET}'.encode()).decode()


REDIRECT_URI = 'http://localhost:8000/integrations/hubspot/oauth2callback'
encoded_redirect_uri= urllib.parse.quote(REDIRECT_URI, safe='')
authorization_url=f"https://app-na2.hubspot.com/oauth/authorize?client_id={CLIENT_ID}&redirect_uri=http://localhost:8000/integrations/hubspot/oauth2callback&scope=crm.objects.contacts.write%20crm.schemas.contacts.write%20oauth%20crm.schemas.contacts.read%20crm.objects.contacts.read"

async def authorize_hubspot(user_id, org_id):
    state_data = {
        "state": secrets.token_urlsafe(32),
        "user_id": user_id,
        "org_id": org_id
    }
    encoded_state = json.dumps(state_data)

    # Save state to Redis for validation later
    await add_key_value_redis(
        f"hubspot_state:{org_id}:{user_id}",
        encoded_state,
        expire=600
    )

    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": " ".join(SCOPES_REQUIRED),
        "optional_scope": " ".join(SCOPES_OPTIONAL),
        "state": encoded_state
    }

    # urlencode with safe=' ' so spaces stay encoded as %20
    query_str = urllib.parse.urlencode(params, safe=' ')
    auth_url = f"https://app-na2.hubspot.com/oauth/authorize?{query_str}"

    return auth_url


async def oauth2callback_hubspot(request: Request):
    if request.query_params.get('error'):
        raise HTTPException(status_code=400, detail=request.query_params.get('error'))

    code = request.query_params.get('code')
    encoded_state = request.query_params.get('state')

    if not code or not encoded_state:
        raise HTTPException(status_code=400, detail='Missing code or state.')

    # URL-decode the state parameter first (if you URL-encoded it)
    import urllib.parse
    decoded_state_str = urllib.parse.unquote_plus(encoded_state)
    state_data = json.loads(decoded_state_str)

    original_state = state_data.get('state')
    user_id = state_data.get('user_id')
    org_id = state_data.get('org_id')

    saved_state = await get_value_redis(f'hubspot_state:{org_id}:{user_id}')
    if not saved_state or original_state != json.loads(saved_state).get('state'):
        raise HTTPException(status_code=400, detail='State does not match.')

    token_url = "https://api.hubapi.com/oauth/v1/token"
    headers = {
        "Authorization": f"Basic {encoded_client_id_secret}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {
        "grant_type": "authorization_code",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
        "code": code
    }

    async with httpx.AsyncClient() as client:
        response, _ = await asyncio.gather(
            client.post(token_url, data=data, headers=headers),
            delete_key_redis(f'hubspot_state:{org_id}:{user_id}')
        )

    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=response.text)

    await add_key_value_redis(
        f'hubspot_credentials:{org_id}:{user_id}',
        json.dumps(response.json()),
        expire=600
    )

    close_window_script = """
    <html>
        <script>
            window.close();
        </script>
    </html>
    """
    return HTMLResponse(content=close_window_script)


async def get_hubspot_credentials(user_id, org_id):
    credentials = await get_value_redis(f'hubspot_credentials:{org_id}:{user_id}')
    if not credentials:
        raise HTTPException(status_code=400, detail='No credentials found.')
    
    credentials = json.loads(credentials)
    if not credentials:
        raise HTTPException(status_code=400, detail='No credentials found.')

    await delete_key_redis(f'hubspot_credentials:{org_id}:{user_id}')
    return credentials

async def create_integration_item_metadata_object(response_json):
    """
    Maps a HubSpot contact JSON response into your IntegrationItem model.
    """

    # Derive a human-readable name
    props = response_json.get("properties", {})
    firstname = props.get("firstname")
    lastname = props.get("lastname")
    name = (
        f"{firstname or ''} {lastname or ''}".strip()
        or props.get("email")
        or f"Contact {response_json.get('id')}"
    )

    # Parse timestamps
    created_at = props.get("createdate") or response_json.get("createdAt")
    updated_at = props.get("hs_lastmodifieddate") or response_json.get("lastmodifieddate")

    try:
        creation_time = parser.isoparse(created_at) if isinstance(created_at, str) else None
    except Exception:
        creation_time = None

    try:
        last_modified_time = parser.isoparse(updated_at) if isinstance(updated_at, str) else None
    except Exception:
        last_modified_time = None

    integration_item_metadata = IntegrationItem(
        id=response_json.get("id"),
        type="HubSpotContact",
        name=name,
        creation_time=creation_time,
        last_modified_time=last_modified_time,
        url=f"https://app.hubspot.com/contacts/{response_json.get('portalId')}/contact/{response_json.get('id')}"
        if response_json.get("portalId") else None,
        directory=False,
        visibility=True
    )

    return integration_item_metadata

async def get_items_hubspot(credentials) -> list[IntegrationItem]:

    credentials = json.loads(credentials)
    access_token = credentials.get("access_token")

    if not access_token:
        return []

    async with httpx.AsyncClient() as client:
        # Example: Fetch contacts from HubSpot CRM v3 API
        response = await client.get(
            "https://api.hubapi.com/crm/v3/objects/contacts",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            },
            params={
                "limit": 50,  # adjust as needed
                "properties": "firstname,lastname,email,createdate,hs_lastmodifieddate"
            }
        )

    if response.status_code == 200:

        results = response.json().get("results", [])

        list_of_integration_item_metadata = [
            await create_integration_item_metadata_object(result) for result in results
        ]

        return list_of_integration_item_metadata
    
    return []