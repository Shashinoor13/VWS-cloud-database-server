# Cloud Reco CLI

Sample Vuforia Cloud Recognition target management and query implementation.

### Getting Started

Install packages listed in `requirements.txt`

### Example CLI Usage

Create a target:
```bash
python3 cloud-target-webapi-client.py --access-key ${server_access_key} --secret-key ${server_secret_key} create --image ./target.jpg --name target-example --width 1 --metadata-base64 "$(echo "example metadata" | base64)"
```
Update a target:
```bash
python3 cloud-target-webapi-client.py --access-key ${server_access_key} --secret-key ${server_secret_key} update ${target_id} --name target-updated --width 2
```

Query a target:
```bash
python3 cloud-target-webapi-client.py --access-key ${client_access_key} --secret-key ${client_secret_key} query --image ./target.jpg
```

Get a database report:
```bash
python3 cloud-target-webapi-client.py --access-key ${server_access_key} --secret-key ${server_secret_key} get-database-report
```

Get a full list of commands:
```bash
python3 cloud-target-webapi-client.py --help
```