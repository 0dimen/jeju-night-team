// 유동인구·지역 비교·시설 지도·내 제보 화면. 자료가 없는 수치는 화면에 '예시'로 표시한다.
const $ = (id) => document.getElementById(id);
const NS = "http://www.w3.org/2000/svg";

function el(tag, text, parent, cls) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (cls) node.className = cls;
  parent?.append(node);
  return node;
}
function svg(parent, tag, attrs = {}, text) {
  const node = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  if (text !== undefined) node.textContent = text;
  parent.append(node);
  return node;
}
function icon(parent, name, size = 20) {
  const s = svg(parent, "svg", { class: "ico", width: size, height: size, "aria-hidden": "true" });
  svg(s, "use", { href: "#i-" + name });
  return s;
}

/* 화면 안의 단계(view) 이동 */
const stacks = {};
let setTitle = () => {};
export function currentView(screen) {
  return stacks[screen]?.at(-1);
}
export function showView(screen, view, push = true) {
  const section = $(screen);
  if (!section?.querySelector(".view")) return;
  const views = [...section.querySelectorAll(":scope > .view")];
  const target = views.find((v) => v.dataset.view === view) || views[0];
  const stack = (stacks[screen] ||= [views[0].dataset.view]);
  if (push && stack.at(-1) !== target.dataset.view) {
    const index = stack.indexOf(target.dataset.view);
    if (index >= 0) stack.length = index + 1;
    else stack.push(target.dataset.view);
  }
  for (const v of views) v.hidden = v !== target;
  setTitle(target.dataset.title);
  onView[screen]?.(target.dataset.view);
  window.scrollTo({ top: 0 });
}
export function resetViews(screen) {
  const section = $(screen);
  const first = section?.querySelector(":scope > .view");
  if (!first) return;
  stacks[screen] = [first.dataset.view];
  showView(screen, first.dataset.view, false);
}
/** 뒤로 가기: 화면 안에서 이전 단계가 있으면 true */
export function viewBack(screen) {
  const stack = stacks[screen];
  if (!stack || stack.length < 2) return false;
  stack.pop();
  showView(screen, stack.at(-1), false);
  return true;
}
export function hasViews(screen) {
  return Boolean($(screen)?.querySelector(":scope > .view"));
}

/* 제주 지도 도식(예시) */
const AREAS = {
  north: { name: "제주시", d: "M190 58 L262 44 L282 74 L262 96 L206 98 Z", level: "high" },
  mid: { name: "제주시 동부", d: "M140 82 L190 60 L210 100 L190 130 L154 124 Z", level: "mid" },
  west: { name: "서귀포시 서부", d: "M100 116 L144 96 L156 126 L150 152 L106 152 Z", level: "mid" },
  east: { name: "서귀포시", d: "M218 108 L274 98 L282 116 L228 128 Z", level: "low" },
};
function jejuMap(host, { highlight = null, label = "예시 지도" } = {}) {
  host.replaceChildren();
  const s = svg(host, "svg", { viewBox: "0 0 350 220", class: "route-map jeju-map", role: "img", "aria-label": "제주 지역 도식 · " + label });
  svg(s, "path", { d: "M24 160 L64 130 L134 102 L194 80 L264 60 L314 64 L330 86 L308 102 L286 128 L220 142 L164 166 L104 170 L54 168 Z", class: "island" });
  for (const [key, a] of Object.entries(AREAS)) {
    svg(s, "path", { d: a.d, class: "area level-" + (highlight ? (key === highlight ? "focus" : "dim") : a.level) });
  }
  svg(s, "path", { d: "M70 150 L140 120 L210 104 L290 84", class: "area-line" });
  svg(s, "path", { d: "M150 60 L170 170 M240 40 L250 150", class: "area-line" });
  svg(s, "text", { x: 222, y: 72, class: "area-label" }, "제주시");
  svg(s, "text", { x: 128, y: 188, class: "area-label" }, "서귀포시");
  el("span", label, host, "map-chip bottom");
}

