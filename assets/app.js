/* 競艇予想AI 静的サイト
 * 静的ホスティングされた予測JSON (api/v1/predict/today.json) を
 * クライアントサイドで fetch して描画する (サーバーレス構成)。
 */
"use strict";

const API_URL = "api/v1/predict/today.json";
const FALLBACK_JS_URL = "api/v1/predict/today.js";

const state = { data: null, selectedStadium: null };

document.addEventListener("DOMContentLoaded", init);

async function init() {
  const status = document.getElementById("status");
  try {
    state.data = await loadPredictData();
    status.remove();
    renderMeta();
    renderModelStats();
    renderStadiumNav();
    renderRaces();
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

function renderMeta() {
  const el = document.getElementById("meta-info");
  const d = state.data;
  const generated = d.generated_at ? new Date(d.generated_at).toLocaleString("ja-JP") : "-";
  el.textContent = `対象日: ${d.race_date ?? "-"} / 全${d.race_count}レース / 予測生成: ${generated}`;
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

function renderStadiumNav() {
  const nav = document.getElementById("stadium-nav");
  const stadiums = [...new Map(
    state.data.races.map((r) => [r.stadium_number, r.stadium_name])
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
      renderStadiumNav();
      renderRaces();
    });
  });
}

function renderRaces() {
  const wrap = document.getElementById("races");
  const races = state.data.races.filter(
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
  const boats = [...race.boats].sort((a, b) => a.predicted_rank - b.predicted_rank);
  const rows = boats
    .map((b) => {
      const prob = Math.round((b.win_probability ?? 0) * 1000) / 10;
      const rankClass = b.predicted_rank <= 2 ? ` r${b.predicted_rank}` : "";
      return `<tr class="rank-${b.predicted_rank}">
        <td class="rank-cell${rankClass}">${b.predicted_rank}</td>
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

  return `<article class="race-card">
    <div class="race-head">
      <span class="race-no">${race.race_number}R</span>
      <span class="race-title">${esc(race.race_title ?? "")}</span>
      <span class="race-close">締切 ${esc(closeTime)}</span>
    </div>
    ${cond ? `<div class="race-cond">${esc(cond)}</div>` : ""}
    <table class="boats">
      <thead><tr>
        <th>予測</th><th>艇</th><th>選手</th><th>全国勝率</th><th>M2連率</th><th>展示T</th><th colspan="2">勝率(AI)</th>
      </tr></thead>
      <tbody>${rows}</tbody>
    </table>
    <div class="trifecta"><span class="trifecta-label">3連単推奨:</span>${combos}</div>
  </article>`;
}

function racerLink(boat) {
  const name = esc(boat.racer_name ?? "-");
  if (boat.racer_number == null) return name;
  return `<a class="racer-link" href="racers.html#${boat.racer_number}">${name}</a>`;
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
