import { drawVworld } from "/app/vworld.mjs";
import {
  addReport,
  clearReports,
  hasViews,
  initScreens,
  openMyDetail,
  resetViews,
  viewBack,
} from "/app/screens.mjs";
const $ = (id) => document.getElementById(id);
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
  reportRevision = 0,
  lastRouteView = null;
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
  $("route").dataset.phase = phase;
  if (current === "route")
    $("screen-title").textContent = {
      input: "이동 조건 입력",
      compare: "두 경로 비교",
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
const reportLabels = {
  streetlight: "가로등·보안등",
  cctv: "CCTV",
  walkway: "보행로",
  other: "기타·확인 필요",
  not_working: "작동하지 않음",
  flickering: "깜빡임",
  too_dark: "어두움",
  damaged: "파손",
  obstructed: "통행 방해",
};
const reportStepCopy = {
  1: ["제보 위치 확인", "문제가 있었던 위치인가요?", "GPS로 위치를 확인하거나 장소를 검색해 주세요."],
  2: ["문제 유형 선택", "어떤 문제가 있었나요?", "현장에서 발견한 문제와 가장 가까운 항목을 선택하세요."],
  3: ["상세 설명 작성", "상황을 자세히 적어 주세요", "문제와 주변 위치를 설명하면 확인하기 쉬워요."],
  4: ["내용 확인과 접수", "이 내용으로 접수할까요?", "위치나 설명을 바꾸려면 내용을 수정하세요."],
  5: ["접수 완료", "", ""],
};
let activeReportStep = 1;
function straightMeters(a, b) {
  const rad = Math.PI / 180,
    dLat = (b.lat - a.lat) * rad,
    dLng = (b.lng - a.lng) * rad;
  const h =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(a.lat * rad) * Math.cos(b.lat * rad) * Math.sin(dLng / 2) ** 2;
  return 2 * 6371000 * Math.asin(Math.sqrt(h));
}
function checkedValue(name) {
  return document.querySelector(`input[name="${name}"]:checked`)?.value;
}
function reportStep(step) {
  activeReportStep = step;
  const [title, heading, sub] = reportStepCopy[step];
  if (current === "report") $("screen-title").textContent = title;
  $("report-heading").textContent = heading;
  $("report-sub").textContent = sub;
  $("report").dataset.step = String(step);
  $("report-map-pin").toggleAttribute("hidden", !reportPlace);
  for (const panel of document.querySelectorAll(".report-step"))
    panel.hidden = panel.dataset.step !== String(step);
  for (const item of document.querySelectorAll(".report-progress li")) {
    const n = Number(item.dataset.reportStep);
    item.classList.toggle("done", n < step);
    item.querySelector("button").disabled = n > step;
    if (n === step) item.setAttribute("aria-current", "step");
    else item.removeAttribute("aria-current");
  }
  if (step !== 4) {
    $("report-confirm").hidden = true;
    $("report-result").replaceChildren();
  }
  if (step === 3)
    $("report-place-row").textContent = reportPlace?.label || "선택하지 않음";
  if (step === 4) {
    const summary = $("report-summary");
    summary.replaceChildren();
    for (const [label, value] of [
      ["위치", reportPlace?.label || "선택하지 않음"],
      ["문제 유형", facilityTitle[checkedValue("report-facility")]],
      ["상태", problemTitle[checkedValue("report-problem")]],
    ]) {
      const row = element("div", "", summary);
      element("dt", label, row);
      element("dd", value, row);
    }
    $("report-summary-text").textContent = $("report-text").value;
  }
}
const facilityTitle = {
  streetlight: "가로등 문제",
  cctv: "CCTV 시설 문제",
  walkway: "보행로 불편",
  other: "기타",
};
const problemTitle = {
  not_working: "꺼져 있음",
  flickering: "깜빡임",
  too_dark: "어두움",
  damaged: "파손",
  obstructed: "통행 방해",
  other: "기타",
};
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
    $("live-" + field + "-value").textContent = "선택해 주세요";
    togglePanel(field, true);
  }
  setDefaultTime();
}
function togglePanel(field, open) {
  const button = $("live-" + field + "-toggle"),
    panel = $("live-" + field + "-panel");
  const next = open ?? panel.hidden;
  panel.hidden = !next;
  button.setAttribute("aria-expanded", String(next));
}
function setDefaultTime() {
  const now = new Date(Date.now() + 9 * 3600 * 1000);
  const iso = now.toISOString();
  $("live-date").value = iso.slice(0, 10);
  $("live-time").value = iso.slice(11, 16);
  updateTimeValue();
}
function updateTimeValue() {
  const d = $("live-date").value,
    t = $("live-time").value;
  if (!d || !t) {
    $("live-time-value").textContent = "날짜와 시각을 골라 주세요";
    return;
  }
  const [h, m] = t.split(":").map(Number);
  const today = new Date(Date.now() + 9 * 3600 * 1000).toISOString().slice(0, 10);
  const day = d === today ? "오늘" : d.slice(5).replace("-", "월 ") + "일";
  $("live-time-value").textContent =
    day + " " + (h < 12 ? "오전 " : "오후 ") + ((h % 12) || 12) + ":" + String(m).padStart(2, "0");
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
  $("report-map-pin").setAttribute("hidden", "");
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
  updateReportCount();
  $("report-result").replaceChildren();
  $("report-confirm").hidden = true;
  $("report-consent").checked = false;
  lastPreview = null;
  reportSnapshot = null;
  $("receipt").replaceChildren();
  clearReports();
  lastRouteView = null;
  for (const button of document.querySelectorAll("button"))
    button.disabled = false;
  reportStep(1);
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
          compare: "두 경로 비교",
          detail: "경로 상세",
          chosen: "선택한 이동 경로",
        }[activeRoutePhase]
      : {
          report: reportStepCopy[activeReportStep][0],
          data: "지역 데이터",
        }[screen] || "";
  for (const section of document.querySelectorAll(".screen"))
    section.hidden = section.id !== screen;
  if (hasViews(screen)) resetViews(screen);
  if (screen === "report" && activeReportStep === 5) reportStep(1);
  const tab =
    { population: "data", region: "data", facility: "route" }[screen] || screen;
  for (const button of document.querySelectorAll("nav button")) {
    if (button.dataset.screen === tab)
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
    if (!response.ok) {
      const error = new Error(
        "처리하지 못했습니다. 입력을 유지했으니 확인 후 다시 시도해 주세요.",
      );
      error.status = response.status;
      try {
        const detail = (await response.json()).detail;
        if (typeof detail === "string") error.detail = detail;
      } catch {}
      throw error;
    }
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
    const labels = reportLabels;
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
function reportInput() {
  return {
    text: $("report-text").value,
    user_choice: {
      facility: checkedValue("report-facility"),
      problem: checkedValue("report-problem"),
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
    reportStep(1);
    message(
      $("report-result"),
      "문제 위치를 검색해 결과에서 선택해 주세요.",
      "error",
    );
    return;
  }
  if (!$("report-text").value.trim()) {
    reportStep(3);
    message($("report-result"), "상황 설명을 적어 주세요.", "error");
    $("report-text").focus();
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
      reportStep(4);
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
      const id = String(view.report.id).replace(/^SYNTHETIC-/, "");
      const facility = reportSnapshot.user_choice.facility,
        problem = reportSnapshot.user_choice.problem;
      addReport({
        id,
        title: facilityTitle[facility],
        facility,
        place: reportSnapshot.location.name,
        problemLabel: problemTitle[problem],
      });
      const receipt = $("receipt");
      receipt.replaceChildren();
      const mark = element("div", "", receipt, "success-mark");
      mark.innerHTML =
        '<svg class="ico" width="44" height="44" aria-hidden="true"><use href="#i-check"/></svg>';
      element("h1", "제보가 접수됐어요", receipt);
      element("p", "검토한 뒤 다음 경로 분석에 반영해요.", receipt, "support");
      const card = element("div", "", receipt, "card rows-card");
      element("h2", "접수 내역", card);
      const dl = element("dl", "", card);
      for (const [k, v] of [
        ["접수번호", id],
        ["위치", reportSnapshot.location.name],
        ["문제 유형", facilityTitle[facility] + " · " + problemTitle[problem]],
        ["처리 상태", "검토 대기"],
      ]) {
        const row = element("div", "", dl);
        element("dt", k, row);
        element("dd", v, row);
      }
      const info = element("p", "", receipt, "info-card success");
      element(
        "span",
        "시범 운영 중이라 기관에는 전달되지 않아요. 검토 후 게시된 내용만 경로 분석에 반영돼요.",
        info,
      );
      const actions = element("div", "", receipt, "step-actions two");
      const mine = element("button", "내 제보 보기", actions, "primary");
      mine.type = "button";
      mine.id = "report-go-my";
      mine.addEventListener("click", () => {
        navigate("my");
        openMyDetail(id);
      });
      const home = element("button", "홈으로 돌아가기", actions, "secondary");
      home.type = "button";
      home.addEventListener("click", () => navigate("home"));
      $("report-confirm").hidden = true;
      lastPreview = null;
      reportSnapshot = null;
      $("report-form").reset();
      clearReportPlace();
      $("report-result").replaceChildren();
      updateReportCount();
      reportStep(5);
      window.scrollTo({ top: 0 });
    } else if (view) showConversation(view, $("report-result"));
  } catch (error) {
    message($("report-result"), error.message, "error");
  } finally {
    button.disabled = false;
  }
});

