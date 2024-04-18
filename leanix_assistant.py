import logging
from pathlib import Path
import yaml
import requests
import json
import os
from urllib.parse import quote

logging.basisConfig(level=logging.INFO)

# Request timeout
TIMEOUT = 10

# API token and Subdomain are set as env variables.
# It is adviced not to hard code sensitive information in your code.
LEANIX_API_TOKEN = os.getenv('TOKEN')
LEANIX_SUBDOMAIN = os.getenv('BASE_URL')
LEANIX_FQDN = f'https://{LEANIX_SUBDOMAIN}.leanix.net/services'
LEANIX_MANIFEST_FILE = os.getenv('LEANIX_MANIFEST_FILE', 'leanix.yaml')

# OAuth2 URL to request the access token.
LEANIX_OAUTH2_URL = f'{LEANIX_FQDN}/mtm/v1/oauth2/token'

# Microservices APIs
LEANIX_MICROSERVICES = f'{LEANIX_FQDN}/technology-discovery/v1/microservices'

# Github Related
GITHUB_SERVER_URL = os.getenv('GITHUB_SERVER_URL')
GITHUB_REPOSITORY = os.getenv('GITHUB_REPOSITORY')

def obtain_access_token() -> str:
    """Obtains a LeanIX Access token using the Technical User generated
    API secret.

    Returns:
        str: The LeanIX Access Token
    """
    if not LEANIX_API_TOKEN:
        raise Exception('A valid token is required')
    response = requests.post(
        LEANIX_OAUTH2_URL,
        auth=('apitoken', LEANIX_API_TOKEN),
        data={'grant_type': 'client_credentials'},
    )
    response.raise_for_status()
    return response.json().get('access_token')


def _parse_manifest_file() -> dict:
    """Parses the Manifest file and generates the payload for the
    API request for the LeanIX Microservices API.

    Returns:
        dict: The payload for the API request
    """
    with open(LEANIX_MANIFEST_FILE, 'r') as file:
        try:
            manifest_data = yaml.safe_load(file)
        except yaml.YAMLError as exc:
            logging.error(f'Failed to load Manifest file: {exc}')
    
    if not manifest_data:
        logging.info('No manifest entries found')
        return
    manifest_microservices = manifest_data.get('services', [])
    micro_services = []
    for micro_service in manifest_microservices:
        api_data = {
            'externalId': micro_service.get('external_id', GITHUB_REPOSITORY),
            'name': micro_service.get('services', []).get('name'),
            'description': micro_service.get('service'),
            'businessApplications': [
                {
                    'name': business_application.get('name'),
                    'factSheetId': business_application.get('factsheet_id')
                }
                for business_application in micro_service.get('business_applications', [])
            ],
            'repository': {
                'url': f'{GITHUB_SERVER_URL}/{GITHUB_REPOSITORY}',
                'status': 'ACTIVE',
                'visibility': 'PUBLIC'
            }
        }
        micro_services.append(api_data)
    return micro_services

def _create_or_update_micro_services(microservice: dict, create: bool=False) -> requests.Response:
    """Creates or Updates the LeanIX Microservice Fact Sheet

    Args:
        microservice (dict): The LeanIX matching API request payload
        create (bool, optional): Indicates wether to `create` or `update` the Fact Sheet. Defaults to False.

    Returns:
        requests.Response: The response of the request for further processing.
    """
    url = f'{LEANIX_MICROSERVICES}'
    method = 'POST' if create is True else 'PUT'
    # Fetch the access token and set the Authorization Header
    auth_header = f'Bearer {os.environ.get('LEANIX_ACCESS_TOKEN')}'
    # Provide the headers
    headers = {
        'Authorization': auth_header,
    }
    response = requests.request(method=method, headers=headers, url=url, json=microservice)
    response.raise_for_status()
    return response
    
    
def create_or_update_micro_services(microservices: list):
    for microservice in microservices:
        factsheet_id = None
        encoded_external_id = quote(microservice.get('externalId'))
        url = f'{LEANIX_MICROSERVICES}/externalId/{encoded_external_id}'
        response = requests.get(url, timeout=TIMEOUT)
        if response.status_code == 200:
            # Micro Service exists, update
            logging.info(f'Microservice {microservice.get('externalId')} exists, updating')
            response = _create_or_update_micro_services(microservice)
            factsheet_id = response.data.get('data').get('factSheetId')
        elif response.status_code == 404:
            # Microservice does not exist, create it
            _create_or_update_micro_services(microservice, create=True)
            logging.info(f'Microservice {microservice.get('externalId')} does not exist, creating')
            factsheet_id = response.data.get('data').get('factSheetId')
        else: 
            response.raise_for_status()
        register_sboms(factsheet_id)
            
    
def register_sboms(factsheet_id: str) -> bool:
    sbom_path = Path('sbom.json')
    if not sbom_path.exists():
        logging.warning('No sbom file found')
        return
    
    url = f'{LEANIX_MICROSERVICES}/{factsheet_id}/sboms'
    sbom_contents = dict()
    with sbom_path.open('r') as f:
        sbom_contents = json.load(f)
        
    request_payload = {
        'sbom': (
            sbom_path.name,
            sbom_contents,
            'application/json'
        )
    }
    logging.debug(f'Populated payload for SBOM: {sbom_path.name}')
    # Fetch the access token and set the Authorization Header
    auth_header = f'Bearer {os.environ.get('LEANIX_ACCESS_TOKEN')}'
    # Provide the headers
    headers = {
        'Authorization': auth_header,
        'Content-Type': 'multipart/form-data'
    }
    response = requests.post(
        url, 
        headers=headers,
        files=request_payload,
        timeout=TIMEOUT
    )
    response.raise_for_status()
    
def main():
    """LeanIX helper to parse the manifest file create or update a microservice
    and register the relevant dependencies.
    """
    manifest_data = _parse_manifest_file()
    create_or_update_micro_services(manifest_data)


if __name__ == "__main__":
    # Set the access token as an environment variable
    os.environ['LEANIX_ACCESS_TOKEN'] = obtain_access_token()
    main()
    
    
