
import os
from dotenv import load_dotenv

import secrets
import json
import asyncio
import base64
import httpx
from fastapi import Request, HTTPException
from fastapi.responses import HTMLResponse


from fastapi import Request

from redis_client import add_key_value_redis, get_value_redis, delete_key_redis

load_dotenv() 

CLIENT_ID = os.getenv('HUBSPOT_CLIENT_ID')
CLIENT_SECRET = os.getenv('HUBSPOT_CLIENT_SECRET')

encoded_client_id_secret = base64.b64encode(f'{CLIENT_ID}:{CLIENT_SECRET}'.encode()).decode()


authorization_url=f"https://app-na2.hubspot.com/oauth/authorize?client_id={CLIENT_ID}&redirect_uri=http://localhost:8000/integrations/hubspot/oauth2callback&scope=crm.objects.contacts.write%20crm.schemas.contacts.write%20oauth%20crm.schemas.contacts.read%20crm.objects.contacts.read"


async def authorize_hubspot(user_id, org_id):
    state_data = {
        'state': secrets.token_urlsafe(32),
        'user_id': user_id,
        'org_id': org_id
    }
    encoded_state = json.dumps(state_data)
    await add_key_value_redis(f'hubspot_state:{org_id}:{user_id}', encoded_state, expire=600)

    return f'{authorization_url}&state={encoded_state}'

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
        "client_id": HUBSPOT_CLIENT_ID,
        "client_secret": HUBSPOT_CLIENT_SECRET,
        "redirect_uri": HUBSPOT_REDIRECT_URI,
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
    # TODO
    pass

async def create_integration_item_metadata_object(response_json):
    # TODO
    pass

async def get_items_hubspot(credentials):
    # TODO
    pass