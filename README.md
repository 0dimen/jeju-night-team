# 제주밤길: 실제 경로와 시설을 비교하는 에이전트

**현재 서비스:** https://jeju-night-team.vercel.app/app · **[최신 기술 기획서](docs/SERVICE_PLAN.md)** · **[PDF](docs/pdf/SERVICE_PLAN.pdf)** · **[아침 인수인계](docs/TEAM_HANDOFF.md)**

**장소를 검색·선택하고, TMAP 보행 경로의 거리·예상 시간·CCTV·조명 인접 비율을 비교할 수 있습니다.** VWorld 배경지도와 공개 구간 대화도 연결했습니다. 시설 위치를 이용한 연구용 비교이며 실제 밝기·촬영·작동·현장 통행을 확인한 서비스는 아닙니다.

최신 서비스·제출 브랜치는 **`feature/service-screens`**입니다. main과 구분하며, 위 주소에 배포돼 있습니다. [현재 상태와 다음 작업](PROJECT_STATUS.md)을 먼저 확인하세요.

맥에서 라즈베리파이 서버를 열려면 [localhost 연결 안내](docs/LOCALHOST_CONNECTION.md)를 따르세요.

## 설치와 실행

Python 3.13·Linux에서 확인했습니다. macOS·Windows·센터 실기기는 별도 확인이 필요합니다.

```bash
git clone --branch feature/service-screens https://github.com/0dimen/jeju-night-team.git
cd jeju-night-team
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-base.txt
.venv/bin/python -m uvicorn agent.api:app --host 127.0.0.1 --port 8000
```

같은 컴퓨터의 브라우저에서 **http://127.0.0.1:8000/app**(서비스 화면)을 엽니다. 에이전트·자료를 확인하는 개발용 화면은 **http://127.0.0.1:8000/lab**에 따로 있습니다. 기본 규칙형 에이전트와 공개 도로망 비교에는 모델 키가 필요 없습니다. 실제 검색·TMAP·배경지도에는 아래 지도 키를 서버 환경변수로 설정한 뒤 서버를 실행해야 합니다. 키 파일을 만들었다면 별도로 불러와야 하며, 저장만으로 실행 중 서버에 반영되지는 않습니다.

Windows PowerShell은 가상환경 실행 경로가 `.venv\Scripts\python.exe`입니다. 자세한 기본 실행·선택 모델 설명은 [매뉴얼](MANUAL.md)을 참고하세요.

## 화면에서 사용할 수 있는 기능

| 화면 | 흐름 | 사용 방법 | 필요한 것 |
|---|---|---|---|
| `/app` | 장소 선택 길찾기 | 장소명·도로명·지번 검색 → 결과 선택 → 날짜·24시간 시각 확인 → 경로 비교 → 근거 확인 → 경로 선택 | VWorld·TMAP 키, 제주 시설 자료 |
| `/app` | 배경지도 | 결과의 '지도에서 경로·시설 보기' → 지도·시설·경로 표시 | VWorld 키 |
| `/app` | 보행환경 제보 | 위치 검색·선택 → 시설·문제 유형 → 설명 → 내용 확인 → 접수(시범 운영, 페이지 메모리) | VWorld 키 |
| `/app` | 지역 데이터·출처 | 데이터 탭 → 지금 쓰는 자료와 확인하지 않은 범위, CCTV 출처 설명 | 추가 키 불필요 |
| `/app` | 유동인구 분석·시설 이슈 | 홈 메뉴에서 '준비 중' 안내 | 자료 연결 전 |
| `/lab` | 공개 도로망 비교 | 연동·서귀포 구간과 선호 조건·반경·가중치 선택 → 최단·시설 선호 후보 탐색 | 공개 자료 또는 서버용 계산 자료 |
| `/lab` | 공개 구간 대화 | `연동 공개 구간을 티맵으로 CCTV 위주로 3시에 갈게요` → 날짜·오전/오후 확인 | TMAP 선택 시 키 필요 |
| `/lab` | 합성 시연·제보 | 합성 경로·대화·긴급 안내·제보 미리보기·시연 접수 | 추가 키 불필요 |

장소 선택 길찾기는 제주 범위에서 직선 5m~20km를 지원합니다. 최대 세 보행 옵션이 같은 길이면 하나로 묶습니다. 이름만으로 지점을 자동 확정하지 않으므로 주소를 보고 선택하세요. 문장 속 임의 장소를 자동 검색·확정하거나 서로 다른 목적지를 한 번에 비교하는 기능은 아직 없습니다.

시간이 필요 없는 자료 출처 질문과 긴급 안내에는 날짜를 묻지 않습니다. 입력 시각은 확인하지만 현재 보행 계산이 시간별 밝기·혼잡·시설 상태를 반영하는 것은 아닙니다.

## 위치와 키

