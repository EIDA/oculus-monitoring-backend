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
  - [Create users and user groups using Ansible](#create-users-and-user-groups-using-ansible)
- [Deploying Oculus Grafana](#deploying-oculus-grafana)
  - [Prerequisites](#prerequisites-1)
  - [Installation steps Grafana](#installation-steps-grafana)
  - [Accessing the Grafana Application (for development)](#accessing-the-grafana-application-for-development)
  - [Add Zabbix datasources](#add-zabbix-datasources)
    - [Create Zabbix API tokens](#create-zabbix-api-tokens)
  - [Deploy Grafana configuration with Ansible](#deploy-grafana-configuration-with-ansible)

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

## Deploy Zabbix configuration with Ansible
For deploying playbook with Ansible, you need to install [Ansible](https://docs.ansible.com/ansible/latest/installation_guide/intro_installation.html)

### Create Ansible user
Go to "Users > Users"
- Click "Create user"
  - Username: ansible
  - Groups: "No access to the frontend" and "Zabbix administrator"
  - Password: {ansible_password}
  - Click to "Permissions"
    - Role: "Super admin role"
- Click "Add"

### 1. Go to .yaml location
```sh
cd ansible/playbooks
```
### 2. Run playbook Ansible
```sh
ansible-playbook zbx_deployment.yaml
```

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
### Create Zabbix API tokens
Go to "Users > API token"
- Click "Create API token"
  - Name: grafana
  - User: grafana
  - Set expiration date and time: uncheck
  - Enabled: check
- Click "Add"
- Copy the {auth_token}

## Deploy Grafana configuration with Ansible
For deploying playbook with Ansible, you need to install [Ansible](https://docs.ansible.com/ansible/latest/installation_guide/intro_installation.html)

### Create Ansible user
Go to "Administration > User and access > Users"
- Click "New user"
  - name: ansible
  - username: ansible
  - password: {ansible_password}
- Click "Create user"
- In section "Permissions" click to "Change" and "Yes" and reclick to "Change"
- In section "Organization" click to "Change role", select "Admin" and click to "Save"
#### 1. Go to .yaml location
```sh
cd ansible/playbooks
```

#### 2. Run playbook Ansible
```sh
ansible-playbook grafana_deployment.yaml
```