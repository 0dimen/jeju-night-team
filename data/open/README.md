# data/open — 저장소에 함께 넣는 공개 자료

2026년 11월 19일부터, **공개 포털에서 누구나 받을 수 있고 개인 위치가 없는 자료**는 이 폴더에 넣어 팀이 같은 파일로 작업합니다. 비공개 원자료·개인 위치·제보 원문·키는 여전히 넣지 않습니다([SHARING_POLICY](../../SHARING_POLICY.md) 4번). 전체 작업 설명은 [실제 자료 확보와 시설 선호 경로 계산](../../docs/REAL_DATA_AND_FACILITY_ROUTES.md)에 있습니다.

## 원본 (받은 그대로, 수정 없음)

| 파일 | 출처 | 행 수 | 문자 형식 | 기준 | 포털 표기 이용 조건 |
|---|---|---:|---|---|---|
| `jeju_city_streetlights_20241010.csv` | [공공데이터포털 제주시 가로등현황](https://www.data.go.kr/data/15129786/fileData.do) | 52,019 | UTF-8(BOM) | 파일명 2024-10-10. 행별 기준일 없음 | 이용허락범위 제한 없음 |
| `seogwipo_streetlights_20250725.csv` | [공공데이터포털 서귀포시 가로등 보안등 현황](https://www.data.go.kr/data/15129941/fileData.do) | 38,022 | CP949 | 2025-07-25 | 이용허락범위 제한 없음 |
| `jeju_cctv_20221215.csv` | [제주데이터허브 846번](https://jejudatahub.net/data/view/data/846) | 479 | CP949 | 2022-12-15·2023-04-11·2024-07-29 혼재 | **미확인** |
| `jeju_cctv_mois_standard.csv` | [행정안전부 CCTV정보](https://www.data.go.kr/data/15075538/fileData.do)의 제주특별자치도 지역 파일 | 1,043 | CP949 | 2025-05-12·2025-11-05 | 이용허락범위 제한 없음 |
| `population/jeju_emd_population_card_2017~2021.csv` (5개) | [제주데이터허브 「유동인구에 따른 카드 매출액 변화 데이터 활용」 매쉬업결과](https://jejudatahub.net/data/view/data/748) (제주특별자치도, 제주빅데이터센터 활용) | 5개 합계 약 12.5만 | 2017~2020 CP949 계열·2021 형식 다름 | 2017-01 ~ 2021-05 | **미확인**(포털 표기 없음) |

- 받은 날은 모두 2026-11-19입니다. 유동인구 파일 5개만 2026-11-20에 받았습니다.
- 유동인구 파일의 인구 값은 '월 × 읍면동 × 성별' 단위로 업종마다 반복됩니다. `scripts/build_population_stats.py`가 남성·여성 값만 더해 `data/population/jeju_emd_population_monthly.json`(읍면동 43곳 × 53개월)을 만듭니다. 값은 매시 정각 측정 인구의 월 합계이며 사람 수가 아닙니다. 2021년 파일은 년월이 `21-Apr` 꼴이고 법인 줄은 인구 값이 비어 있어 제외합니다.
- **내용은 받은 그대로이고 파일 이름만 바꿨습니다.** 포털이 준 원래 이름은 순서대로 `제주특별자치도_제주시_가로등현황_20241010.csv`, `제주특별자치도_서귀포시_가로등, 보안등 현황_20250725.csv`, `CCTV정보.csv`, `CCTV정보_제주특별자치도.csv`입니다.
- 제주시 가로등 원본은 16,155행의 위도·경도가 뒤바뀌어 있습니다. 원본은 고치지 않았고 아래 복구 사본을 따로 둡니다.
- 서귀포 가로등은 좌표 빈칸이 103행 있습니다.
- CCTV 두 파일은 열 이름이 다릅니다(`설치목적`·`위도` 대 `설치목적구분`·`WGS84위도`).

## 만든 자료 (스크립트로 다시 만들 수 있음)

| 위치 | 내용 | 만드는 명령 |
|---|---|---|
| `derived/jeju_city_streetlights_20241010_axisfixed.csv`, `.note.json` | 축 교환 복구 사본. `좌표수정` 열에 바꾼 행 표시 | `scripts/fix_light_axes.py` |
| `foot_routes/` | 공개 지점 두 구간의 OSRM 보행 경로 후보·원 응답·수집 요약 | `scripts/collect_foot_routes.py` |
| `osm/` | 두 구간 주변 약 600m의 OpenStreetMap 도로망(Overpass 응답) | `scripts/build_facility_routes.py --download-osm` |
| `facility_routes/` | 최단 경로와 시설 선호 경로, 계산 요약 | `scripts/build_facility_routes.py` |

### 만든 자료가 원본에서 달라진 점

| 자료 | 무엇을 바꿨나 | 바꾸지 않은 것 |
|---|---|---|
| 축 교환 복구 사본 | 위도 칸이 126~127이고 경도 칸이 33~34.1인 16,155행만 두 값을 교환. `좌표수정` 열 추가. 문자 형식은 원본과 같은 UTF-8(BOM) | 나머지 35,864행, 행 순서, 다른 열. 중복 좌표 29행도 그대로 |
| 보행 경로 후보 | OSRM 응답에서 경로 선·거리·시간만 뽑아 GeoJSON으로 정리(`agent/data/foot_route_import.py`). 수집 기록(검색어·보정 거리·경유 가로등) 추가 | 좌표·거리·시간 값. 원 응답은 `*_osrm_responses.json`에 그대로 보관 |
| 도로망 | Overpass 응답에 수집 정보(`_collection`: 요청문·받은 시각) 한 항목 추가 | 노드·도로 자료 |
| 시설 선호 경로 | 위 자료로 계산한 결과. 계산에 쓴 반경·가중치·자료 파일 이름을 각 파일의 `calculation`에 기록 | — |

- 경로 구간: 삼무공원 → 누웨마루거리 공중화장실 지도점(연동), 중앙로62번길 → 서귀포매일올레시장(서귀포). Nominatim 지명 검색 결과를 그대로 썼습니다.
- CCTV는 파일을 고치지 않고, 읽을 때 `config/cctv_selection.yaml`의 네 목적만 골라 씁니다. 행정안전부 표준 파일은 읽을 때 열 이름만 맞춥니다.

## 사용할 때 지킬 것

- `foot_routes/`·`osm/`·`facility_routes/`는 **© OpenStreetMap contributors, ODbL 1.0** 자료입니다. 화면·보고서에 출처를 표시해야 합니다(https://www.openstreetmap.org/copyright).
- 저장소에 넣었다고 서비스 사용이 승인된 것은 아닙니다. 각 파일·설정의 `rights_confirmed`는 `false` 그대로이며, 공개 서비스에 쓰기 전에 이용 조건과 좌표계를 확인해야 합니다. 특히 제주데이터허브 CCTV 파일의 이용 조건은 확인하지 못했습니다.
- 시설 위치는 현재 작동·점등·촬영 범위를 뜻하지 않습니다.
- 경로의 출발·도착은 공원·시장·도로 같은 공개 지점입니다. 개인 위치가 들어간 경로나 응답은 이 폴더에 넣지 않습니다.
- 수집 스크립트의 요청 캐시는 `data/raw/osrm_cache/`(Git 제외)에 남습니다.
