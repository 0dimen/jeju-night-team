import { drawVworld } from "/app/vworld.mjs";
const $ = (id) => document.getElementById(id);
const iconPaths = {
  home: "M3 11 12 3l9 8M6 9v12h5v-7h3v7h4V9",
  route: "M4 20V4l6 3 6-3 4 3v14l-4-3-6 3-6-3M10 7v14M16 4v14",
  report: "M4 4h16v13H9l-5 4V4Zm4 5h8M8 12h6",
  data: "M4 20h16M6 16V9M12 16V4M18 16V7",
  my: "M6 21v-3a6 6 0 0 1 12 0v3M16 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0",
};
for (const button of document.querySelectorAll(
  "nav button,.feature-grid button",
)) {
  const span = button.querySelector("span");
  if (!span) continue;
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  for (const [key, value] of Object.entries({
    viewBox: "0 0 24 24",
    width: "24",
    height: "24",
    fill: "none",
    stroke: "currentColor",
    "stroke-width": "1.75",
    "stroke-linecap": "round",
    "stroke-linejoin": "round",
    "aria-hidden": "true",
  }))
    svg.setAttribute(key, value);
  const path = document.createElementNS(svg.namespaceURI, "path");
  const label = button.textContent;
  let glyph = iconPaths[button.dataset.screen] || iconPaths.route;
  if (button.closest(".feature-grid")) {
    if (button.dataset.screen === "route")
      glyph = "M6 18a3 3 0 1 0 0 .01M18 6a3 3 0 1 0 0 .01M6 15V9h12";
    else if (label.includes("지역 데이터")) glyph = iconPaths.route;
    else if (label.includes("유동인구")) glyph = iconPaths.data;
    else if (label.includes("시설 이슈"))
      glyph = "M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4";
  }
  path.setAttribute("d", glyph);
  svg.append(path);
  span.replaceChildren(svg);
}
let activeRoutePhase = "input",
  activeRouteTarget = null;
let liveLocations = {},
  liveRevision = { origin: 0, destination: 0, settings: 0 };
let current = "home",
  generation = 0,
  pending = new Set(),
  lastPreview = null,
  reportSnapshot = null,
  reportPlace = null,
  reportRevision = 0;
