import yaml
import requests
import json
import os
from urllib.parse import quote

from dotenv import load_dotenv

load_dotenv()


TOKEN = os.getenv("TOKEN")
BASE_URL = os.getenv("BASE_URL")
HOST = os.getenv("HOST")


def authenticate(apitoken: str = TOKEN):
    url = HOST+"mtm/v1/oauth2/token"
    response = requests.post(url, auth=('apitoken', apitoken),
                             data={'grant_type': 'client_credentials'})

    if response.status_code == 200:
        access_token = response.json()['access_token']
        error = None

    elif response.status_code == 401:
        error = "API Token invalid."
        access_token = None
        print('API Token invalid')
        raise Exception(error)

    return access_token


def send_yaml(bearer_token: str):

    # Load YAML file
    # check https://gist.github.com/vg-leanix/70999f4705fd8ed930871ea4c8cc8864
    with open('leanix.yaml', 'r') as stream:
        try:
            manifest_data = yaml.safe_load(stream)
        except yaml.YAMLError as exc:
            print(exc)

    # Prepare the data for the API call
    # fs_id = manifest_data['services'][0]['id']
    api_data = {
        'name': manifest_data['services'][0]['name'],
        'description': manifest_data['services'][0]['description'],
        # 'businessApplications': manifest_data['services'][0]['business_applications'],
        # 'teams': manifest_data['services'][0]['teams'],
        # 'tags': manifest_data['services'][0]['tags'],
        # 'resources': manifest_data['services'][0]['resources'],
    }

    # Convert the data to JSON

    # Define the headers for the API call
    # headers = {
    #     'Content-Type': 'application/json',
    #     'Authorization': 'Bearer ${{ secrets.YOUR_SECRET_NAME }}'
    # }

    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {bearer_token}'
    }

    # Repository URL is used as the identifier for the microservice

    repository_url = os.getenv('REPOSITORY_URL')
    external_id = "vg-leanix/technology-discovery" + "/"+api_data['name']

    api_data['externalId'] = external_id
    repo = {
        "url": "https://github.com/vg-leanix/technology-discovery",
        "status": "ACTIVE",
        "visibility": "PUBLIC"

    }
    api_data['repository'] = repo

    api_data_json = json.dumps(api_data, indent=2)
    print("PAYLOAD: ", api_data_json)

    # First, check if the microservice already exists
    encoded_ext_id = quote(external_id, safe='')
    url = BASE_URL + f"/microservices/externalId/{encoded_ext_id}"
    response = requests.get(url, headers=headers)

    # url = BASE_URL + f"/microservices/{fs_id}"
    # response = requests.get(url, headers=headers)

    print("GET",  url)
    print("GET",  response.text)

    # If the microservice does not exist, create it
    if response.status_code == 404:
        print("Microservice doesnt exist. Will create..")
        url = f'{BASE_URL}/microservices'
        print(url)
        response = requests.post(url, headers=headers, data=api_data_json)

        print("POST", response.text)
    # If the microservice exists, update it
    elif response.status_code == 200:
        microservice_id = response.json()['data']['factsheetId']
        url = BASE_URL + f"/microservices/{microservice_id}"
        response = requests.put(url, headers=headers, data=api_data_json)

        print("PUT", response.text)
        print("Updated Microservice")

    # Get the microservice id
    microservice_id = response.json()['data']['factsheetId']

    # Upload SBOM file
    # replace with the path to your SBOM file
    sbom_file_path = 'bom.json'
    files = {'sbom': open(sbom_file_path, 'rb')}
    url = BASE_URL + f"/microservices/{microservice_id}/sboms"

    files = [
        ('sbom', ('sbom.json', open(sbom_file_path, 'rb'), 'application/json'))
    ]

    headers.pop('Content-Type')
    response = requests.post(url, headers=headers, files=files)

    # Print the response from the API
    print("Attached SBOM")
    print("POST SBOM", url)
    print(response.json())


if __name__ == "__main__":
    bearer = authenticate()
    send_yaml(bearer_token=bearer)