/* 유동인구 */
function popRender(view) {
  const unit = document.querySelector('input[name="pop-unit"]:checked')?.value || "읍면동";
  for (const dd of document.querySelectorAll('[data-pop="unit"]')) dd.textContent = unit;
  if (view === "overview") jejuMap(document.querySelector('[data-jeju-map="overview"]'));
  if (view === "distribution") {
    const area = $("pop-area").value,
      month = $("pop-month").value;
    $("pop-dist-title").textContent = area + " 월별 방문 분포";
    $("pop-dist-sub").textContent = month + " · " + unit + " 단위 · 예시";
    jejuMap(document.querySelector('[data-jeju-map="distribution"]'), {
      highlight: area === "서귀포시" ? "east" : "north",
      label: "예시 분포",
    });
  }
}

/* 지역 비교: 방문객 수는 예시 값 */
const REGIONS = [
  { id: "yeon", name: "연동", city: "제주시", visits: 12430, area: "north" },
  { id: "nohyeong", name: "노형동", city: "제주시", visits: 9860, area: "mid" },
  { id: "ido2", name: "이도2동", city: "제주시", visits: 8120, area: "north" },
  { id: "samdo2", name: "삼도2동", city: "제주시", visits: 6540, area: "mid" },
];
function josa(word, withBatchim, without) {
  const code = word.charCodeAt(word.length - 1) - 0xac00;
  return word + (code >= 0 && code % 28 ? withBatchim : without);
}
function selectedRegions() {
  return [...document.querySelectorAll('#region-choices input:checked')].map((i) => REGIONS.find((r) => r.id === i.value));
}
function regionInit() {
  const host = $("region-choices");
  for (const r of REGIONS) {
    const card = el("label", "", host, "select-card");
    const input = el("input", undefined, card);
    input.type = "checkbox";
    input.value = r.id;
    input.checked = r.id === "yeon" || r.id === "nohyeong";
    icon(card, "pin", 22);
    el("strong", r.name, card);
    el("small", r.city, card);
  }
  host.addEventListener("change", (event) => {
    const checked = selectedRegions();
    if (checked.length > 2) event.target.checked = false;
    regionButton();
  });
  $("region-compare").addEventListener("click", () => {
    if (selectedRegions().length === 2) showView("region", "compare");
  });
  regionButton();
}
function regionButton() {
  const n = selectedRegions().length;
  const button = $("region-compare");
  button.disabled = n !== 2;
  button.textContent = n === 2 ? "선택한 2개 지역 비교" : "지역을 두 곳 선택해 주세요 (" + n + "/2)";
}
function regionRender(view) {
  const [a, b] = selectedRegions();
  if (!a || !b) return;
  const month = $("region-month").value;
  if (view === "compare") {
    $("region-compare-title").textContent = josa(a.name, "과", "와") + " " + b.name + " 비교";
    $("region-compare-sub").textContent = month + " · 월별 방문 규모 예시";
    const bars = $("region-bars");
    bars.replaceChildren();
    const max = Math.max(a.visits, b.visits);
    for (const r of [a, b]) {
      const row = el("div", "", bars, "bar-row");
      const head = el("div", "", row, "bar-head");
      el("span", r.name, head);
      el("strong", r.visits.toLocaleString("ko-KR"), head);
      const track = el("div", "", row, "bar-track");
      const fill = el("div", "", track, "bar-fill");
      fill.style.width = Math.round((r.visits / max) * 90) + "%";
    }
    $("region-detail-button").textContent = a.name + "의 자료 상세 보기";
  }
  if (view === "detail") {
    $("region-detail-title").textContent = a.name + " 자료 상세";
    jejuMap(document.querySelector('[data-jeju-map="detail"]'), { highlight: a.area, label: "예시 지도" });
  }
}

/* 시설 지도: 공개 CCTV·조명 위치(실제 목록) */
let facilityData = null,
  facilityLoading = null;
