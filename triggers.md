#  Zabbix triggers description

Zabbix have 6 levels of severity :
- Not classified
- Information
- Warning
- Average
- High
- Disaster

# Zabbix  triggers definition
## Webservices
### Availability

`Average` : response http code **204** (no content), require http code **200** (OK) | 

`Average` : response http code **403** (forbidden)

`Average` : response http code **404** (not found)

`High` : service is **down** or **not responding** since **15 min**

`High` : content **not found** "content-type: application/mxl" on **https://{#EIDA_WS_ENDPOINT}/fdsnws/availability/1/application.wadl**

`Disaster` : service is **down** or **not responding** since **1 hour**

### Dataselect

`Average` : response http code **204** (no content), require http code **200** (OK)

`Average` : response http code **403** (forbidden)

`Average` : response http code **404** (not found)

`High` : service is **down** or **not responding** since **15 min**

`Disaster` : service is **down** or **not responding** since **1 hour**

### Present in central eida routing

`Warning` : not present in query

`Average` : response http code **204** (no content), require http code **200** (OK)

`Average` : response http code **403** (forbidden)

`Average` : response http code **404** (not found)

### Routing information published at node

`Average` : route network **{#EIDA_NETWORK}** **not found** on **https://{#EIDA_WS_ENDPOINT}/fdsnws/routing/1/query?service=dataselect&network={#EIDA_NETWORK}**

### station

`Average` : response http code **204** (no content), require http code **200** (OK)

`Average` : response http code **403** (forbidden)

`Average` : response http code **404** (not found)

`High` : service is **down** or **not responding** since **15 min**

`Disaster` : service is **down** or **not responding** since **1 hour**

### wfcatalog

`Average` : response http code **204** (no content), require http code **200** (OK)

`Average` : response http code **403** (forbidden)

`Average` : response http code **404** (not found)

`High` : service is **down** or **not responding** since **15 min**

`Disaster` : service is **down** or **not responding** since **1 hour**

## Certificats

`Information` : Fingerprint has **changed**

`Warning` : SSL certificate expires in **1 day**

`Average` : SSL certificate expires in **2 week**

`High` : SSL certificate is **invalid**

`Disaster` : SSL certificate has **expired**


## Other TODO
