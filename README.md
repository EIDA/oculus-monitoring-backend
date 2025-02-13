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
    export ZABBIX_CHART_VERSION='7.0.3'
    ```
4. Create a Namespace for Zabbix
    ```sh
    kubectl create namespace eida-monitoring
    ```
5. Create databse postgresql
    ```sql
    CREATE DATABASE oculus_zabbix
    CREATE USER oculus WITH PASSWORD '{password}'
    GRANT CONNECT ON DATABASE oculus_zabbix TO oculus 
    ```
     
6. Install the Zabbix Helm Chart
    ```sh
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

## Launch nodes
```sh
cd zabbix_agent
kubectl apply -f zabbix_agent_{name}_deployment.yaml
```


# Zabbix configuration
## Import templates
Go to "Data collectiion > Templates"
- Select "Import" in the top right corner and select the files "zbx_export_templates.yaml" (OR "zbx_export_templates_discovery.xml" and "zbx_export_web_templates.yaml" ) location : ```zabbix_server/templates```
- Rules: all checked 
- Click on "Import"

## Autoregistration
Go to "Alerte > Actions > Autoregistration actions" and create a new action with the following parameters:
- Action:
  - Name: EIDA nodes autoregistration
  - Enabled: checked
- Operations:
  - Add host
  - Add to host groups: Discovered hosts
  - Link templates: Template discovery
  - Link templates: Linux by Zabbix agent
  - Ennable hosts
- Click "Add"