let getRouteView = () => null;
async function loadFacility() {
  const routeView = getRouteView();
  if (routeView?.map_points) {
    facilityData = { points: routeView.map_points.points, notice: routeView.map_points.notice, scope: "비교한 경로 주변", routes: routeView.routes };
    return facilityData;
  }
  if (facilityData && facilityData.scope !== "비교한 경로 주변") return facilityData;
  facilityLoading ||= fetch("/research/maps/facilities", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ region: "yeondong" }),
    cache: "no-store",
  })
    .then((r) => {
      if (!r.ok) throw new Error("facility");
      return r.json();
    })
    .then((data) => (facilityData = { points: data.points, notice: data.notice, scope: "연동 공개 구간 주변" }))
    .finally(() => (facilityLoading = null));
  return facilityLoading;
}
function layers() {
  return new Set([...document.querySelectorAll("#facility-layers input:checked")].map((i) => i.value));
}
function facilityRender() {
  const host = $("facility-map");
  host.replaceChildren();
  const s = svg(host, "svg", { viewBox: "0 0 380 250", class: "route-map", role: "img", "aria-label": "공개 시설 위치 도식" });
  const grid = svg(s, "g", { class: "map-grid" });
  for (let x = 30; x < 380; x += 58) svg(grid, "line", { x1: x, y1: 0, x2: x + 12, y2: 250 });
  for (let y = 28; y < 250; y += 52) svg(grid, "line", { x1: 0, y1: y, x2: 380, y2: y - 8 });
  const on = layers();
  if (!facilityData) {
    el("span", "시설 위치를 불러오는 중이에요…", host, "map-chip");
    return;
  }
  const pts = facilityData.points;
  const coords = [...pts.map((p) => p.coordinates), ...(facilityData.routes || []).flatMap((r) => r.coordinates)];
  if (!coords.length) {
    el("span", "표시할 시설 위치가 없어요", host, "map-chip");
    return;
  }
  const xs = coords.map((c) => c[0]),
    ys = coords.map((c) => c[1]);
  const minx = Math.min(...xs), maxx = Math.max(...xs), miny = Math.min(...ys), maxy = Math.max(...ys);
  const k = Math.cos((((miny + maxy) / 2) * Math.PI) / 180);
  const scale = Math.min(340 / Math.max((maxx - minx) * k, 1e-8), 210 / Math.max(maxy - miny, 1e-8));
  const map = (c) => [(380 - (maxx - minx) * k * scale) / 2 + (c[0] - minx) * k * scale, (250 + (maxy - miny) * scale) / 2 - (c[1] - miny) * scale];
  for (const [i, r] of (facilityData.routes || []).entries()) {
    const line = svg(s, "polyline", { points: r.coordinates.map((c) => map(c).join(",")).join(" "), fill: "none", stroke: i ? "#89e3dd" : "#af86ff", "stroke-width": 3, opacity: ".7" });
    if (i) line.setAttribute("stroke-dasharray", "7 6");
  }
  let cctv = 0, light = 0;
  for (const p of pts) {
    if (p.kind === "cctv") cctv++;
    else light++;
    if (!on.has(p.kind)) continue;
    const [x, y] = map(p.coordinates);
    svg(s, "circle", { cx: x, cy: y, r: p.kind === "cctv" ? 4.5 : 2.5, class: "fac-" + p.kind });
  }
  el("span", facilityData.scope + " · 공개 목록 위치", host, "map-chip");
  const legend = el("div", "", host, "map-legend fac");
  if (on.has("cctv")) el("span", "CCTV", legend, "lg-cctv");
  if (on.has("light")) el("span", "조명", legend, "lg-light");
  $("facility-cctv-note").textContent = on.has("cctv") ? "공개 목록 위치 " + cctv.toLocaleString("ko-KR") + "곳 · " + facilityData.scope : "레이어를 선택해 확인";
  $("facility-light-note").textContent = on.has("light") ? "공개 목록 위치 " + light.toLocaleString("ko-KR") + "곳 · " + facilityData.scope : "레이어를 선택해 확인";
  $("nearby-cctv").textContent = "CCTV 설치 위치 " + cctv.toLocaleString("ko-KR") + "곳";
  $("nearby-light").textContent = "가로등·보안등 위치 " + light.toLocaleString("ko-KR") + "곳";
  if (on.has("issue")) el("p", "게시된 실제 제보는 아직 없어요. 처리 흐름 예시는 '주변 시설 목록 보기'에서 볼 수 있어요.", host, "map-note");
}
async function facilityShow() {
  facilityRender();
  try {
    await loadFacility();
  } catch {
    $("facility-map").replaceChildren();
    el("p", "시설 위치를 불러오지 못했어요. 잠시 뒤 다시 시도해 주세요.", $("facility-map"), "error map-note");
    $("facility-cctv-note").textContent = "불러오지 못함";
    return;
  }
  facilityRender();
}