const soonCopy = {
  population: [
    "유동인구 분석",
    "시간대별 보행량 자료를 연결하고 있어요. 월별 방문 통계를 지금 걷는 사람 수처럼 보여 주지 않도록 확인한 뒤 열어요.",
  ],
  issues: [
    "시설 이슈",
    "검토를 마친 제보를 지역별로 모아 보여 줄 예정이에요. 지금은 이번 페이지에서 접수한 제보를 마이 탭에서 볼 수 있어요.",
  ],
};
function element(tag, text, parent, cls) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (cls) node.className = cls;
  parent?.append(node);
  return node;
}
function message(parent, text, cls) {
  parent.replaceChildren();
  return element("p", text, parent, cls);
}
function routePhase(phase) {
  activeRoutePhase = phase;
  if (current === "route")
    $("screen-title").textContent = {
      input: "이동 조건 입력",
      compare: "경로 비교",
      detail: "경로 상세",
      chosen: "선택한 이동 경로",
    }[phase];
  for (const item of document.querySelectorAll(".route-progress li")) {
    if (item.dataset.phase === phase) item.setAttribute("aria-current", "step");
    else item.removeAttribute("aria-current");
  }
  const heading = document.querySelector("#route .section-top h1");
  if (heading)
    heading.textContent = {
      input: "어디로 걸어갈까요?",
      compare: "같은 목적지, 경로 비교",
      detail: "경로의 비교 근거",
      chosen: "선택한 이동 경로",
    }[phase];
}
function reportStep(step) {
  if(current==="report")$("screen-title").textContent={1:"보행환경 제보",2:"제보 유형 선택",3:"상세 설명 작성",4:"제보 내용 확인"}[step];
  for (const item of document.querySelectorAll(".report-progress li")) {
    if (item.dataset.reportStep === String(step))
      item.setAttribute("aria-current", "step");
    else item.removeAttribute("aria-current");
  }
}
function durationLabel(row) {
  const seconds = Math.round(
    row.provider_duration_seconds ?? row.duration_minutes * 60,
  );
  return (
    Math.floor(seconds / 60) +
    "분" +
    (seconds % 60 ? " " + (seconds % 60) + "초" : "")
  );
}
function clearLive() {
  liveLocations = {};
  liveRevision.origin++;
  liveRevision.destination++;
  liveRevision.settings++;
  $("live-place-form")?.reset();
  $("live-route-result")?.replaceChildren();
  for (const field of ["origin", "destination"]) {
    $("live-" + field + "-candidates")?.replaceChildren();
    const p = $("live-" + field + "-selected");
    if (p)
      p.textContent =
        (field === "origin" ? "출발지" : "도착지") + "를 선택해 주세요.";
  }
}
function clearRoute() {
  routePhase("input");
  activeRouteTarget = null;
  $("route-input").open = true;
  clearLive();
}
function clearReportPlace() {
  reportPlace = null;
  reportRevision++;
  $("report-place-candidates").replaceChildren();
  $("report-place-selected").textContent = "문제 위치를 선택해 주세요.";
}
function abortRequests() {
  generation++;
  for (const request of pending) request.abort();
  pending.clear();
}
function wipe() {
  abortRequests();
  clearRoute();
  $("report-form").reset();
  clearReportPlace();
  reportStep(1);
  $("report-result").replaceChildren();
  $("report-confirm").hidden = true;
  $("report-consent").checked = false;
  lastPreview = null;
  reportSnapshot = null;
  $("data-result").replaceChildren();
  message($("receipt"), "이번 페이지에서 접수한 제보가 없어요.");
  for (const button of document.querySelectorAll("button"))
    button.disabled = false;
}
function navigate(screen) {
  if (current === "route" && screen !== "route") clearRoute();
  abortRequests();
  current = screen;
  $("screen-back").hidden = screen === "home";
  $("brand-home").hidden = screen !== "home";
  $("screen-title").hidden = screen === "home";
  $("screen-title").textContent =
    screen === "route"
      ? {
          input: "이동 조건 입력",
          compare: "경로 비교",
          detail: "경로 상세",
          chosen: "선택한 이동 경로",
        }[activeRoutePhase]
      : {
          report: "보행환경 제보",
          data: "지역 데이터",
          my: "이번 페이지의 제보",
          soon: $("soon-title").textContent,
        }[screen] || "";
  for (const section of document.querySelectorAll(".screen"))
    section.hidden = section.id !== screen;
  for (const button of document.querySelectorAll("nav button")) {
    if (button.dataset.screen === screen)
      button.setAttribute("aria-current", "page");
    else button.removeAttribute("aria-current");
  }
  if (screen === "home") window.scrollTo({ top: 0 });
  else
    document
      .querySelector("#" + screen + " h1")
      ?.scrollIntoView({ block: "start" });
}
document.addEventListener("click", (event) => {
  const target = event.target.closest("[data-screen]");
  if (!target) return;
  const copy = soonCopy[target.dataset.soon];
  if (copy) {
    $("soon-title").textContent = copy[0];
    $("soon-text").textContent = copy[1];
  }
  navigate(target.dataset.screen);
});
$("brand-home").addEventListener("click", () => navigate("home"));
$("clear-page").addEventListener("click", () => {
  wipe();
  navigate("home");
});
window.addEventListener("pagehide", wipe);
window.addEventListener("pageshow", wipe);
async function post(endpoint, body) {
  const epoch = generation,
    aborter = new AbortController();
  pending.add(aborter);
  try {
    const response = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      cache: "no-store",
      signal: aborter.signal,
    });
    if (epoch !== generation) return null;
    if (!response.ok)
      throw new Error(
        "처리하지 못했습니다. 입력을 유지했으니 확인 후 다시 시도해 주세요.",
      );
    const result = await response.json();
    return epoch === generation ? result : null;
  } catch (error) {
    if (aborter.signal.aborted || epoch !== generation) return null;
    throw error;
  } finally {
    pending.delete(aborter);
  }
}
function showData(view, target) {
  target.replaceChildren();
  element("h2", "자료 설명", target);
  element(
    "p",
    view.explanation?.summary ||
      view.message ||
      "자료 설명을 확인하지 못했습니다.",
    target,
  );
  const list = element("ul", "", target, "source-list");
  for (const source of view.data_sources || [])
    element("li", source.source_label + "：" + source.note, list);
  for (const text of view.explanation?.not_checked || [])
    element("li", "미확인: " + text, list);
}
function showPreview(view, target) {
  target.replaceChildren();
  element("p", view.message, target);
  if (view.classification_candidate) {
    const labels = {
      streetlight: "가로등·보안등",
      cctv: "CCTV",
      walkway: "보행로",
      other: "확인 필요",
      not_working: "작동하지 않음",
      flickering: "깜빡임",
      too_dark: "어두움",
      damaged: "파손",
      obstructed: "통행 방해",
    };
    const c = view.classification_candidate;
    element(
      "p",
      "분류 후보: " + labels[c.facility] + " / " + labels[c.problem],
      target,
    );
  }
  for (const q of view.questions || []) element("p", q.message, target);
}
function showConversation(view, target) {
  if (view.kind === "data_question") showData(view, target);
  else if (view.kind === "report_preview") showPreview(view, target);
  else
    message(
      target,
      view.message || "입력을 확인해 주세요.",
      view.kind === "emergency" ? "error" : undefined,
    );
}
$("source-button").addEventListener("click", async () => {
  try {
    const view = await post("/agent/conversation", {
      text: "CCTV 자료의 출처와 기준일이 뭐야?",
      state: {},
    });
    if (view) showData(view, $("data-result"));
  } catch (error) {
    message($("data-result"), error.message, "error");
  }
});
function reportInput() {
  return {
    text: $("report-text").value,
    user_choice: {
      facility: $("report-facility").value,
      problem: $("report-problem").value,
    },
    location: reportPlace,
  };
}
$("report-form").addEventListener("input", () => {
  $("report-confirm").hidden = true;
  $("report-consent").checked = false;
  lastPreview = null;
  reportSnapshot = null;
});
$("report-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!reportPlace) {
    message(
      $("report-result"),
      "문제 위치를 검색해 결과에서 선택해 주세요.",
      "error",
    );
    reportStep(1);
    return;
  }
  const button = $("report-preview-button");
  button.disabled = true;
  $("report-confirm").hidden = true;
  lastPreview = null;
  try {
    const snapshot = reportInput();
    const view = await post("/reports/preview", {
      text: snapshot.text,
      user_choice: snapshot.user_choice,
    });
    if (view) {
      showPreview(view, $("report-result"));
      if (view.kind !== "emergency") {
        lastPreview = view;
        reportSnapshot = snapshot;
        if (
          !view.needs_clarification &&
          !view.classification_candidate?.conflict_with_user_choice
        )
          $("report-confirm").hidden = false;
        else
          element(
            "p",
            "문제·선택 항목을 수정해 다시 확인해 주세요. 확인 질문이 남으면 접수하지 않습니다.",
            $("report-result"),
          );
      }
    }
  } catch (error) {
    message($("report-result"), error.message, "error");
  } finally {
    button.disabled = false;
  }
});
$("report-submit").addEventListener("click", async () => {
  if (!lastPreview || !reportSnapshot || !$("report-consent").checked) {
    element(
      "p",
      "위치·유형·내용과 확인 항목을 체크해 주세요.",
      $("report-result"),
    );
    return;
  }
  if (JSON.stringify(reportInput()) !== JSON.stringify(reportSnapshot)) return;
  const button = $("report-submit");
  button.disabled = true;
  try {
    const { lat, lng } = reportSnapshot.location;
    const view = await post("/agent/chat", {
      text: reportSnapshot.text,
      context: { lat, lng, user_choice: reportSnapshot.user_choice },
    });
    if (view?.stored && view.report) {
      const receipt = $("receipt");
      receipt.replaceChildren();
      element("h2", "제보가 접수됐어요", receipt);
      element("p", "접수번호: " + view.report.id, receipt);
      element("p", "위치: " + reportSnapshot.location.name, receipt);
      element("span", "검토 대기", receipt, "badge");
      element(
        "p",
        "검토를 마치기 전까지는 경로 분석에 반영하지 않아요. 시범 운영 중이라 기관에는 전달되지 않아요.",
        receipt,
      );
      $("report-confirm").hidden = true;
      lastPreview = null;
      reportSnapshot = null;
      navigate("my");
      $("report-form").reset();
      clearReportPlace();
      $("report-result").replaceChildren();
      reportStep(1);
    } else if (view) showConversation(view, $("report-result"));
  } catch (error) {
    message($("report-result"), error.message, "error");
  } finally {
    button.disabled = false;
  }
});

