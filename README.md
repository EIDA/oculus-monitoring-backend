#  Deploying Oculus Zabbix on Kubernetes using Helm
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
    cd zabbix_server/helm_values
    ```
3. Add the Helm epository
    ```sh
    helm repo add zabbix-community https://zabbix-community.github.io/helm-zabbix
    helm repo update
    ```
4. Create a Namespace for Zabbix
    ```sh
    kubectl create namespace eida-monitoring
    ```
5. Create databse postgresql
    ```sql
    CREATE USER oculus WITH PASSWORD '{password}';
    CREATE DATABASE oculus_zabbix OWNER oculus;
    ```
     
6. Install the Zabbix Helm Chart
    ```sh
    export ZABBIX_CHART_VERSION='7.0.3'
    helm upgrade --install oculus-zabbix zabbix-community/zabbix \
    --dependency-update \
    --create-namespace \
    --version $ZABBIX_CHART_VERSION \
    -f values.yaml -n eida-monitoring --debug
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

## Deploy an agent

Create a configuration file for each agent in `oculus-zbx-agent-deployments` (for instant `epos-france.yaml`).

Set the content according to this template:

``` yaml
---
eidaNode:
  name: MyNodeName    # Will be used as identifier for the agent
  endpoint: ws.resif.fr  # The endpoint to test
  serviceParameters:   # Set default test parameters for each services
    net: FR
    sta: CIEL
    loc: 00
    cha: HHZ
    start: 2025-02-01T00:00:00
    end: 2025-02-01T00:00:05
```

Then deploy (or update) the agent using helm:

     helm upgrade -i epos-france occulus-zbx-agent -f oculus-zbx-agent-deployments/epos-france.yaml 
