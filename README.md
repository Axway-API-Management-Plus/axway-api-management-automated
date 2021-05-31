# API Project examples

In this Repostiory you will find a number of sample API projects that are synchronized with the Axway API Management Platform based on a CI/CD pipeline. The 
integration pipeline is based on the Axway APIM-CLI described [here](https://github.com/Axway-API-Management-Plus/apim-cli).  

This repository is not so much about the API configuration itself, but the various ways to build a full-fledged pipeline, including unit and 
integration testing, release management, etc.  

GitHub Actions is used as the integration pipeline, but you can use any other pipeline tool like Jenkins or Azure pipelines equivalently.

| API-Name                             | Description                                                                                           | Last update  |
| :---                                 | :---:                                                                                                 | :---         |
| [EMR-Catalog](api-emr-catalog)       | An API just deployed without anything special.                                                        | 2021/05/31   |
| [EMR-Diagnostic](api-emr-diagnostic) | This API, creates a new Release-Artefact and uploads to GitHub packages.                              | 2021/05/31   |