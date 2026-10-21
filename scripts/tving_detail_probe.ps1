param(
    [ValidatePattern('^https://www\.tving\.com/contents/[PE][0-9]+$')]
    [string]$Url = 'https://www.tving.com/contents/P001790587',
    [string]$OutputDirectory = 'data/probes/tving-P001790587',
    [string]$HtmlFile
)

# Probe exactly one public detail page, or parse a previously captured response.
$ErrorActionPreference = 'Stop'
$outputPath = [System.IO.Path]::GetFullPath($OutputDirectory)
New-Item -ItemType Directory -Path $outputPath -Force | Out-Null
$utf8 = [System.Text.UTF8Encoding]::new($false)
$access = [ordered]@{ source_url = $Url; mode = 'offline'; http_status = $null }
if ($HtmlFile) {
    $html = Get-Content -LiteralPath $HtmlFile -Raw -Encoding utf8
} else {
    $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 30
    $html = $response.Content
    $access.mode = 'http'
    $access.http_status = [int]$response.StatusCode
    $access['collected_at'] = [DateTimeOffset]::UtcNow.ToString('o')
    $access['content_type'] = [string]$response.Headers['Content-Type']
    $access['final_url'] = [string]$response.BaseResponse.RequestMessage.RequestUri
    [System.IO.File]::WriteAllText((Join-Path $outputPath 'page.html'), $html, $utf8)
    [System.IO.File]::WriteAllText((Join-Path $outputPath 'access.json'), ($access | ConvertTo-Json), $utf8)
}

$nextMatch = [regex]::Match($html, '<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', 'Singleline')
if (-not $nextMatch.Success) { throw 'Missing __NEXT_DATA__; page format may have changed.' }
$nextData = $nextMatch.Groups[1].Value | ConvertFrom-Json -Depth 100
$info = $nextData.props.pageProps.contentInfo
if (-not $info -or -not $info.program_code) { throw 'Missing program metadata in contentInfo.' }

$jsonLd = @([regex]::Matches($html, '<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', 'Singleline') | ForEach-Object {
    $_.Groups[1].Value | ConvertFrom-Json -Depth 100
})
$result = [ordered]@{
    source_url = $Url
    extraction_channels = @('__NEXT_DATA__.props.pageProps.contentInfo', 'application/ld+json')
    content_info = $info
    json_ld = $jsonLd
    pre_release_clips = @($nextData.props.pageProps.preReleaseClipInfo)
    content_clips = $nextData.props.pageProps.contentClipInfo
    missing_or_empty_content_info_fields = @($info.PSObject.Properties | Where-Object {
        $null -eq $_.Value -or ($_.Value -is [string] -and $_.Value.Length -eq 0)
    } | ForEach-Object { $_.Name })
    notes = @(
        'contentInfo describes the program and the selected episode; duration belongs to that episode.',
        'Keep raw date, grade, season, and broadcast state codes; do not infer undocumented meanings.',
        'productionCompany is the site supplied label, not verified external production credits.',
        'A successful HTTP response does not verify browser rendering, playback, or other pages.',
        'Only the selected episode is captured; complete episode lists require separate verification.'
    )
}
[System.IO.File]::WriteAllText((Join-Path $outputPath 'metadata.json'), ($result | ConvertTo-Json -Depth 100), $utf8)
Write-Output ([pscustomobject]@{
    source_url = $Url
    mode = $access.mode
    http_status = $access.http_status
    program = $info.title
    episode = $info.episode_title
    content_info_field_count = @($info.PSObject.Properties).Count
    metadata_file = Join-Path $outputPath 'metadata.json'
} | ConvertTo-Json -Depth 5)
