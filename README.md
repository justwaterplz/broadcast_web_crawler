# 방송 콘텐츠 메타데이터 수집기

TVING·tvN 공식 사이트의 방송 콘텐츠 정보를 URL로 수집하는 로컬 앱입니다.
CJ ENM은 공식 작품 URL과 사용자가 저장한 API 응답 파일을 연결해 가져옵니다.
기존 나무위키 직접 문서 URL 수집은 별도로 유지합니다.
React와 shadcn/ui로 만든 웹 UI를 Electron 창에서 실행하며, 실제 수집은 사이트별 Python 모듈이 담당합니다.
현재 작업 범위는 데이터 수집과 저장입니다. TVING 원본에 인물 역할 분류, 필드 정규화, 출처 간 병합을 적용하지 않습니다.

## 지원하는 입력

| 입력 종류 | 수집 범위 |
|---|---|
| TVING 작품 상세 URL | 해당 작품의 페이지 메타데이터와 회차 API 응답 |
| TVING 드라마·예능 목록 URL | 지정한 시작 순위와 작품 수에 해당하는 콘텐츠 |
| TVING 세부 장르 URL | 선택한 드라마·예능 카테고리 안의 세부 장르 목록 |
| tvN 프로그램 목록·상세 URL | 입력 URL의 필터에 따른 목록, 작품 소개·인물·회차 미리보기 |
| CJ ENM 공식 작품 URL과 저장된 응답 | 네트워크 요청 없이 작품·등장인물 응답 원본 가져오기 |
| 나무위키 문서 URL | 입력한 문서의 방송 정보표, 선택된 본문과 관련 링크 |

입력 예시:

- TVING 작품: `https://www.tving.com/contents/P001790301`
- TVING 드라마 전체: `https://www.tving.com/more/genre/PCA`
- TVING 예능 전체: `https://www.tving.com/more/genre/PCD`
- 나무위키 문서: `https://namu.wiki/w/포핸즈`

나무위키는 사람이 대상 작품의 문서임을 확인한 URL을 입력합니다.
제목으로 URL을 추측해 여러 문서를 자동 매칭하는 기능은 앱 사용 흐름에 포함하지 않습니다.

## 설치

