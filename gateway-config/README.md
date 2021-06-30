## Build a new Base-Image

```
tar xvfz APIGateway_7.7.20210330-DockerScripts-2.2.0-2.tar.gz
cd apigw-emt-scripts-2.2.0-2
./build_base_image.py --installer $HOME/APIGateway_7.7.20210330_Install_linux-x86-64_BN06.run --os centos7 --out-image docker.pkg.github.com/cwiechmann/api-project-examples/base:77-20210330
docker login docker.pkg.github.com
docker push docker.pkg.github.com/cwiechmann/api-project-examples/base:77-20210330
```