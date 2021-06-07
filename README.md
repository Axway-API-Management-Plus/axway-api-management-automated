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
- an API-Design Tool for instance Stoplight

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

You are welcome to fork this repository and customize it according to your own needs. In the default setup with a Kubernetes cluster (EKS) on AWS and using GitPackages as the repository, the following environment variables are required. These must be created accordingly in your fork. 

| Secret/Variable        | Description                                                                            |
| :---                   | :---                                                                                   |
| APIGATEWAY_LICENSE     | The Axway API-Gateway License Base64 encode                                            |
| APIM_HOST              | The host of the API-Manager used by the APIM-CLI                                       |
| APIM_PORT              | The port of the API-Manager used by the APIM-CLI                                       |
| APIM_USER              | System Account for the API-Manager System Account used by the APIM-CLI                 |
| APIM_PASS              | Password for the API-Manager System Account used by the APIM-CLI                       |
| AWS_ACCESS_KEY_ID      | Used to authenticate at AWS in oder to control the K8S-Cluster running at AWS-EKS      |
| AWS_SECRET_ACCESS_KEY  | Used to authenticate at AWS in oder to control the K8S-Cluster running at AWS-EKS      |
| KUBE_CONFIG_DATA       | Kubectl configuration                                                                  |


| API-Name                                             | Description                                                                                           | Last update  |
| :---                                                 | :---:                                                                                                 | :---         |
| [EMR-Catalog](api-emr-catalog)                       | An API just deployed without anything special. It has no backend configured.                          | 2021/05/31   |
| [EMR-Diagnostic Mocked](api-emr-diagnostic)          | This API is mocked based on an API-Builder container running on the K8S-Cluster.                      | 2021/05/31   |
