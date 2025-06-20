# Contribute to change monitoring EIDA Nodes values

To modify the parameters of the checks made by Oculus, you must:
1. create a new branch
2. modify the .yaml file of your Node (present [here](oculus-zbx-agent-deployments/)) You can modifie everything in the GitHub web interface
3. Create a new [Pull Requests](https://github.com/EIDA/oculus-monitoring-backend/pulls)

The `OnlineCheck` section is used to perform the main zabbix tests, while `perfCheck` is for performance tests, do not chenge this.


## OnlineCheck
Same parameter values is used for all the webservices.
- net: is network
- sta: is station
- loc: is location
- cha: is channel
- start: is start date
- end: is end date

## PerfCheck
Change require validation with the administator.
Each performance check as organise by services and each services as a list of scenarios with their parameters

## Contact for alerts 
Update email contact [here](ansible/oculus_users.yaml)