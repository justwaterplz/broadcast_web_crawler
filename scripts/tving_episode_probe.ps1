param(
    [ValidatePattern('^P[0-9]+$')]
    [string]$ProgramCode = 'P001790587',
    [string]$OutputDirectory = 'data/probes/tving-P001790587',
    [string]$ClientScriptFile = 'data/probes/tving-P001790587/_app-5c3e3017193cd1e0.js',
    [string]$ApiFile
)

$ErrorActionPreference = 'Stop'
$outputPath = [System.IO.Path]::GetFullPath($OutputDirectory)
New-Item -ItemType Directory -Path $outputPath -Force | Out-Null
$utf8 = [System.Text.UTF8Encoding]::new($false)
$endpoint = 'https://api.tving.com/v2/media/frequency/program/' + $ProgramCode
$collectedAt = $null
if ($ApiFile) {
    $raw = Get-Content -LiteralPath $ApiFile -Raw -Encoding utf8
    $mode = 'offline'
    $httpStatus = $null
} else {
    # Use only the public web client's application key, never account/session tokens.
    # This lookup is intentionally strict so a changed bundle fails visibly.
    $clientScript = Get-Content -LiteralPath $ClientScriptFile -Raw -Encoding utf8
    $moduleIndex = $clientScript.IndexOf('46900:function')
    if ($moduleIndex -lt 0) { throw 'Public client configuration changed; inspect the current bundle.' }
    $config = $clientScript.Substring($moduleIndex, [Math]::Min(1500, $clientScript.Length - $moduleIndex))
    $keyMatch = [regex]::Match($config, '\bb="([^"]+)"')
    if (-not $keyMatch.Success) { throw 'Public client application key not found.' }
    $query = '?order=new&cacheType=main&pageSize=20&adult=all&free=all&guest=all&scope=all' +
        '&screenCode=CSSD0100&networkCode=CSND0900&osCode=CSOD0900&teleCode=CSCD0900&apiKey=' +
        [uri]::EscapeDataString($keyMatch.Groups[1].Value)
    $response = Invoke-WebRequest -Uri ($endpoint + $query) -UseBasicParsing -TimeoutSec 30
    $raw = $response.Content
    $httpStatus = [int]$response.StatusCode
    $collectedAt = [DateTimeOffset]::UtcNow.ToString('o')
    $mode = 'http'
}
$api = $raw | ConvertFrom-Json -Depth 100
# TVING can return HTTP 200 while the JSON header reports an authorization error.
if ($api.header.status -ne 200 -or $null -eq $api.body) {
    throw ('API error: ' + $api.header.status + ' ' + $api.header.message)
}
if (-not $ApiFile) {
    [System.IO.File]::WriteAllText((Join-Path $outputPath 'episodes-api.raw.json'), $raw, $utf8)
}
$episodes = @($api.body.result | ForEach-Object {
    [ordered]@{
        program_code = $ProgramCode
        program_name = $_.program.name.ko
        episode_code = $_.episode.code
        episode_number = $_.episode.frequency
        title = $_.vod_name.ko
        synopsis = $_.episode.synopsis.ko
        broadcast_date_raw = $_.episode.broadcast_date
        duration_seconds = $_.episode.duration
        grade_code = $_.episode.grade_code
        free_yn = $_.episode.free_yn
        images = $_.episode.image
    }
})
$complete = $api.body.has_more -eq 'N' -and $episodes.Count -eq $api.body.total_count
$result = [ordered]@{
    source_endpoint = $endpoint
    mode = $mode
    collected_at = $collectedAt
    http_status = $httpStatus
    api_status = $api.header.status
    total_count = $api.body.total_count
    has_more = $api.body.has_more
    collected_count = $episodes.Count
    complete_for_current_api_listing = $complete
    episodes = $episodes
    notes = @(
        'synopsis is the site supplied episode description, not a screenplay.',
        'Completeness is checked against the current API listing, not planned future episodes.',
        'This probe makes one list request; pagination and multiple seasons need separate handling.'
    )
}
[System.IO.File]::WriteAllText((Join-Path $outputPath 'episodes.json'), ($result | ConvertTo-Json -Depth 100), $utf8)
if (-not $complete) { Write-Warning 'Partial list: do not treat this response as all episodes.' }
Write-Output ([ordered]@{
    api_status = $api.header.status
    collected_count = $episodes.Count
    total_count = $api.body.total_count
    has_more = $api.body.has_more
    complete = $complete
    episodes_file = Join-Path $outputPath 'episodes.json'
} | ConvertTo-Json)
