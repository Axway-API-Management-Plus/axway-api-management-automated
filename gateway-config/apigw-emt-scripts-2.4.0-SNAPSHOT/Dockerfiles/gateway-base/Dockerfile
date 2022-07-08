ARG PARENT_IMAGE=docker.io/centos:7
#checkov:skip=CKV_DOCKER_7:Base image is not a "latest" tag
FROM $PARENT_IMAGE as builder

ARG USER_UID=1000
ARG USER_GID=0

COPY APIGateway_Install.run /opt/APIGateway_Install.run
COPY scripts/runInstall.sh /opt/runInstall.sh
RUN chmod a+x /opt/runInstall.sh && opt/runInstall.sh /opt/APIGateway_Install.run

FROM $PARENT_IMAGE
LABEL maintainer="support@axway.com"

ARG USER_UID
ARG USER_GID

RUN chmod a+rx /opt
RUN getent group "$USER_GID" || groupadd -g "$USER_GID" emt
 
RUN adduser emtuser -l -u "$USER_UID" -g "$USER_GID" -c "EMT User"
COPY --chown=emtuser:0 --from=builder /opt/Axway /opt/Axway

#checkov:skip=CKV_DOCKER_2:This is meant to run in Kubernetes, no HEALTHCHECK defined
#checkov:skip=CKV_DOCKER_3:This is a base image, no user are created