const ROUTE_STYLES = [
  { color: "#af86ff", dash: null, name: "보라 실선" },
  { color: "#89e3dd", dash: "7 6", name: "청록 점선" },
  { color: "#ffdaa3", dash: "2 6", name: "주황 점선" },
];
function routeStyle(index) {
  return ROUTE_STYLES[Math.min(index, ROUTE_STYLES.length - 1)];
}
function routeLetter(index) {
  return String.fromCharCode(65 + index);
}
function distanceLabel(meters) {
  return meters >= 1000
    ? (meters / 1000).toFixed(1) + " km"
    : Math.round(meters) + " m";
}
function minutesLabel(row) {
  const seconds = row.provider_duration_seconds ?? row.duration_minutes * 60;
  return Math.max(1, Math.round(seconds / 60)) + "분";
}
function svgNode(parent, tag, attrs, text) {
  const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [key, value] of Object.entries(attrs))
    node.setAttribute(key, value);
  if (text !== undefined) node.textContent = text;
  parent.append(node);
  return node;
}
function renderFacilityRoutes(view, target) {
  activeRouteTarget = target;
  lastRouteView = view;
  target.replaceChildren();
  routePhase("compare");
  const count = view.routes.length;
  element(
    "h2",
    count === 1
      ? "경로 후보를 확인해 보세요"
      : "같은 목적지, " + (["두", "세"][count - 2] || count) + " 가지 길",
    target,
    "result-heading",
  );
  element(
    "p",
    "거리와 예상 시간, CCTV·조명 위치 인접성을 비교해요.",
    target,
    "support result-sub",
  );
  const frame = element("div", "", target, "map-frame");
  const svg = svgNode(frame, "svg", {
    viewBox: "0 0 380 250",
    role: "img",
    class: "route-map",
    "aria-label":
      "경로 좌표 도식. " +
      view.routes
        .map((row, i) => "경로 " + routeLetter(i) + " " + routeStyle(i).name)
        .join(", ") +
      ". 배경지도·현재 위치 안내가 아닙니다.",
  });
  const grid = svgNode(svg, "g", { class: "map-grid", "aria-hidden": "true" });
  for (let x = 30; x < 380; x += 58)
    svgNode(grid, "line", { x1: x, y1: 0, x2: x + 12, y2: 250 });
  for (let y = 28; y < 250; y += 52)
    svgNode(grid, "line", { x1: 0, y1: y, x2: 380, y2: y - 8 });
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
    scale = Math.min(300 / Math.max(dx, 1e-8), 160 / Math.max(dy, 1e-8));
  const map = (p) => [
    (380 - dx * scale) / 2 + (p[0] - minx) * Math.cos(lat) * scale,
    45 + (160 + dy * scale) / 2 - (p[1] - miny) * scale,
  ];
  // 뒤 경로부터 그려 A가 맨 위에 오게 한다.
  for (const [i, row] of [...view.routes.entries()].reverse()) {
    const pts = row.coordinates.map((p) => map(p).join(",")).join(" ");
    svgNode(svg, "polyline", { points: pts, class: "route-halo" });
    const line = svgNode(svg, "polyline", {
      points: pts,
      stroke: routeStyle(i).color,
      fill: "none",
      "stroke-width": "5",
      "stroke-linecap": "round",
      "stroke-linejoin": "round",
    });
    if (routeStyle(i).dash)
      line.setAttribute("stroke-dasharray", routeStyle(i).dash);
    line.dataset.route = row.id;
  }
  const first = view.routes[0].coordinates;
  for (const [label, p, cls] of [
    ["출발", first[0], "map-start"],
    ["도착", first.at(-1), "map-end"],
  ]) {
    const [x, y] = map(p);
    svgNode(svg, "circle", { cx: x, cy: y, r: 7, class: cls });
    const tag = svgNode(svg, "g", { class: "map-tag" });
    const tx = Math.min(Math.max(x - 16, 4), 344),
      ty = y < 40 ? y + 12 : y - 30;
    svgNode(tag, "rect", { x: tx, y: ty, width: 32, height: 20, rx: 6 });
    svgNode(tag, "text", { x: tx + 16, y: ty + 14 }, label);
  }
  const chip = svgNode(svg, "g", { class: "map-tag map-chip" });
  svgNode(chip, "rect", { x: 10, y: 10, width: 92, height: 22, rx: 11 });
  svgNode(chip, "text", { x: 56, y: 25 }, "경로 좌표 도식");
  const legend = element("div", "", frame, "map-legend");
  legend.setAttribute("aria-hidden", "true");
  for (const [i] of view.routes.entries()) {
    const item = element("span", routeLetter(i), legend);
    item.dataset.letter = routeLetter(i);
  }
  const cards = element("div", "", target, "route-options");
  element(
    "p",
    "출처: " +
      (view.provider === "tmap" ? "TMAP 보행 경로" : "OpenStreetMap 도로망") +
      " · 공공데이터포털 CCTV·조명 위치(기준일은 아래 계산 근거)",
    target,
    "caption",
  );
  const mapHost = element("div", "", target, "vworld-host");
  const mapEpoch = generation;
  async function loadMap() {
    const mapAbort = new AbortController();
    pending.add(mapAbort);
    const isCurrent = () =>
      mapEpoch === generation &&
      mapHost.isConnected &&
      !mapAbort.signal.aborted;
    message(mapHost, "지도에 경로와 주변 시설을 표시하고 있어요…", "support");
    try {
      await drawVworld(view, mapHost, isCurrent, mapAbort.signal);
      frame.toggleAttribute(
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
      if (isCurrent()) {
        message(
          mapHost,
          "배경지도를 불러오지 못했어요. 아래 경로 도식과 수치는 그대로 볼 수 있어요.",
          "error",
        );
        const retry = element("button", "지도 다시 불러오기", mapHost, "secondary");
        retry.type = "button";
        retry.addEventListener("click", loadMap);
      }
    } finally {
      pending.delete(mapAbort);
    }
  }
  queueMicrotask(loadMap);
  const about = element("div", "", target, "info-card");
  element(
    "p",
    "공개된 시설 위치로 계산한 비교예요. 지금 불이 켜져 있는지, 현장을 지나갈 수 있는지는 확인하지 않았어요.",
    about,
  );
  if (view.reason) element("p", view.reason, about);
  if (view.departure)
    element(
      "p",
      "확인한 출발: " + view.departure + " · " + view.time_effect,
      about,
    );
  if (view.label) element("p", view.label, about);
  const detailBar = element("div", "", target, "step-actions route-cta");
  const showDetail = element(
    "button",
    "선택한 경로의 비교 근거 보기",
    detailBar,
    "primary",
  );
  showDetail.type = "button";
  const detail = element("div", "", target, "route-detail");
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
    const letter = routeLetter(view.routes.indexOf(row));
    showDetail.textContent = "경로 " + letter + "의 비교 근거 보기";
    for (const button of cards.children)
      button.setAttribute(
        "aria-pressed",
        String(button.dataset.route === row.id),
      );
    for (const line of target.querySelectorAll("polyline[data-route]"))
      line.setAttribute("opacity", line.dataset.route === row.id ? "1" : ".6");
    detail.replaceChildren();
    element("h2", "경로 " + letter + "의 비교 근거", detail, "result-heading");
    element("p", "경로에 표시된 수치의 기준을 확인하세요.", detail, "support result-sub");
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
    const used = element("div", "", detail, "card rows-card");
    element("h2", "사용한 자료", used);
    const usedList = element("dl", "", used);
    for (const [k, v] of [
      ["경로", view.provider === "tmap" ? "TMAP 보행 경로" : "공개 도로망"],
      ["CCTV 기준일", Object.keys(view.sources.cctv.basis_dates).join(", ")],
      ["조명 기준일", view.sources.light.basis_date],
    ]) {
      const r = element("div", "", usedList);
      element("dt", k, r);
      element("dd", v, r);
    }
    const base = view.routes[0];
    if (row !== base)
    element(
      "p",
      "경로 A 대비 " +
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
        frame.scrollIntoView({ block: "start" });
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
    button.dataset.letter = routeLetter(i);
    element("span", routeLetter(i), button, "route-token");
    const content = element("div", "", button, "route-choice-body");
    const title = element("strong", row.label, content);
    if (row.id === view.recommended_route_id)
      element("span", "추천", title, "tag");
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
      distanceLabel(row.distance_m) + " · " + minutesLabel(row),
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
          $("live-" + field + "-value").textContent = place.name;
          togglePanel(field, false);
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
  const meters = straightMeters(liveLocations.origin, liveLocations.destination);
  if (meters < 5 || meters > 20000) {
    message(
      target,
      meters < 5
        ? "출발지와 도착지가 너무 가까워요. 다른 장소를 골라 주세요."
        : "직선거리 약 " +
            (meters / 1000).toFixed(1) +
            "km예요. 걸어서 비교할 수 있는 거리(20km 이내)로 골라 주세요.",
      "error",
    );
    return;
  }
  if (!$("live-date").value || !$("live-time").value) {
    message(target, "출발 날짜와 시각을 골라 주세요.", "error");
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
      preference: checkedValue("live-preference"),
    });
    if (
      view &&
      originRevision === liveRevision.origin &&
      destinationRevision === liveRevision.destination &&
      settingsRevision === liveRevision.settings
    )
      renderFacilityRoutes(view, target);
  } catch (error) {
    if (
      originRevision === liveRevision.origin &&
      destinationRevision === liveRevision.destination &&
      settingsRevision === liveRevision.settings
    )
      message(
        target,
        "경로를 비교하지 못했어요. " +
          (error.detail ||
            "잠시 뒤 다시 시도해 주세요.") +
          " 입력은 그대로 두었어요.",
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
    routePhase("input");
  });

$("live-place-form").addEventListener("input", () => routePhase("input"));
function updateReportCount() {
  $("report-count").textContent =
    $("report-text").value.length.toLocaleString("ko-KR") + " / 5,000자";
}
$("report-text").addEventListener("input", updateReportCount);
$("report-step1-next").addEventListener("click", () => {
  if (!reportPlace) {
    message(
      $("report-result"),
      "문제 위치를 검색해 결과에서 선택해 주세요.",
      "error",
    );
    return;
  }
  reportStep(2);
});
$("report-step2-next").addEventListener("click", () => reportStep(3));
document.addEventListener("click", (event) => {
  const target = event.target.closest("[data-goto-step]");
  if (!target || target.disabled) return;
  const step = Number(target.dataset.gotoStep);
  if (step === 4 && !lastPreview) return;
  reportStep(step);
});
for (const field of ["origin", "destination"])
  $("live-" + field + "-query").addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      $("live-" + field + "-search").click();
    }
  });

