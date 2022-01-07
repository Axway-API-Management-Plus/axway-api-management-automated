## EMR-DiagnosticInfo

### Summary

The API is implemented by an API builder microservice. Changes to the API configuration or microservice result in 
deployment to the API management platform and then the API is tested end-to-end.  

### Technical details

The defined [API specification](config/EMR-DiagnosticInfo.json) is referenced by the [API config file](config/api-config.json). 
When changes are made the API is replicated into the API-Management platform by the 
GitHub workflow [api.emr-diagnostic.deploy.yml](../.github/workflows/api.emr-diagnostic.deploy.yml) 
using the [APIM CLI](https://github.com/Axway-API-Management-Plus/apim-cli). A Backend-Path is configured for this API, that points to 
the API-Builder Microservice based on the deployed service:
```json
"backendBasepath" : "http://api-emr-diagnostic:8080/api/api/emr/diagnostic/"
```

The integration of the APIM CLI is based on Maven, therefore a corresponding [pom.xml](pom.xml) defines the dependency.

The [API-Builder](https://docs.axway.com/bundle/api-builder/page/docs/index.html) microservice, which implements the API as a mock, 
is located in the directory: [emr-diagnostic-app](emr-diagnostic-app). When you check out the project, you can start the API Builder 
project locally to see the simple mock implementation.  

```
git clone https://github.com/Axway-API-Management-Plus/axway-api-management-automated.git
cd axway-api-management-automated/api-emr-diagnostic/emr-diagnostic-app
npm start
```


As part of the CI/CD workflow, a Docker image for the API-Builder application is created and rolled out in 
Kubernetes using the [deployment](config/api-deployment.yaml).
