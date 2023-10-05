# Raspberry Pi Gate Opener

This project comes as a pre-built docker image that enables you to uitilze a relay and raspberry pi to open a gate or garage door via API call.

## Quick Setup

1. Install Docker and Docker-Compose

- [Docker Install documentation](https://docs.docker.com/install/)
- [Docker-Compose Install documentation](https://docs.docker.com/compose/install/)

2. Create a docker-compose.yml file similar to this:

```yml
version: "3"

services:
  gate_opener:
    image: gateopener
    restart: unless-stopped
    privileged: true
    environment:
      AT_API_KEY: "<AirTable_Token>" #Airtable token (generate in the airtable dev portal and grant it access to the table)
      BASE_ID: "<AirTable_Base_ID>" #Airtable Base ID (found in the URL)
      TABLE_NAME: "users" #Airtable name
      GPIO_PIN: "16" #GPIO PIN
      TOKEN_INTERVAL: "5400" #how long in seconds before pulling in new tokens. (Free version has a limit of 1000 calls a month)

    ports:
      - "5151:5151"
```

3. Bring up your stack by running

```bash
docker-compose up -d
```
