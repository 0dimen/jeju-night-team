import { drawVworld } from "/app/vworld.mjs";
import { createPageConversation } from "/demo/page_conversation.mjs";
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
    else if (label.includes("시설 이슈"))
      glyph = "M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4";
  }
  path.setAttribute("d", glyph);
  svg.append(path);
  span.replaceChildren(svg);
}
const points = {
  제주시청: { lat: 33.4996, lng: 126.5312 },
  탑동광장: { lat: 33.517, lng: 126.525 },
  제주공항: { lat: 33.5104, lng: 126.4913 },
  동문시장: { lat: 33.5117, lng: 126.526 },
};
const controller = createPageConversation();
let researchState = {};
let activeRoutePhase = "input",
  activeRouteTarget = null;
let liveLocations = {},
  liveRevision = { origin: 0, destination: 0, settings: 0 };
let current = "home",
  generation = 0,
  pending = new Set(),
  lastPreview = null,
  reportSnapshot = null;
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
  $("research-tools").open = false;
  $("synthetic-tools").open = false;
  clearLive();
  researchState = {};
  $("research-chat-form")?.reset();
  $("research-chat-result")?.replaceChildren();
  $("facility-result")?.replaceChildren();
  controller.clear();
  $("route-form").reset();
  $("chat-form").reset();
  $("route-result").replaceChildren();
  $("chat-result").replaceChildren();
}
function abortRequests() {
  generation++;
  for (const request of pending) request.abort();
  pending.clear();
}
function wipe() {
  document.getElementById("facility-form")?.reset();
  document.getElementById("facility-result")?.replaceChildren();
  abortRequests();
  clearRoute();
  $("report-form").reset();
  reportStep(1);
  $("report-result").replaceChildren();
  $("report-confirm").hidden = true;
  $("report-consent").checked = false;
  lastPreview = null;
  reportSnapshot = null;
  $("data-result").replaceChildren();
  message($("receipt"), "이번 페이지에서 확인한 접수 내역이 없습니다.");
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
  if (target) navigate(target.dataset.screen);
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
function showConversation(view) {
  if (view.kind === "route") {
    renderRoutes(view);
    message($("chat-result"), "비교 결과를 위에 표시했습니다.");
  } else if (view.kind === "data_question") showData(view, $("chat-result"));
  else if (view.kind === "report_preview") showPreview(view, $("chat-result"));
  else
    message(
      $("chat-result"),
      view.message || "입력을 확인해 주세요.",
      view.kind === "emergency" ? "error" : undefined,
    );
}
function renderRoutes(view) {
  const target = $("route-result");
  target.replaceChildren();
  element("h2", "같은 목적지, 경로 비교", target);
  element("p", view.message || "합성 경로·시설 비교입니다.", target, "notice");
  const comparison = view.comparison_table;
  const map = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  map.setAttribute("viewBox", "0 0 380 170");
  map.classList.add("route-map");
  map.setAttribute("role", "img");
  map.setAttribute(
    "aria-label",
    "합성 경로 A 보라 실선과 B 청록 점선 도식. 실제 지도가 아닙니다.",
  );
  const svgNode = (tag, attrs, text) => {
    const n = document.createElementNS(map.namespaceURI, tag);
    for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
    if (text) n.textContent = text;
    map.append(n);
    return n;
  };
  svgNode(
    "text",
    { x: 18, y: 28, fill: "#c4bcd9", "font-size": 13 },
    "합성 경로 도식 · 실제 지도 아님",
  );
  svgNode("path", {
    "data-route": "A",
    d: "M45 65 H310",
    stroke: "#af86ff",
    "stroke-width": 5,
    fill: "none",
  });
  svgNode("text", { x: 18, y: 70, fill: "#af86ff", "font-size": 16 }, "A");
  svgNode("path", {
    "data-route": "B",
    d: "M45 120 H350",
    stroke: "#89e3dd",
    "stroke-width": 5,
    "stroke-dasharray": "7 6",
    fill: "none",
  });
  svgNode("text", { x: 18, y: 125, fill: "#89e3dd", "font-size": 16 }, "B");
  if (
    view.synthetic === true &&
    comparison.rows.every((row) => ["A", "B"].includes(row.id))
  )
    target.append(map);
  else
    element(
      "p",
      "경로 좌표를 표시할 지도는 연결 전입니다. 아래 수치와 출처를 확인해 주세요.",
      target,
      "notice",
    );
  element("p", comparison.value_meaning, target, "support");
  const cards = element("div", "", target);
  const detail = element("div", "", target, "card");
  function select(row) {
    map.dataset.selected = row.id;
    for (const button of cards.children)
      button.setAttribute(
        "aria-pressed",
        String(button.dataset.route === row.id),
      );
    map.setAttribute(
      "aria-label",
      "선택한 합성 경로 " + row.id + " 도식. 실제 지도가 아닙니다.",
    );
    detail.replaceChildren();
    element("h2", "경로 " + row.id + "의 비교 근거", detail);
    const metrics = element("div", "", detail, "details-grid");
    for (const [label, value] of [
      ["거리", row.distance],
      ["예상 시간", row.duration],
      [
        "CCTV 인접 비율",
        row.cctv_comparison_value == null
          ? "자료 없음"
          : row.cctv_comparison_value + "%",
      ],
      ["조명", "자료 없음"],
    ]) {
      const box = element("div", label, metrics, "metric");
      element("strong", value, box);
    }
    element("p", comparison.rank_reason, detail);
    element("p", comparison.tradeoff, detail);
    for (const source of comparison.sources)
      element(
        "p",
        "출처: " + source.name + " / 기준: " + source.observed_at,
        detail,
        "support",
      );
    for (const limitation of comparison.limitations)
      element("p", limitation, detail, "support");
  }
  for (const row of comparison.rows) {
    const button = element("button", "", cards, "route-card");
    button.type = "button";
    button.dataset.route = row.id;
    element(
      "strong",
      row.id + " · " + row.distance + " · " + row.duration,
      button,
    );
    element(
      "p",
      "CCTV 인접 " +
        (row.cctv_comparison_value == null
          ? "자료 없음"
          : row.cctv_comparison_value + "%") +
        " · 비교 순위 " +
        row.rank,
      button,
    );
    button.addEventListener("click", () => select(row));
  }
  if (comparison.rows.length) select(comparison.rows[0]);
}
$("route-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = $("compare-button");
  button.disabled = true;
  button.textContent = "비교하고 있어요…";
  const epoch = generation;
  try {
    if ($("origin").value === $("destination").value)
      throw new Error("출발지와 도착지를 다르게 선택해 주세요.");
    controller.clear();
    controller.setLocations({
      origin: { name: $("origin").value, ...points[$("origin").value] },
      destination: {
        name: $("destination").value,
        ...points[$("destination").value],
      },
    });
    controller.setPreferences([
      document.querySelector("[name=preference]:checked").value,
    ]);
    const view = await controller.send(
      $("departure-date").value + "T" + $("departure-time").value,
    );
    if (view && epoch === generation) showConversation(view);
  } catch (error) {
    if (epoch === generation)
      message($("route-result"), error.message, "error");
  } finally {
    button.disabled = false;
    button.textContent = "두 경로 비교하기";
  }
});
$("chat-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = $("chat-send"),
    epoch = generation;
  button.disabled = true;
  try {
    const view = await controller.send($("chat-input").value);
    if (view && epoch === generation) {
      showConversation(view);
      if (view.kind === "emergency") {
        clearRoute();
        $("synthetic-tools").open = true;
        message($("chat-result"), view.message, "error");
        $("chat-result").scrollIntoView({ block: "start" });
      }
    }
  } catch (error) {
    if (epoch === generation) message($("chat-result"), error.message, "error");
  } finally {
    button.disabled = false;
  }
});
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
    location: $("report-location").value,
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
      "위치·유형·내용과 시연 동의를 확인해 주세요.",
      $("report-result"),
    );
    return;
  }
  if (JSON.stringify(reportInput()) !== JSON.stringify(reportSnapshot)) return;
  const button = $("report-submit");
  button.disabled = true;
  try {
    const point = points[reportSnapshot.location];
    const view = await post("/agent/chat", {
      text: reportSnapshot.text,
      context: { ...point, user_choice: reportSnapshot.user_choice },
    });
    if (view?.stored && view.report) {
      const receipt = $("receipt");
      receipt.replaceChildren();
      element("h2", "합성 제보가 접수됐어요", receipt);
      element("p", "접수번호: " + view.report.id, receipt);
      element("span", "검토 대기", receipt, "badge");
      element(
        "p",
        "행정기관에 수리 요청한 것이 아니며 경로 계산에 아직 반영하지 않습니다.",
        receipt,
      );
      $("report-confirm").hidden = true;
      lastPreview = null;
      reportSnapshot = null;
      navigate("my");
    } else if (view) showConversation(view);
  } catch (error) {
    message($("report-result"), error.message, "error");
  } finally {
    button.disabled = false;
  }
});

