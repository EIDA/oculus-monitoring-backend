import json
from pathlib import Path
from zabbix_utils import Sender, ItemValue

def main():
    # zbx srv config
    ZABBIX_SERVER = "127.0.0.1"
    ZABBIX_PORT = 10051

    results_dir = Path("performance_results")

    if not results_dir.exists():
        print("performance_results directory not found")
        return
    
    # connnect sender to zbx srv
    sender = Sender(server=ZABBIX_SERVER, port=ZABBIX_PORT)

    # process json
    for json_file in results_dir.glob("*.json"):
        hostname = json_file.stem.upper()

        try:
            with open(json_file, 'r') as f:
                data = json.load(f)
            
            print(f"\nprocessing host: {hostname}")

            items = []

            for key, metrics in data.items():
                # key format: "dataselect.9streams"

                items.extend([
                    ItemValue(hostname, f"{key}.status_code", str(metrics['status_code'])),
                    ItemValue(hostname, f"{key}.response_time_ms", metrics['response_time_ms']),
                    ItemValue(hostname, f"{key}.content_size_bytes", metrics['content_size_bytes'])
                ])

                print(f"    {key}.status_code = {metrics['status_code']}")
                print(f"    {key}.response_time_ms = {metrics['response_time_ms']}")
                print(f"    {key}.content_size_bytes = {metrics['content_size_bytes']}")

            # send via zbx srv
            print(f"\nsending {len(items)} items to zabbix")
            response = sender.send(items)
            print(f"{hostname}: {response.processed}/{response.total} items sent success")

            if response.failed > 0:
                print(f"    failed: {response.failed} items")
            else:
                print(f"    all items sent sucess")
        
        except Exception as e:
            print(f"    errror processing {json_file}: {e}")
    
    print("\ndata sending completed")

if __name__ == "__main__":
    main()