// V2 (item script)
var url = 'https://{$ENDPOINT}/fdsnws/availability/1/';

try {
    var request = new HttpRequest();
    request.addHeader('User-agent', 'oculus-monitor');
    var response = request.get(url);

    var status = request.getStatus();

    Zabbix.log(3, 'Status: ' + status);
    return status;

} catch (e) {
    var error = e.message;
    Zabbix.log(2, 'Error: ' + error);

    return 504;
}

// V3 (item browser) 
var browser = new Browser(Browser.firefoxOptions());
var url = 'https://{$ENDPOINT}/fdsnws/availability/1/';

try {
    Zabbix.log(3, 'Browser item: using HttpRequest fallback for ' + url);

    var request = new HttpRequest();
    request.addHeader('User-Agent', 'oculus-monitor/1.0');
    request.addHeader('Accept', 'application/json,text/plain,*/*');
    request.get(url);

    var status = request.getStatus();
    Zabbix.log(3, 'Browser item status via HttpRequest: ' + status);
    return status;
} catch (e) {
    Zabbix.log(2, 'Browser item error: ' + (e.message || e));
    return 504;
}