Windows에서 Python 3.11 이상과 Node.js 22.12 이상을 준비합니다.
아래 명령은 프로젝트 최상위 폴더에서 실행합니다.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
Set-Location desktop
npm install
```

가상환경을 활성화하는 명령은 필요하지 않습니다.
앱이 프로젝트의 `.venv\Scripts\python.exe`를 찾아 수집기를 실행합니다.
현재 앱의 기본 수집에는 Playwright 브라우저 설치, LLM API 키, 별도 DB 설정이 필요하지 않습니다.

## 앱 실행

프로젝트 최상위 폴더에서 실행할 때:

```powershell
Set-Location desktop
npm start
```

이미 `desktop` 폴더에 있다면 `npm start`만 실행합니다.
실행 시 화면을 빌드하고, 세션 인증을 사용하는 로컬 Python API를 자동으로 시작합니다.
앱을 닫으면 Python API도 종료됩니다.

현재 웹 UI는 Electron 안에서 실행하는 형태입니다.
일반 브라우저로 개발 서버 주소만 열면 앱의 수집·파일 조회 연결을 사용할 수 없습니다.
화면이나 수집 코드를 수정한 뒤에는 앱을 다시 실행해 변경을 반영합니다.

## 웹 UI 사용 방법

### 1. 수집할 URL 입력

상단의 **콘텐츠 URL**에 대상 주소를 붙여넣습니다.
**빠른 입력** 버튼으로 TVING 드라마 전체, TVING 예능 전체, 나무위키 예시 문서를 선택할 수도 있습니다.

공식 사이트 URL은 **URL 확인 → 표시된 작품명 또는 목록 범위 확인 → 확인 체크 → 수집 시작** 순서로 사용합니다.
공식 URL을 직접 입력하며, 작품명으로 공식 사이트나 위키를 검색하거나 다른 작품으로 자동 대체하지 않습니다.
URL이나 카테고리를 변경하면 검수 상태가 초기화됩니다. 검수 기록은 수집 이력에 보존합니다.

**URL 확인**을 누르면 다음을 확인합니다.

- TVING·tvN: 실제 입력 URL에 접속해 작품명·출처 또는 목록 범위를 확인합니다.
- CJ ENM: 공식 작품 URL을 확인한 뒤 **CJ ENM 응답 파일 선택**으로 저장한 작품 응답과 선택적인 등장인물 응답을 가져옵니다.
  응답의 작품명을 보고 공식 페이지와 같은 작품인지 체크합니다. 이 경로는 웹사이트를 자동 순회하지 않습니다.
- 나무위키: 입력한 문서의 존재 여부와 접근 상태를 확인합니다. HTTP 200만으로 문서가 있다고 판단하지 않습니다.

문서가 있어도 방송 콘텐츠 문서가 아니거나 정보표 형식을 인식하지 못하면 추출에 실패할 수 있습니다.

### 2. TVING 목록 수집 범위 설정

작품 상세 URL과 나무위키 문서 URL은 해당 콘텐츠 하나를 대상으로 합니다.
TVING 목록 URL을 입력하면 아래 옵션이 나타납니다.

| 항목 | 설정 방법 |
|---|---|
| 카테고리 | 입력한 URL에 맞춰 드라마 또는 예능 선택 |
| 시작 순위 | 목록에서 수집을 시작할 위치. 기본값 1 |
| 수집 작품 수 | 시작 순위부터 수집할 작품 수. 기본값 20, 설정 범위 1~1,000 |
| 전체 작품 수집 | 시작 순위부터 목록 끝까지 수집 |
| 최대 목록 페이지 | 전체 목록 확인·수집 시 읽을 목록 페이지 상한. 기본값 500, 설정 범위 1~500 |

예를 들어 시작 순위 21, 작품 수 20이면 목록의 21~40번째 작품을 대상으로 합니다.
이 순위는 해당 페이지의 목록 순서입니다.
세부 장르는 해당 장르 URL을 직접 입력하고 드라마·예능 카테고리를 맞춰 선택합니다.
최대 목록 페이지는 작품 목록 탐색의 상한이며, 회차 API의 페이지 수를 설정하는 항목이 아닙니다.

**전체 목록 확인**을 누르면 첫 페이지의 `nextApiUrl`을 따라 목록의 끝까지 읽고,
작품 ID 기준으로 중복을 제외한 수와 확인 시각을 표시합니다.
목록 확인은 작품별 상세 메타데이터 수집과 별개의 작업입니다.
페이지 상한이나 연결 오류로 중단되면 확인한 수를 하한으로 표시하고 전체 수가 확정되지 않았음을 알립니다.

완료된 전체 목록은 `data/tving-inventories/<타임스탬프>_<카테고리>_<세부카테고리>/inventory.json`에 저장됩니다.
앱을 다시 실행해도 입력한 URL과 카테고리에 맞는 최신 목록을 읽어 표시합니다.
같은 URL에서 수집을 시작하면 확인한 목록의 URL을 사용해 목록 순서 변화로 인한 중복·누락을 줄입니다.
전부 수집하려면 **시작 순위 1**, **전체 작품 수집**을 선택하고 **수집 시작**을 누릅니다.
오래 걸리는 경우 전체 수집을 해제하고 같은 저장 목록을 기준으로 구간을 나눠 수집할 수 있습니다.

### 3. 수집 시작과 진행 확인

**수집 시작**을 누르면 페이지 메타데이터와 회차 정보를 가져와 저장합니다.
진행 상태와 처리한 작품 수는 입력 영역 아래에 표시됩니다.
현재 작업은 한 번에 하나씩 실행됩니다. 수집 중 앱을 닫으면 진행 중인 작업이 중단됩니다.

TVING 목록 수집은 작품을 순서대로 처리하고, 작품 사이에 1초 간격을 둡니다.
결과 목록은 작품을 처리할 때마다 저장됩니다.
일부 작품 수집에 실패하면 실행 보고서에서 실패 이유를 확인할 수 있습니다.

### 4. 저장된 결과 확인

왼쪽 **저장된 수집** 목록에서 실행 결과를 선택합니다.
결과 영역의 작품 선택 메뉴로 확인할 콘텐츠를 바꿀 수 있습니다.
큰 TVING 결과도 선택한 작품의 원본만 읽어 표시합니다.

이력 항목을 **우클릭 → 이력에서 삭제**하면 목록에서만 숨깁니다.
저장된 JSON과 결과 폴더는 보존하며, 숨김 상태는 앱 재실행 후에도 유지됩니다.
삭제 직후 왼쪽 아래의 **되돌리기**로 복원할 수 있습니다.

| 탭·버튼 | 확인할 내용 |
|---|---|
| 작품 정보 | 프로그램 소개, 출연진, 장르 등 화면 표시용 정보 |
| 회차 | 회차 제목과 시놉시스. 제목·시놉시스로 검색 가능 |
| JSON | 새 TVING 결과는 선택한 작품의 원본 통합 JSON. 나무위키와 과거 결과는 해당 저장 형식의 JSON |
| 수집 보고서 | 실행 범위, 성공·실패 및 회차 목록 완전성 등 수집 진단 |
| 저장 폴더 열기 | 선택한 실행 결과가 저장된 폴더 열기 |

TVING의 `director` 인명 목록은 화면에서 **크리에이터**로 표시합니다.
연출·작가·제작 등의 역할을 추정하지 않습니다.
화면에서는 날짜와 필드를 읽기 편하게 표시할 수 있지만, 그 표시용 정리본을 별도 파일로 저장하지 않습니다.
`—`는 해당 화면 항목을 출처에서 제공하지 않거나 추출하지 못한 경우입니다.

## 저장 위치와 파일 구조

앱의 저장 위치는 프로젝트 아래 `data/tving`과 `data/namuwiki`입니다.
앱의 새 수집은 실행마다 한국 시간 기준 타임스탬프를 포함한 폴더를 만듭니다.
작품 폴더는 원래 작품명과 실행 날짜를 사용하며, 파일명으로 사용할 수 없는 문자는 치환합니다.
이름이 겹치면 번호를 추가합니다.

### TVING

새 TVING 수집은 **작품당 `metadata.json` 하나**를 저장합니다.

```text
data/tving/<타임스탬프>_<카테고리>_<세부카테고리>/
  contents.json
  collection-report.json
  <작품명>_<날짜>/
    metadata.json
