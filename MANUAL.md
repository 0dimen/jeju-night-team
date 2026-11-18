# 제주밤길 실행 안내

결론: 키와 인터넷 없이 합성 경로 비교와 제보 처리를 확인할 수 있다. 실제 길찾기나 현장 상태를 알려 주는 서비스는 아직 아니다.

## 먼저 실행할 것

이 Raspberry Pi에서는 저장소 폴더에서 다음 명령을 실행한다.

```bash
.venv/bin/python -m agent --demo
.venv/bin/python -m agent --text "제주시청에서 탑동광장까지 CCTV 2026-11-18T22:00"
.venv/bin/python -m agent --text "누가 따라와요"
```

첫 명령은 같은 합성 시설·경로를 비교한다. 결과의 SYNTHETIC은 합성 예시라는 뜻이다. 두 번째는 문장을 해석한다. 출발지·도착지·시각이 없으면 확인을 요청한다. 세 번째는 모델·저장보다 먼저 112 안내를 표시한다. 이 프로그램이 긴급 신고를 접수하는 것은 아니다.

새 컴퓨터에서는 Python 3.13과 가상환경을 준비한 뒤 `requirements.lock.txt`를 설치한다. 기본 합성 시연·`agent.api`만 쓸 때는 `requirements-base.txt`로 직접 의존성 범위를 줄일 수 있다. Pi Linux의 새 가상환경에 이 목록만 설치해 합성 시연과 기본 API를 확인했다. 전체 실험에는 앞의 전체 목록이 필요하다. 현재 확인한 환경은 Raspberry Pi의 Linux이며 제출 센터 PC는 별도 확인이 필요하다. 공급자 파일 잠금은 Linux와 Windows용으로 분리했다. Linux의 동시 실행 검사는 통과했으나 Windows 실기기와 센터 실행은 아직 확인하지 않았다.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock.txt
.venv/bin/python -m pytest -q
```

## 화면 대신 자동 API 문서로 확인

```bash
.venv/bin/uvicorn discovery.api:app --host 127.0.0.1 --port 8000
```

브라우저에서 `http://127.0.0.1:8000/docs`를 열고 다음 기능을 사용한다. 자동 문서의 화면 자원은 인터넷 연결이 필요할 수 있으므로 오프라인 시연은 위 명령을 먼저 사용한다.

| 기능 | 입력과 결과 |
|---|---|
| `POST /agent/chat` | text에 문장, context에 선택 위치·사용자 선택을 넣는다. 경로 비교·제보·확인 요청·긴급 안내가 나온다. |
| `POST /routes/compare` | request에 `contracts/examples/SYNTHETIC_route_request.json`의 내용을 넣는다. 반경과 합성 시설 인접 비율을 비교한다. |
| `POST /data/candidates` | 내부 목록·벡터가 준비된 저장소에서만 검색한다. 후보를 보여 주며 지표로 채택하지 않는다. |
| `GET /experiments/results` | 저장된 실험의 코드판·관측/고유/채점 분모·부분 상태·실패·대체·비용 한계·최종 결과를 확인한다. 쓰기 중이거나 깨진 결과는 `incomplete_results` 개수로 구별한다. |

자연어를 주소의 물음표 뒤에 붙이지 말고 입력 본문에 넣는다. 검토·게시 HTTP 기능은 제공하지 않는다. 관리자 권한은 서비스 담당이 연결해야 한다.

## 결과를 읽는 방법

- `unavailable`: 자료 없음. 0을 뜻하지 않는다.
- `historical`: 과거 통계. 출발 시각의 실제 보행량이 아니다.
- 제보는 검토 대기로 저장한다. 분류의 확신도 값은 교정된 정답 확률이 아니며 자동 승인을 하지 않는다.
- 문장에 없는 날짜·좌표를 만들어 채우지 않는다. 현재 장소 사전은 제주시청·탑동광장·제주공항·동문시장뿐이다.
- 시설 인접 반경은 비교 조건이다. 촬영 범위·점등·현재 밝기를 뜻하지 않는다.

