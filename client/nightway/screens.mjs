// 유동인구·지역 비교·시설 지도·내 제보 화면. 유동인구는 제주데이터허브 748번 실제 월별 집계를 쓴다.
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

/* 제주 위치 도식(실제 경계 아님) */
const AREAS = {
  north: { name: "제주시", d: "M190 58 L262 44 L282 74 L262 96 L206 98 Z", level: "high" },
  mid: { name: "제주시 동부", d: "M140 82 L190 60 L210 100 L190 130 L154 124 Z", level: "mid" },
  west: { name: "서귀포시 서부", d: "M100 116 L144 96 L156 126 L150 152 L106 152 Z", level: "mid" },
  east: { name: "서귀포시", d: "M218 108 L274 98 L282 116 L228 128 Z", level: "low" },
};
function jejuMap(host, { highlight = null, label = "위치 도식" } = {}) {
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

/* 유동인구·지역 비교: 제주데이터허브 748번 자료의 읍면동·월별 실제 집계 */
let popData = null,
  popLoading = null;
function loadPopulation() {
  popLoading ||= fetch("/data/population", { cache: "no-store" })
    .then((r) => {
      if (!r.ok) throw new Error("population");
      return r.json();
    })
    .then((d) => (popData = d))
    .catch((error) => {
      popLoading = null;
      throw error;
    });
  return popLoading;
}
function monthLabel(m) {
  const [y, mo] = m.split("-");
  return y + "년 " + Number(mo) + "월";
}
function man(v) {
  return v == null ? "자료 없음" : Math.round(v / 10000).toLocaleString("ko-KR") + "만";
}
function fillMonths(select) {
  if (select.dataset.filled) return;
  select.replaceChildren();
  for (const m of [...popData.months].reverse()) el("option", monthLabel(m), select).value = m;
  select.dataset.filled = "1";
}
function renderBars(host, rows) {
  host.replaceChildren();
  const max = Math.max(1, ...rows.map((r) => r.value ?? 0));
  for (const r of rows) {
    const row = el("div", "", host, "bar-row");
    const head = el("div", "", row, "bar-head");
    el("span", r.name, head);
    el("strong", man(r.value), head);
    const track = el("div", "", row, "bar-track");
    el("div", "", track, "bar-fill").style.width = Math.round(((r.value ?? 0) / max) * 90) + "%";
  }
}
async function popRender(view) {
  const unit = document.querySelector('input[name="pop-unit"]:checked')?.value || "읍면동";
  for (const dd of document.querySelectorAll('[data-pop="unit"]')) dd.textContent = unit;
  if (view === "overview") jejuMap(document.querySelector('[data-jeju-map="overview"]'), { label: "위치 도식" });
  try {
    await loadPopulation();
  } catch {
    if (view === "distribution") el("p", "유동인구 자료를 불러오지 못했어요. 잠시 뒤 다시 시도해 주세요.", $("pop-bars"), "error");
    return;
  }
  fillMonths($("pop-month"));
  $("pop-range").textContent = monthLabel(popData.months[0]) + " ~ " + monthLabel(popData.months.at(-1));
  if (view === "distribution") {
    const area = $("pop-area").value,
      month = $("pop-month").value;
    let rows;
    if (unit === "시 전체") {
      $("pop-dist-title").textContent = "제주시·서귀포시 방문인구";
      rows = ["제주시", "서귀포시"].map((city) => {
        const list = popData.regions.filter((r) => r.city === city && r.values[month]);
        return { name: city, value: list.length ? list.reduce((sum, r) => sum + r.values[month][2], 0) : null };
      });
    } else {
      $("pop-dist-title").textContent = area + " 읍면동별 방문인구";
      rows = popData.regions
        .filter((r) => r.city === area)
        .map((r) => ({ name: r.name, value: r.values[month]?.[2] ?? null }))
        .sort((x, y) => (y.value ?? -1) - (x.value ?? -1))
        .slice(0, 10);
    }
    $("pop-dist-sub").textContent = monthLabel(month) + " · 월 누적(매시 측정 합) · " + (unit === "시 전체" ? "시 합계" : "상위 10곳");
    renderBars($("pop-bars"), rows);
    $("pop-unit-note").textContent = popData.unit_note;
  }
}

/* 지역 비교 */
function josa(word, withBatchim, without) {
  const code = word.charCodeAt(word.length - 1) - 0xac00;
  return word + (code >= 0 && code % 28 ? withBatchim : without);
}
function selectedRegions() {
  return [...document.querySelectorAll("#region-choices input:checked")]
    .map((i) => popData?.regions.find((r) => r.name === i.value))
    .filter(Boolean);
}
async function regionInit() {
  const host = $("region-choices");
  try {
    await loadPopulation();
  } catch {
    el("p", "지역 자료를 불러오지 못했어요. 잠시 뒤 다시 시도해 주세요.", host, "error");
    return;
  }
  fillMonths($("region-month"));
  for (const r of popData.regions) {
    const card = el("label", "", host, "select-card");
    const input = el("input", undefined, card);
    input.type = "checkbox";
    input.value = r.name;
    input.checked = r.name === "연동" || r.name === "노형동";
    icon(card, "pin", 22);
    el("strong", r.name, card);
    el("small", r.city, card);
  }
  host.addEventListener("change", (event) => {
    if (selectedRegions().length > 2) event.target.checked = false;
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
    $("region-compare-sub").textContent = monthLabel(month) + " · 월 누적 방문인구(매시 측정 합)";
    renderBars($("region-bars"), [a, b].map((r) => ({ name: r.name, value: r.values[month]?.[2] ?? null })));
    const more = $("region-more");
    more.replaceChildren();
    for (const r of [a, b]) {
      const v = r.values[month];
      el("div", "", more).append(el("dt", r.name), el("dd", v ? "거주 " + man(v[0]) + " · 근무 " + man(v[1]) : "자료 없음"));
    }
    $("region-detail-button").textContent = a.name + "의 자료 상세 보기";
  }
  if (view === "detail") {
    $("region-detail-title").textContent = a.name + " 자료 상세";
    jejuMap(document.querySelector('[data-jeju-map="detail"]'), { label: "위치 도식" });
    const series = popData.months.slice(-12).filter((m) => a.values[m]);
    $("region-trend-sub").textContent = monthLabel(series[0]) + " ~ " + monthLabel(series.at(-1)) + " · 월 누적 방문인구";
    renderBars($("region-trend"), series.map((m) => ({ name: monthLabel(m), value: a.values[m][2] })));
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