```

| 파일 | 역할 |
|---|---|
| 작품별 `metadata.json` | 원본 메타데이터, 회차 응답과 수집 이력을 함께 저장 |
| 실행별 `contents.json` | 작품 제목과 통합 파일의 상대 경로만 담은 목록 |
| 실행별 `collection-report.json` | 실행 범위, 작품별 처리 상태, 오류와 수집 진단 |

`metadata.json`에는 다음 블록이 들어갑니다.

| 블록 | 내용 |
|---|---|
| `contentInfo` | 상세 페이지에서 제공한 작품 메타데이터 객체 |
| `jsonLd` | 상세 페이지에서 제공한 JSON-LD 객체들의 배열 |
| `episodeApi` | 회차 API의 전체 JSON 응답. 원래 `header`와 `body` 구조 유지 |
| `collection` | 출처 URL, 수집 시각, 수집 방식, API 주소와 수집 상태 |

원본 블록 안의 필드명, 값, JSON 자료형, 배열 순서, `null`과 빈 값을 유지합니다.
통합 파일로 저장하면서 들여쓰기나 공백은 달라질 수 있습니다.
원본의 서로 다른 필드·출처 블록·회차에 같은 제목이나 인명이 있더라도 삭제하지 않습니다.
중복 저장을 줄이기 위해 수집기가 만들던 화면용 정리본과 콘텐츠 복사본을 저장하지 않는 방식입니다.
이미지 경로 문자열은 원본에 포함되어 있으면 보존하지만, 이미지 파일은 다운로드하지 않습니다.

회차 응답은 화면용 파싱 전에 저장합니다.
API 응답이 유효한 JSON이 아니면 원문을 `episodeApiResponseText`에 보존합니다.
수집 도중 실패한 경우 파일에 확보된 정보만 남을 수 있으므로 `collection.status`를 함께 확인합니다.

### 나무위키

나무위키는 현재 방송 정보표와 선택된 본문을 추출해 저장하는 별도 형식을 사용합니다.
TVING의 원본 응답 통합 구조와 다릅니다.

```text
data/namuwiki/<타임스탬프>_나무위키_<문서명>/
  contents.json
  collection-report.json
  <작품명>_<날짜>/
    program.json
    source-record.json
