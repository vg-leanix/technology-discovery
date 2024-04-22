import logging
from pathlib import Path
import yaml
import requests
import json
import os

logging.basicConfig(level=logging.INFO)

# Request timeout
TIMEOUT = 10

# API token and Subdomain are set as env variables.
# It is adviced not to hard code sensitive information in your code.
LEANIX_API_TOKEN = os.getenv('LEANIX_API_TOKEN')
LEANIX_SUBDOMAIN = os.getenv('LEANIX_SUBDOMAIN')
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
            logging.info(f'Parsing manifest file: {file.name}')
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
            'externalId': micro_service.get('externalId', GITHUB_REPOSITORY),
            'name': micro_service.get('name'),
            'description': micro_service.get('description'),
            'applications': [
                {
                    'factSheetId': application.get('factSheetId')
                }
                for application in micro_service.get('applications', [])
            ],
            'repository': {
                'url': f'{GITHUB_SERVER_URL}/{GITHUB_REPOSITORY}',
                'status': 'ACTIVE',
                'visibility': 'PUBLIC'
            },
            'tags': [
                {
                    'tagGroupName': tag.get('tagGroupName'),
                    'tagNames': [
                        tag for tag in tag.get('tagNames')
                    ]
                }
                for tag in micro_service.get('tags', [])
            ]
        }
        micro_services.append(api_data)
    return micro_services

def _create_or_update_micro_services(microservice: dict, factsheet_id:str, create: bool=False) -> requests.Response:
    """Creates or Updates the LeanIX Microservice Fact Sheet

    Args:
        microservice (dict): The LeanIX matching API request payload
        create (bool, optional): Indicates wether to `create` or `update` the Fact Sheet. Defaults to False.

    Returns:
        requests.Response: The response of the request for further processing.
    """
    url = f'{LEANIX_MICROSERVICES}'
    if not create:
        url = f'{url}/{factsheet_id}'
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
    """Creates or updates the LeanIX Microservice Fact Sheet based on the provided manifest file.

    This function either updates an existing microservice or registers a new one based on the HTTP response status.
    If the response is `200`, an update is performed while a `404` status leads to registration of the microservice.
    Once the relevant operation is complete and the corresponding fact sheet ID has been received, 
    the function triggers the sbom ingestion request to register the relevant SBOM file with LeanIX.

    Args:
        microservices (List[dict]): A list of dictionaries, each representing a microservice.

    Returns:
        None
    """
    for microservice in microservices:
        factsheet_id = None
        encoded_external_id = microservice.get('externalId')
        url = f'{LEANIX_MICROSERVICES}/externalId/{encoded_external_id}'
        # Fetch the access token and set the Authorization Header
        auth_header = f'Bearer {os.environ.get('LEANIX_ACCESS_TOKEN')}'
        # Provide the headers
        headers = {
            'Authorization': auth_header,
        }
        response = requests.get(url, headers=headers, timeout=TIMEOUT)
        if response.status_code == 200:
            # Micro Service exists, update
            logging.info(f'Microservice {microservice.get('externalId')} exists, updating')
            # Get the fact sheet id in order to perform the update.
            factsheet_id = response.json().get('data').get('factSheetId')
            crud_response = _create_or_update_micro_services(microservice, factsheet_id)
            logging.info(f'Updated Microservice: {microservice.get('externalId')}')
            logging.debug(f'Response: {json.dumps(crud_response.json())}')
        elif response.status_code == 404:
            # Microservice does not exist, create it
            crud_response = _create_or_update_micro_services(microservice, create=True)
            logging.info(f'Microservice {microservice.get('externalId')} does not exist, creating')
            factsheet_id = crud_response.json().get('data').get('factSheetId')
            logging.info(f'Created Microservice: {microservice.get('externalId')}')
            logging.debug(f'Created Microservice: {json.dumps(crud_response.json())}')
        else:
            logging.error(f'Microservice check failed with: {response.status_code}, {response.content}')
            response.raise_for_status()
        if factsheet_id:
            register_sboms(factsheet_id)
            
    
def register_sboms(factsheet_id: str):
    """
    Registers the Software Bill of Materials (SBOM) file with LeanIX.

    This function enables improved understanding of the dependency landscape of your microservices.
    The SBOM provides comprehensive details about software components, their relationships, and 
    attributes, which are crucial for managing, securing, and licensing your open-source software.
    By registering the SBOM with LeanIX, these details can be effectively managed and tracked.

    Args:
        factsheet_id (str): The unique identifier of the microservice fact sheet. This ID is used 
        to associate the SBOM with the corresponding microservice in LeanIX.

    Returns:
        None
    """
    sbom_path = Path('sbom.json')
    if not sbom_path.exists():
        logging.warning('No sbom file found')
        return
    
    url = f'{LEANIX_MICROSERVICES}/{factsheet_id}/sboms'
    sbom_contents = dict()
    logging.info(f'Processing sbom file: {sbom_path.name} for Fact Sheet: {factsheet_id}')
    with sbom_path.open('rb') as f:
        sbom_contents = f.read()
        
    request_payload = {
        'sbom': (
            sbom_path.name,
            sbom_contents
        )
    }
    logging.debug(f'Populated payload for SBOM: {sbom_path.name}')
    # Fetch the access token and set the Authorization Header
    auth_header = f'Bearer {os.environ.get('LEANIX_ACCESS_TOKEN')}'
    # Provide the headers
    # NOTE: Don't set the content type, `requests` should handle this.
    headers = {
        'Authorization': auth_header,
    }
    logging.info(f'Sending sbom ingestion request for Fact Sheet: {factsheet_id}')
    response = requests.post(
        url, 
        headers=headers,
        files=request_payload,
        timeout=TIMEOUT
    )
    response.raise_for_status()
    logging.info(f'Successfully submited sbom request for Fact Sheet: {factsheet_id}')
    
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
    
    
