#!/bin/sh

#Check if installer was passed as parameter
if [ $# -eq 0 ]
then
  echo "No API Gateway installer provided"
  echo "Usage: ./opt/runInstall.sh /opt/APIGateway_Install.run"
  exit 1
fi

#Get installer version from .run file ($1)
installerInfo="$(./"$1" --version)"
echo 'Provided installer version:'
echo "$installerInfo"
#Strip out "." ie 7.7.0 = 770
installerVersion=$(( $(echo "$installerInfo" | cut -c 19-23 | tr -d .) ))
#Strip out year ie 2020-01-30 = 2020
installerDate=$(( $(echo "$installerInfo" | cut -c 37-41) ))

disabled_components="apigateway,nodemanager,apimgmt,policystudio,configurationstudio,qstart,cassandra,packagedeploytools"
#Only add apitester to components in versions released before 2020 ie before 7.7.20200130
if [ $installerVersion -lt 770 ] || [ $installerDate -lt 2020 ]
then
  disabled_components=$("$disabled_components",apitester)
fi

echo 'Performing install steps...'
cd /opt && \
    ./APIGateway_Install.run \
        --mode unattended \
        --unattendedmodeui none \
        --setup_type complete \
        --prefix /opt/Axway/ \
        --firstInNewDomain 0 \
        --configureGatewayQuestion 0 \
        --nmStartupQuestion 0 \
        --enable-components analytics \
        --disable-components "${disabled_components}" \
        --startCassandra 0 && \
    rm -rf /opt/Axway/Axway-installLog.log \
        /opt/Axway/uninstall* \
        /opt/Axway/analytics/system/lib/embeddedAMQ \
        /opt/Axway/analytics/system/lib/ibmmq \
        /opt/Axway/analytics/system/lib/mapper
