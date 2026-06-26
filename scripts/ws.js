var url = 'https://{$ENDPOINT}/fdsnws/availability/1/';

try {
    var request = new HttpRequest();
    var response = request.get(url);

    var status = request.getStatus();

    Zabbix.log(3, 'Status: ' + status);
    return status;

} catch (e) {
    var error = e.message;
    Zabbix.log(2, 'Error: ' + error);

    return 999;
}