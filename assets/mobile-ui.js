/* 競艇予想AI モバイルUI共通処理
 * 全ページ (index / racers / links / racers/*.html) で読み込まれる小さな共通スクリプト。
 * トップへ戻るボタン・共有(クリップボードコピー)・トースト通知を提供する。
 */
"use strict";

(function () {
  function initBackToTop() {
    const btn = document.getElementById("to-top-btn");
    if (!btn) return;
    const toggle = () => {
      btn.classList.toggle("show", window.scrollY > 480);
    };
    window.addEventListener("scroll", toggle, { passive: true });
    btn.addEventListener("click", () => {
      window.scrollTo({ top: 0, behavior: "smooth" });
    });
    toggle();
  }

  function initFilterBarShadow() {
    const bar = document.querySelector(".filter-bar");
    if (!bar) return;
    const toggle = () => bar.classList.toggle("scrolled", window.scrollY > 4);
    window.addEventListener("scroll", toggle, { passive: true });
    toggle();
  }

  function showToast(message) {
    let toast = document.getElementById("mini-toast");
    if (!toast) {
      toast = document.createElement("div");
      toast.id = "mini-toast";
      toast.className = "mini-toast";
      document.body.appendChild(toast);
    }
    toast.textContent = message;
    toast.classList.add("show");
    clearTimeout(toast._hideTimer);
    toast._hideTimer = window.setTimeout(() => toast.classList.remove("show"), 2200);
  }

  async function share(title, url) {
    if (navigator.share) {
      try {
        await navigator.share({ title, url });
      } catch (err) {
        /* ユーザーがキャンセルした場合は何もしない */
      }
      return;
    }
    try {
      await navigator.clipboard.writeText(url);
      showToast("リンクをコピーしました");
    } catch (err) {
      showToast("コピーできませんでした");
    }
  }

  window.KyoteiUI = { showToast, share };

  document.addEventListener("DOMContentLoaded", () => {
    initBackToTop();
    initFilterBarShadow();
  });
})();
