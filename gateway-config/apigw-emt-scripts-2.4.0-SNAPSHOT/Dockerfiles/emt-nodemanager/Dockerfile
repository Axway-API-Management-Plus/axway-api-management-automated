ARG PARENT_IMAGE=apigw-base:nocache
#checkov:skip=CKV_DOCKER_7:Base image is built skipping the cache
FROM $PARENT_IMAGE

ARG DOCKER_IMAGE_ID
ARG ANM_USERNAME
ARG HEALTHCHECK
ARG METRICS_DB_URL
ARG METRICS_DB_USERNAME
ARG FIPS_MODE

COPY --chown=emtuser:0 opt/emt_resources /tmp/emt
COPY --chown=emtuser:0 scripts/* /opt/Axway/apigateway/posix/bin/


RUN yum install -y python3
RUN yum install -y python3-pip
RUN pip3 install pyyaml

USER emtuser

RUN if [ -e /tmp/emt/lic.lic ]; then cp /tmp/emt/lic.lic /opt/Axway/apigateway/conf/licenses; fi && \
    if [ "$HEALTHCHECK" = "True" ]; then cp /tmp/emt/anm_hc_path.xml /opt/Axway/apigateway/samples/SamplePolicies/HealthCheck; fi && \
    mkdir -p /opt/Axway/apigateway/groups/certs/private && \
    touch /opt/Axway/apigateway/groups/certs/index.txt && \
    echo $(printf '%x\n' `date +"%s%2N"`) > /opt/Axway/apigateway/groups/certs/serial && \
    cp /tmp/emt/domaincert.pem /opt/Axway/apigateway/groups/certs/ && \
    cp /tmp/emt/domainkey.pem /opt/Axway/apigateway/groups/certs/private/ && \
    cd /opt/Axway/apigateway/posix/bin && \
    ./setup-emt-nodemanager \
        --props /tmp/emt/config.props \
        --fed /tmp/emt/fed.fed \
        --anm-username "$ANM_USERNAME" \
        --merge-dir /tmp/emt/apigateway \
        --healthcheck $HEALTHCHECK \
        --docker-image-id "$DOCKER_IMAGE_ID" \
        --metrics-db-url "$METRICS_DB_URL" \
        --metrics-db-username "$METRICS_DB_USERNAME" \
        --fips $FIPS_MODE && \
    chmod -R ug+rw /opt/Axway

RUN rm -rf /tmp/emt

CMD ["/opt/Axway/apigateway/posix/bin/start-emt-nodemanager"]
#checkov:skip=CKV_DOCKER_2:This is meant to run in Kubernetes, no HEALTHCHECK defined
