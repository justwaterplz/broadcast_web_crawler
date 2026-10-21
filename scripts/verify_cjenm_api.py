"""Verify the two user-observed CJ ENM requests without browser cookies."""
import json
import argparse
import urllib.request
import urllib.error
import urllib.robotparser
from pathlib import Path
from datetime import datetime, timezone, timedelta

BASE = 'https://web2-cf-api.cjenm.com'
UA = 'BroadcastMetadataVerifier/1.0'
KST = timezone(timedelta(hours=9))
out = Path('reports/cjenm-api-verification') / datetime.now(KST).strftime('%Y%m%d_%H%M%S')
out.mkdir(parents=True, exist_ok=True)
results = []
arguments = argparse.ArgumentParser()
arguments.add_argument('--technical-check', action='store_true', help='Run the explicitly requested limited API check even when robots disallows crawling.')
args = arguments.parse_args()

def request(label, path, headers=None):
    url = BASE + path
    used = {'User-Agent': UA, 'Accept': 'application/json', **(headers or {})}
    row = {'label': label, 'url': url, 'method': 'GET', 'request_headers': used, 'cookies_sent': False}
    body = b''
    try:
        try:
            response = urllib.request.urlopen(urllib.request.Request(url, headers=used), timeout=20)
        except urllib.error.HTTPError as exc:
            response = exc
        with response:
            row.update(http_status=response.code, final_url=response.url, content_type=response.headers.get('Content-Type'))
            body = response.read(2_000_000)
        text = body.decode('utf-8', errors='replace')
        try:
            data = json.loads(text)
            (out / (label + '.json')).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
            row.update(result_code=data.get('resultCd'), result_message=data.get('resultMsg'))
            row['data_keys'] = list((data.get('result') or {}).get('data', {}))
        except (ValueError, AttributeError):
            (out / (label + '.txt')).write_text(text, encoding='utf-8')
    except Exception as exc:
        row['error'] = str(exc)
    results.append(row)
    return row, body

robot_row, robot_body = request('robots', '/robots.txt')
policy_ok = False
if robot_row.get('http_status') == 200:
    parser = urllib.robotparser.RobotFileParser()
    parser.parse(robot_body.decode('utf-8', errors='replace').splitlines())
    policy_ok = parser.can_fetch(UA, BASE + '/apis/v1/conts/detail') and parser.can_fetch(UA, BASE + '/apis/v1/conts/detail/prsn')
elif robot_row.get('http_status') in (404, 410):
    policy_ok = True

if policy_ok or args.technical_check:
    endpoints = {
        'program': '/apis/v1/conts/detail?pgmSeq=220264&svcCd=SV001&siteCd=ST000001&ctgCd=MC010003',
        'characters': '/apis/v1/conts/detail/prsn?pgmSeq=220264',
    }
    for label, path in endpoints.items():
        row, _ = request(label + '_minimal', path)
        if row.get('http_status') != 200 or row.get('result_code') != '0000':
            request(label + '_observed_headers', path, {'Authorization': 'SV001', 'Origin': 'https://www.cjenm.com', 'Referer': 'https://www.cjenm.com/'})

report = {'checked_at': datetime.now(KST).isoformat(), 'api_robots_permits_test_paths': policy_ok, 'limited_technical_check_requested': args.technical_check, 'requests': results}
(out / 'verification-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'output_directory': str(out), **report}, ensure_ascii=True, indent=2))