/* 내 제보: 이번 페이지에서 접수한 제보만 */
const reports = [];
let openReport = null;
const EXAMPLE = { id: "예시", example: true, title: "가로등 소등 확인", facility: "streetlight", place: "예시 구간", status: "published" };
const STATUS = { review: "검토 대기", published: "게시 완료" };
export function addReport(report) {
  reports.unshift({ ...report, status: "review" });
  myRender();
}
export function clearReports() {
  reports.length = 0;
  openReport = null;
  myRender();
}
const facilityIcon = { streetlight: "lamp", cctv: "camera", walkway: "walk", other: "report" };
function myRender() {
  const host = $("my-list");
  if (!host) return;
  host.replaceChildren();
  const filter = document.querySelector('input[name="my-filter"]:checked')?.value || "all";
  const rows = [...reports, EXAMPLE].filter((r) => filter === "all" || r.status === filter);
  if (!reports.length && filter !== "published") el("p", "아직 남긴 제보가 없어요.", host, "empty");
  for (const r of rows) {
    const card = el("button", "", host, "card report-card");
    card.type = "button";
    const head = el("span", (r.example ? "예시 제보" : r.id) + " · " + STATUS[r.status], card, "report-card-head");
    if (r.example) head.classList.add("muted");
    const item = el("span", "", card, "list-item");
    icon(item, facilityIcon[r.facility] || "report");
    const text = el("span", "", item, "field-text");
    el("strong", r.title, text);
    el("small", r.place + (r.problemLabel ? " · " + r.problemLabel : ""), text);
    icon(item, "chev", 18).classList.add("chev");
    card.addEventListener("click", () => {
      openReport = r;
      showView("my", "detail");
    });
  }
  const action = $("my-open-latest");
  action.textContent = reports.length ? reports[0].id + " 상세 보기" : "제보하러 가기";
}
function myDetail() {
  const r = openReport || reports[0] || EXAMPLE;
  $("my-detail-title").textContent = r.title + (r.example ? "" : " 제보");
  $("my-detail-sub").textContent = (r.example ? "예시 제보" : r.id) + " · " + r.place;
  const steps = [
    ["접수 완료", "제보 내용이 저장됐어요."],
    ["검토 대기", "담당자가 위치와 내용을 확인할 예정이에요."],
    ["검증", "확인이 끝나면 결과를 표시해요."],
    ["게시", "게시된 시설 변경이 다음 분석에 적용돼요."],
  ];
  const reached = r.status === "published" ? 4 : 2;
  const list = $("my-timeline");
  list.replaceChildren();
  steps.forEach(([title, desc], i) => {
    const li = el("li", "", list, i < reached - 1 || reached === 4 ? "done" : i === reached - 1 ? "current" : "");
    el("span", String(i + 1), li, "dot");
    const t = el("span", "", li);
    el("strong", title, t);
    el("small", desc, t);
    if (i === reached - 1) li.setAttribute("aria-current", "step");
  });
  $("my-detail-info").textContent = r.status === "published" ? "예시예요. 게시되면 같은 경로 조건으로 다시 비교할 수 있어요." : "현재 단계에서는 경로 분석에 반영되지 않았어요. 시범 운영 중이라 기관에는 전달되지 않아요.";
  const action = $("my-detail-action");
  action.textContent = r.status === "published" ? "게시된 변경 보기" : "내 제보 목록으로";
  action.onclick = () => showView("my", r.status === "published" ? "published" : "list");
}

const onView = {
  population: popRender,
  region: regionRender,
  facility: (view) => {
    if (view === "map" || view === "nearby") facilityShow();
  },
  my: (view) => {
    if (view === "list") myRender();
    if (view === "detail") myDetail();
  },
};

export function initScreens({ title, routeView, navigate }) {
  setTitle = title;
  getRouteView = routeView;
  regionInit();
  document.addEventListener("click", (event) => {
    const go = event.target.closest("[data-view-go]");
    if (!go) return;
    const screen = go.closest(".screen")?.id;
    if (screen) showView(screen, go.dataset.viewGo);
  });
  $("facility-layers").addEventListener("change", facilityRender);
  $("my-filter").addEventListener("change", myRender);
  $("pop-area").addEventListener("change", () => popRender("settings"));
  $("my-open-latest").addEventListener("click", () => {
    if (!reports.length) return navigate("report");
    openReport = reports[0];
    showView("my", "detail");
  });
  myRender();
}
export function openMyDetail(id) {
  openReport = reports.find((r) => r.id === id) || null;
  showView("my", "detail");
}
