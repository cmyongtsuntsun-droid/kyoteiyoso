/* 競艇予想AI 選手分析ページ
 * api/v1/racers/racers.json を fetch し、検索・ソート・個別詳細を描画する。
 * file:// で開かれた場合は racers.js (グローバル変数) にフォールバック。
 */
"use strict";

const RACERS_API_URL = "api/v1/racers/racers.json";
const RACERS_FALLBACK_URL = "api/v1/racers/racers.js";
const LIST_LIMIT = 100;
// この出走数以上の選手は静的ページ (racers/登番.html) が生成される (seo.py と一致)
const MIN_PAGE_RACES = 6;

const state = {
  racers: [],
  query: "",
  classFilter: "",
  sortKey: "win_rate",
  minRaces: true,
  selected: null,
};

document.addEventListener("DOMContentLoaded", init);

async function init() {
  const status = document.getElementById("status");
  try {
    const data = await loadData();
    state.racers = data.racers;
    status.remove();
    renderMeta(data);
    bindControls();
    openFromHash();
    renderList();
  } catch (err) {
    status.textContent =
      "選手データの読み込みに失敗しました。python -m kyotei.cli racers を実行してください。 (" + err.message + ")";
    status.classList.add("error");
  }
}

async function loadData() {
  try {
    const res = await fetch(RACERS_API_URL, { cache: "no-store" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (fetchErr) {
    const data = await new Promise((resolve) => {
      const script = document.createElement("script");
      script.src = RACERS_FALLBACK_URL;
      script.onload = () => resolve(window.__KYOTEI_RACERS__ ?? null);
      script.onerror = () => resolve(null);
      document.head.appendChild(script);
    });
    if (data) return data;
    throw fetchErr;
  }
}

function renderMeta(data) {
  document.getElementById("meta-info").textContent =
    `集計期間: ${data.period[0]} 〜 ${data.period[1]} / 対象 ${data.racer_count} 選手`;
}

function bindControls() {
  document.getElementById("search-box").addEventListener("input", (e) => {
    state.query = e.target.value.trim();
    renderList();
  });
  document.getElementById("sort-select").addEventListener("change", (e) => {
    state.sortKey = e.target.value;
    renderList();
  });
  document.getElementById("min-races").addEventListener("change", (e) => {
    state.minRaces = e.target.checked;
    renderList();
  });
  document.querySelectorAll("#class-filter .stadium-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("#class-filter .stadium-btn")
        .forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      state.classFilter = btn.dataset.class;
      renderList();
    });
  });
  window.addEventListener("hashchange", openFromHash);
}

function openFromHash() {
  const num = Number(location.hash.slice(1));
  if (!num) return;
  const racer = state.racers.find((r) => r.racer_number === num);
  if (racer) {
    state.selected = racer;
    renderDetail();
    document.getElementById("racer-detail").scrollIntoView({ behavior: "smooth" });
  }
}

function filteredRacers() {
  let list = state.racers;
  if (state.minRaces) list = list.filter((r) => r.stats.races >= 10);
  if (state.classFilter) list = list.filter((r) => r.racer_class === state.classFilter);
  if (state.query) {
    const q = state.query.toLowerCase();
    list = list.filter(
      (r) =>
        String(r.racer_number).includes(q) ||
        (r.racer_name ?? "").toLowerCase().replace(/\s/g, "").includes(q.replace(/\s/g, ""))
    );
  }
  const key = state.sortKey;
  list = [...list].sort((a, b) => {
    const av = a.stats[key], bv = b.stats[key];
    if (av == null) return 1;
    if (bv == null) return -1;
    return key === "avg_st" ? av - bv : bv - av; // STは小さいほど良い
  });
  return list;
}

function renderList() {
  const wrap = document.getElementById("racer-list");
  const list = filteredRacers();
  const shown = list.slice(0, LIST_LIMIT);

  const rows = shown
    .map((r, i) => {
      const s = r.stats;
      const name = esc(r.racer_name ?? "-");
      // 静的ページがある選手はクロール可能な実リンクにする (SEO)
      const nameCell =
        s.races >= MIN_PAGE_RACES
          ? `<a class="racer-link" href="racers/${r.racer_number}.html">${name}</a>`
          : name;
      return `<tr class="racer-row" data-racer="${r.racer_number}">
        <td class="dim">${i + 1}</td>
        <td>${esc(r.racer_number)}</td>
        <td class="racer-name-cell">${nameCell}</td>
        <td><span class="class-badge class-${esc(r.racer_class)}">${esc(r.racer_class)}</span></td>
        <td>${s.races}</td>
        <td class="num strong">${pct(s.win_rate)}</td>
        <td class="num">${pct(s.top2_rate)}</td>
        <td class="num">${pct(s.top3_rate)}</td>
        <td class="num">${fmt(s.avg_st)}</td>
        <td class="num">${pct(s.recent_win_rate)}</td>
      </tr>`;
    })
    .join("");

  wrap.innerHTML = `
    <p class="list-note">${list.length} 選手中 ${shown.length} 名を表示 (行クリックで詳細)</p>
    <table class="boats racer-table">
      <thead><tr>
        <th>#</th><th>登番</th><th>選手名</th><th>級</th><th>出走</th>
        <th>1着率</th><th>2連対</th><th>3連対</th><th>平均ST</th><th>直近調子</th>
      </tr></thead>
      <tbody>${rows}</tbody>
    </table>`;

  wrap.querySelectorAll(".racer-row").forEach((tr) => {
    tr.addEventListener("click", (e) => {
      // 選手名リンク(静的ページ)のクリックはそのまま遷移させる
      if (e.target.closest("a")) return;
      location.hash = tr.dataset.racer;
    });
  });
}

