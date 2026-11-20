# 경로·시설 파일 계산기 연결

## 동작 범위

`FileRouteEngine`은 명시한 경로 파일과 CCTV 파일을 읽어 거리·시설 인접 비율을 계산합니다. 경로를 새로 찾는 온라인 길찾기 서비스는 아닙니다. 파일에 없는 출발·도착점은 거부합니다. 기본 합성 엔진을 자동으로 바꾸지 않습니다.

```bash
.venv/bin/python -m pip install -r requirements-geo.txt
.venv/bin/python scripts/run_file_routes.py \
  --routes data/route_examples/SYNTHETIC_routes.geojson \
  --cctv data/route_examples/SYNTHETIC_cctv.json \
  --request data/route_examples/SYNTHETIC_file_request.json
```

예시 파일은 모두 합성입니다. 실제 학교·집·CCTV를 연결한 결과가 아닙니다. 합성 표시는 응답에 유지됩니다. 서비스 담당은 `NightAgent(engine=FileRouteEngine(route_path, cctv_path))`로 같은 계산기를 주입할 수 있습니다. 파일 엔진을 대화 API에 연결하는 모의 통합 검사도 포함했습니다.

## 실제 파일 준비 조건

- 경로: 기존 GeoJSON 검사 형식을 따릅니다. 같은 출발·도착의 보행 경로, 출처·이용 조건·기준일·시간 산정 근거와 보행 확인 표시가 필요합니다.
- CCTV: metadata와 rows를 둡니다. 행에는 고유id·type=cctv·lat·lng·basis_date가 필요합니다. 위도·경도는 확인된 WGS84여야 하며 자동으로 축을 뒤집지 않습니다.
- 양쪽 metadata의 synthetic값이 같아야 합니다. 실제와 합성을 섞지 않습니다.
- 실제 자료는 양쪽에 rights_confirmed·coordinate_system_confirmed가 참이고 rights_evidence·coordinate_evidence가 있어야 합니다. 이 값은 문서 근거를 확인한 담당자가 준비하는 것이며, 임의로 참으로 바꾸면 안 됩니다. 프로그램의 문자열 검사가 법적 사용 승인이나 현장 검증을 대신하지 않습니다.
- 현재 조사 중인 실제 원본을 자동으로 변환·채택하지 않았습니다. 실제 지도 기반 보행 후보는 별도 연구에서 확보했지만 이용 조건·현장 확인과 서비스 채택은 완료하지 않았습니다.

## 계산과 변경 반영

출발점 중심 미터 좌표로 투영한 선분과 CCTV 반경 원의 겹친 구간을 계산합니다. 겹치는 시설 구간은 중복 합산하지 않습니다. [pyproj 공식 좌표 변환 문서](https://pyproj4.github.io/pyproj/stable/api/transformer.html)를 참고했고, 경도·위도 순서를 명시했습니다. 이 계산은 근사 거리이며 지형·횡단 가능성·실제 조도를 확인하지 않습니다.

현재 기술 지원 범위는 출발점 주변5km와 반경0초과200미터입니다. 범위 밖이나 과도한 연산량은 거부합니다. 이것은 안전 기준이나 우회 허용 정책이 아닙니다.

CCTV 행이 없으면 자료 없음으로 표시합니다. 행이 있지만 인접 구간이 없으면 비율0일 수 있으며 지역에 실제 CCTV가 없다는 뜻이 아닙니다. 행의 기준일을 출처에 표시하고 등록일로 바꾸지 않습니다. 가로등·활동 통계는 현재 엔진에서 자료 없음입니다.

기존 제보 저장 대역에서 검증 후 게시한 정상/미작동 변경만 계산에 반영합니다. 검토 대기·검증만 된 제보는 영향을 주지 않습니다. 파일에 없는 시설이나 지원하지 않는 CCTV상태 변경은 조용히 정상으로 처리하지 않고 거부합니다. 실제 관리자 인증·게시 화면은 별도입니다.

## 검증과 다음 작업

파일 거리·인접 계산, 같은 요청 끝점, 실제 자료 확인 조건, 혼합 거부, 빈 시설, 중복ID·좌표축, 범위·연산량, 기준일, 게시 후 재분석, API연결을 합성 파일로 검사합니다. 실제 자료와 센터 실행 확인은 별도입니다.

경로 메타데이터에 출처·라이선스와 지도 오류 수정 링크가 있으면 계산 응답의 한계 설명에도 유지합니다. 원본 링크가 결과에서 사라지지 않는지 검사합니다.