function renderFacilityRoutes(view, target = $("facility-result")) {
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
    "실제 공개 좌표·도로망으로 계산한 연구 후보입니다. 실시간 시설 상태나 안전을 보증하지 않습니다.",
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
    "VWorld 배경지도·시설 위치 불러오기",
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
    if (view.region === "custom") {
      $("route-input").open = true;
      $("route-input").scrollIntoView({ block: "start" });
    } else {
      $("research-tools").open = true;
      $("facility-form").scrollIntoView({ block: "start" });
    }
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
$("facility-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = $("facility-button");
  button.disabled = true;
  button.textContent = "도로망에서 찾고 있어요…";
  try {
    const view = await post("/research/routes/facilities", {
      region: $("facility-region").value,
      preference: $("facility-preference").value,
      cctv_source: $("facility-source").value,
      light_radius: Number($("facility-light-radius").value),
      cctv_radius: Number($("facility-cctv-radius").value),
      weight: Number($("facility-weight").value),
      max_detour: Number($("facility-detour").value),
    });
    if (view) renderFacilityRoutes(view);
  } catch (error) {
    message(
      $("facility-result"),
      "공개 자료 경로를 계산하지 못했습니다. 데이터 연결과 설정을 확인해 주세요. 합성 경로로 대신하지 않았습니다.",
      "error",
    );
  } finally {
    button.disabled = false;
    button.textContent = "공개 자료로 자동 경로 찾기";
  }
});