```

`program.json`과 `contents.json`은 추출된 작품 정보이며,
`source-record.json`은 출처 URL·수집 시각·필드의 추출 위치와 검토 상태를 담습니다.
`collection-report.json`에는 문서 접근 상태와 원문 정보표 등 추출 근거가 들어갑니다.

## 수집 범위와 해석

- TVING 회차 API는 현재 작품당 한 번 요청합니다. 회차 페이지네이션과 다른 시즌 탐색은 구현되어 있지 않습니다.
  `collection.complete_for_current_api_listing`과 실행 보고서를 확인해야 현재 응답 목록의 완전성을 판단할 수 있습니다.
- TVING 목록의 전체 수집은 설정한 최대 목록 페이지 안에서 진행합니다. 상한에 도달하면 미완료 상태를 오류로 알립니다.
- 회차 시놉시스는 소개·줄거리 텍스트이며, 대본이나 전체 시나리오가 아닙니다.
- tvN은 상세 페이지에 실제로 명시된 같은 작품의 미리보기 메뉴를 따라갑니다.
  미리보기 목록의 다음 페이지 정보와 모듈 API가 있으면 최대 100페이지까지 확인합니다.
  원본 페이지와 API 응답은 작품의 `metadata.json` 안에서 출처별로 보존합니다.
  `collection.preview_listing.complete_for_current_preview_listing`은 현재 미리보기 목록의 완전성만 나타내며,
  방송 전체 회차·대본을 확보했다는 뜻이 아닙니다. 오류가 있으면 `preview_warning`을 기록합니다.
- 국가 정보가 없는 콘텐츠는 제목·방송사·TVING 오리지널 여부로 한국 콘텐츠라고 추정하지 않습니다.
  한국 콘텐츠만 선정하는 작업은 원본의 국가 정보 또는 별도의 명시적인 사용자 검수를 근거로 해야 합니다.
- 나무위키는 입력한 문서만 수집합니다. 등장인물·방영 목록 등의 하위 문서와 외부 공식 링크는 관련 URL을 기록하지만 자동으로 따라가지 않습니다.
- 나무위키는 공동 편집 문서입니다. 수집된 서술은 검증된 사실로 자동 확정하지 않으며, 사용 전에 공식 출처와 대조하고 사실·평가를 구분해야 합니다.
- 기존 저장 결과는 보존합니다. 예전에 저장하지 않은 원본 필드는 과거 정리본만으로 복원할 수 없습니다.

## 터미널에서 수집

아래 명령은 프로젝트 최상위 폴더에서 실행합니다.

```powershell
# TVING 작품 하나
.\.venv\Scripts\python.exe -m broadcast_web_crawler.tving "https://www.tving.com/contents/P001790301"

# TVING 드라마 전체 목록의 상위 20개
.\.venv\Scripts\python.exe -m broadcast_web_crawler.tving_batch --category drama --limit 20

# TVING 예능 목록의 21~40번째 작품
.\.venv\Scripts\python.exe -m broadcast_web_crawler.tving_batch --category entertainment --start-rank 21 --limit 20

# 나무위키 문서 존재 여부만 확인
.\.venv\Scripts\python.exe -m broadcast_web_crawler.namuwiki "https://namu.wiki/w/포핸즈" --check-only

