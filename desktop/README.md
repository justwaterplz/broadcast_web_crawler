# 방송 메타데이터 스튜디오 앱

React·shadcn/ui 화면을 Electron에서 실행하고, 프로젝트의 Python 수집기를 연결하는 로컬 앱입니다.
설치 순서, URL 입력, 수집 범위 설정, 결과 확인과 JSON 저장 구조는
[프로젝트 사용 안내](../README.md)에 정리되어 있습니다.

## 실행

프로젝트 최상위 폴더에서 Python 의존성을 설치한 뒤, 이 폴더에서 실행합니다.

```powershell
npm install
npm start
```

`npm start`는 화면을 빌드하고 Electron과 Python API를 시작합니다.
Python은 프로젝트의 `.venv\Scripts\python.exe`를 우선 사용합니다.
다른 실행 파일은 `BROADCAST_PYTHON`으로 지정할 수 있습니다.
Node.js는 22.12 이상을 기준으로 사용하며, 실행 파일을 따로 지정할 때는 `BROADCAST_NODE`를 사용합니다.

현재 화면은 Electron의 수집·파일 조회 연결을 사용합니다.
일반 브라우저에서 개발 서버 주소만 여는 방식으로는 전체 기능을 사용할 수 없습니다.

## 화면 구성

- 입력 영역: TVING·tvN 공식 목록·상세 URL, CJ ENM 공식 작품 URL 또는 직접 확인한 나무위키 문서 URL 입력
- URL 검수: 실제 URL 확인 결과의 작품명·목록 범위를 보고 체크 한 번으로 확인. URL 변경 시 초기화
- CJ ENM: 공식 작품 URL과 사용자가 선택한 원본 응답 파일을 연결해 가져오기
- 수집 범위: TVING 목록의 카테고리, 시작 순위, 작품 수, 전체 수집과 최대 목록 페이지 설정
- 저장 목록: 이전 실행 결과 선택과 목록 새로고침
- 이력 우클릭: 저장된 JSON을 보존한 채 이력에서 숨기기, 삭제 직후 되돌리기
- 전체 목록 확인: 다음 목록 주소를 끝까지 따라 고유 작품 수와 확인 시각 표시
- 결과 영역: 작품 선택, 작품 정보·회차·JSON·수집 보고서 확인, 저장 폴더 열기

새 TVING 결과의 JSON 탭은 선택한 작품의 `metadata.json`을 보여줍니다.
작품·회차 탭은 같은 원본에서 표시용 정보를 메모리로 읽으며, 표시용 정리본은 별도 파일로 저장하지 않습니다.
나무위키는 별도의 추출 결과 형식을 유지합니다.
tvN은 명시된 같은 작품의 미리보기 메뉴와 모듈 API 페이지를 따라 부족한 회차 소개를 보완합니다.
CJ ENM은 자동 순회를 하지 않으며, 사용자가 선택한 응답 원본을 `metadata.json`에 보존합니다.
큰 TVING 결과는 선택한 작품만 읽어 표시합니다.
화면 테마는 흑백과 회색을 사용합니다.
전체 목록 확인 후 시작 순위 1과 전체 작품 수집을 선택하면 저장한 URL 목록 전체를 수집합니다.

## 주요 파일

| 경로 | 역할 |
|---|---|
| `src/main.jsx` | 입력, 수집 진행과 결과 화면 |
| `src/components/ui/` | shadcn/ui 컴포넌트 소스 |
| `src/theme.css` | 색상 등 테마 변수 |
| `src/style.css` | 화면 배치와 스타일 |
| `electron/main.cjs` | 앱 창, Python API 실행과 수집·파일 조회 연결 |
| `electron/preload.cjs` | 화면에서 호출하는 제한된 연결 함수 |
| `electron/paths.cjs` | 결과 경로 접근 범위 검사 |
| `scripts/run.cjs` | 화면 빌드, 개발 서버와 앱 실행 |
| `../src/broadcast_web_crawler/desktop_api.py` | 앱용 로컬 API |

## 개발과 검사

이 폴더에서 실행합니다.

```powershell
npm run dev
npm run build
npm test
```

- `npm run dev`: 화면 개발 서버와 Electron을 함께 실행
- `npm run build`: 화면 빌드
- `npm test`: 저장 경로 접근 제한 검사

저장 위치는 프로젝트의 `data/tving`과 `data/namuwiki`입니다.
화면이나 수집 코드를 변경한 뒤에는 앱을 다시 실행해 반영합니다.
