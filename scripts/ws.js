// V2 item script
var url = 'https://{$ENDPOINT}/fdsnws/availability/1/';

try {
    var request = new HttpRequest();

    request.addHeader('User-Agent', 'oculus-monitor/3.0');
    request.addHeader('Accept', '*/*');
    request.addHeader('Accept-Language', 'en-US,en;q=0.9');

    request.get(url);

    var status = request.getStatus();
    Zabbix.log(3, 'HTTP status for ' + url + ': ' + status);
    return status;

} catch (e) {
    Zabbix.log(2, 'HTTP request failed: ' + (e.message || e));
    return 504;
}

// V3 item browser
var browser = new Browser(Browser.firefoxOptions());
var url = 'https://{$ENDPOINT}/fdsnws/availability/1/';

try {
    Zabbix.log(3, 'Browser item: testing with browser for ' + url);
    
    // Utilisation d'une approche différente avec des en-têtes spécifiques
    var response = browser.get(url);
    var status = response.status();
    
    Zabbix.log(3, 'Browser item status: ' + status);
    return status;
} catch (e) {
    Zabbix.log(2, 'Browser item error: ' + (e.message || e));
    // Fallback complet avec tous les en-têtes nécessaires
    try {
        Zabbix.log(3, 'Fallback to HttpRequest for ' + url);
        var request = new HttpRequest();
        request.addHeader('User-Agent', 'oculus-monitor/3.0');
        request.get(url);
        var status = request.getStatus();
        Zabbix.log(3, 'HttpRequest status: ' + status);
        return status;
    } catch (e2) {
        Zabbix.log(2, 'HttpRequest also failed: ' + (e2.message || e2));
        return 504;
    }
}