# 확인한 나무위키 문서 수집
.\.venv\Scripts\python.exe -m broadcast_web_crawler.namuwiki "https://namu.wiki/w/포핸즈"
```

TVING 목록 수집은 `--url`로 세부 장르 URL을 지정하고, `--all`로 목록 끝까지 수집할 수 있습니다.
`--max-pages`는 목록 탐색 상한입니다. `--output-dir`은 새 실행 폴더를 만들 상위 경로를 지정합니다.

TVING 단일 작품 명령의 기본 저장 위치는 `data/probes/tving-<콘텐츠ID>-python`입니다.
반복 실행 시 같은 경로를 사용하므로 실행을 구분하려면 `--output-dir`로 별도 경로를 지정합니다.
`--save-raw`는 TVING 단일 작품 수집에서 전체 `page.html`을 추가 저장하는 옵션입니다.
원본 통합 JSON 저장에는 이 옵션이 필요하지 않습니다.

## tvN과 CJ ENM 사용

tvN은 `https://tvn.cjenm.com/ko/program/` 같은 목록 URL 또는 프로그램 공식 상세 URL을 입력합니다.
입력 URL의 채널·장르 필터를 유지하며, `tvN DRAMA` 같은 채널 탭을 작품 장르로 재분류하지 않습니다.
원본은 `data/tvn/<실행 폴더>/<작품 폴더>/metadata.json`에 저장하며,
`modules`, `pageInfo`, `templates`를 보존합니다. 명시된 미리보기 메뉴는 `linkedPages`,
다음 모듈 API 응답은 `previewApiResponses`에 출처 URL과 함께 보존합니다.

```powershell
.\.venv\Scripts\python.exe -m broadcast_web_crawler.tvn "https://tvn.cjenm.com/ko/Four-Hands-Two-Sonatas/"
```

TVING·tvN 단일 URL은 `--check-only`로 작품명·출처를 먼저 확인할 수 있습니다.
터미널에서도 작품명을 입력해 검색하지 않고 공식 URL을 직접 지정합니다.
CLI는 사용자가 URL을 선정·확인해 실행하며, 앱은 추가로 화면에서 확인 체크를 받습니다.

CJ ENM은 다음 순서로 사용합니다.

1. 공식 작품 상세 URL을 입력합니다.
2. **CJ ENM 응답 파일 선택**에서 작품 기본 정보 JSON과 선택적으로 등장인물 JSON을 선택합니다. 확장자는 `.json`, `.txt`를 지원합니다.
3. 응답에 표시된 작품명을 보고 공식 페이지와 같은 작품인지 확인 체크합니다.
4. **수집 시작**으로 응답을 가져옵니다. 네트워크 요청은 하지 않습니다.

`data/cjenm/<실행 폴더>/<작품 폴더>/metadata.json`의 `programResponse`, `charactersResponse`는
선택한 JSON을 그대로 보존합니다. 파일과 URL의 대응 관계는 사용자 확인으로 기록하며,
가져온 시각과 원본 응답을 실제 조회한 시각은 구분합니다.

```powershell
.\.venv\Scripts\python.exe -m broadcast_web_crawler.cjenm "https://www.cjenm.com/ko/featured-contents/포핸즈/" --program-response "작품응답.json" --characters-response "등장인물응답.json" --confirmed-target
```

## 기존 TVING 원본 파일 통합

작품별로 `content-info.raw.json`, `json-ld.raw.json`, `episodes-api.raw.json`과 수집 보고서를
저장했던 실행 폴더는 아래 명령으로 통합할 수 있습니다.
`<기존 실행 폴더>`는 실제 폴더 이름으로 바꿉니다.

```powershell
.\.venv\Scripts\python.exe -m broadcast_web_crawler.tving_storage --input-run "data/tving/<기존 실행 폴더>"
```

네트워크에 다시 접속하지 않고 저장된 원본을 읽어 새 통합 폴더를 만듭니다.
기존 파일은 삭제하거나 덮어쓰지 않습니다. 원본 파일이 없는 과거 정리본은 이 명령의 대상이 아닙니다.

## 터미널에서 전체 목록 확인과 수집

작품 상세에 접속하기 전에 현재 목록의 전체 작품 수와 URL을 저장할 수 있습니다.

```powershell
.\.venv\Scripts\python.exe -m broadcast_web_crawler.tving_inventory --category drama --max-pages 500
```

출력된 `inventory_file` 경로를 다음 수집 명령에 사용합니다.
`<확인한 목록 폴더>`는 실제 폴더 이름으로 바꿉니다.

```powershell
.\.venv\Scripts\python.exe -m broadcast_web_crawler.tving_batch --category drama --all --inventory-file "data/tving-inventories/<확인한 목록 폴더>/inventory.json"
```

