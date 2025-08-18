# Oculus Monitoring
For the EIDA Technical Committee and EIDA Management Board that need to improve there services quality, Oculus is a central monitoring and alerting system that tests all the services at EIDA nodes. Unlike the previous situation where the monitoring was very scattered and uneven, OCULUS will provide a global view of the services status and indicators for keeping track of service quality evolution.

## Table of contents
- [Oculus Monitoring](#oculus-monitoring)
  - [Table of contents](#table-of-contents)
- [How to monitor a new thing](#how-to-monitor-a-new-thing)
- [Deploying Oculus Zabbix and Grafana on Kubernetes using Helm](#deploying-oculus-zabbix-and-grafana-on-kubernetes-using-helm)
  - [Prerequisites](#prerequisites)
  - [Installation steps Zabbix](#installation-steps-zabbix)
    - [1. Clone this repository](#1-clone-this-repository)
    - [2. Go to .yaml location](#2-go-to-yaml-location)
    - [3. Add the Helm repository](#3-add-the-helm-repository)
    - [4. Create a Namespace for Zabbix](#4-create-a-namespace-for-zabbix)
    - [5. Create DataBase postgresql](#5-create-database-postgresql)
    - [6. Connection to the DataBase](#6-connection-to-the-database)
    - [7. decrypt password](#7-decrypt-password)
    - [8. Install Zabbix](#8-install-zabbix)
  - [Accessing the Zabbix Application (for development)](#accessing-the-zabbix-application-for-development)
- [Zabbix configuration](#zabbix-configuration)
  - [Deploy Zabbix configuration with Ansible](#deploy-zabbix-configuration-with-ansible)
    - [Zabbix Ansible deployment descriptions](#zabbix-ansible-deployment-descriptions)
    - [Create Ansible user](#create-ansible-user)
      - [1. Go to .yaml location](#1-go-to-yaml-location)
      - [2. Run playbook Ansible](#2-run-playbook-ansible)
- [Deploying Oculus Grafana](#deploying-oculus-grafana)
  - [Prerequisites](#prerequisites-1)
  - [Installation steps Grafana](#installation-steps-grafana)
    - [1. Clone this repository](#1-clone-this-repository-1)
    - [2. Go to .yaml location](#2-go-to-yaml-location-1)
    - [3. Add the Helm repository](#3-add-the-helm-repository-1)
    - [4. Decrypt password](#4-decrypt-password)
    - [5. Install Grafana](#5-install-grafana)
  - [Accessing the Grafana Application (for development)](#accessing-the-grafana-application-for-development)
  - [Add Zabbix datasources](#add-zabbix-datasources)
    - [Accessing the Zabbix Application](#accessing-the-zabbix-application)
    - [Create Zabbix API tokens](#create-zabbix-api-tokens)
  - [Deploy Grafana configuration with Ansible](#deploy-grafana-configuration-with-ansible)
    - [Grafana Ansible deployment descriptions](#grafana-ansible-deployment-descriptions)
    - [Create Ansible user and service accounts](#create-ansible-user-and-service-accounts)
    - [Configure Ansible Grafana auth](#configure-ansible-grafana-auth)
      - [1. Go to config auth location](#1-go-to-config-auth-location)
      - [2. Decrypt file](#2-decrypt-file)
    - [Launch Ansible](#launch-ansible)
      - [1. Go to .yaml location](#1-go-to-yaml-location-1)
      - [2. Run playbook Ansible](#2-run-playbook-ansible-1)

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
  sops -d -i values.yaml
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

# Zabbix configuration

## Deploy Zabbix configuration with Ansible
For deploying playbook with Ansible, you need to install [Ansible](https://docs.ansible.com/ansible/latest/installation_guide/intro_installation.html)

### Zabbix Ansible deployment descriptions
The Zabbix Ansible script will deploy this playbooks:
- Import templates
- Config autoregistration
- Deploying agents
- Activate media type
- Create EIDA users
- Configuration triggers actions

### Create Ansible user
Go to "Users > Users"
- Click "Create user"
  - Username: ansible
  - Groups: "No access to the frontend" and "Zabbix administrator"
  - Password: {ansible_password}
  - Click to "Permissions"
    - Role: "Super admin role"
- Click "Add"

#### 1. Go to .yaml location
```sh
cd ansible/playbooks
```
#### 2. Run playbook Ansible
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
- Port forward Grafana
  ```sh
  kubectl port-forward service/oculus-grafana 3000:3000 -n eida-monitoring
  ```
- [localhost:3000](http://localhost:3000)
- Default credentials:
  - Username: admin
  - Password: {admin_passwd}

## Add Zabbix datasources
### Accessing the Zabbix Application
Port forwrd Zabbix
  ```sh
  kubectl port-forward service/oculus-zabbix-zabbix-web 8888:8888 -n eida-monitoring
  ```

### Create Zabbix API tokens
In Zabbix application, go to "Users > API token"
- Click "Create API token"
  - Name: grafana
  - User: grafana
  - Set expiration date and time: uncheck
  - Enabled: check
- Click "Add"
- Copy the {auth_token}

## Deploy Grafana configuration with Ansible
For deploying playbook with Ansible, you need to install [Ansible](https://docs.ansible.com/ansible/latest/installation_guide/intro_installation.html)

### Grafana Ansible deployment descriptions
The Grafana Ansible script will deploy this playbooks:
- Add datasources
- Import dashboards

### Create Ansible user and service accounts
In Grafana application, go to "Administration > User and access > Users"
- Click "New user"
  - Name: ansible
  - Username: ansible
  - Password: {ansible_password}
- Click "Create user"
- In section "Permissions" click to "Change" and "Yes" and reclick to "Change"
- In section "Organization" click to "Change role", select "Admin" and click to "Save"
Go to "Administration > User and access > Service accounts"
- Click "Add service account"
  - Name: ansible
  - Role: Admin
    - Click "Add service account token"
    - Click "No expiration"
    - Click "Generate token"
      - Copy to clipboard and paste in file "config_prod" or "config_staging" in path ``` ansible/config/```
      - Click "Close"
    - Click in red cross on section "User"
    - Click "Add permission"
      - Select "User"
      - Select "ansible"
      - Select "Admin"
      - Click "Save"

### Configure Ansible Grafana auth
#### 1. Go to config auth location
  ```sh
  cd ansible/config
  ```

#### 2. Decrypt file
  ```sh
  sops -d -i config_prod.yaml
  OR
  sops -d -i config_staging.yaml
  ```

### Launch Ansible
#### 1. Go to .yaml location
```sh
cd ansible/playbooks
```

#### 2. Run playbook Ansible
```sh
ansible-playbook grafana_deployment.yaml
```