- 검색어는 POST 본문으로 VWorld에, 선택한 좌표는 POST 본문으로 TMAP에 전달합니다. 사용자 문장·주소를 URL 쿼리에 넣지 않습니다.
- 선택 위치는 해당 페이지의 메모리에만 둡니다. 페이지 이동·종료·새로고침·초기화 시 지웁니다. 선택 위치의 검색·요청·경로를 앱 서버 파일·데이터베이스·캐시에 저장하지 않습니다. 외부 제공사의 처리·로그 정책은 별도입니다.
- 공개 두 구간의 고정 응답만 한 시간 캐시합니다. 임의 선택 좌표는 이 캐시를 사용하지 않습니다.
- 기본 에이전트는 규칙·문장 틀입니다. 모델이 숫자를 만들지 않으며 사용자 주소·문장을 외부 언어모델에 보내지 않습니다.

| 환경변수 | 용도 |
|---|---|
| `VWORLD_API_KEY` | 장소·주소 검색과 서버 배경지도 중계 |
| `VWORLD_DOMAIN` | 발급 조건에 맞는 실제 등록 도메인, 필요한 경우 설정 |
| `TMAP_APP_KEY` | 보행 경로 조회 |
| `DATA_GO_KR_SERVICE_KEY` | 선택 사항: 공공 CCTV 원본 갱신 도구 |

키는 Git이나 채팅에 올리지 않습니다. Vercel에서는 프로젝트 환경변수에 설정하고 다시 배포합니다. [VWorld 연결](docs/VWORLD_CONNECTION.md) · [TMAP 연결](docs/TMAP_PEDESTRIAN_CONNECTION.md) · [장소 선택·위치 정책](docs/SELECTED_ROUTE_AGENT.md)

## 자료와 배포

공개 원본·수정 사본·도로망은 [data/open/README.md](data/open/README.md)에 출처와 함께 있습니다. 원본은 유지하고 제주시 가로등의 좌표 교환 수정 사본을 검사해 사용합니다. CCTV는 생활방범·교통단속·어린이보호·시설물관리 네 목적을 포함합니다. 기준일이 있는 목록이며 현재 작동 상태 자료가 아닙니다.

원본 파일은 배포 실행물에서 제외합니다. 배포 준비 시 다음 명령으로 구간별 도로망과 제주 시설의 서버용 계산 자료를 생성합니다.

```bash
.venv/bin/python scripts/build_vercel_data.py
```

계산 자료는 약 4.3MB이며 전체 원본의 주소·다른 열을 포함하지 않습니다. 좌표·출처는 서버에 필요하고 선택한 경로·주변 시설만 브라우저에 응답합니다. 데이터가 바뀌면 다시 생성해야 합니다. 로컬 원본 개발은 `agent.api:app`, Vercel 진입점 `app.py`는 준비된 계산 자료를 사용합니다. 데이터가 없으면 합성 결과로 대신하지 않습니다.

Vercel에서는 저장소 루트·FastAPI·이 기능 브랜치를 사용합니다. [시험 배포 인수 안내](docs/VERCEL_PREVIEW.md)를 따르세요. 현재 배포 빌드와 공개 주소 검사를 완료했습니다. [배포 확인 기록](docs/DEPLOYMENT_2026-11-20.md)을 확인하세요.

## 검사와 다음 개발

```bash
.venv/bin/python -m pip install -r requirements-test.txt
.venv/bin/python -m pytest -q --ignore=tests/browser
```

현재 통합 코드의 자동 검사 359개와 PC Chromium 화면 폭 검사를 통과했습니다. 실제 휴대폰 검사와는 구분합니다. 실제 API 시험에는 공개 장소만 사용했습니다. 모델 합의·합성 문장 검사가 실제 사용자 정확도를 뜻하지 않습니다. [시험과 남은 일](docs/SELECTED_ROUTE_AGENT.md)에 범위를 정리했습니다.

다음 우선순위는 실제 휴대폰·센터 확인, 지도·로드뷰 대조, 추천 기준의 사람 평가, 제보 영구 저장·관리자 승인·운영 경로 반영입니다. 최신 기능·수식·검증 범위는 기술 기획서를 기준으로 확인합니다.

## 참고 문서

- [최신 기술 기획서와 구조 그림](docs/SERVICE_PLAN.md) · [PDF](docs/pdf/SERVICE_PLAN.pdf)

- [현재 완성 범위·배포 담당 인수](PROJECT_STATUS.md)
- [새 장소 선택·대화 연결](docs/SELECTED_ROUTE_AGENT.md)
- [시설 선호 탐색·식·배포 제외](docs/FACILITY_ROUTE_APP.md)
- [공개 자료 처리·출처](docs/REAL_DATA_AND_FACILITY_ROUTES.md)
- [제공 문장 평가](docs/AGENT_INPUT_EVALUATION.md) · [수희 문장 안내](docs/SUHEE_SENTENCE_REQUEST.md)
- [세 계산식과 4인 30문항 시험](docs/THREE_ROUTE_FORMULAS_AND_USER_STUDY.md)
- [팀 역할 안내](docs/TEAM_BRIEF.md) · [공유·검토 규칙](SHARING_POLICY.md)

이 저장소는 팀 개발용입니다. 커밋 전 `requirements-share-check.txt`를 설치하고 `git config core.hooksPath .githooks`로 공유 검사 훅을 설정합니다. 관리 권한·제보 영구 저장·기관 전달·현장 통행 확인은 구현된 시연과 구분합니다.