구간 수집은 `--all` 대신 `--start-rank`와 `--limit`를 지정합니다.
수집마다 목록을 다시 탐색하지 않고 완료된 저장 목록의 순서를 사용합니다.
목록 확인이 완료되지 않았거나 카테고리·URL이 다른 파일은 수집 입력으로 받지 않습니다.

## 문제 해결

| 증상 | 확인할 내용 |
|---|---|
| 로컬 수집기 연결 실패 | `.venv`에 프로젝트 의존성을 설치했는지, Python 실행 파일이 있는지 확인 |
| Node.js 버전 오류 | 지원 버전을 설치하거나 `BROADCAST_NODE`에 실행 파일 경로 지정 |
| 다른 Python을 사용하고 싶음 | `BROADCAST_PYTHON`에 실행 파일 경로 지정 후 앱 실행 |
| 나무위키 문서가 없거나 접근 제한됨 | 입력 URL을 직접 확인하고 보고서의 문서 상태와 오류 확인 |
| 작품 정보 또는 회차가 비어 있음 | 원본 JSON에 정보가 있는지, 보고서에 추출 오류나 미완료 표시가 있는지 확인 |
| 목록 전체 수집 중 페이지 상한 도달 | 수집 범위를 줄이거나 최대 목록 페이지를 조정 |
| 파일 구조나 화면 변경이 반영되지 않음 | 앱 종료 후 `npm start`로 다시 실행 |

Python 실행 파일을 지정하는 예시입니다. 경로는 실제 설치 위치에 맞춰 바꿉니다.

```powershell
$env:BROADCAST_PYTHON = 'C:\Python313\python.exe'
npm start
```

위 명령은 `desktop` 폴더에서 실행합니다.
Node.js 실행 파일도 같은 방식으로 `BROADCAST_NODE`에 지정할 수 있습니다.

## 개발 명령

화면 관련 명령은 `desktop` 폴더에서 실행합니다.

```powershell
npm run dev    # 개발 서버와 Electron 함께 실행
npm run build  # 화면 빌드
npm test       # 저장 경로 접근 제한·CJ ENM 응답 파일 읽기 검사
```

Python 검사 도구는 프로젝트 최상위 폴더에서 설치하고 실행합니다.

```powershell
.\.venv\Scripts\python.exe -m pip install -e '.[dev]'
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check src tests
```

화면 코드와 실행 설정의 위치는 [앱 구성 안내](desktop/README.md)를 참고합니다.

### 실제 URL로 처리 흐름 검증

실제 접속은 수집 코드가 작동하는지 확인하기 위한 테스트입니다.
한 번 확인한 응답을 코드에 넣어 결과를 대신 생성하지 않습니다.
아래 도구는 웹앱과 같은 API에서 URL 확인, 확인 전 요청 거부, 확인 후 수집,
작품당 JSON 1개 저장, 검수 기록 보존, 저장 결과 조회까지 검사합니다.
테스트에서는 사용자 확인 체크를 모의하며 실제 사용자의 검수를 대신하지 않습니다.

```powershell
.\.venv\Scripts\python.exe scripts/verify_desktop_url_flow.py --url "https://www.tving.com/contents/P001790301" --url "https://tvn.cjenm.com/ko/Four-Hands-Two-Sonatas/" --output-dir reports/url-flow-test
```

`--url`을 반복해서 다른 공식 URL도 검사할 수 있습니다.
CJ ENM 경로는 `--cjenm-url`, `--program-response`, 선택적인 `--characters-response`로
공식 작품 URL과 직접 저장한 응답 파일을 지정합니다. CJ ENM 사이트에 자동 요청하지 않습니다.
검사 결과는 지정한 폴더의 `contract-verification.json`, 수집 원본은 그 아래 `app-data`에 저장됩니다.
사이트의 최신 응답에 따라 작품명·회차 수가 달라질 수 있으며, 실패하면 오류로 종료합니다.

tvN의 예고 목록 수집 완료와 전체 방송 회차 확보는 구분합니다.
TVING도 현재 API 목록의 총수와 수집 수를 비교하며, 확인하지 못한 회차를 확보했다고 표시하지 않습니다.
원본에 직접적인 국가 정보가 없으면 작품명·채널·오리지널 여부로 한국 콘텐츠임을 추정하지 않습니다.
