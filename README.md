# Raspberry Pi Gate Opener

This project comes as a pre-built docker image that enables you to uitilze a relay and raspberry pi to open a gate or garage door via API call. You will need to create a table in [AirTable](https://airtable.com/) with 4 fields:
- user (single line of text)
- auth (single line of text)
- enabled (checkbox)
- admin (checkbox)

You will also need to generate a token from the [Airtable Dev Portal](https://airtable.com/create/tokens). Grant read and write scopes to the base.

## Hardware

This is the hardware I am using. You can certainly do this with less. A pi0, jumper wires, and any relay will work.

- [Raspberry Pi 3B+](https://www.raspberrypi.com/products/raspberry-pi-3-model-b-plus/)
- [RPi GPIO Terminal Block Breakout Board HAT](https://www.amazon.com/gp/product/B0876V959B)
- [HiLetgo 5V One Channel Relay Module](https://www.amazon.com/gp/product/B00LW15A4W)
- [16 Gauge Wire Combo 6 Pack](https://www.amazon.com/gp/product/B07MBWKX53)

## Wiring
![Raspberry Pi 3 Wiring](diagrams/pi-wiring.png)

## Installation

1. Install Docker (I prefer the apt method):
- [Docker Install documentation](https://docs.docker.com/engine/install/raspberry-pi-os/)

2. Install Docker Compose:
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

3. Add the current user to the docker group to avoid using sudo. You must lougout and back in after doing this, otherwise you will need to sudo the rest of the commands!:
```bash
sudo usermod -aG docker ${USER}
```

4. Clone the Github repo (docker hub does not support automated arm builds at this time. See [issue 109](https://github.com/docker/roadmap/issues/109)):
```bash
git clone https://github.com/ChrisTracy/gate-opener
```

5. Change directories into gate-opener:
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
      FRIENDLY_NAME: "My garage door" #Name of the device you're controlling
      AT_API_KEY: "<AirTable_Token>" #Airtable token (generate in the airtable dev portal and grant it access to the table)
      JWT_SECRET_KEY: "<JWT_Secret_Key>" #This can be anything but it must be long, random and kept secret
      JWT_EXPIRATION_DAYS: "365" #Number of days before a clients JWT token will expire
      BASE_ID: "<AirTable_Base_ID>" #Airtable Base ID (found in the URL)
      TABLE_NAME: "users" #Airtable table name
      GPIO_PIN: "16" #GPIO PIN
      TOKEN_INTERVAL: "5400" #how long in seconds before pulling in new tokens. (Free version has a limit of 1000 calls a month)

    ports:
      - "5151:5151"
```

9. Bring up your stack by running:

```bash
docker-compose up -d
```

## Updating
Until the previously mentioned [issue with Docker hub](https://github.com/docker/roadmap/issues/109) is resolved, you will need to update the server from github directly.

```bash
cd gate-opener
```

```bash
git pull
```

```bash
docker build -t gate-opener .
```

```bash
docker-compose up -d
```

## API

These are the api endpoints for the server:

| Method   | URL                                      | Description                                             | Auth | Params |
| -------- | ---------------------------------------- | --------------------------------------------------------| ---- | ------ |
| `GET`    | `/api/v1/hello`                          | Sends an authorized request to the server to test access.|:heavy_check_mark:|       |
| `POST`   | `/api/v1/register`                       | Registers a new device/key to the Airtable. Admin approval is required in Airtable after this is completed. |      | device      |
| `POST`   | `/api/v1/trigger`                        | Triggers the relay.                                     |:heavy_check_mark:|        |
| `POST`   | `/api/v1/refreshtokens`                  | Refreshes the tokens from Airtable.                     |:heavy_check_mark:|        |
