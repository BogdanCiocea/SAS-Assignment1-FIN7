sudo pkill -f fin7_topology.py
sudo mn -c
docker rm -f mn.attacker mn.proxy mn.victim 2>/dev/null
sudo python3 fin7_topology.py
