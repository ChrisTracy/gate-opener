# Raspberry Pi Gate Opener

This project comes as a pre-built docker image that enables you to uitilze a relay and raspberry pi to open a gate or garage door via API call. You will need to create a table in AirTable with 3 fields:
- user (single line of text)
- token (single line of text)
- enabled (checkbox)

## Quick Setup

1. Install Docker (I prefer the apt method)
- [Docker Install documentation](https://docs.docker.com/engine/install/raspberry-pi-os/)

2. Install Docker Compose
```bash
sudo apt-get install libffi-dev libssl-dev
```
```bash
sudo apt install python3-dev
```
```bash
sudo apt-get install -y python3 python3-pip
```
```bash
sudo pip3 install docker-compose
```

3. Add the current user to the docker group to avoid using sudo. You must lougout and back in after doing this, otherwise you will need to sudo the rest of the commands!
```bash
sudo usermod -aG docker ${USER}
```

4. Clone the Github repo (docker hub does not support automated arm builds at this time. See [issue 109](https://github.com/docker/roadmap/issues/109)):
```bash
git clone https://github.com/ChrisTracy/gate-opener
```

5. Change directories into gate-opener
```bash
cd gate-opener
```

6. Build the docker image:
```bash
docker build -t gate-opener .
```

7. Create a docker-compose.yml file:
```bash
nano docker-compose.yml
```

8. Add this to the YAML file with your own parameters:
```yml
version: "3"

services:
  gate_opener:
    image: gate-opener
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

9. Bring up your stack by running

```bash
docker-compose up -d
```
