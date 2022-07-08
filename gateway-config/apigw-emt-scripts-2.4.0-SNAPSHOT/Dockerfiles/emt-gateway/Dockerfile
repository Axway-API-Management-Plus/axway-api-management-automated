ARG PARENT_IMAGE=apigw-base:nocache
#checkov:skip=CKV_DOCKER_7:Base image is built skipping the cache
FROM $PARENT_IMAGE

ARG GROUP_ID
ARG DOCKER_IMAGE_ID
ARG SETUP_APIMGR
ARG FIPS_MODE
ARG FACTORY_YAML
ENV LANG=en_US.UTF-8

COPY --chown=emtuser:0 opt/emt_resources /tmp/emt
COPY --chown=emtuser:0 scripts/* /opt/Axway/apigateway/posix/bin/

RUN yum install -y python3
RUN yum install -y python3-pip
RUN pip3 install pyyaml

USER emtuser

RUN cp /tmp/emt/lic.lic /opt/Axway/apigateway/conf/licenses && \
    mkdir -p /opt/Axway/apigateway/groups/certs/private && \
    touch /opt/Axway/apigateway/groups/certs/index.txt && \
    echo $(printf '%x\n' `date +"%s%2N"`) > /opt/Axway/apigateway/groups/certs/serial && \
    cp /tmp/emt/domaincert.pem /opt/Axway/apigateway/groups/certs/ && \
    cp /tmp/emt/domainkey.pem /opt/Axway/apigateway/groups/certs/private/ && \
    cd /opt/Axway/apigateway/posix/bin && \
    ./setup-emt-instance \
        --props /tmp/emt/config.props \
        --group-id "$GROUP_ID" \
        --fed /tmp/emt/fed.fed \
        --pol /tmp/emt/pol.pol \
        --env /tmp/emt/env.env \
        --yaml /tmp/emt/yaml \
        --merge-dir /tmp/emt/apigateway \
        --docker-image-id "$DOCKER_IMAGE_ID" \
        --setup-apimgr $SETUP_APIMGR \
        --fips $FIPS_MODE \
        --factory-yaml $FACTORY_YAML && \
    mkdir /opt/Axway/apigateway/events && \
    chmod -R ug+rw /opt/Axway

RUN rm -rf /tmp/emt

CMD ["/opt/Axway/apigateway/posix/bin/start-emt-instance"]
#checkov:skip=CKV_DOCKER_2:This is meant to run in Kubernetes, no HEALTHCHECK defined
