#  Zabbix triggers description
## Webservices
### Availability

`Not classified` :

`Warning` : 

`Average` : response http code 204, no content, require http code 200

`Average` : response http code 403, forbidden

`Average` : response http code 404, not found

`High` : service is down or not responding since 15min

`High` : content not found "content-type: application/mxl" on https://{#EIDA_WS_ENDPOINT}/fdsnws/availability/1/application.wadl

`Disaster` : service is down or not responding since 1 hours

### Dataselect

`Not classified` :

`Warning` : 

`Average` : response http code 204, no content, require http code 200

`Average` : response http code 403, forbidden

`Average` : response http code 404, not found

`High` : service is down or not responding since 15min

`Disaster` : service is down or not responding since 1 hours

### Present in central eida routing

`Not classified` :

`Warning` : not present in query

`Average` : response http code 204, no content, require http code 200

`Average` : response http code 403, forbidden

`Average` : response http code 404, not found

`High` : 

`Disaster` : 

### Routing information published at node

`Not classified` :

`Information` :

`Warning` :

`Average` : route network {#EIDA_NETWORK} not found on https://{#EIDA_WS_ENDPOINT}/fdsnws/routing/1/query?service=dataselect&network={#EIDA_NETWORK}

`High` :

`Disaster` :

### station

`Not classified` :

`Warning` : 

`Average` : response http code 204, no content, require http code 200

`Average` : response http code 403, forbidden

`Average` : response http code 404, not found

`High` : service is down or not responding since 15min

`Disaster` : service is down or not responding since 1 hours

### wfcatalog

`Not classified` :

`Warning` : 

`Average` : response http code 204, no content, require http code 200

`Average` : response http code 403, forbidden

`Average` : response http code 404, not found

`High` : service is down or not responding since 15min

`Disaster` : service is down or not responding since 1 hours

## Certificats

`Information` : Fingerprint has changed

`Warning` : SSL certificate expires in 1 day

`Average` : SSL certificate expires in 2 week

`High` : SSL certificate is invalid

`Disaster` : SSL certificate has expired


## Other TODO
