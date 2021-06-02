# API Project examples

In this Repostiory you will find a number of sample API projects that are synchronized with the Axway API Management Platform based on a CI/CD pipeline. The 
integration pipeline is based on the Axway APIM-CLI described [here](https://github.com/Axway-API-Management-Plus/apim-cli).  

This repository is not so much about the API configuration itself, but the various ways to build a full-fledged pipeline, including unit and 
integration testing, release management, etc.  

GitHub Actions is used as the integration pipeline, but you can use any other pipeline tool like Jenkins or Azure pipelines equivalently.

| API-Name                                             | Description                                                                                           | Last update  |
| :---                                                 | :---:                                                                                                 | :---         |
| [EMR-Catalog](api-emr-catalog)                       | An API just deployed without anything special. It has no backend configured.                          | 2021/05/31   |
| [EMR-Diagnostic Mocked](api-emr-diagnostic)          | This API is mocked based on an API-Builder container running on the K8S-Cluster.                      | 2021/05/31   |