function renderFacilityRoutes(view, target) {
  activeRouteTarget = target;
  target.replaceChildren();
  routePhase("compare");
  element(
    "span",
    view.provider === "tmap"
      ? "TMAP 보행 · 실제 자료"
      : "공개 도로망 · 실제 자료",
    target,
    "result-source",
  );
  element(
    "h2",
    view.routes.length > 1
      ? "같은 목적지, 경로 비교"
      : "경로 후보를 확인해 보세요",
    target,
    "result-heading",
  );
  element("p", view.label, target, "support");
  element(
    "p",
    "공개된 시설 위치로 계산한 비교예요. 지금 불이 켜져 있는지, 현장을 지나갈 수 있는지는 확인하지 않았어요.",
    target,
    "notice",
  );
  element("p", view.reason, target);
  if (view.departure)
    element(
      "p",
      "확인한 출발: " + view.departure + " · " + view.time_effect,
      target,
    );
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 380 250");
  svg.setAttribute("role", "img");
  svg.classList.add("route-map");
  svg.setAttribute(
    "aria-label",
    "공개 도로망 경로 좌표 도식. 배경지도·현재 위치 안내가 아닙니다.",
  );
  const points = view.routes.flatMap((row) => row.coordinates),
    xs = points.map((p) => p[0]),
    ys = points.map((p) => p[1]);
  const minx = Math.min(...xs),
    maxx = Math.max(...xs),
    miny = Math.min(...ys),
    maxy = Math.max(...ys);
  const lat = (((miny + maxy) / 2) * Math.PI) / 180,
    dx = (maxx - minx) * Math.cos(lat),
    dy = maxy - miny,
    scale = Math.min(330 / Math.max(dx, 1e-8), 180 / Math.max(dy, 1e-8));
  const map = (p) => [
    (380 - dx * scale) / 2 + (p[0] - minx) * Math.cos(lat) * scale,
    40 + (180 + dy * scale) / 2 - (p[1] - miny) * scale,
  ];
  const text = document.createElementNS(svg.namespaceURI, "text");
  text.setAttribute("x", "16");
  text.setAttribute("y", "25");
  text.setAttribute("fill", "#c4bcd9");
  text.setAttribute("font-size", "13");
  text.textContent = "실제 경로 좌표 도식 · 배경지도 없음";
  svg.append(text);
  for (const row of view.routes) {
    const line = document.createElementNS(svg.namespaceURI, "polyline");
    line.setAttribute(
      "points",
      row.coordinates.map((p) => map(p).join(",")).join(" "),
    );
    line.setAttribute("stroke", row.id === "SHORTEST" ? "#af86ff" : "#89e3dd");
    line.setAttribute("fill", "none");
    line.setAttribute("stroke-width", "5");
    if (row.id !== "SHORTEST") line.setAttribute("stroke-dasharray", "7 6");
    line.dataset.route = row.id;
    svg.append(line);
  }
  const mapButton = element(
    "button",
    "지도에서 경로·시설 보기",
    target,
  );
  mapButton.type = "button";
  const mapHost = element("div", "", target);
  const mapEpoch = generation;
  mapButton.addEventListener("click", async () => {
    mapButton.disabled = true;
    const mapAbort = new AbortController();
    pending.add(mapAbort);
    const isCurrent = () =>
      mapEpoch === generation &&
      mapHost.isConnected &&
      !mapAbort.signal.aborted;
    try {
      await drawVworld(view, mapHost, isCurrent, mapAbort.signal);
      svg.toggleAttribute(
        "hidden",
        mapHost.textContent.includes("VWorld 배경지도 연결 완료"),
      );
      const selected = target.querySelector(".route-card[aria-pressed=true]")
        ?.dataset.route;
      for (const line of mapHost.querySelectorAll("polyline[data-route]"))
        line.setAttribute(
          "opacity",
          line.dataset.route === selected ? "1" : ".35",
        );
    } catch {
      if (isCurrent())
        message(
          mapHost,
          "VWorld 배경지도를 불러오지 못했습니다. 키·도메인·연결을 확인해 주세요. 좌표 도식과 경로 수치는 유지됩니다.",
          "error",
        );
    } finally {
      pending.delete(mapAbort);
      mapButton.disabled = false;
    }
  });
  target.append(svg);
  element(
    "p",
    view.routes.length === 1
      ? "보라 실선: 표시된 경로"
      : view.provider === "tmap"
        ? "보라 실선: 받은 후보 중 짧은 길 · 청록 점선: 다른 보행 옵션"
        : "보라 실선: 최단 · 청록 점선: 시설 조건 우선",
    target,
    "support",
  );
  const cards = element("div", "", target, "route-options");
  const showDetail = element(
    "button",
    "선택한 경로의 비교 근거 보기",
    target,
    "primary",
  );
  showDetail.type = "button";
  const detail = element("div", "", target, "card route-detail");
  detail.hidden = true;
  const chosen = element("div", "", target, "chosen-route");
  chosen.hidden = true;
  let selected;
  function changeConditions() {
    routePhase("input");
    $("route-input").open = true;
    $("route-input").scrollIntoView({ block: "start" });
  }
  function select(row) {
    selected = row;
    const letter = String.fromCharCode(65 + view.routes.indexOf(row));
    for (const button of cards.children)
      button.setAttribute(
        "aria-pressed",
        String(button.dataset.route === row.id),
      );
    for (const line of target.querySelectorAll("polyline[data-route]"))
      line.setAttribute("opacity", line.dataset.route === row.id ? "1" : ".35");
    detail.replaceChildren();
    element("h2", "경로 " + letter + "의 비교 근거", detail);
    const metrics = element("div", "", detail, "details-grid");
    for (const [label, value] of [
      ["거리", row.distance_m.toLocaleString("ko-KR") + "m"],
      ["예상 시간", durationLabel(row)],
      ["CCTV 인접 구간", row.cctv_percent + "%"],
      ["조명 인접 구간", row.light_percent + "%"],
    ]) {
      const box = element("div", label, metrics, "metric");
      element("strong", value, box);
    }
    const base = view.routes[0];
    element(
      "p",
      "최단 대비 " +
        (row.distance_m - base.distance_m).toFixed(1) +
        "m · CCTV " +
        (row.cctv_percent - base.cctv_percent).toFixed(2) +
        "%p · 조명 " +
        (row.light_percent - base.light_percent).toFixed(2) +
        "%p",
      detail,
      "support",
    );
    element(
      "p",
      "설치 위치 기준의 인접 비율입니다. 현재 작동·촬영 범위·현장 통행은 확인하지 않았습니다.",
      detail,
      "notice",
    );
    const confirm = element("button", "이 경로 선택하기", detail, "primary");
    confirm.type = "button";
    confirm.addEventListener("click", () => {
      routePhase("chosen");
      chosen.hidden = false;
      chosen.replaceChildren();
      element("span", "이번 페이지의 선택", chosen, "result-source");
      element("h2", "경로 " + letter + "를 선택했어요", chosen);
      element(
        "p",
        row.label + " · " + row.distance_m + "m · 약 " + durationLabel(row),
        chosen,
      );
      element(
        "p",
        "실시간 길 안내나 현장 통행 확인을 시작한 것은 아닙니다. 선택은 페이지를 떠나면 지워집니다.",
        chosen,
        "support",
      );
      const again = element("button", "경로 다시 비교", chosen, "primary");
      again.type = "button";
      again.addEventListener("click", () => {
        chosen.hidden = true;
        detail.hidden = true;
        routePhase("compare");
        svg.scrollIntoView({ block: "start" });
      });
      const edit = element("button", "조건 수정하기", chosen, "secondary");
      edit.type = "button";
      edit.addEventListener("click", changeConditions);
      chosen.scrollIntoView({ block: "start" });
    });
  }
  for (const [i, row] of view.routes.entries()) {
    const button = element("button", "", cards, "route-card route-choice");
    button.type = "button";
    button.dataset.route = row.id;
    element("span", String.fromCharCode(65 + i), button, "route-token");
    const content = element("div", "", button, "route-choice-body");
    element(
      "strong",
      row.label + (row.id === view.recommended_route_id ? " · 추천 후보" : ""),
      content,
    );
    element(
      "p",
      "CCTV " +
        row.cctv_percent +
        "% · 조명 " +
        row.light_percent +
        "%" +
        (row.eligible_for_recommendation === false
          ? " · 우회 한도 초과, 비교용"
          : ""),
      content,
    );
    const short = element(
      "span",
      row.distance_m + "m · " + durationLabel(row),
      button,
    );
    short.dataset.shortMetric = "true";
    button.addEventListener("click", () => {
      select(row);
      chosen.hidden = true;
      routePhase(detail.hidden ? "compare" : "detail");
    });
  }
  select(
    view.routes.find((row) => row.id === view.recommended_route_id) ||
      view.routes[0],
  );
  showDetail.addEventListener("click", () => {
    detail.hidden = false;
    routePhase("detail");
    detail.scrollIntoView({ block: "start" });
  });
  const edit = element("button", "이동 조건 수정", target, "text-button");
  edit.type = "button";
  edit.addEventListener("click", changeConditions);
  const sources = element("details", "", target);
  element("summary", "계산식·자료·미확인 범위", sources);
  for (const row of view.routes) {
    if (row.walk_review)
      element(
        "p",
        row.label +
          ": 보행 검토 " +
          row.walk_review.reviewed_segments +
          "/" +
          row.walk_review.total_segments +
          "구간. " +
          row.walk_review.message,
        sources,
        "support",
      );
  }

  element(
    "p",
    view.provider === "tmap"
      ? "TMAP 옵션별 경로를 받은 뒤 비교합니다. 시설 우선 조건은 제공사 경로 생성에 쓰이지 않습니다. 비교 비용 = 형상 길이 × [1 + 조명가중치×(1−조명 인접비율) + CCTV가중치×(1−CCTV 인접비율)]. 빠른 길은 제공 예상 시간 기준입니다."
      : "도로 조각 비용 = 길이 × [1 + 조명가중치×(1−조명 인접비율) + CCTV가중치×(1−CCTV 인접비율)]",
    sources,
  );
  element(
    "p",
    "사용 가중치: 조명 " +
      view.parameters.weights_used.light +
      " / CCTV " +
      view.parameters.weights_used.cctv +
      " · 거리 상한 " +
      view.parameters.max_detour +
      "배",
    sources,
  );
  element(
    "p",
    "CCTV 원본 " +
      view.sources.cctv.source_rows +
      "행 중 선택 " +
      view.sources.cctv.selected_rows +
      "행 · 목적 " +
      view.sources.cctv.purposes.join(", "),
    sources,
  );
  element(
    "p",
    "CCTV 기준일: " +
      Object.keys(view.sources.cctv.basis_dates).join(", ") +
      " · 조명: " +
      view.sources.light.basis_date,
    sources,
  );
  element(
    "p",
    "요청 지점에서 도로 노드까지: " + view.endpoint_snap_m.join("m / ") + "m",
    sources,
  );
  for (const limitation of view.limitations)
    element("p", limitation, sources, "support");
  for (const [label, url] of [
    [
      view.provider === "tmap"
        ? "경로: TMAP 보행자 경로안내"
        : "OpenStreetMap contributors · ODbL",
      view.provider === "tmap"
        ? "https://tmap-skopenapi.readme.io/reference/보행자-경로안내"
        : "https://www.openstreetmap.org/copyright",
    ],
    [
      view.provider === "tmap" ? "TMAP 제공사 안내" : "지도 오류 수정",
      view.provider === "tmap"
        ? "https://openapi.sk.com/"
        : "https://www.openstreetmap.org/fixthemap",
    ],
  ]) {
    const a = element("a", label, sources);
    a.href = url;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    element("br", "", sources);
  }
  target.scrollIntoView({ block: "start" });
}
for (const field of ["origin", "destination"]) {
  const input = $("live-" + field + "-query");
  input.addEventListener("input", () => {
    delete liveLocations[field];
    liveRevision[field]++;
    $("live-" + field + "-candidates").replaceChildren();
    $("live-" + field + "-selected").textContent =
      "검색 결과에서 위치를 다시 선택해 주세요.";
    $("live-route-result").replaceChildren();
  });
  $("live-" + field + "-search").addEventListener("click", async () => {
    const button = $("live-" + field + "-search"),
      target = $("live-" + field + "-candidates"),
      revision = ++liveRevision[field];
    button.disabled = true;
    delete liveLocations[field];
    $("live-" + field + "-selected").textContent =
      "검색 결과에서 위치를 선택해 주세요.";
    $("live-route-result").replaceChildren();
    try {
      const view = await post("/maps/places/search", {
        query: input.value,
        mode: $("live-search-mode").value,
      });
      if (!view || revision !== liveRevision[field]) return;
      target.replaceChildren();
      element("p", view.message, target);
      for (const place of view.candidates) {
        const choice = element(
          "button",
          place.name + " · " + (place.road_address || place.parcel_address),
          target,
          "route-card",
        );
        choice.type = "button";
        choice.addEventListener("click", () => {
          liveLocations[field] = { lat: place.lat, lng: place.lng };
          $("live-" + field + "-selected").textContent =
            "선택: " +
            place.name +
            " · " +
            (place.road_address || place.parcel_address);
          target.replaceChildren();
          $("live-route-result").replaceChildren();
        });
      }
    } catch {
      if (revision === liveRevision[field])
        message(
          target,
          "장소 검색을 처리하지 못했습니다. 입력은 유지했습니다.",
          "error",
        );
    } finally {
      button.disabled = false;
    }
  });
}
$("live-search-mode").addEventListener("change", () => {
  for (const f of ["origin", "destination"]) {
    delete liveLocations[f];
    liveRevision[f]++;
    $("live-" + f + "-candidates").replaceChildren();
    $("live-" + f + "-selected").textContent =
      "검색 방식이 바뀌었습니다. 위치를 다시 선택해 주세요.";
  }
  $("live-route-result").replaceChildren();
});
$("live-clear").addEventListener("click", () => {
  abortRequests();
  clearLive();
});
$("live-place-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const target = $("live-route-result"),
    button = $("live-route-button");
  if (!liveLocations.origin || !liveLocations.destination) {
    message(
      target,
      "출발지와 도착지를 검색한 뒤 결과에서 각각 선택해 주세요.",
      "error",
    );
    return;
  }
  const originRevision = liveRevision.origin,
    destinationRevision = liveRevision.destination,
    settingsRevision = liveRevision.settings;
  button.disabled = true;
  try {
    const view = await post("/research/routes/selected", {
      origin: liveLocations.origin,
      destination: liveLocations.destination,
      departure: $("live-date").value + "T" + $("live-time").value,
      preference: $("live-preference").value,
    });
    if (
      view &&
      originRevision === liveRevision.origin &&
      destinationRevision === liveRevision.destination &&
      settingsRevision === liveRevision.settings
    )
      renderFacilityRoutes(view, target);
  } catch {
    if (
      originRevision === liveRevision.origin &&
      destinationRevision === liveRevision.destination &&
      settingsRevision === liveRevision.settings
    )
      message(
        target,
        "경로를 비교하지 못했어요. 입력은 그대로 두었으니 위치와 시각을 확인한 뒤 다시 시도해 주세요.",
        "error",
      );
  } finally {
    button.disabled = false;
  }
});

