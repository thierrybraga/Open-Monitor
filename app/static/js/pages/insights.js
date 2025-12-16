"use strict";

(function () {
  let state = {
    page: 1,
    perPage: 10,
    severity: "all",
    search: "",
    rows: []
  };

  function fetchOverviewAndUpdateCards() {
    const elCritical = document.getElementById("critical-count");
    const elAssets = document.getElementById("assets-count");
    const elRules = document.getElementById("monitoring-rules-count");
    const elAssetsWithVulns = document.getElementById("assets-with-vulns-count");
    const elAssetsWithCritical = document.getElementById("assets-with-critical-count");
    const elAssetsWithoutVendor = document.getElementById("assets-without-vendor-count");
    const elAssetsWithoutOwner = document.getElementById("assets-without-owner-count");
    if (!elCritical && !elAssets && !elRules && !elAssetsWithVulns && !elAssetsWithCritical && !elAssetsWithoutVendor && !elAssetsWithoutOwner) return;
    fetch("/api/insights/overview", { credentials: "include" })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error("Falha ao carregar overview"))))
      .then((json) => {
        const data = json && json.data ? json.data : {};
        const num = (v) => {
          const n = parseInt(v, 10);
          return Number.isFinite(n) ? n : 0;
        };
        if (elCritical) elCritical.textContent = num(data.critical_count);
        if (elAssets) elAssets.textContent = num(data.assets_count);
        if (elRules) elRules.textContent = num(data.monitoring_rules_count);
        if (elAssetsWithVulns) elAssetsWithVulns.textContent = num(data.assets_with_vulns_count);
        if (elAssetsWithCritical) elAssetsWithCritical.textContent = num(data.assets_with_critical_count);
        if (elAssetsWithoutVendor) elAssetsWithoutVendor.textContent = num(data.assets_without_vendor_count);
        if (elAssetsWithoutOwner) elAssetsWithoutOwner.textContent = num(data.assets_without_owner_count);
      })
      .catch((err) => {
        console.warn("[Insights] Erro overview:", err);
      });
  }

  function initInsightsCharts() {
    try {
      const trendCanvas = document.getElementById("vulnerabilityTrendChart");
      const trendEmpty = document.getElementById("trend-chart-empty");
      const severityCanvas = document.getElementById("severityChart");
      const severityEmpty = document.getElementById("severity-chart-empty");

      if (trendCanvas) {
        fetch("/api/insights/timeseries/asset_vulns", { credentials: "include" })
          .then((r) => (r.ok ? r.json() : Promise.reject(new Error("Falha ao carregar timeseries"))))
          .then((json) => {
            const points = Array.isArray(json.data) ? json.data : [];
            if (!points.length) {
              if (trendEmpty) trendEmpty.style.display = "block";
              trendCanvas.style.display = "none";
              return;
            }
            const labels = points.map((d) => d.date);
            const values = points.map((d) => d.value);
            const ctx = trendCanvas.getContext("2d");
            new Chart(ctx, {
              type: "line",
              data: {
                labels: labels,
                datasets: [
                  {
                    label: "CVEs por dia",
                    data: values,
                    borderColor: "rgba(54, 162, 235, 1)",
                    backgroundColor: "rgba(54, 162, 235, 0.2)",
                    tension: 0.25,
                    fill: true,
                  },
                ],
              },
              options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                  legend: { display: true },
                  tooltip: { enabled: true },
                },
                scales: {
                  x: { display: true },
                  y: { display: true, beginAtZero: true },
                },
              },
            });
          })
          .catch((err) => {
            console.warn("[Insights] Erro carregando timeseries:", err);
          });
      }

      if (severityCanvas) {
        fetch("/api/insights/severity-distribution", { credentials: "include" })
          .then((r) => (r.ok ? r.json() : Promise.reject(new Error("Falha ao carregar distribuição de severidade"))))
          .then((json) => {
            const data = json && json.data ? json.data : { labels: [], data: [] };
            const hasData = (Array.isArray(data.labels) && data.labels.length) || (Array.isArray(data.data) && data.data.reduce((a, b) => a + b, 0) > 0);
            if (!hasData) {
              if (severityEmpty) severityEmpty.style.display = "block";
              severityCanvas.style.display = "none";
              return;
            }
            const ctx = severityCanvas.getContext("2d");
            new Chart(ctx, {
              type: "pie",
              data: {
                labels: data.labels,
                datasets: [
                  {
                    data: data.data,
                    backgroundColor: [
                      "rgba(220, 53, 69, 0.7)", // Critical - vermelho
                      "rgba(255, 193, 7, 0.7)", // High - amarelo
                      "rgba(13, 110, 253, 0.7)", // Medium - azul
                      "rgba(25, 135, 84, 0.7)", // Low - verde
                    ],
                    borderColor: [
                      "rgba(220, 53, 69, 1)",
                      "rgba(255, 193, 7, 1)",
                      "rgba(13, 110, 253, 1)",
                      "rgba(25, 135, 84, 1)",
                    ],
                    borderWidth: 1,
                  },
                ],
              },
              options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                  legend: { position: "bottom" },
                  tooltip: { enabled: true },
                },
              },
            });
          })
          .catch((err) => {
            console.warn("[Insights] Erro carregando distribuição de severidade:", err);
          });
      }
    } catch (e) {
      console.error("[Insights] Falha ao inicializar gráficos:", e);
    }
  }

  function readTableRows() {
    const tbody = document.getElementById("insights-tbody");
    if (!tbody) return [];
    return Array.from(tbody.querySelectorAll("tr"));
  }

  function normalize(text) {
    return (text || "").toString().toLowerCase();
  }

  function applyFilters() {
    const rows = state.rows;
    const severity = state.severity;
    const q = normalize(state.search);
    const filtered = rows.filter((tr) => {
      const tds = tr.querySelectorAll("td");
      const type = normalize(tds[1]?.textContent || "");
      const desc = normalize(tds[2]?.textContent || "");
      const sevText = normalize(tr.querySelector(".badge")?.textContent || "");
      const matchSeverity = severity === "all" || sevText === normalize(severity);
      const matchSearch = !q || type.includes(q) || desc.includes(q);
      return matchSeverity && matchSearch;
    });
    return filtered;
  }

  function renderPagination(total) {
    const container = document.getElementById("insights-pagination");
    if (!container) return;
    const pages = Math.max(1, Math.ceil(total / state.perPage));
    state.page = Math.min(state.page, pages);
    let html = "";
    const prevDisabled = state.page <= 1 ? "disabled" : "";
    const nextDisabled = state.page >= pages ? "disabled" : "";
    html += `<button class="btn btn-sm btn-outline-primary me-2" ${prevDisabled} id="insights-prev">&laquo; Anterior</button>`;
    html += `<span class="small me-2">Página ${state.page} de ${pages}</span>`;
    html += `<button class="btn btn-sm btn-outline-primary" ${nextDisabled} id="insights-next">Próxima &raquo;</button>`;
    container.innerHTML = html;
    const prevBtn = document.getElementById("insights-prev");
    const nextBtn = document.getElementById("insights-next");
    if (prevBtn) prevBtn.onclick = () => { if (state.page > 1) { state.page--; renderTable(); } };
    if (nextBtn) nextBtn.onclick = () => { const pages2 = Math.ceil(total / state.perPage); if (state.page < pages2) { state.page++; renderTable(); } };
  }

  function renderTable() {
    const rows = state.rows;
    const filtered = applyFilters();
    const total = filtered.length;
    const start = (state.page - 1) * state.perPage;
    const end = start + state.perPage;
    rows.forEach((tr) => (tr.style.display = "none"));
    filtered.slice(start, end).forEach((tr) => (tr.style.display = ""));
    renderPagination(total);
  }

  function bindControls() {
    const perPageSel = document.getElementById("insight-per-page");
    const sevSel = document.getElementById("insight-filter-severity");
    const searchInput = document.getElementById("insight-search");
    if (perPageSel) {
      perPageSel.addEventListener("change", () => {
        state.perPage = parseInt(perPageSel.value, 10) || 10;
        state.page = 1;
        renderTable();
      });
    }
    if (sevSel) {
      sevSel.addEventListener("change", () => {
        state.severity = sevSel.value;
        state.page = 1;
        renderTable();
      });
    }
    if (searchInput) {
      let t;
      searchInput.addEventListener("input", () => {
        clearTimeout(t);
        t = setTimeout(() => {
          state.search = searchInput.value || "";
          state.page = 1;
          renderTable();
        }, 200);
      });
    }
  }

  function initTable() {
    state.rows = readTableRows();
    bindControls();
    renderTable();
  }

  function init() {
    fetchOverviewAndUpdateCards();
    initInsightsCharts();
    initTable();
  }

  document.addEventListener("DOMContentLoaded", init, { once: true });
})();
