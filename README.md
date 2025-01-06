#  Deploying Oculus Zabbix on Kubernetes Using Helm
## Prerequisites
- Kubernetes cluster (version 1.20 or later) configured and running
- ```kubectl``` installed and configured
- ```git``` installed and configured
- Helm CLI (version 3 or later) installed
- Sufficient resources in the cluster to run Zabbix components

## Installation Steps
1. Clone this repository
    ```sh
    git clone https://github.com/EIDA/oculus-monitoring-backend
    ```
2. Go to .yaml location
    ```sh
    cd zabbix-server/helm-values
    ```
3. Add the Helm epository
    ```sh
    helm repo add zabbix-community https://zabbix-community.github.io/helm-zabbix
    helm repo update
    export ZABBIX_CHART_VERSION='6.1.1'
    ```
4. Create a Namespace for Zabbix
    ```sh
    kubectl create namespace eida-monitoring
    ```
5. Install the Zabbix Helm Chart
    ```sh
    helm upgrade --install oculus-zabbix zabbix-community/zabbix \
    --dependency-update \
    --create-namespace \
    --version $ZABBIX_CHART_VERSION \
    -f {PWD}values.yaml -n eida-monitoring --debug
    ```
## Accessing the Zabbix Application
- Port forwad
    ```sh
    kubectl port-forward service/oculus-zabbix-zabbix-web 8888:80 -n eida-monitoring
    ```
- [localhost:8888](http://localhost:8888)
- Default credentials:
    - Username: Admin
    - Password: zabbix