## EMR HealthCatalog API

This is the simplest way to store an API for the API-Management platform. 

The stored [API specification](config/EMR-HealthCatalog.json) is referenced by the [API config file](config/api-config.json), which is 
replicated to the API-Management platform when changes are made by the GitHub workflow [api.emr-catalog.deploy.yml](../.github/workflows/api.emr-catalog.deploy.yml) 
using the [APIM CLI](https://github.com/Axway-API-Management-Plus/apim-cli).

The integration of the APIM CLI is based on Maven, therefore a corresponding [pom.xml](pom.xml) which defines the dependency is stored
