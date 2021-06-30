## Build a new Base-Image

```
cd axway-api-management-automated/gateway-config
tar xvfz APIGateway_7.7.20210330-DockerScripts-2.2.0-2.tar.gz
# Optionally remove some folder according to: 
# https://docs.axway.com/bundle/axway-open-docs/page/docs/apim_howto_guides/apigw_in_containers/index.html
vi Dockerfiles/gateway-base/scripts/runInstall.sh
cd apigw-emt-scripts-2.2.0-2
./build_base_image.py --installer $HOME/APIGateway_7.7.20210530_Install_linux-x86-64_BN02.run --os centos7 --out-image docker.pkg.github.com/cwiechmann/axway-api-management-automated/base:77-20210530
docker login docker.pkg.github.com
docker push docker.pkg.github.com/cwiechmann/axway-api-management-automated/base:77-20210530
```