for (const id of ["live-date", "live-time", "live-preference"])
  $(id).addEventListener("input", () => {
    liveRevision.settings++;
    $("live-route-result").replaceChildren();
  });

$("live-place-form").addEventListener("input", () => routePhase("input"));
$("report-form").addEventListener("focusin", (event) => {
  const id = event.target.id;
  if (id === "report-place-query") reportStep(1);
  else if (id === "report-facility" || id === "report-problem") reportStep(2);
  else if (id === "report-text") reportStep(3);
});
$("report-form").addEventListener("submit", () => reportStep(4));
for (const field of ["origin", "destination"])
  $("live-" + field + "-query").addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      $("live-" + field + "-search").click();
    }
  });

$("screen-back").addEventListener("click", (event) => {
  event.stopPropagation();
  if (
    current === "route" &&
    activeRouteTarget &&
    activeRoutePhase !== "input"
  ) {
    const detail = activeRouteTarget.querySelector(".route-detail"),
      chosen = activeRouteTarget.querySelector(".chosen-route");
    if (activeRoutePhase === "chosen") {
      chosen.hidden = true;
      detail.hidden = false;
      routePhase("detail");
      detail.scrollIntoView({ block: "start" });
    } else if (activeRoutePhase === "detail") {
      detail.hidden = true;
      routePhase("compare");
      activeRouteTarget.scrollIntoView({ block: "start" });
    } else {
      routePhase("input");
      $("route-input").open = true;
      $("route-input").scrollIntoView({ block: "start" });
    }
  } else navigate("home");
});

