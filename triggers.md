#  Zabbix triggers description
#### Zabbix have 6 levels of severity :
- Not classified
- Information
- Warning
- Average
- High
- Disaster

# Zabbix  triggers definition
## Webservices
### Availability, Dataselect, Station, WFCatalog
### | Step 1 : get documentation

`Average` : response http code **204** *(no content)*, require http code **200** (OK)* 

`Average` : response http code **403** *(forbidden)*

`Average` : response http code **404** *(not found)*

`High` : service is **down** or **not responding** since **15 min**

`Disaster` : service is **down** or **not responding** since **1 hour**

### | Step 2 : simple request

`Average` : response http code **204** *(no content)*, require http code **200** (OK)*

`Average` : response http code **403** *(forbidden)*

`Average` : response http code **404** *(not found)*

### | Step 3 : application.wadl

`High` : content **not found** "content-type: application/mxl" on **https://{#EIDA_WS_ENDPOINT}/fdsnws/availability/1/application.wadl**

### Present in central eida routing
#### | Step 1 : EIDA routing information 

`Warning` : not present in query

`Average` : response http code **204** *(no content)*, require http code **200** *(OK)*

`Average` : response http code **403** *(forbidden)*

`Average` : response http code **404** *(not found)*

### Routing information published at node
#### | Step 1 : EIDA routing XML file
`Average` : route network **{#EIDA_NETWORK}** *(not found)* on **https://{#EIDA_WS_ENDPOINT}/fdsnws/routing/1/query?service=dataselect&network={#EIDA_NETWORK}**

## Certificats

`Information` : Fingerprint has **changed**

`Warning` : SSL certificate expires in **1 day**

`Average` : SSL certificate expires in **2 week**

`High` : SSL certificate is **invalid**

`Disaster` : SSL certificate has **expired**


## Other TODO