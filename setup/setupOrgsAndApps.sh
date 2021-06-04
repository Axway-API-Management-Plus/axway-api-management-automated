#!/bin/bash

currentDir=$PWD
APIM_CLI_VERSION="${APIM_CLI_VERSION:=1.3.7}"
CLI_DIR=$currentDir/apim-cli

if [ ! -d "$CLI_DIR/apim-cli-$APIM_CLI_VERSION" ]; then
    mkdir $CLI_DIR
    wget -qO- https://github.com/Axway-API-Management-Plus/apim-cli/releases/download/apimcli-$APIM_CLI_VERSION/axway-apimcli-$APIM_CLI_VERSION.tar.gz | tar xvfz  - -C $CLI_DIR
fi

CLI=$CLI_DIR/apim-cli-$APIM_CLI_VERSION/scripts/apim.sh

TYPE=$1

if [ "$TYPE" == "" ]; then
    echo "Type not set, importing orgs and applications"
    TYPE="all"
fi

if [ "$TYPE" != "orgs" -a "$TYPE" != "apps" ]; then
    echo "Unkown TYPE: $TYPE. Must be either 'orgs' or 'apps'"
    exit 99
fi

# Import all organizations
if [ "$TYPE" == "orgs" -o "$TYPE" == "all" ]; then
    cd Organizations
    for orgDirectory in `find . -mindepth 1 -type d`
    do
        echo "Import organization from config: $orgDirectory"
        $CLI org import -h $APIM_HOST -port $APIM_PORT -u $APIM_USER -p $APIM_PASS -c $orgDirectory/org-config.json -returnCodeMapping 10:0
    done
fi

# Import all applications
if [ "$TYPE" == "apps" -o "$TYPE" == "all" ]; then
    cd ClientApps
    for appDirectory in `find . -mindepth 1 -type d`
    do
        echo "Import applicaton from config directory: $appDirectory"
        $CLI app import -h $APIM_HOST -port $APIM_PORT -u $APIM_USER -p $APIM_PASS -c $appDirectory/application-config.json -returnCodeMapping 10:0
    done
fi

exit