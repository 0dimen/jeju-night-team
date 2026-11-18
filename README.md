# 제주밤길: 실행 방법과 다음 개발

**팀 공유 시작 문서: [현재 완성 범위·실행·다음 담당 작업](PROJECT_STATUS.md).** 최신 대화·페이지 모듈은 `feature/conversation-route-comparison` 브랜치에서 검토하며 main에는 아직 합쳐지지 않았습니다.

**현재는 개발자 컴퓨터에서 실행하는 보행 경로 비교·시설 제보 시연 프로그램입니다.** 공개 웹사이트나 완성된 지도 앱은 없습니다. 기본 실행은 AI 모델 없이 규칙과 문장 틀을 사용하며 키가 필요 없습니다.

## 어디에서 사용할 수 있나요?

| 사용 방법 | 할 수 있는 일 | 현재 한계 |
|---|---|---|
| 터미널 시연 | 합성 경로의 거리·시간·시설 인접 비율 비교 | 실제 길찾기 아님 |
| 로컬 API와 자동 설명 화면 | 문장 입력, 합성 경로 비교, 제보 미리보기, 날짜·시각 확인 | 실제 서비스 화면·관리자 권한·페이지 이동 처리는 별도 |
| 선택 AI 모듈 | 문장 해석·제보 분류·설명 생성의 모델 연결 실험 | 기본 꺼짐. 실제 개인정보를 무료 API에 보내면 안 됨 |
| 자료 탐색 모듈 | 자료 목록에서 후보 검색 | 공유본에는 내부 목록이 없어 자료 미준비로 응답 |

기본 구성은 정해진 처리 순서·키워드 해석·문장 틀입니다. 선택 AI는 `agent/llm/`에서 연결하며 모델은 계산된 거리·시설 수를 대신 만들지 않습니다. 전체 실험을 하려면 `requirements.lock.txt`와 별도 모델 준비가 필요합니다. 기본 실행부터 확인하세요.

## 1. 설치와 기본 실행

Python 3.13을 기준으로 준비했습니다. 현재 확인 환경은 Linux이며 Windows 잠금·한글 파일 대응을 보강했지만 Windows 실기기·센터 컴퓨터는 아직 확인 전입니다.

Linux 또는 macOS 형식의 명령:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-base.txt
.venv/bin/python scripts/check_basic_runtime.py
.venv/bin/python -m agent --demo
.venv/bin/python -m agent --text '누가 따라와요'
```

macOS에서는 아직 실행 검증하지 않았습니다. Windows PowerShell:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-base.txt
.\.venv\Scripts\python.exe scripts/check_basic_runtime.py
.\.venv\Scripts\python.exe -m agent --demo
```

`passed: true`는 가상 자료 기본 실행 점검을 뜻합니다. 실제 자료 사용·센터 전체 기능 완료는 아닙니다.

## 2. API 사용

```bash
.venv/bin/python -m uvicorn agent.api:app --host 127.0.0.1 --port 8000
```