모델을 시험할 때는 `README.md`의 설정·무료 한도·합성 입력 제한을 따른다. 기본 실행에는 모델이 필요하지 않다. API 키는 환경변수로만 넣고 명령 출력·파일·제출물에 쓰지 않는다.

## 검토용 묶음의 범위

`scripts/build_demo_bundle.py`는 코드·합성 시험·보고서·허용된 공개 뉴스만 검토용 ZIP으로 만든다. 내부 목록·파생 벡터·내부 표·키·모델 가중치·제보 DB는 넣지 않는다. 따라서 묶음만 받았을 때 내부 데이터 탐색은 사용할 수 없고 기본 합성 시연·오프라인 테스트부터 실행한다. 원자료 1종의 실제 활용·이용 조건·센터 실행·최종 제출 확인은 별도다.

묶음을 다시 만들고 분리 실행을 확인하려면 `scripts/build_demo_bundle.py` 다음에 `scripts/validate_demo_bundle.py`를 실행한다. 검증 결과는 `data/processed/bundle_validation.json`에 남는다. 키 검사 시 비밀 환경 파일을 명령 직전에 읽을 수 있으나 키 값은 출력하지 않는다.

공식 CCTV 원본의 기본 품질은 `.venv/bin/python scripts/audit_cctv_source.py --source data/raw/PUBLIC_jeju_cctv_source.csv`로 검사했다. 원본 CSV는 검토 묶음에 들어 있지 않다.479행·기재카메라1,916대·좌표쌍476개를 구별하며 기본 검사가 권리·좌표계·지정 요건 확인이나 지표 채택을 대신하지 않는다. 집계 근거는 `data/processed/cctv_source_audit.json`이다.

## 센터 컴퓨터에서 먼저 할 기본 점검

Windows PowerShell에서 저장소 폴더를 연 뒤 다음을 실행한다. Python 3.13이 준비되어 있어야 한다. 이 과정에는 모델과 API 키가 필요 없다.

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-base.txt
.\.venv\Scripts\python.exe scripts/check_basic_runtime.py --output runtime-check.json
```

결과의 `passed`가 `true`면 가상 자료 기본 실행 점검을 통과한 것이다. 실제 자료 활용·전체 Windows 호환·센터 최종 시연 완료를 뜻하지 않는다. 실패하면 결과 파일과 실패한 명령을 채원에게 전달한다. 키 값·실제 제보는 보내지 않는다. Linux에서는 마지막 명령의 Python 경로를 `.venv/bin/python`으로 바꾼다.

## 경로 파일과 제보 미리보기

준비할 보행 경로 파일의 형식 예시는 `data/route_examples/SYNTHETIC_routes.geojson`이다. 실제 길이 아니므로 시연 자료로 바꿔 부르지 않는다. `.venv/bin/python scripts/check_route_file.py <파일경로>`로 출처·좌표·거리·시간 근거를 검사한다. 이 명령만으로 CCTV 인접 계산이나 실제 길찾기가 실행되지는 않는다.

`POST /reports/preview`에는 `text`와 선택 사항인 `user_choice`를 보낸다. 개인정보를 가린 후보와 확인 질문을 반환하고 저장하지 않는다. 긴급 표현은 확인 질문보다 먼저 112 안내를 반환한다. 기존 제보 접수·검토·게시와 별도인 미리보기이며, 확인 답변의 저장 연결·관리자 인증은 후속이다.

## 페이지 안에서만 이어지는 대화

`POST /agent/conversation`에 `text`와 현재 페이지의 `state`를 보낸다. 날짜·오전·오후를 확인하며 서버는 집 위치를 저장하지 않는다. 위치가 담긴 상태를 브라우저 저장소·URL·로그에 넣지 않는다. 실제 화면에서 페이지를 떠날 때 상태를 지우고 진행 중인 요청을 중단하는 연결이 필요하다. 자세한 계약과 미구현 범위는 docs/PAGE_TIME_LOCATION_POLICY.md에 있다.
