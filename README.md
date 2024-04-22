# Technology Risk and Compliance

## Registering Microservices and their dependencies in LeanIX

This project provides a demonstration on how to register Microservices in LeanIX, including their dependencies as Software Bill of Materials (SBOMS). The primary focus is to showcase the usage of a manifest file (YAML file) within a CI/CD environment and the LeanIX APIs to facilitate the registration process.

## Key Features

- **Manifest File**: A YAML file that contains all the necessary data to successfully register the microservice and generate the corresponding LeanIX Microservice fact sheet.
- **CI/CD Integration**: The ability to use the manifest file within a CI/CD environment, enabling developers to perform the required actions through familiar environments.
- **LeanIX APIs**: The APIs can be used independently, allowing developers to manually perform the registration if desired.

## Usage

This section will guide you on how to use the manifest file and LeanIX APIs.

### Manifest File

The manifest file (YAML file) contains all the necessary data to register the microservice. Here's a sample structure of the manifest file:

```yaml
version: 1
services:
  - name: payments-service-v2
    externalId: payments-service-v2
    description: |
      A microservice responsible for payment processing.
      This service handles various payment transactions and is an integral part of our payment ecosystem.
      NOTE: This is an updated service

    applications:
      - factSheetId: fa787383-7233-4896-8fad-c1f1bef30dd2

    tags:
      - tagGroupName: Domain
        tagNames: 
          - Payments

      - tagGroupName: Location
        tagNames:
          - AWS-EU1

    resources:
      - type: website
        url: https://myorg.atlassian.net/wiki/spaces/payment
        description: Confluence documentation

    teams:
      - factSheetId: afd1ee0f-095b-4c68-88f6-d3628070ce18
```

### CI/CD Integration

You can integrate the manifest file within your CI/CD pipeline. This allows you to automate the process of registering the microservice and it's dependencies whenever there's a change in your codebase.
