# 기획서 v3 본문 (PDF에서 추출한 텍스트)

원본: 제주밤길 기능명세서 v3(PDF, 팀 자료). 표 배치는 추출 과정에서 일부 흐트러질 수 있습니다. 밤 작업자와 문서 갱신의 기준으로 씁니다.

```text
 제주밤길 | JEJU NIGHT MAP 2.0
 제주 공공데이터와 시민 현장 제보를 결합한 AI 야간 보행환경 분석 및 경로 비교 서비스

 문서 유형: 모바일 웹앱 PoC 상세 기능명세서 / 기준: 사용자가 제공한 6개 화면 UI 시안 / 작성일: 2026.11.17




 그림 1. 사용자 제공 UI 시안 원본 (6개 모바일 화면). 본 문서의 화면 구조는 이 이미지를 기준으로 합니다.




제주밤길 | AI 야간 보행환경 Agent | PoC 기능명세서 v2.0                                   1
 01. 서비스 정의 및 범위
 서비스 목적: 야간에 제주 지역을 이동하는 도민·관광객이 출발지와 목적지, 이동 시간, 선호 조건을 입력하면 이용 가능한 유동인구 통계와
 방범시설 정보를 비교해 보행환경을 이해하도록 돕는다. 시민은 조명·CCTV·보행로 문제를 제보하고, 검증된 기록은 다음 분석에
 반영된다.


  구분                    정의


  주 사용자                 제주 도민, 야간 관광객, 1인 보행자


  핵심 가치                 경로 비교의 근거 제시 + 현장 정보 갱신 + 변경 이력의 투명성


  PoC 핵심                경로 설정 → 분석 결과 → 유동인구 상세 → AI 제보 → 검증·반영 결과


  필수 원칙                 방범시설 인접성과 활동인구는 실제 범죄 위험이나 안전 보장을 뜻하지 않음


  디자인 기준                네이비/퍼플 다크 UI, 하단 5탭: 홈·지도·제보·데이터·마이




 범위 및 우선순위

  등급                포함 기능


  P0                장소 검색, 이동시간/선호 입력, 지도 경로 비교, 분석 근거, 제보 접수·AI 구조화, 상태 이력, 검증된 제보 재반영


  P1                시간대별 유동인구 히트맵(재사용 가능한 최신 데이터 확보 시), 사진 첨부, 경로 비교 전후 설명


  P2                실시간 내비게이션, 위치 지속 추적, 자동 위험 예보, 외부 기관 민원 자동 접수




 02. 화면 IA 및 사용자 흐름

  화면 ID         화면명                        진입 / 주요 액션


  S01           홈                          검색, 안전 경로 찾기, 보행환경 제보, 지역 데이터


  S02           안전한 이동 경로 찾기               출발지·도착지, 시간, 경로 선호 체크, 분석 요청


  S03           경로 비교 분석 결과                추천·대안 경로 지도, 필터, 상세 분석


  S04           시간대별 유동인구 분석               히트맵, 시간 슬라이더, 데이터 설명


  S05           보행환경 제보하기                  유형·위치·사진·AI 자동 분류·등록


  S06           데이터 반영 및 변화                처리 상태, 전후 비교, 검증 이력


 대표 시나리오: 홈 → 출발지/목적지·22시 선택 → Agent가 후보 경로와 시설 데이터를 분석 → 경로 비교 → 특정 구간의 가로등 고장 제보
 → AI가 제보를 구조화하고 검토 대기 저장 → 담당 검증 후 시설 상태 갱신 → 재분석 시 변경 근거 표시.




제주밤길 | AI 야간 보행환경 Agent | PoC 기능명세서 v2.0                                                  2
 03. 화면별 UI 및 상세 기능
 S01. 홈

  ID            UI 요소 / 사용자 행동             동작·상태 / 예외


  F01-01        검색창: 어디로 이동하시나요?           입력 시 장소 검색, 후보 선택 후 S02로 이동


  F01-02        안전 경로 찾기 카드                S02 진입, 이전 검색 조건이 있으면 복원


  F01-03        보행환경 제보 카드                 S05 진입, 위치 권한은 선택적으로 요청


  F01-04        지역 데이터 보기 카드               S04 진입, 기준 시점·출처 함께 표시


  F01-05        하단 5탭                      홈·지도·제보·데이터·마이 공통 탐색




 S02. 경로 검색 설정

  ID            입력/제어                      처리 규칙


  F02-01        출발지·도착지                    주소/장소 자동완성; 빈 값·동일 위치 입력 시 안내


  F02-02        출발·도착 교환                   두 위치를 교환하고 이전 분석 결과 초기화


  F02-03        이동 시간 선택                   현재 또는 특정 날짜·시간 선택; 데이터 시간대와 매핑


  F02-04        선호도 다중 선택                  가로등 충분 / CCTV 많은 / 야간 활동인구 많은 경로


  F02-05        AI로 경로 분석하기                좌표 유효성 확인 후 분석 실행, 로딩/실패/재시도 제공


 데이터 부재 규칙: 가로등 위치 데이터가 없다면 해당 옵션을 비활성화하고 이유를 안내한다. 최신 유동인구가 없다면 과거 통계 기반 참고
 비교임을 명시한다. 선택한 조건을 만족하는 경로가 없을 때는 대안을 설명한다.




제주밤길 | AI 야간 보행환경 Agent | PoC 기능명세서 v2.0                                       3
 S03. 경로 비교 분석 결과

  ID            UI 요소                      동작 / 출력


  F03-01        지도 위 추천·대안 경로              경로별 색상 구분, 출발·도착 핀, 선택 시 강조


  F03-02        경로 비교/상세 분석 탭              지도 비교와 근거·지표 상세 전환


  F03-03        유동인구/CCTV/시설 제보 필터         활성 레이어만 지도에 표시, 원본 갱신 시 재조회


  F03-04        경로 카드                      거리·예상시간·상대 비교·자료 기준일 표시


  F03-05        추천 근거                      지표별 비교와 미확인 항목, 우회 시간 설명


  F03-06        분석 실패 처리                   대안 경로가 없으면 단일 경로와 데이터 한계 안내


 추천 로직: (1) 보행 가능한 후보 경로 생성, (2) 각 경로와 CCTV/조명 시설 위치를 공간 결합, (3) 유동인구가 이용 가능하면 경로가
 통과하는 집계 구역과 시간대를 결합, (4) 사용자 선호와 우회 허용 범위에 따라 비교, (5) 계산 결과를 Agent가 자연어로 설명. LLM은
 거리·시간·시설 개수를 직접 만들어내지 않는다.


 S04. 시간대별 유동인구 분석

  ID            UI 요소                      동작 / 검증 기준


  F04-01        유동인구 지도 탭                  집계 구역/격자에 따른 단계별 색상 표시


  F04-02        시간대 추이 탭                   가용 시간 단위로 변화 시각화


  F04-03        지역 비교 탭                    선택 지역 간 동일 기준·동일 기간 비교


  F04-04        시간 슬라이더                    18·20·22·24·02시 등 선택, 실제 데이터 단위에 맞춤


  F04-05        출처·갱신 정보                   제공기관, 관측 기간, 공간 해상도, 실시간 여부 표시


  F04-06        데이터 미제공                    히트맵 대신 이용 가능한 지역 집계 또는 설명 표시


 중요: 제주관광빅데이터플랫폼 데이터맵의 시각화 형태를 참고하되, 공개 웹 화면을 그대로 복제하거나 실시간 원본 API가 제공된다고
 가정하지 않는다. 데이터 다운로드·라이선스·집계 단위는 실제 확인 후 구현한다. 과거 집계와 실시간 위치 데이터는 혼동하지 않는다.


 S05. 보행환경 제보하기

  ID            UI 요소                      동작 / 검증 기준


  F05-01        문제 유형 4종                   가로등 고장 / CCTV 문제 / 보행로 불편 / 기타


  F05-02        위치 선택                      GPS 또는 지도 핀 수동 지정, 주소 역지오코딩


  F05-03        사진 첨부 최대 3장                확장자·용량 검사, 얼굴/차량번호 비식별 안내


  F05-04        AI 자동 분류 결과                시설·문제·설명 추출, 사용자 수정 가능




제주밤길 | AI 야간 보행환경 Agent | PoC 기능명세서 v2.0                                             4
  ID            UI 요소                      동작 / 검증 기준


  F05-05        유사 제보 확인                   일정 반경·기간·유형 기준 중복 후보 표시


  F05-06        제보 등록                      동의 확인 후 검토 대기 저장, 접수 ID 발급


 AI 판정은 잠정 결과다. 사진만으로 가로등의 고장이나 CCTV 실제 작동 여부를 확정하지 않는다. 악의적 제보, 개인정보 포함 사진, 중복
 제출을 검토 대기 상태로 분리한다.


 S06. 데이터 반영 및 변화

  ID            UI 요소                      동작 / 검증 기준


  F06-01        변화 요약                      검증된 시설 상태의 전후 비교 및 반영 일시


  F06-02        제보 처리 현황                   접수 → AI 분석 → 검토 → 조치 확인 → 데이터 반영


  F06-03        지역 변화 추이                   검증된 문제·해결 건수와 기준 기간 표시


  F06-04        추천 경로 변화                   시설 상태 변경 전후 동일 조건 재분석


  F06-05        이력 상세                      누가/언제/무슨 근거로 상태 변경했는지 기록


 처리 단계는 실제 외부 기관의 공식 민원 처리 상태를 의미하지 않는다. 기관 연동이 없는 PoC에서는 서비스 내부 검증·반영 상태로
 표시해야 한다.




제주밤길 | AI 야간 보행환경 Agent | PoC 기능명세서 v2.0                                          5
 04. AI Agent 업무 설계

  도구                         입력                                         출력 / 역할


  parse_user_intent          자연어, 사용자 선택                                장소·시간·선호를 구조화


  search_places              장소명·주소                                     좌표와 장소 후보


  get_walking_routes         출발/도착 좌표                                   보행 경로 후보, 거리·시간·geometry


  analyze_facilities         경로 geometry                                시설 위치·인접 구간·자료 신뢰도


  query_population           구역·시간·기간                                   집계 통계, 기준일·해상도·결측 여부


  rank_and_explain           분석 결과·선호                                   경로 비교 및 근거 설명


  classify_report            사진·설명·위치                                   제보 유형·추출값·불확실성


  check_duplicates           유형·좌표·기간                                   유사 제보 후보


  submit_report              검토된 제보 내용                                  검토 대기 레코드 생성


  recalculate_route          갱신된 시설 상태·기존 조건                            전후 비교와 변경 사유




 상태 전이
 제보: DRAFT → SUBMITTED → AI_CLASSIFIED → UNDER_REVIEW → VERIFIED 또는 REJECTED → RESOLVED(선택) →
 PUBLISHED. VERIFIED는 시설 문제 사실 확인, RESOLVED는 조치 확인, PUBLISHED는 분석 데이터 반영을 의미한다. 모든 전이에는
 변경자·시간·사유를 기록한다.


 추천 신뢰성 규칙
 ① 검증되지 않은 제보는 경로 점수에 직접 반영하지 않음. ② 자료가 없는 항목은 0점이 아닌 미확인으로 표시. ③ 인구가 많은 지역을
 곧바로 안전한 지역으로 단정하지 않음. ④ CCTV 인접 거리는 촬영 범위가 아님. ⑤ 데이터 버전과 추천 로직 버전을 저장해 결과를 재현
 가능하게 함.



 05. 데이터 모델 및 연동

  테이블                             핵심 필드


  places                          place_id, name, address, lat, lng


  facilities                      facility_id, type, lat, lng, purpose, status, source, observed_at


  population_aggregates           area_id, geometry, time_slot, metric, value, observed_period, source


  route_searches                  search_id, origin, destination, departure_at, preferences, data_version




제주밤길 | AI 야간 보행환경 Agent | PoC 기능명세서 v2.0                                                                    6
  테이블                                      핵심 필드


  route_candidates                         route_id, search_id, geometry, distance_m, duration_min


  reports                                  report_id, type, description, geometry, photo_refs, status, created_at


  report_reviews                           review_id, report_id, decision, reason, reviewer, reviewed_at


  facility_changes                         change_id, facility_id, before_state, after_state, evidence, changed_at


  analysis_runs                            run_id, search_id, model_version, dataset_version, explanation




 API 초안

  Method             Endpoint                                                     응답


  GET                /places/search                                               장소 후보


  POST               /routes/analyze                                              경로별 분석 및 근거


  GET                /population/summary                                          구역·시간대별 집계


  POST               /reports/classify                                            AI 제보 분류 초안


  POST               /reports                                                     제보 접수 ID


  GET                /reports/{id}                                                처리 이력


  POST               /admin/reports/{id}/review                                   검증 결과


  POST               /routes/reanalyze                                            데이터 변경 전후 비교




제주밤길 | AI 야간 보행환경 Agent | PoC 기능명세서 v2.0                                                                             7
 06. 데이터 활용 및 구현 제약

  데이터                     사용 방식                           확인해야 할 사항


  제주관광 유동인구               시간대별 지역 활동 패턴 비교                원본 재사용 권한, 시계열·공간 단위, 최신성, API 여부


  CCTV 위치                 경로 인접 시설 분석                     방범 목적 구분, 좌표 정확도, 촬영 범위 미확인


  가로등/보행시설                시설 위치 및 상태 비교                   제주 데이터 가용성·갱신주기 확인


  지도·보행 경로                경로 후보 생성                        보행 API 사용 조건·대안 경로 지원 여부


  시민 제보                   시설 상태 변화의 보조 근거                 중복·허위 제보 방지, 검토 담당자 정의


 대회 필수 데이터는 실제 다운로드/조회가 가능한 제주데이터허브 또는 제주빅데이터센터 데이터셋 1종 이상을 확보해 별도로 출처·가공
 내역·사용 필드를 기록해야 한다. 제주관광공사 데이터맵 화면 자체만으로 데이터 연동이 증명되지는 않는다.



 07. 예외·보안·개인정보 요구사항

  상황                            요구 동작


  GPS 권한 거부                     주소·지도 핀으로 수동 선택 가능


  보행 경로 API 실패                  재시도 및 지도에 결과 미제공 표시


  최신 유동인구 없음                    과거 집계/자료 없음 표시, 실시간으로 표현 금지


  AI 분류 불확실                     사용자 수정 및 수동 검토로 전환


  사진 속 개인정보                     업로드 전 안내, 저장 시 최소화·접근통제


  허위·중복 제보                      자동 게시하지 않고 검토 대기


  긴급 상황                         앱이 긴급 신고를 대체하지 않음을 안내, 112 신고 정보 제공


  위치 데이터                        최소 수집, 세션 종료 후 보존기간에 따라 삭제




 08. 3일 PoC 개발 및 시연 계획

  일정             필수 구현                                     완료 기준


  Day 1          데이터 확보·정제, 장소 검색, 지도·경로 생성                실제 제주 장소로 경로 1개 이상 표시


  Day 2          경로 시설 분석, Agent 설명, 제보 등록·분류              분석 근거와 제보 DB 저장 확인


  Day 3          검증 상태 전이, 재분석, UI·시연·문서                   검증된 제보가 분석 결과를 바꾸는 시나리오 재현




제주밤길 | AI 야간 보행환경 Agent | PoC 기능명세서 v2.0                                                      8
 데모 시나리오
 1) 제주시청 → 탑동광장, 22:00 선택. 2) 경로 A/B의 거리·CCTV 인접성을 비교. 3) 유동인구 화면에서 실제 확보한 통계의 기준 시점
 확인. 4) 가로등 문제 사진과 위치를 등록. 5) 검토자가 해당 문제를 검증·반영. 6) 동일 조건으로 경로 재분석하여 변화된 시설 상태와 추천
 이유를 확인. 데모 데이터는 가상임을 명시.



 09. 기능 수용 기준
 □ AC01 출발지·도착지·시간을 지정하고 경로를 조회할 수 있다.

 □ AC02 경로별 거리·시간과 실제 확보된 시설 지표를 구분해 표시한다.

 □ AC03 유동인구의 출처·관측 기간·집계 단위·실시간 여부를 표시한다.

 □ AC04 제보 사진/설명을 AI가 구조화하고 사용자가 수정할 수 있다.

 □ AC05 중복 후보와 미검증 상태를 명확히 구분한다.

 □ AC06 검증된 제보만 시설 상태 데이터에 반영된다.

 □ AC07 재분석 결과는 이전 데이터 버전과 변경 이유를 표시한다.

 □ AC08 위치 권한 거부, API 오류, 결측 데이터 상태를 처리한다.

 □ AC09 실제 범죄 위험이나 안전을 보장하는 표현을 사용하지 않는다.

 문서 해석 주의: UI 이미지의 수치, 지도 히트맵, 상태 변경 이력은 디자인 예시이며 실측·운영 데이터가 아니다. 본 명세서는 구현 목표와
 검증 조건을 정의하며, 외부 데이터 및 API 제공 여부는 별도 확인이 필요하다.




제주밤길 | AI 야간 보행환경 Agent | PoC 기능명세서 v2.0                                               9
 부록 A. 데이터 확보                                가공              활용 구현 명세
 제주밤길 JEJU NIGHT MAP 2.0 | 기존 UI               기능명세서 v2.0 확장 | 2026-11-17

 본 부록은 원본 PDF의 6개 화면과 F01~F06을 그대로 유지하고, 실증 가능한 데이터와 미확인 의존성을 구분합니다.
 출처 페이지 확인은 완료했으나 실제 원본 CSV/API 응답 다운로드                         접근 권한    전체 레코드 품질 검증은 아직
 완료하지 않았습니다.


 A1. 데이터 확보 매트릭스

  데이터 / 링크                                확인된 단위      필드                확보 및 적용 방침


  행안부 CCTV 표준 /                           WGS84 위경도, 주소, 설치 목적, 카메라     CSV 내려받기 → 제주 행만 필터 →
  data.go.kr/data/15013094/standard.do    대수, 관리기관, 촬영 방면 등             위치   목적 정제 → PostGIS 저장. F03 경로
                                                                        인접 시설 분석


  행안부 CCTV API /                          REST JSON/XML, 활용신청 필요        개발계정 신청 후 정기 동기화. PoC는 CSV를
  data.go.kr/data/15155042/openapi.do                                   우선 사용


  제주관광공사 읍면동 방문객 /                        기준연월, 읍면동 코드, 내외국인 방문객        CSV → 읍면동 경계와 조인 → 월별 관광
  data.ijto.or.kr/.../view.do?regSn=21    수; SKT 30분 체류 기반              활동 지도. F04 참고 레이어; 시간대별 경로
                                                                        점수에는 사용 금지


  제주관광공사 리별 방문객 /                         기준연월, 리 코드, 내외국인 방문객 수        CSV → 리 경계 결합 가능 시 상세 지역 비교.
  data.ijto.or.kr/.../view.do?regSn=97                                  야간 보행자 수로 해석 금지


  제주 250m 격자 /                            2015~2016 시간대별 제주도민           과거 공간 분석 PoC 실험에 한정; 현재 경로
  data.go.kr/data/15069810/fileData.do    유동인구, 250m 격자                 추천 점수 제외


  행안부 공통POI 보안등 /                         전국 보안등 위치 안내; 원 출처            제주 데이터 포함 여부,
  data.go.kr/data/79782/linkedData.do     safetydata.go.kr              다운로드    좌표   사용 조건 검증 후 F03에
                                                                        선택 적용




 A2. 출처별 필수 확인 항목
 • CSV 파일의 실제 컬럼명                좌표 결측률      제주 행 수를 직접 검사한 뒤 내부 스키마에 매핑

 • 제주관광공사 데이터맵(sub01.do)은 시각적 참고 출처. 실시간 레이어 원본/API의 외부 재사용 가능 여부는 별도
 문의

 • 가로등/보안등 설치 위치와 현재 점등                    고장 상태는 별개. 위치만으로 밝기를 단정하지 않음

 • 보행 길찾기 API는 공급자                 요금    제주 보행 경로 제공 범위        대안 경로 지원 여부 확인 후 확정

 • 제주데이터허브 또는 제주빅데이터센터 지정 데이터 1종 이상 활용 요건은 대회 지정 목록과 별도로 대조




JEJU NIGHT MAP 2.0 | 데이터 확보 및 활용 상세 명세                                                                    1
 부록 B. 데이터 처리 파이프라인

 B1. 수집 → 정제 → 공간 결합
 • 1) 원본 수집: CCTV CSV / 관광공사 CSV / 보안등 후보 파일을 원본 그대로 보관, 출처
 URL    기준일     해시   다운로드 일시 기록

 • 2) 정제: 위경도 범위 검증, 중복 시설 ID 처리, 제주 행정구역 필터, 설치 목적 표준화, null                이상 좌표 제외

 • 3) 공간 적재: PostgreSQL + PostGIS에 시설 POINT, 보행 경로 LINESTRING, 읍면동 POLYGON 저장; 거리
 계산은 미터 기반 투영좌표로 수행

 • 4) 공간 분석: 경로 주변 30~50m 버퍼에 포함되는 시설 위치 검색, 겹친 버퍼는 union 후 경로와 교차 길이 계산

 • 5) 관광객 통계: 월별 읍면동 코드로 경계 조인, 지도에 월별 방문 규모만 표시; 도로 단위 보행량이나 실시간 수치로
 변환하지 않음

 • 6) 응답 구성: 각 지표마다 source_id, observed_period, updated_at, coverage, limitation 함께 반환


 B2. 경로 분석 산식과 조건
 시설 인접 비율 = (경로 선과 시설 위치 버퍼의 합집합이 겹치는 길이) / (전체 경로 길이). 반경 50m는 실험
 파라미터이며 CCTV 촬영 가능 범위를 뜻하지 않습니다.

 초기 경로 정렬은 보행 가능성 → 사용자 허용 우회율 → 시설 인접 구간 비율 → 이동 시간 순으로 수행합니다. 관광객
 월별 방문 수와 2015~2016 격자 유동인구는 현재의 경로 점수에서 제외합니다.

 예시: A 경로 950m       12분   CCTV 인접 310m, B 경로 1100m   14분   인접 660m. 인접 비율 A 32.6%, B 60.0%.
 B가 더 안전하다는 결론은 도출하지 않고 시설 인접성의 차이만 설명합니다.


 B3. 데이터 신뢰도 상태

  상태                  조건                                    UI 표기


  verified            좌표    기준일   출처 확인                     시설 위치 확인됨


  historical          오래된 시계열 통계                            과거 통계 / 현재 상태 아님


  unavailable         API 또는 원본 접근 불가                       데이터 없음 / 분석에서 제외


  pending             시민 제보 미검증                             검토 중 / 추천 반영 안 됨


  confirmed           제보 확인    승인                           검증된 시설 상태 변경




JEJU NIGHT MAP 2.0 | 데이터 확보 및 활용 상세 명세                                                         2
 부록 C. 6개 화면별 실제 데이터 연동

  화면                 사용 데이터                          화면 동작 / 실패 시


  S01 홈              장소 검색 API, 최근 검색(로컬), 월별 지역     목적지 입력 → 장소 후보 선택. 홈 카드에는 최근 월별
                     방문 통계                           지역 방문 지표만 표시


  S02 경로 설정          장소 좌표, 출발 예정 시간, 사용자 선호         시간은 분석 컨텍스트로 저장. 해당 시간대 유동인구
                                                     미확보 시 선택 항목 비활성화


  S03 경로 비교          보행 경로 API, CCTV POINT, 검증된 시설   복수 경로 좌표 생성 → 버퍼 교차 → 인접 구간
                     상태                              비율   시간   거리 비교. 대안 경로 불가 시 1개 경로만
                                                     표시


  S04 유동인구 분석        제주관광공사 월별 읍면동/리별 방문객; 역사        기본 탭은 월별 지역 방문 규모. 18~02시 시간 슬라이더는
                     격자(선택)                          적법한 시간별 원본 확보 전 숨김


  S05 보행환경 제보        GPS/지도핀, 사진, 설명, 자체 DB          AI가 유형    좌표   설명 추출 → 유사 제보 검색 → 검토
                                                     대기 저장. 사진만으로 고장 확정 금지


  S06 데이터 변화         검증 이력, 시설 상태 변경, 경로 분석 버전       승인 전후 시설 상태     경로 지표 재계산 비교. 기관 수리
                                                     완료는 공식 확인 없으면 표시 금지




 C2. 사용자 제보 데이터 축적 프로토콜
 • 사용자 입력: 위치 좌표, 시설 유형(가로등/CCTV/보행로), 설명, 선택 사진, 촬영시각(선택)

 • AI 처리: 구조화 JSON 생성 + 위치 반경 30m 및 유사 텍스트 기준 중복 후보 조회

 • 저장: reports.status=pending. 개인정보   얼굴   차량번호 포함 사진은 자동 공개하지 않고 접근 제한

 • 검증: 관리자 또는 신뢰 가능한 근거로 상태 confirmed / rejected / duplicate 판정. 미확인 제보는 지도에서 분리

 • 반영: confirmed인 시설 문제만 facility_observations에 새 버전으로 기록, 기존 기록을 덮어쓰지 않음

 • 재분석: 영향받는 경로의 공간 분석 캐시 무효화 → 새 시설 상태 기반 재계산 → 변화 이유 및 시점 표시




JEJU NIGHT MAP 2.0 | 데이터 확보 및 활용 상세 명세                                                      3
 부록 D. API                       DB              개발 및 검증

 D1. 최소 DB 스키마

  테이블                         핵심 필드                                                      용도


  source_registry             source_id, url, license, observed_at, fetched_at,          출처    최신성 추적
                              version


  cctv_facilities             facility_id, geom, purpose, camera_count, source_id        CCTV 공간 조회


  regional_visits             ym, area_code, domestic, foreign, total, source_id         월별 지역 방문 통계


  route_candidates            route_id, geom, meters, minutes, routing_provider          보행 경로 후보


  route_metrics               route_id, cctv_near_m, ratio, calculated_at,               재현 가능한 분석
                              source_version


  reports                     report_id, geom, type, description, photo_ref, status      시민 제보


  facility_observations       observation_id, facility_id, state, valid_from,            검증된 상태 변경
                              verified_by


  analysis_runs               run_id, input_hash, data_versions, output_json             전후 비교 및 재현




 D2. API 계약

  API                                        입력                                       출력


  POST /routes/search                        origin, destination,                     routes[] 거리    시간    polyline
                                             departure_time, preferences


  POST /routes/analyze                       route_ids, data_version                  cctv_near_m, ratio, evidence[], limitations[]


  GET /population/regions                    year_month, area_code                    monthly_visits, source, observed_period


  POST /reports                              lat, lng, category, description,         report_id, pending, duplicate_candidates
                                             photo


  POST /reports/{id}/review                  decision, reviewer, evidence             confirmed/rejected/duplicate


  POST /analysis/recompute                   route_id, data_version                   before, after, changed_fields, explanation




 D3. 개발 순서 및 완료 기준
 • D1: CCTV 원본 다운로드             제주 필터         지도 핀 표시, 출처 메타데이터 저장

 • D2: 보행 경로 생성 + CCTV 공간 분석, 경로 비교 UI 구현

 • D3: 제보 입력 → AI 구조화 → pending 저장 → 관리자 승인 → 재분석 및 변경 이력 시연

 • AC1: 원본 자료 기준일과 출처를 화면에서 확인 가능




JEJU NIGHT MAP 2.0 | 데이터 확보 및 활용 상세 명세                                                                                                4
 • AC2: 관광공사 월별 방문 통계가 특정 시간대 보행자 수로 오표시되지 않음

 • AC3: pending 제보는 추천 지표에 반영되지 않음

 • AC4: 동일 입력            동일 데이터 버전으로 분석을 재실행하면 같은 정량 결과를 얻음


 D4. 원문 데이터 링크
 https://www.data.go.kr/data/15013094/standard.do
 https://www.data.go.kr/data/15155042/openapi.do
 https://data.ijto.or.kr/prog/dataPick/bigdata/sub02/view.do?regSn=21
 https://data.ijto.or.kr/prog/dataPick/bigdata/sub02/view.do?regSn=97
 https://www.data.go.kr/data/15069810/fileData.do
 https://www.data.go.kr/data/79782/linkedData.do
 https://data.ijto.or.kr/bigdata/sub01.do
 검증 경계: 실제 원본 다운로드, 제주 지역 보안등 포함 여부, 실시간 데이터 재사용 권한, 길찾기 API 계약 및 대회 지정 데이터 목록 대조는
 구현 전 확인이 필요합니다.




JEJU NIGHT MAP 2.0 | 데이터 확보 및 활용 상세 명세                                               5
```
