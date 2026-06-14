/* 競艇予想AI 静的サイト
 * 静的ホスティングされた予測JSON (api/v1/predict/today.json) を
 * クライアントサイドで fetch して描画する (サーバーレス構成)。
 *
 * today.json は「既定日のレース」と「1週間分の日付インデックス(days)」を持つ。
 * 既定日以外を選択した場合は per-date JSON (api/v1/predict/YYYYMMDD.json) を
 * 遅延読み込みする。過去日は実際の着順・的中結果も併記する。
 */
"use strict";

const API_BASE = "api/v1/predict/";
const API_URL = API_BASE + "today.json";
const FALLBACK_JS_URL = API_BASE + "today.js";

const state = {
  data: null, // today.json 全体
  selectedDate: null, // 表示中の日付 (YYYY-MM-DD)
  selectedStadium: null,
  dayCache: {}, // { "YYYY-MM-DD": { races: [...], ... } }
};

document.addEventListener("DOMContentLoaded", init);

async function init() {
  const status = document.getElementById("status");
  try {
    state.data = await loadPredictData();
    // 既定日のレースをキャッシュに登録 (today.json に同梱されている)
    state.selectedDate = state.data.default_date ?? state.data.race_date ?? null;
    if (state.selectedDate) {
      const meta = dayMetaFor(state.selectedDate) || {};
      state.dayCache[state.selectedDate] = {
        race_date: state.selectedDate,
        race_count: state.data.race_count,
        has_results: meta.has_results ?? false,
        result_summary: meta.result_summary ?? null,
        races: state.data.races,
      };
    }
    status.remove();
    renderModelStats();
    renderDayNav();
    await selectDate(state.selectedDate);
  } catch (err) {
    status.textContent =
      "予想データの読み込みに失敗しました。予測パイプライン (python -m kyotei.cli predict) を実行してください。 (" + err.message + ")";
    status.classList.add("error");
  }
}