async function searchReportPlace() {
  const button = $("report-place-search"),
    target = $("report-place-candidates"),
    revision = ++reportRevision;
  reportPlace = null;
  $("report-place-selected").textContent =
    "검색 결과에서 위치를 선택해 주세요.";
  button.disabled = true;
  try {
    const view = await post("/maps/places/search", {
      query: $("report-place-query").value,
      mode: "place",
    });
    if (!view || revision !== reportRevision) return;
    target.replaceChildren();
    element("p", view.message, target);
    for (const place of view.candidates) {
      const address = place.road_address || place.parcel_address;
      const choice = element(
        "button",
        place.name + " · " + address,
        target,
        "route-card",
      );
      choice.type = "button";
      choice.addEventListener("click", () => {
        reportPlace = { name: place.name, lat: place.lat, lng: place.lng };
        $("report-place-selected").textContent =
          "선택: " + place.name + " · " + address;
        target.replaceChildren();
        $("report-confirm").hidden = true;
        $("report-consent").checked = false;
        lastPreview = null;
        reportSnapshot = null;
        reportStep(2);
      });
    }
  } catch {
    if (revision === reportRevision)
      message(
        target,
        "위치를 찾지 못했어요. 입력은 그대로 두었으니 다시 시도해 주세요.",
        "error",
      );
  } finally {
    button.disabled = false;
  }
}
$("report-place-search").addEventListener("click", searchReportPlace);
$("report-place-query").addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    event.preventDefault();
    searchReportPlace();
  }
});
$("report-place-query").addEventListener("input", clearReportPlace);
