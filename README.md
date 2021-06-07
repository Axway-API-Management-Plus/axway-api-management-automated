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
- Windows or Linux environment (Learn more [System requirements](https://docs.axway.com/bundle/axway-open-docs/page/docs/apim_installation/apigtw_install/system_requirements/index.html#operating-systems-and-hardware))
- Git client for instance GitHub Desktop
- GitHub account
- Axway Policy Studio installed (Learn more [Install Policy Studio](https://docs.axway.com/bundle/axway-open-docs/page/docs/apim_installation/apigtw_install/install_policy_studio/index.html))
- npm and Nodes.js installed (Learn more [API Builder Getting Started Guide](https://docs.axway.com/bundle/API_Builder_4x_allOS_en/page/api_builder_getting_started_guide.html))
- [apim-cli](https://github.com/Axway-API-Management-Plus/apim-cli/wiki/1.-How-to-get-started) installed
- Access to npm repositories
- an API-Design Tool for instance Stoplight

### Check-Out

As a first step, the API service provider must check out the repository. The following example:
```
git clone https://github.com/Axway-API-Management-Plus/axway-api-management-automated.git
```

Then, the API service provider opens the checked-out repository in its desired development tool, such as Visual Studio Code.

## Use-Cases

This repository simulates how the Axway API management platform can be fully automated based on version management and DevOps pipelines. This includes a number of use cases that are presented here.

### APIs as Code

The API as Code approach means that instead of manually configuring their APIs in the system, they define them in the version management system of their choice and register and keep them in sync through a DevOps pipeline in the API management platform.

### API-Design

This use case is about creating a completely new API based on an API-first approach. To do this, you use an API design editor of your choice, design the first version of your API and then register it in the API management platform.

### API Mockup with API-Builder

After you have designed an API, it is a convenient way of the API builder to quickly and easily mock APIs, separating the process between API service and API consumption. 

### API Integration with API-Builder

Of course, the real strength of the API Builder is not mocking APIs, but various integration scenarios, customizing and optimizing APIs. 

### API Gateway Configuration

The API gateways are controlled by policies, which are configured in Policy Studio and then deployed to the API gateways completely automatically through the DevOps pipelines set up here without any downtime.

### API Gateway Updates

Using DevOps pipelines and a Kubernetes cluster, updating the API management platform is done by a rolling exchange of the corresponding Docker images, which are built by the pipeline and registered with the Kubernetes cluster.

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
| KUBE_CONFIG_DATA       | The Base64 encoded Kubectl configuration. cat $HOME/.kube/config | base64              |