async function loadPredictData() {
  // 通常は fetch で JSON を取得。file:// で直接開いた場合などは
  // fetch がブロックされるため、<script> 読み込みにフォールバックする。
  try {
    const res = await fetch(API_URL, { cache: "no-store" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (fetchErr) {
    const data = await loadViaScriptTag();
    if (data) return data;
    throw fetchErr;
  }
}

function loadViaScriptTag() {
  return new Promise((resolve) => {
    const script = document.createElement("script");
    script.src = FALLBACK_JS_URL;
    script.onload = () => resolve(window.__KYOTEI_PREDICT__ ?? null);
    script.onerror = () => resolve(null);
    document.head.appendChild(script);
  });
}

/* ===== 日付選択 ===== */

function dayMetaFor(dateStr) {
  return (state.data.days || []).find((d) => d.race_date === dateStr) || null;
}

async function loadDay(dateStr) {
  if (state.dayCache[dateStr]) return state.dayCache[dateStr];
  const meta = dayMetaFor(dateStr);
  const file = meta && meta.file ? meta.file : dateStr.replace(/-/g, "") + ".json";
  const res = await fetch(API_BASE + file, { cache: "no-store" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const day = await res.json();
  state.dayCache[dateStr] = day;
  return day;
}

async function selectDate(dateStr) {
  if (!dateStr) {
    renderRaces([]);
    return;
  }
  state.selectedDate = dateStr;
  state.selectedStadium = null;
  renderDayNav();
  const wrap = document.getElementById("races");
  let day;
  try {
    day = await loadDay(dateStr);
  } catch (err) {
    wrap.innerHTML = `<div class="status error">${esc(dateStr)} の予想データを読み込めませんでした。(${esc(err.message)})</div>`;
    return;
  }
  state.currentDay = day;
  renderMeta(day);
  renderStadiumNav(day.races);
  renderRaces(day.races);
}

function renderDayNav() {
  const nav = document.getElementById("day-nav");
  if (!nav) return;
  const days = state.data.days || [];
  if (days.length <= 1) {
    nav.innerHTML = "";
    return;
  }
  nav.innerHTML = days
    .map((d) => {
      const active = d.race_date === state.selectedDate ? " active" : "";
      const tag = d.is_today ? "本日" : d.is_future ? "予定" : "結果";
      const sub = d.has_results && d.result_summary
        ? `的中 ${d.result_summary.win_hits}/${d.result_summary.races_with_result}`
        : `${d.race_count}R`;
      return `<button class="day-btn${active}" data-date="${esc(d.race_date)}">
        <span class="day-date">${esc(formatDate(d.race_date))}</span>
        <span class="day-tag day-tag-${d.is_today ? "today" : d.is_future ? "future" : "past"}">${tag}</span>
        <span class="day-sub">${esc(sub)}</span>
      </button>`;
    })
    .join("");
  nav.querySelectorAll(".day-btn").forEach((btn) => {
    btn.addEventListener("click", () => selectDate(btn.dataset.date));
  });
}

/* ===== メタ情報 ===== */

function renderMeta(day) {
  const el = document.getElementById("meta-info");
  const generated = state.data.generated_at
    ? new Date(state.data.generated_at).toLocaleString("ja-JP")
    : "-";
  let line = `対象日: ${day.race_date ?? "-"} / 全${day.race_count}レース / 予測生成: ${generated}`;
  if (day.has_results && day.result_summary) {
    const s = day.result_summary;
    line += ` ／ 実績: 単勝的中 ${s.win_hits}/${s.races_with_result} (${pct(s.win_hit_rate)})`
      + ` ・ 3連単的中 ${s.trifecta_hits}/${s.races_with_result} (${pct(s.trifecta_hit_rate)})`;
  }
  el.textContent = line;
}

function renderModelStats() {
  const el = document.getElementById("model-stats");
  const m = state.data.model || {};
  const items = [
    ["単勝的中率(検証)", pct(m.win_hit_rate)],
    ["2連単的中率(検証)", pct(m.exacta_hit_rate)],
    ["3連単的中率(検証)", pct(m.trifecta_hit_rate)],
    ["検証レース数", m.valid_races != null ? String(m.valid_races) : "-"],
  ];
  el.innerHTML = items
    .map(([label, value]) => `<div class="stat-chip">${esc(label)}<strong>${esc(value)}</strong></div>`)
    .join("");
}

/* ===== 競艇場ナビ ===== */

function renderStadiumNav(races) {
  const nav = document.getElementById("stadium-nav");
  const stadiums = [...new Map(
    races.map((r) => [r.stadium_number, r.stadium_name])
  ).entries()].sort((a, b) => a[0] - b[0]);

  const buttons = [[null, "全場"], ...stadiums];
  nav.innerHTML = buttons
    .map(([num, name]) =>
      `<button class="stadium-btn${num === state.selectedStadium ? " active" : ""}" data-stadium="${num ?? ""}">${esc(name)}</button>`)
    .join("");

  nav.querySelectorAll(".stadium-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const v = btn.dataset.stadium;
      state.selectedStadium = v === "" ? null : Number(v);
      renderStadiumNav(races);
      renderRaces(races);
    });
  });
}

/* ===== レース描画 ===== */

function renderRaces(allRaces) {
  const wrap = document.getElementById("races");
  const races = (allRaces || []).filter(
    (r) => state.selectedStadium == null || r.stadium_number === state.selectedStadium
  );

  // 場ごとにグルーピング
  const byStadium = new Map();
  for (const race of races) {
    if (!byStadium.has(race.stadium_number)) byStadium.set(race.stadium_number, []);
    byStadium.get(race.stadium_number).push(race);
  }

  wrap.innerHTML = [...byStadium.entries()]
    .sort((a, b) => a[0] - b[0])
    .map(([num, list]) => {
      const name = list[0].stadium_name;
      const cards = list
        .sort((a, b) => a.race_number - b.race_number)
        .map(renderRaceCard)
        .join("");
      return `<section class="stadium-section"><h2>${esc(name)}</h2><div class="race-grid">${cards}</div></section>`;
    })
    .join("") || '<div class="status">表示できるレースがありません。</div>';
}

function renderRaceCard(race) {
  const result = race.result || {};
  const showResult = result.has_result;
  const boats = [...race.boats].sort((a, b) => a.predicted_rank - b.predicted_rank);
  const rows = boats
    .map((b) => {
      const prob = Math.round((b.win_probability ?? 0) * 1000) / 10;
      const rankClass = b.predicted_rank <= 2 ? ` r${b.predicted_rank}` : "";
      const placeCell = showResult
        ? `<td class="place-cell${b.actual_place ? " place-" + b.actual_place : ""}">${b.actual_place ?? "-"}</td>`
        : "";
      return `<tr class="rank-${b.predicted_rank}">
        <td class="rank-cell${rankClass}">${b.predicted_rank}</td>
        ${placeCell}
        <td><span class="boat-badge boat-${b.boat_number}">${b.boat_number}</span></td>
        <td>${racerLink(b)} <small style="color:var(--text-dim)">${esc(b.racer_class ?? "-")}</small></td>
        <td>${fmt(b.national_top1)}</td>
        <td>${fmt(b.motor_top2)}</td>
        <td>${fmt(b.exhibition_time)}</td>
        <td>
          <div class="prob-bar-wrap"><div class="prob-bar" style="width:${Math.min(prob * 2.2, 100)}%"></div></div>
        </td>
        <td class="prob-label">${prob.toFixed(1)}%</td>
      </tr>`;
    })
    .join("");

  const combos = (race.trifecta || [])
    .map((c) =>
      `<span class="combo-chip"><strong>${esc(c.combination)}</strong><span>${(c.probability * 100).toFixed(1)}%</span></span>`)
    .join("");

  const closeTime = race.race_closed_at ? race.race_closed_at.slice(11, 16) : "-";
  const cond = [
    race.wind != null ? `風 ${race.wind}m` : null,
    race.wave != null ? `波 ${race.wave}cm` : null,
  ].filter(Boolean).join(" / ");

  const placeHead = showResult ? "<th>着</th>" : "";
  const resultBadge = showResult ? renderResultBadge(result) : "";
  const resultLine = showResult ? renderResultLine(result) : "";

  return `<article class="race-card">
    <div class="race-head">
      <span class="race-no">${race.race_number}R</span>
      <span class="race-title">${esc(race.race_title ?? "")}</span>
      <span class="race-close">締切 ${esc(closeTime)}</span>
    </div>
    ${cond ? `<div class="race-cond">${esc(cond)}</div>` : ""}
    ${resultBadge}
    <table class="boats">
      <thead><tr>
        <th>予測</th>${placeHead}<th>艇</th><th>選手</th><th>全国勝率</th><th>M2連率</th><th>展示T</th><th colspan="2">勝率(AI)</th>
      </tr></thead>
      <tbody>${rows}</tbody>
    </table>
    <div class="trifecta"><span class="trifecta-label">3連単推奨:</span>${combos}</div>
    ${resultLine}
  </article>`;
}

function renderResultBadge(result) {
  const win = result.win_hit
    ? '<span class="hit-badge hit">単勝的中</span>'
    : '<span class="hit-badge miss">単勝不的中</span>';
  const tri = result.trifecta_hit
    ? '<span class="hit-badge hit">3連単的中</span>'
    : '<span class="hit-badge miss">3連単不的中</span>';
  return `<div class="result-badges">${win}${tri}</div>`;
}

function renderResultLine(result) {
  if (!result.actual_trifecta) return "";
  return `<div class="result-line">結果(3連単): <strong>${esc(result.actual_trifecta)}</strong></div>`;
}

function racerLink(boat) {
  const name = esc(boat.racer_name ?? "-");
  if (boat.racer_number == null) return name;
  return `<a class="racer-link" href="racers.html#${boat.racer_number}">${name}</a>`;
}

/* ===== ユーティリティ ===== */

function formatDate(dateStr) {
  if (!dateStr) return "-";
  const [, m, d] = dateStr.split("-");
  const wd = ["日", "月", "火", "水", "木", "金", "土"][new Date(dateStr).getDay()] ?? "";
  return `${Number(m)}/${Number(d)}(${wd})`;
}
function pct(v) {
  return v == null ? "-" : (v * 100).toFixed(1) + "%";
}
function fmt(v) {
  return v == null ? "-" : String(v);
}
function esc(s) {
  return String(s).replace(/[&<>"']/g, (ch) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]));
}