Windows에서는 Python 경로만 `.\.venv\Scripts\python.exe`로 바꿉니다. 실행한 컴퓨터에서 [API 설명 화면](http://127.0.0.1:8000/docs)을 엽니다. 다른 컴퓨터에 배포한 주소가 아닙니다. 각 POST 항목의 **Try it out**으로 입력합니다.

| 주소 | 입력 예 | 결과 |
|---|---|---|
| `POST /agent/chat` | `{"text":"누가 따라와요"}` | 112 안내 |
| `POST /agent/chat` | `{"text":"데이터 출처 알려줘"}` | 시간 없이 자료 범위·한계 안내 |
| `POST /reports/preview` | `{"text":"CCTV와 가로등이 고장 났어요"}` | 분류 후보·추가 확인 질문, 저장 안 함 |
| `POST /agent/conversation` | `{"text":"집으로 갈거야","state":{}}` | 필요한 위치·날짜·오전/오후 확인 |
| `POST /routes/compare` | `contracts/examples/SYNTHETIC_route_request.json` 내용을 `request`에 넣음 | 합성 경로 비교 |

대화 API는 응답의 `state`를 같은 페이지의 다음 요청에 넣어 이어갑니다. 서버는 집 위치를 저장하지 않습니다. 실제 화면은 페이지를 떠날 때 메모리를 지우고 진행 중인 요청을 중단해야 합니다. 브라우저 저장소·URL·로그에는 집 위치를 넣지 않습니다. 입력이 모이면 합성 비교표·추천 이유를 반환합니다. 실제 위치의 길찾기 결과는 아니며 응답에 합성 시연임을 표시합니다. `초기화` 또는 `취소`를 보내면 페이지 상태를 비웁니다.

## 3. 지금까지 구현한 범위

- 합성 경로 비교와 반경 50미터의 CCTV 인접 비율 계산. 다른 반경도 명시 가능.
- 긴급 안내, 개인정보 가림, 제보 검토 대기·검토 후 게시·재분석의 저장 대역.
- 제보 저장 전 모호한 항목 확인 질문. 실제 확인 화면·게시 권한은 미구현.
- 날짜와 오전·오후 확인, 페이지 상태를 주고받는 대화 API.
- 생활방범 CCTV 선택 전처리와 출처·좌표·보행시간 근거를 검사하는 경로 파일 입력부.
- 실제 CCTV는 8행을 사용 후보로 분리했으나 이용 조건·좌표계·실제 경로 연결은 미완료.

시설 인접성은 현재 작동·촬영 범위·안전을 보장하지 않습니다. 가로등 자료가 없으면 밝기를 계산하지 않습니다. 제보는 사람이 검토·게시하기 전 계산에 반영하지 않습니다.

## 4. 다음 개발자가 이어서 할 일

1. **센터 실행:** 위 기본 점검을 실제 제출 컴퓨터에서 실행하고 성공·실패를 남깁니다.
2. **실제 자료:** 시연 지역·경로를 정하고 자료 이용 조건·좌표계를 확인합니다. 원본과 실제 개인 위치는 공유 코드에 넣지 않습니다.
3. **경로 입력:** 아래 합성 예시로 입력 형식을 확인한 후 실제 보행 경로를 준비합니다.
4. **계산 연결:** `NightAgent(engine=...)`에 같은 입력·출력 형식의 실제 계산기를 연결합니다. 현재 합성 표시와 자료 버전·시점도 함께 처리해야 합니다.
5. **화면 연결:** 대화 상태를 페이지 메모리에만 두고 이탈 시 지웁니다. 제보 미리보기와 실제 검토·게시 권한은 구분합니다.
6. **사람 시험:** 수희의 문장과 작성 의도를 보존하고 실제 응답을 비교합니다. AI가 만든 후보를 사람 정답으로 바꾸어 기록하지 않습니다.

```bash
.venv/bin/python scripts/check_route_file.py data/route_examples/SYNTHETIC_routes.geojson
```

`agent/`는 요청 처리, `agent/data/`는 자료 검사, `stubs/`는 합성 계산·제보 저장 대역, `contracts/`는 주고받는 형식, `config/`는 교체 설정, `tests/`는 검사입니다. 기본 실행 의존성에는 pytest가 없으므로 검사는 별도로 설치합니다.

```bash
.venv/bin/python -m pip install -r requirements-test.txt
.venv/bin/python -m pytest -q
```

현재 기본 기능과 파일 엔진 검사를 수행했습니다. 최신 수치는 PROJECT_STATUS.md를 따릅니다. 선택 모델·벡터·외부 뉴스의 추가 기능은 전체 의존성과 파일 준비가 별도이며 공유본의 내부 목록 탐색은 사용할 수 없습니다.

## 5. 팀 참고 문서

- [팀 역할과 진행 순서](docs/TEAM_BRIEF.md) · [한 장 PDF](docs/pdf/TEAM_BRIEF.pdf)
- [수희에게 요청할 문장 안내](docs/SUHEE_SENTENCE_REQUEST.md)
- [날짜 확인과 페이지 위치 처리](docs/PAGE_TIME_LOCATION_POLICY.md)
- [CCTV 선택 근거와 대안](docs/CCTV_SELECTION_DECISION.md)
- [시연 지역 조사](docs/DEMO_REGION_RESEARCH.md)

공유본은 실행·개발 검토용입니다. 실제 자료 시연·관리자 권한·센터 검증과 최종 제출 완료는 별도로 확인합니다.

이 저장소는 팀 개발용으로 선별한 코드에서 새 이력을 시작했습니다. 다음 변경은 SHARING_POLICY.md의 사전 검사와 검토 절차를 따릅니다.

커밋 전 점검 도구: `python -m pip install -r requirements-share-check.txt` 후 `git config core.hooksPath .githooks`. 자세한 변경·검토 규칙은 [SHARING_POLICY.md](SHARING_POLICY.md)를 따릅니다.

페이지 연결 모듈: [사용 방법](docs/PAGE_CLIENT_INTEGRATION.md). 실제 화면은 아직 없으며, 지도·페이지 이동 연결 후 브라우저에서 통합 확인해야 합니다.

경로·CCTV 파일 계산기: [설치와 연결](docs/FILE_ROUTE_ENGINE.md). 선택 의존성을 설치한 뒤 합성 파일로 먼저 확인하며, 실제 자료 채택을 대신하지 않습니다.

최신 후속: 공개 연구 구간의 지도 보행 경로4개를 확보하고, 출처·예약·모호한 제보 분기를 보완했습니다. [자료 수집 범위](docs/REAL_ROUTE_COLLECTION.md)와 [평가·보완 내용](docs/AGENT_INPUT_EVALUATION.md)을 확인하세요.
