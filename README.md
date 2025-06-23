# Oculus Monitoring
For the EIDA Technical Committee and EIDA Management Board that need to improve there services quality, Oculus is a central monitoring and alerting system that tests all the services at EIDA nodes. Unlike the previous situation where the monitoring was very scattered and uneven, OCULUS will provide a global view of the services status and indicators for keeping track of service quality evolution.

## Table of contents
- [How to monitor a new thing](#how-to-monitor-a-new-thing)
- [Deploying Oculus Zabbix and Grafana on Kubernetes using Helm](#--deploying-oculus-zabbix-and-grafana-on-kubernetes-using-helm)
  - [Prerequisites](#prerequisites)
  - [Installation steps Zabbix](#installation-steps-zabbix)
  - [Accessing the Zabbix Application (for development)](#accessing-the-zabbix-application-for-development)
  - [Agent deployments](#agent-deployments)
    - [Deploy one agent](#deploy-one-agent)
    - [Deploy all agents](#deploy-all-agents)
- [Zabbix configuration](#zabbix-configuration)
  - [Import templates](#import-templates)
  - [Autoregistration](#autoregistration)
  - [Configure trigger actions](#configure-trigger-actions)
    - [Create users and user groups using Ansible](#create-users-and-user-groups-using-ansible)
    - [Trigger actions](#trigger-actions)
- [Deploying Oculus Grafana](#deploying-oculus-grafana)
  - [Prerequisites](#prerequisites-1)
  - [Installation steps Grafana](#installation-steps-grafana)
  - [Accessing the Grafana Application (for development)](#accessing-the-grafana-application-for-development)
  - [Add Zabbix datasources](#add-zabbix-datasources)
    - [Create Grafana User groups in Zabbix](#create-grafana-user-groups-in-zabbix)
    - [Create Grafana User in Zabbix](#create-grafana-user-in-zabbix)
    - [Create Zabbix API tokens](#create-zabbix-api-tokens)
    - [Configuration Zabbix datasource](#configuration-zabbix-datasource)

# How to monitor a new thing
So you woud like to monitor something related to EIDA federation ?

Please create a new issue using the template "New Monitoring".

In order to edit Nodes values is in this [procedures](contribute_to_change_values.md)

#  Deploying Oculus Zabbix and Grafana on Kubernetes using Helm
## Prerequisites
- Kubernetes cluster (version 1.20 or later) configured and running
- ```kubectl``` installed and configured
- ```git``` installed and configured
- Helm CLI (version 3 or later) installed https://helm.sh/docs/intro/install
- Plugin Helm secret https://github.com/jkroepke/helm-secrets
- Sops core https://github.com/getsops/sops
- Sufficient resources in the cluster to run Zabbix components

## Installation steps Zabbix
### 1. Clone this repository
  ```sh
  git clone https://github.com/EIDA/oculus-monitoring-backend
  ```

### 2. Go to .yaml location
  ```sh
  cd zabbix_server/helm_values
  ```

### 3. Add the Helm repository
  ```sh
  helm repo add zabbix-community https://zabbix-community.github.io/helm-zabbix
  helm repo update
  ```

### 4. Create a Namespace for Zabbix
  ```sh
  kubectl create namespace eida-monitoring
  ```

### 5. Create DataBase postgresql
  ```sql
  CREATE USER oculus WITH PASSWORD '{password}';
  CREATE DATABASE oculus_zabbix OWNER oculus;
  ```

### 6. Connection to the DataBase
  We recommend to use ```pgcli```

  Usage :
  ```
  pgcli postgres://{user}@{netloc}/{dbname}
  ```
  Example:
  ```
  pgcli postgres://oculus@bdd-resif.fr/oculus_zabbix
  ```

### 7. decrypt password
  ```sh
  cd oculus-monitoring-backend/zabbix_server/helm_values
  sops decrypt values.yaml
  ```
  /!\ TODO

### 8. Install Zabbix
  Apply Helm Chart
  ```sh
  export ZABBIX_CHART_VERSION='7.0.6'
  helm secrets upgrade --install oculus-zabbix zabbix-community/zabbix \
  --dependency-update \
  --version $ZABBIX_CHART_VERSION \
  -f values.yaml -n eida-monitoring --debug
  ```

## Accessing the Zabbix Application (for development)
- Port forward
  ```sh
  kubectl port-forward service/oculus-zabbix-zabbix-web 8888:80 -n eida-monitoring
  ```
- [localhost:8888](http://localhost:8888)

- Default credentials:
  - Username: Admin
  - Password: zabbix

## Agent deployments
### Deploy one agent
Create a configuration file for each agent in `oculus-zbx-agent-deployments` (for instant `epos-france.yaml`).

Set the content according to this template:

Complet template example [here](oculus-zbx-agent/scripts/example_lld.yaml) 

``` yaml
---
node: Epos-France    # Will be used as identifier for the agent
endpoint: ws.resif.fr  # The endpoint to test
routingFile: routing/eida_routing.xml
onlineCheck: # Set default test parameters for each services
  net: FR
  sta: CIEL
  loc: "00"
  cha: HHZ
  start: 2025-02-01T00:00:00
  end: 2025-02-01T00:00:05
```

Then deploy (or update) the agent using helm:

⚠️ If you want delete host, deleted the host FIRST in the Discovery template, and only then in the Webservice template ⚠️

    helm upgrade -i epos-france oculus-zbx-agent --set-file zbx_lld=oculus-zbx-agent-deployments/epos-france.yaml -n eida-monitoring

### Deploy all agents
    for f in $(find oculus-zbx-agent-deployments -type f); do name=$(basename $f|cut -f1 -d'.'); echo $name; echo $f; helm upgrade -i $name oculus-zbx-agent --set-file zbx_lld=$f -n eida-monitoring; done

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
  - Link templates: Template discovery (Templates/EIDA)
  - Link templates: Linux by Zabbix agent (Templates/Operating Systems)
  - Ennable hosts
- Click "Add"

## Configure trigger actions
For activate mail triggers
- Go to "Alerts > Media types" and Enabled email, click on Email, and configure with your SMTP server, username, password etc.
- Enabled: checked
- Click "Update"

### Create users and user groups using Ansible
For deploying playbook with Ansible, you need to install [Ansible](https://docs.ansible.com/ansible/latest/installation_guide/intro_installation.html)

Groups must be created for each EIDA node, as well as users.

#### 1. Go to .yaml location
```sh
cd ansible/playbooks
```
#### 2. Run playbook Ansible
```sh
ansible-playbook create_user.yaml
```

### Trigger actions
- Go to "Alerts > Actions > Trigger actions"
- Click "Create action"
  - Name: Reports problems
  - Type of calculation: And/or
  - Conditions, click "Add"
    - Type : Trigger
    - Operator: equals
    - Trigger source: Template
    - Triggers: click "Select"
      - Select "Template/EIDA > Template Webservice", select all
    - Click "Add"
    - Enabled: checked
  - Click "Operations"
    - Default operations step duration: 1h
    - Operations, (create a step for each EIDA Nodes) click "Add"
      - Steps: 1 - 1
      - Step duration : 0
      - Send to user groups > Select {EIDA_nodes_name}
      - Send only to : Email
      - Click "Add"
    - Update operations (create a step for each EIDA Nodes) click "Add"
      - Operation : Send message
      - Send to user groups > Select {EIDA_nodes_name}
      - Send only to : Email
      - Click "Add"
    - Pause operations for symptom problems: checked
    - Pause operations for suppressed problems: checked
    - Notify about canceled escalations: checked
    - Click "Add"
- Check if status is "Enabled"

# Deploying Oculus Grafana
## Prerequisites
- Kubernetes cluster (version 1.20 or later) configured and running
- ```kubectl``` installed and configured
- ```git``` installed and configured
- Helm CLI (version 3 or later) installed https://helm.sh/docs/intro/install
- Plugin Helm secret https://github.com/jkroepke/helm-secrets
- Sops core https://github.com/getsops/sops
- Sufficient resources in the cluster to run Grafana components

## Installation steps Grafana
### 1. Clone this repository
  ```sh
  git clone https://github.com/EIDA/oculus-monitoring-backend
  ```

### 2. Go to .yaml location
  ```sh
  cd grafana_server/helm_values
  ```

### 3. Add the Helm repository
  ```sh
  helm repo add grafana https://grafana.github.io/helm-charts
  helm repo update
  ```

### 4. Decrypt password
  ```sh
  cd oculus-monitoring-backend/grafana_server/helm_values
  sops decrypt values.yaml
  ```

### 5. Install Grafana
  ```sh
  helm secrets upgrade --install oculus-grafana grafana/grafana \
  -f values.yaml -n eida-monitoring
  ```

## Accessing the Grafana Application (for development)
- Port forward
  ```sh
  kubectl port-forward service/oculus-grafana 3000:3000 -n eida-monitoring
  ```
- [localhost:3000](http://localhost:3000)
- Default credentials:
  - Username: /
  - Password: /

## Add Zabbix datasources
You must first create a new user and user groups for Grafana in Zabbix.

### Create Grafana User groups in Zabbix
Go to "Users > User groups"
- Click "Create user group"
  - Group name: API-RO
  - Enabled: check
- Click "Template permissions"
  - click "Add"
  - Click "Select"
    - Select: All Template groups
    - Click "Select"
  - permissions: Read
- Click "Host permissions"
  - Click "Add"
  - Click "Select"
    - Select: All Host groups
    - Click "Select"
- Click "Problem tag filter"
  - Click "Add"
  - Click "Select"
    - Select: All Host groups EXCEPT "Application", "Databases", "Hypervisors", "Linux servers", "Virtual machines" and "Zabbix servers"
    - Click: "Select"
    - Click "Add"
- Click "Update"

### Create Grafana User in Zabbix
Go to "Users > Users"
- Click "Create User"
  - Username: grafana
  - Groups: API-RO and No access to the frontend
  - Password: {passwd_user_grafana}
- Click "Permissions"
  - Role: Select "User role"
- Click "Add"

### Create Zabbix API tokens
Go to "Users > API token"
- Click "Create API token"
  - Name: grafana
  - User: grafana
  - Set expiration date and time: uncheck
  - Enabled: check
- Click "Add"
- Copy the {auth_token}

### Install Zabbix Plugin in Grafana
Normally, the Zabbix plugin is installed, but if this is not the case, install it manually:

Go to "Administration > General > Plugins and data"
- Plugins:
  - Search "Zabbix"
  - Click "Install"

### Configuration Zabbix datasource
Go to "Connections > Data sources"
- Click "+ Add new data source"
  - select Zabbix
- Rename in "oculus-zabbix-datasource"
- Connection:
  - url: ```http://oculus-zabbix-zabbix-web:8888/api_jsonrpc.php```
- Authentication
  - Select "Basic authentication"
    - user : grafana
    - password : {passwd_user_grafana}
- Zabbix Connection
  - API token : {auth_token}
- Trends : Enable
- Click "Save & test
