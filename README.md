# Axway API-Management Automated

This repository includes a set of sample APIs and API-Gateway policy configurations, just as would be set up for customers if they wanted to automate control of the Axway API-Management platform based on DevOps pipelines, which is of course Axway's clear recommendation.

The following use cases/requirements are illustrated:

API Design
APIs as Code
API Mockup with API-Builder
API integration with API-Builder
API Gateway Configuration
API Gateway Updates

The DevOps pipelines run on top of GitHub actions, but are also implementable with any other technology such as Jenkins or Azure pipelines, as only standard tools such as the APIM CLI, kubectl, etc. are used. 
Some of the use cases, like API builder or API gateway updates, require the API management solution to run in a Kubernetes cluster.

## Setup 

### Service-Provider Setup

The steps listed here are necessary for the API service provider if they want to use all or some of the use cases. For example, if you want to register or modify APIs or change policies.

The following requirements
- Windows or Linux environment
- Git client
- GitHub account
- Axway Policy Studio installed
- npm and Nodes.js installed
- apim-cli installed
- Access to npm repositories

### Check-Out

As a first step, the API service provider must check out the repository. The following example:
```
git clone https://github.com/cwiechmann/api-project-examples.git
```

Then, the API service provider opens the checked-out repository in its desired development tool, such as Visual Studio Code.

## Use-Cases

### API-Design

### APIs as Code

### API Mockup with API-Builder

### API Integration with API-Builder

### API Gateway Configuration

### API Gateway Updates


## Base-Setup

APIGATEWAY_LICENSE
APIM_HOST
APIM_PASS
APIM_PORT
APIM_USER
AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY
AXWAY_DOCKER_REG_PASS
AXWAY_DOCKER_REG_USER
BACKEND_HOST
KUBE_CONFIG_DATA


| API-Name                                             | Description                                                                                           | Last update  |
| :---                                                 | :---:                                                                                                 | :---         |
| [EMR-Catalog](api-emr-catalog)                       | An API just deployed without anything special. It has no backend configured.                          | 2021/05/31   |
| [EMR-Diagnostic Mocked](api-emr-diagnostic)          | This API is mocked based on an API-Builder container running on the K8S-Cluster.                      | 2021/05/31   |