# Oculus Monitoring

For the EIDA Technical Committee and EIDA Management Board that need to improve there services quality, Oculus is a central monitoring and alerting system that tests all the services at EIDA nodes. Unlike the previous situation where the moniitoring was very scattered and uneven, OCULUS will provide a global view of the services status and indicators for keeping track of service quality evolution.

## How to monitor a new thing

So you woud like to monitor something related to EIDA federation ?

Please create a new issue using the template "New Monitoring".

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

## Deploy all agents

     for f in $(find oculus-zbx-agent-deployments -type f); do name=$(basename $f|cut -f1 -d'.'); echo $name; echo $f; helm upgrade -i $name oculus-zbx-agent -f $f; done


# Zabbix configuration
## Import templates
Go to "Data collection > Templates"
- Select "Import" in the top right corner and select the files "zbx_export_templates.yaml" (OR "zbx_export_templates_discovery.xml" and "zbx_export_web_templates.yaml" ) location : ```zabbix_server/templates```
- Rules: all checked 
- Click on "Import"

## Autoregistration
Go to "Alerts > Actions > Autoregistration actions" and create a new action with the following parameters:
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

