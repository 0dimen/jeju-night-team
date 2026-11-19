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
  path.setAttribute("d", iconPaths[button.dataset.screen] || iconPaths.route);
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
function clearRoute() {
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
  abortRequests();
  clearRoute();
  $("report-form").reset();
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
  for (const section of document.querySelectorAll(".screen"))
    section.hidden = section.id !== screen;
  for (const button of document.querySelectorAll("nav button")) {
    if (button.dataset.screen === screen)
      button.setAttribute("aria-current", "page");
    else button.removeAttribute("aria-current");
  }
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
        message($("chat-result"), view.message, "error");
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