$("screen-back").addEventListener("click", (event) => {
  event.stopPropagation();
  if (hasViews(current)) {
    if (!viewBack(current)) navigate("home");
    return;
  }
  if (current === "report" && activeReportStep === 5) return navigate("home");
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
  } else if (current === "report" && activeReportStep > 1)
    reportStep(activeReportStep - 1);
  else navigate("home");
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
        $("report-map-pin").removeAttribute("hidden");
        toggleReportSearch(false);
        Object.defineProperty(reportPlace, "label", {
          value: place.name + " · " + address,
        });
        $("report-place-selected").textContent =
          "선택: " + place.name + " · " + address;
        target.replaceChildren();
        $("report-result").replaceChildren();
        $("report-confirm").hidden = true;
        $("report-consent").checked = false;
        lastPreview = null;
        reportSnapshot = null;
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
const JEJU_BOUNDS = { south: 33.1, north: 33.6, west: 126.1, east: 127.0 };
function chooseReportPlace(place, label) {
  reportPlace = place;
  $("report-map-pin").removeAttribute("hidden");
  Object.defineProperty(reportPlace, "label", { value: label });
  $("report-place-selected").textContent = "선택: " + label;
  $("report-place-candidates").replaceChildren();
  $("report-result").replaceChildren();
  $("report-confirm").hidden = true;
  $("report-consent").checked = false;
  lastPreview = null;
  reportSnapshot = null;
}
$("report-gps").addEventListener("click", () => {
  const button = $("report-gps"),
    target = $("report-place-candidates"),
    revision = ++reportRevision;
  reportPlace = null;
  $("report-place-selected").textContent = "현재 위치를 확인하고 있어요…";
  if (!navigator.geolocation) {
    $("report-place-selected").textContent = "문제 위치를 선택해 주세요.";
    message(
      target,
      "이 브라우저에서는 현재 위치를 쓸 수 없어요. 아래에서 장소를 검색해 주세요.",
      "error",
    );
    return;
  }
  button.disabled = true;
  navigator.geolocation.getCurrentPosition(
    (position) => {
      button.disabled = false;
      if (revision !== reportRevision) return;
      const { latitude: lat, longitude: lng, accuracy } = position.coords;
      if (
        lat < JEJU_BOUNDS.south ||
        lat > JEJU_BOUNDS.north ||
        lng < JEJU_BOUNDS.west ||
        lng > JEJU_BOUNDS.east
      ) {
        $("report-place-selected").textContent = "문제 위치를 선택해 주세요.";
        message(
          target,
          "현재 위치가 제주 밖이에요. 제주 안의 장소를 검색해 골라 주세요.",
          "error",
        );
        return;
      }
      const meters = Math.round(accuracy);
      $("report-place-query").value = "";
      chooseReportPlace(
        { name: "현재 위치", lat, lng },
        "현재 위치 · 정확도 약 " + meters + "m",
      );
      if (meters > 100)
        message(
          target,
          "위치 정확도가 낮아요. 설명에 가까운 건물이나 표지판을 함께 적어 주세요.",
        );
    },
    (error) => {
      button.disabled = false;
      if (revision !== reportRevision) return;
      $("report-place-selected").textContent = "문제 위치를 선택해 주세요.";
      message(
        target,
        error.code === error.PERMISSION_DENIED
          ? "위치 권한이 꺼져 있어요. 아래에서 장소를 검색해 골라 주세요."
          : "현재 위치를 확인하지 못했어요. 아래에서 장소를 검색해 골라 주세요.",
        "error",
      );
    },
    { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 },
  );
});
$("report-place-query").addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    event.preventDefault();
    searchReportPlace();
  }
});
$("report-place-query").addEventListener("input", clearReportPlace);

function toggleReportSearch(open) {
  const panel = $("report-search-panel");
  const next = open ?? panel.hidden;
  panel.hidden = !next;
  $("report-search-toggle").setAttribute("aria-expanded", String(next));
  if (next) $("report-place-query").focus();
}
$("report-search-toggle").addEventListener("click", () => toggleReportSearch());
for (const field of ["origin", "destination"])
  $("live-" + field + "-toggle").addEventListener("click", () => togglePanel(field));
$("live-time-toggle").addEventListener("click", () => {
  const panel = $("live-time-panel");
  panel.hidden = !panel.hidden;
  $("live-time-toggle").setAttribute("aria-expanded", String(!panel.hidden));
});
for (const id of ["live-date", "live-time"])
  $(id).addEventListener("input", updateTimeValue);
initScreens({
  title: (text) => {
    $("screen-title").textContent = text;
  },
  routeView: () => lastRouteView,
  navigate,
});