$("research-chat-reset").addEventListener("click", () => {
  abortRequests();
  researchState = {};
  $("research-chat-form").reset();
  $("research-chat-result").replaceChildren();
  $("facility-result").replaceChildren();
});
$("research-chat-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = $("research-chat-send");
  button.disabled = true;
  try {
    const view = await post("/research/agent/conversation", {
      text: $("research-chat-input").value,
      state: researchState,
    });
    if (!view) return;
    researchState = view.state || {};
    $("facility-result").replaceChildren();
    if (view.kind === "facility_routes") {
      renderFacilityRoutes(view);
      message($("research-chat-result"), view.message);
    } else if (view.kind === "data_question")
      showData(view, $("research-chat-result"));
    else if (view.kind === "report_preview")
      showPreview(view, $("research-chat-result"));
    else {
      if (view.kind === "emergency") {
        clearRoute();
        $("research-tools").open = true;
      }
      message(
        $("research-chat-result"),
        view.message || "공개 구간 입력을 확인해 주세요.",
        view.kind === "emergency" ? "error" : undefined,
      );
    }
    $("research-chat-input").value = "";
  } catch (error) {
    message(
      $("research-chat-result"),
      "공개 자료 대화를 처리하지 못했습니다. 입력은 유지했습니다. 합성 경로로 대신하지 않았습니다.",
      "error",
    );
  } finally {
    button.disabled = false;
  }
});

fetch("/runtime/status", { cache: "no-store" })
  .then((response) => {
    if (!response.ok) throw new Error("status");
    return response.json();
  })
  .then((info) => {
    const status = document.getElementById("runtime-connection");
    status.textContent =
      (info.facility_data_connected
        ? "공개 경로 자료 연결됨"
        : "공개 경로 자료 미연결") +
      " · 규칙형 에이전트 연결됨" +
      (info.built_at
        ? " · 준비 시각 " + new Date(info.built_at).toLocaleString("ko-KR")
        : "");
  })
  .catch(() => {
    document.getElementById("runtime-connection").textContent =
      "연결 상태를 확인하지 못했습니다. 다시 접속해 주세요.";
  });

$("tmap-button").addEventListener("click", async () => {
  const button = $("tmap-button");
  button.disabled = true;
  try {
    const view = await post("/research/routes/tmap", {
      region: $("facility-region").value,
      preference: $("facility-preference").value,
      cctv_source: $("facility-source").value,
      light_radius: Number($("facility-light-radius").value),
      cctv_radius: Number($("facility-cctv-radius").value),
      weight: Number($("facility-weight").value),
      max_detour: Number($("facility-detour").value),
    });
    if (view) renderFacilityRoutes(view);
  } catch {
    message(
      $("facility-result"),
      "TMAP 보행 후보를 불러오지 못했습니다. 키·이용 권한·한도·시설 자료 연결을 확인해 주세요. 합성 경로로 대신하지 않았습니다.",
      "error",
    );
  } finally {
    button.disabled = false;
  }
});

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
        "선택한 위치의 경로·시설 비교를 처리하지 못했습니다. 위치·시각·키·한도를 확인해 주세요. 입력은 유지했습니다. 합성 경로로 대신하지 않았습니다.",
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
  if (id === "report-location") reportStep(1);
  else if (id === "report-facility" || id === "report-problem") reportStep(2);
  else if (id === "report-text") reportStep(3);
});
$("report-form").addEventListener("submit", () => reportStep(4));
for (const id of ["research-chat-send", "research-chat-reset", "tmap-button"])
  $(id).classList.add("secondary");
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
      if (activeRouteTarget.id === "live-route-result") {
        $("route-input").open = true;
        $("route-input").scrollIntoView({ block: "start" });
      } else {
        $("research-tools").open = true;
        $("facility-form").scrollIntoView({ block: "start" });
      }
    }
  } else navigate("home");
});
