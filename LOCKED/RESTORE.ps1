# Restore core engine from LOCKED snapshot
$src = 'D:\ai manager\LOCKED'
$dst = 'D:\ai manager'
Get-ChildItem $src -Recurse -File | Where-Object {
  $_.Name -notin @('MANIFEST.json','RESTORE.ps1','verify.py')
} | ForEach-Object {
  $rel = $_.FullName.Substring($src.Length + 1)
  $t = Join-Path $dst $rel
  $d = Split-Path $t -Parent
  if(-not (Test-Path $d)){ New-Item -ItemType Directory -Force -Path $d | Out-Null }
  Copy-Item $_.FullName $t -Force
  Write-Output "restored: $rel"
}
Write-Output 'DONE - core engine restored from LOCKED snapshot'