function renderDetail() {
  const wrap = document.getElementById("racer-detail");
  const r = state.selected;
  if (!r) { wrap.innerHTML = ""; return; }
  const s = r.stats;

  const courseRows = r.by_course
    .map((c) => {
      const w = c.races ? (c.win_rate * 100) : 0;
      return `<tr>
        <td><span class="boat-badge boat-${c.course}">${c.course}</span></td>
        <td>${c.races}</td>
        <td class="num">${c.races ? pct(c.win_rate) : "-"}</td>
        <td class="num">${c.races ? pct(c.top3_rate) : "-"}</td>
        <td class="num">${c.races ? fmt(c.avg_st) : "-"}</td>
        <td class="bar-cell"><div class="prob-bar-wrap"><div class="prob-bar" style="width:${Math.min(w, 100)}%"></div></div></td>
      </tr>`;
    })
    .join("");

  const stadiumRows = r.by_stadium
    .slice(0, 8)
    .map((st) =>
      `<tr><td>${esc(st.stadium)}</td><td>${st.races}</td>
       <td class="num">${pct(st.win_rate)}</td><td class="num">${pct(st.top3_rate)}</td></tr>`)
    .join("");

  const recentRows = r.recent_races
    .map((race) => {
      const placeClass = race.place === 1 ? "place-1" : race.place <= 3 ? "place-3" : "";
      return `<tr>
        <td class="dim">${esc(race.race_date.slice(5))}</td>
        <td>${esc(race.stadium)} ${race.race_number}R</td>
        <td><span class="boat-badge boat-${race.course}">${race.course}</span></td>
        <td class="num">${fmt(race.st)}</td>
        <td class="num ${placeClass}">${race.place}着</td>
      </tr>`;
    })
    .join("");

  wrap.innerHTML = `<article class="race-card detail-card">
    <div class="detail-head">
      <h2>${esc(r.racer_name ?? "-")}
        <span class="class-badge class-${esc(r.racer_class)}">${esc(r.racer_class)}</span>
      </h2>
      <button class="close-btn" id="close-detail">✕ 閉じる</button>
    </div>
    <div class="model-stats detail-chips">
      <div class="stat-chip">登番<strong>${esc(r.racer_number)}</strong></div>
      <div class="stat-chip">年齢<strong>${fmt(r.age)}</strong></div>
      <div class="stat-chip">体重<strong>${fmt(r.weight)}kg</strong></div>
      <div class="stat-chip">全国勝率<strong>${fmt(r.national_top1)}</strong></div>
      <div class="stat-chip">F数<strong>${fmt(r.flying_count)}</strong></div>
    </div>
    <div class="model-stats detail-chips">
      <div class="stat-chip">出走<strong>${s.races}</strong></div>
      <div class="stat-chip">1着率<strong>${pct(s.win_rate)}</strong></div>
      <div class="stat-chip">2連対率<strong>${pct(s.top2_rate)}</strong></div>
      <div class="stat-chip">3連対率<strong>${pct(s.top3_rate)}</strong></div>
      <div class="stat-chip">平均ST<strong>${fmt(s.avg_st)}</strong></div>
      <div class="stat-chip">ST安定度(σ)<strong>${fmt(s.st_std)}</strong></div>
      <div class="stat-chip">展示平均<strong>${fmt(s.avg_exhibition_time)}</strong></div>
    </div>
    <div class="detail-grid">
      <section>
        <h3>コース別成績</h3>
        <table class="boats">
          <thead><tr><th>コース</th><th>出走</th><th>1着率</th><th>3連対</th><th>平均ST</th><th></th></tr></thead>
          <tbody>${courseRows}</tbody>
        </table>
      </section>
      <section>
        <h3>場別成績</h3>
        <table class="boats">
          <thead><tr><th>場</th><th>出走</th><th>1着率</th><th>3連対</th></tr></thead>
          <tbody>${stadiumRows}</tbody>
        </table>
      </section>
      <section>
        <h3>直近${r.recent_races.length}走</h3>
        <table class="boats">
          <thead><tr><th>日付</th><th>レース</th><th>進入</th><th>ST</th><th>着順</th></tr></thead>
          <tbody>${recentRows}</tbody>
        </table>
      </section>
    </div>
  </article>`;

  document.getElementById("close-detail").addEventListener("click", () => {
    state.selected = null;
    history.replaceState(null, "", location.pathname + location.search);
    renderDetail();
  });
}

function pct(v) { return v == null ? "-" : (v * 100).toFixed(1) + "%"; }
function fmt(v) { return v == null ? "-" : String(v); }
function esc(s) {
  return String(s).replace(/[&<>"']/g, (ch) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]));
}
