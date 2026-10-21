param([string]$Stage = 'initial')
$ErrorActionPreference = 'Stop'
$probeOut = Join-Path $PSScriptRoot '..\reports\platform-feasibility-20261014'
New-Item -ItemType Directory -Path $probeOut -Force | Out-Null
$urls = [ordered]@{
  'tving-list' = 'https://www.tving.com/more/genre/PCA'
  'tvn-filter-page1' = 'https://tvn.cjenm.com/ko/program/?14382=removeCacheYn%3DN%26repGenreCdList%3DALL%26sortType%3DMC010207%26pageNum%3D1%26searchTlviseStatCd%3DALL%26searchChnCd%3DMC010271'
  'tvn-all-page1' = 'https://tvn.cjenm.com/ko/program/?14382=removeCacheYn%3DN%26repGenreCdList%3DALL%26sortType%3DMC010207%26pageNum%3D1%26searchTlviseStatCd%3DALL%26searchChnCd%3DALL'
  'tvn-all-page2' = 'https://tvn.cjenm.com/ko/program/?14382=removeCacheYn%3DN%26repGenreCdList%3DALL%26sortType%3DMC010207%26pageNum%3D2%26searchTlviseStatCd%3DALL%26searchChnCd%3DALL'
  'tvn-all-page21' = 'https://tvn.cjenm.com/ko/program/?14382=removeCacheYn%3DN%26repGenreCdList%3DALL%26sortType%3DMC010207%26pageNum%3D21%26searchTlviseStatCd%3DALL%26searchChnCd%3DALL'
}
$results = @()
foreach ($item in $urls.GetEnumerator()) {
  try {
    $reply = Invoke-WebRequest -Uri $item.Value -UseBasicParsing -TimeoutSec 30 -Headers @{'User-Agent'='broadcast-metadata-probe/0.1'}
    [IO.File]::WriteAllText((Join-Path $probeOut ($item.Key + '.html')), $reply.Content)
    $results += [pscustomobject]@{name=$item.Key;url=$item.Value;status=[int]$reply.StatusCode;length=$reply.Content.Length;file=($item.Key+'.html')}
  } catch { $results += [pscustomobject]@{name=$item.Key;url=$item.Value;error=$_.Exception.Message} }
  Start-Sleep -Milliseconds 1000
}
$results | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $probeOut 'http-results.json') -Encoding UTF8
$results | ConvertTo-Json -Depth 8
Get-Command python, python3 -ErrorAction SilentlyContinue | Select-Object Name, Source | ConvertTo-Json
