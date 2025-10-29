/*
  Monitoring page interactions
  - Client-side filtering, sorting, pagination, export
  - Data refresh via /api/v1/assets
  - Safe Mapbox modal initialization preserved
*/
(function () {
  function onReady(fn) {
    if (document.readyState !== 'loading') fn();
    else document.addEventListener('DOMContentLoaded', fn, { once: true });
  }

  const STATUS_ALIASES = {
    online: new Set(['active', 'online', 'up']),
    offline: new Set(['inactive', 'offline', 'down']),
    warning: new Set(['warning', 'degraded', 'maintenance']),
  };
  function normStatus(s) {
    return (s || '').trim().toLowerCase();
  }

  const state = {
    items: [],
    filtered: [],
    page: 1,
    perPage: 10,
    total: 0,
    pages: 1,
    search: '',
    statusFilter: 'all',
    sort: 'ip_asc',
    view: 'table',
    autoRefreshId: null,
    apiPerPage: 100,
  };

  function qs(sel) { return document.querySelector(sel); }
  function qsa(sel) { return Array.from(document.querySelectorAll(sel)); }

  // Debounce util para inputs
  function debounce(fn, ms) {
    var t;
    return function() {
      var ctx = this, args = arguments;
      clearTimeout(t);
      t = setTimeout(function() { fn.apply(ctx, args); }, ms);
    };
  }

  function updateBulkDeleteVisibility() {
    var selected = qsa('#device-table-body .select-device:checked').length;
    var btn = qs('#bulkDeleteBtn');
    if (!btn) return;
    // Manter visível; desabilitar quando não houver seleção e ajustar estilo
    var hasSelection = selected > 0;
    btn.disabled = !hasSelection;
    btn.classList.toggle('btn-danger', hasSelection);
    btn.classList.toggle('btn-outline-danger', !hasSelection);
    btn.setAttribute('title', hasSelection ? ('Apagar ' + selected + ' selecionado(s)') : 'Selecione dispositivos para apagar');
    var textEl = btn.querySelector('.btn-text');
    if (textEl) {
      textEl.textContent = hasSelection ? ('Apagar Selecionados (' + selected + ')') : 'Apagar Selecionados';
    }
  }

  function updateSortIndicators() {
    var sort = state.sort;
    qsa('th.sortable').forEach(function(th) {
      var icon = th.querySelector('i');
      var key = th.getAttribute('data-sort');
      if (!icon || !key) return;
      icon.className = 'bi bi-arrow-down-up';
      if (key + '_asc' === sort) icon.className = 'bi bi-arrow-up';
      else if (key + '_desc' === sort) icon.className = 'bi bi-arrow-down';
      else if (key === 'status' && sort === 'status') icon.className = 'bi bi-arrow-down-up';
    });
    var sortSel = qs('#sort-devices');
    if (sortSel) sortSel.value = sort;
  }

  function setLoading(loading) {
    var spinner = qs('#spinner');
    if (!spinner) return;
    spinner.classList.toggle('d-none', !loading);
  }

  // Mapbox: preserve safe initialization used by template
  var mapInstance = null;
  function resolveCenter() {
    var container = document.getElementById('map');
    if (container && container.dataset) {
      var lat = parseFloat(container.dataset.lat);
      var lng = parseFloat(container.dataset.lng);
      if (Number.isFinite(lat) && Number.isFinite(lng)) {
        return [lng, lat];
      }
    }
    return [0, 0];
  }
  window.initMap = function () {
    try {
      var container = document.getElementById('map');
      if (!container) { console.warn('[monitoring.js] #map not found'); return; }
      if (!window.mapboxgl) { console.warn('[monitoring.js] Mapbox GL JS not available'); return; }
      if (!window.MAPBOX_ACCESS_TOKEN) { console.warn('[monitoring.js] MAPBOX_ACCESS_TOKEN missing'); return; }
      mapboxgl.accessToken = window.MAPBOX_ACCESS_TOKEN;
      var center = resolveCenter();
      if (mapInstance) { mapInstance.resize(); return; }
      mapInstance = new mapboxgl.Map({
        container: container,
        style: 'mapbox://styles/mapbox/streets-v11',
        center: center,
        zoom: 2,
        attributionControl: true,
      });
      mapInstance.on('load', function () {
        try {
          new mapboxgl.Marker({ color: '#e74c3c' }).setLngLat(center).addTo(mapInstance);
          mapInstance.resize();
        } catch (innerErr) { console.warn('[monitoring.js] map load error:', innerErr); }
      });
    } catch (err) { console.warn('[monitoring.js] initMap error:', err); }
  };

  function computeMetrics(items) {
    const counts = { total: items.length, online: 0, offline: 0, warning: 0 };
    for (const it of items) {
      const s = normStatus(it.status);
      if (STATUS_ALIASES.online.has(s)) counts.online++;
      else if (STATUS_ALIASES.offline.has(s)) counts.offline++;
      else if (STATUS_ALIASES.warning.has(s)) counts.warning++;
    }
    return counts;
  }

  function updateMetricCards(items) {
    const c = computeMetrics(items);
    const ids = ['total', 'online', 'offline', 'warning'];
    ids.forEach(k => {
      const el = document.getElementById(`${k}-devices`);
      if (el) el.textContent = String(c[k] || 0);
    });
  }

  function renderTable(rows) {
    const tbody = qs('#device-table-body');
    if (!tbody) return;
    if (!rows || rows.length === 0) {
      tbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted p-4">No Devices Found</td></tr>';
      return;
    }
    const html = rows.map(it => {
      const s = normStatus(it.status);
      let badge = 'bg-secondary';
      if (STATUS_ALIASES.online.has(s)) badge = 'bg-success';
      else if (STATUS_ALIASES.offline.has(s)) badge = 'bg-danger';
      else if (STATUS_ALIASES.warning.has(s)) badge = 'bg-warning text-dark';
      const lastSeen = it.updated_at || it.created_at || '-';
      const nameEsc = (it.name || '').replace(/</g, '&lt;').replace(/>/g, '&gt;');
      const ipEsc = (it.ip_address || '').replace(/</g, '&lt;').replace(/>/g, '&gt;');
      const vendorNameEsc = ((it.vendor && it.vendor.name) || it.vendor_name || '-').replace(/</g, '&lt;').replace(/>/g, '&gt;');
      return (
        `<tr>`+
          `<td><input type="checkbox" class="select-device" data-id="${it.id}" aria-label="Select device ${nameEsc}" /></td>`+
          `<td><span class="font-monospace">${ipEsc}</span></td>`+
          `<td>${nameEsc}</td>`+
          `<td>${vendorNameEsc}</td>`+
          `<td><span class="badge ${badge} text-capitalize">${s || 'unknown'}</span></td>`+
          `<td>${lastSeen}</td>`+
          `<td><a href="/assets/${it.id}" class="btn btn-sm btn-outline-primary" title="View details" aria-label="View details for ${nameEsc}"><i class="bi bi-eye"></i></a></td>`+
        `</tr>`
      );
    }).join('');
    tbody.innerHTML = html;
  }

  function renderGrid(rows) {
    const grid = qs('#device-grid');
    if (!grid) return;
    if (!rows || rows.length === 0) {
      grid.innerHTML = '<div class="col"><div class="card p-4 text-center text-muted">No Devices Found</div></div>';
      return;
    }
    const html = rows.map(it => {
      const s = normStatus(it.status);
      let badge = 'bg-secondary';
      if (STATUS_ALIASES.online.has(s)) badge = 'bg-success';
      else if (STATUS_ALIASES.offline.has(s)) badge = 'bg-danger';
      else if (STATUS_ALIASES.warning.has(s)) badge = 'bg-warning text-dark';
      const lastSeen = it.updated_at || it.created_at || '-';
      const nameEsc = (it.name || '').replace(/</g, '&lt;').replace(/>/g, '&gt;');
      const ipEsc = (it.ip_address || '').replace(/</g, '&lt;').replace(/>/g, '&gt;');
      const vendorNameEsc = ((it.vendor && it.vendor.name) || it.vendor_name || '-').replace(/</g, '&lt;').replace(/>/g, '&gt;');
      return (
        `<div class="col">`+
          `<div class="card shadow-sm h-100">`+
            `<div class="card-body">`+
              `<div class="d-flex justify-content-between align-items-start">`+
                `<div>`+
                  `<div class="fw-semibold">${nameEsc || 'Unknown Device'}</div>`+
                  `<div class="text-muted font-monospace">${ipEsc}</div>`+
                  `<div class="text-muted small">Vendor: ${vendorNameEsc}</div>`+
                `</div>`+
                `<span class="badge ${badge} text-capitalize">${s || 'unknown'}</span>`+
              `</div>`+
              `<div class="mt-3 text-muted small">Last Seen: ${lastSeen}</div>`+
            `</div>`+
            `<div class="card-footer d-flex justify-content-end">`+
              `<a href="/assets/${it.id}" class="btn btn-sm btn-outline-primary" title="View details" aria-label="View details for ${nameEsc}"><i class="bi bi-eye"></i></a>`+
            `</div>`+
          `</div>`+
        `</div>`
      );
    }).join('');
    grid.innerHTML = html;
  }

  function applyFilters() {
    const term = state.search.trim().toLowerCase();
    const statusF = state.statusFilter;
    let arr = state.items.slice();
    if (term) {
      arr = arr.filter(it => {
        const ip = (it.ip_address || '').toLowerCase();
        const name = (it.name || '').toLowerCase();
        const vendor = ((it.vendor && it.vendor.name) || it.vendor_name || '').toLowerCase();
        return ip.includes(term) || name.includes(term) || vendor.includes(term);
      });
    }
    if (statusF !== 'all') {
      arr = arr.filter(it => {
        const s = normStatus(it.status);
        if (statusF === 'online') return STATUS_ALIASES.online.has(s);
        if (statusF === 'offline') return STATUS_ALIASES.offline.has(s);
        if (statusF === 'warning') return STATUS_ALIASES.warning.has(s);
        return true;
      });
    }
    // sort
    const sort = state.sort;
    arr.sort((a, b) => {
      if (sort === 'ip_asc' || sort === 'ip_desc') {
        const ai = (a.ip_address || '');
        const bi = (b.ip_address || '');
        if (ai < bi) return sort === 'ip_asc' ? -1 : 1;
        if (ai > bi) return sort === 'ip_asc' ? 1 : -1;
        return 0;
      } else if (sort === 'name_asc') {
        const an = (a.name || '').toLowerCase();
        const bn = (b.name || '').toLowerCase();
        if (an < bn) return -1; if (an > bn) return 1; return 0;
      } else if (sort === 'status') {
        const order = (s) => STATUS_ALIASES.online.has(s) ? 0 : STATUS_ALIASES.warning.has(s) ? 1 : STATUS_ALIASES.offline.has(s) ? 2 : 3;
        const as = order(normStatus(a.status));
        const bs = order(normStatus(b.status));
        if (as !== bs) return as - bs;
        const an = (a.name || '').toLowerCase();
        const bn = (b.name || '').toLowerCase();
        if (an < bn) return -1; if (an > bn) return 1; return 0;
      } else if (sort === 'vendor_asc' || sort === 'vendor_desc') {
        const av = ((a.vendor && a.vendor.name) || a.vendor_name || '').toLowerCase();
        const bv = ((b.vendor && b.vendor.name) || b.vendor_name || '').toLowerCase();
        if (av < bv) return sort === 'vendor_asc' ? -1 : 1;
        if (av > bv) return sort === 'vendor_asc' ? 1 : -1;
        const an = (a.name || '').toLowerCase();
        const bn = (b.name || '').toLowerCase();
        if (an < bn) return -1; if (an > bn) return 1; return 0;
      }
      return 0;
    });

    state.filtered = arr;
    state.pages = Math.max(1, Math.ceil(arr.length / state.perPage));
    state.page = Math.min(state.page, state.pages);
    updateMetricCards(arr);
  }

  function sliceForPage() {
    const start = (state.page - 1) * state.perPage;
    return state.filtered.slice(start, start + state.perPage);
  }

  function updatePaginationUI() {
    const info = qs('#page-info');
    const prev = qs('#prev-page');
    const next = qs('#next-page');
    if (info) info.textContent = `Page ${state.page} of ${state.pages}`;
    if (prev) prev.disabled = state.page <= 1;
    if (next) next.disabled = state.page >= state.pages;
  }

  function render() {
    applyFilters();
    const pageRows = sliceForPage();
    if (state.view === 'table') {
      qs('#device-table')?.classList.remove('d-none');
      qs('#device-grid')?.classList.add('d-none');
      renderTable(pageRows);
    } else {
      qs('#device-table')?.classList.add('d-none');
      qs('#device-grid')?.classList.remove('d-none');
      renderGrid(pageRows);
    }
    updatePaginationUI();
    updateSortIndicators();
    updateBulkDeleteVisibility();
  }

  async function fetchAllAssets() {
    setLoading(true);
    try {
      const firstUrl = `/api/v1/assets?page=1&per_page=${state.apiPerPage}`;
      const r1 = await fetch(firstUrl, { headers: { 'Accept': 'application/json' } });
      if (!r1.ok) throw new Error(`HTTP ${r1.status}`);
      const j1 = await r1.json();
      let items = j1.data || [];
      const pages = (j1.meta && j1.meta.pages) || 1;
      for (let p = 2; p <= pages; p++) {
        const url = `/api/v1/assets?page=${p}&per_page=${state.apiPerPage}`;
        const r = await fetch(url, { headers: { 'Accept': 'application/json' } });
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const j = await r.json();
        items = items.concat(j.data || []);
      }
      state.items = items;
      state.total = items.length;
      render();
    } catch (err) {
      console.warn('[monitoring.js] Failed to fetch assets:', err);
    } finally {
      setLoading(false);
    }
  }

  function wireEvents() {
    const toggle = qs('#view-toggle');
    if (toggle) {
      toggle.addEventListener('click', function () {
        const next = state.view === 'table' ? 'grid' : 'table';
        state.view = next;
        toggle.dataset.view = next;
        toggle.innerHTML = next === 'table' ? '<i class="bi bi-list"></i> Table View' : '<i class="bi bi-grid"></i> Grid View';
        render();
      });
    }

    // Ordenação por cabeçalhos
    qsa('th.sortable').forEach(function(th) {
      th.addEventListener('click', function () {
        var key = th.getAttribute('data-sort');
        var next;
        if (key === 'status') next = 'status';
        else {
          var asc = key + '_asc';
          var desc = key + '_desc';
          next = (state.sort === asc) ? desc : asc;
        }
        state.sort = next;
        state.page = 1;
        updateSortIndicators();
        render();
      });
    });

    const filterInput = qs('#filter-devices');
    if (filterInput) {
      const onSearch = debounce(function (e) {
        state.search = e.target.value || '';
        state.page = 1;
        render();
      }, 150);
      filterInput.addEventListener('input', onSearch);
      filterInput.addEventListener('keydown', function(e) {
        var key = e.key || e.keyCode;
        if (key === 'Escape' || key === 27) {
          filterInput.value = '';
          state.search = '';
          state.page = 1;
          render();
        }
      });
    }
    const clearBtn = qs('#clear-search');
    if (clearBtn && filterInput) {
      clearBtn.addEventListener('click', function() {
        filterInput.value = '';
        state.search = '';
        state.page = 1;
        render();
      });
    }

    const statusSel = qs('#status-filter');
    if (statusSel) {
      statusSel.addEventListener('change', function (e) {
        state.statusFilter = e.target.value || 'all';
        state.page = 1;
        render();
      });
    }
    // Removido: sortSel (dropdown), mantido guard caso exista em templates antigos
    const sortSel = qs('#sort-devices');
    if (sortSel) {
      sortSel.addEventListener('change', function (e) {
        state.sort = e.target.value || 'ip_asc';
        render();
      });
    }

    const pageSizeSel = qs('#page-size');
    if (pageSizeSel) {
      pageSizeSel.addEventListener('change', function (e) {
        const v = parseInt(e.target.value, 10);
        state.perPage = Number.isFinite(v) && v > 0 ? v : 10;
        state.page = 1;
        render();
      });
    }
    const prev = qs('#prev-page');
    const next = qs('#next-page');
    if (prev) prev.addEventListener('click', function () { if (state.page > 1) { state.page--; render(); } });
    if (next) next.addEventListener('click', function () { if (state.page < state.pages) { state.page++; render(); } });

    const selectAll = qs('#select-all-table');
    if (selectAll) {
      selectAll.addEventListener('change', function (e) {
        const checked = e.target.checked;
        qsa('#device-table-body .select-device').forEach(function(cb) { cb.checked = checked; });
        updateBulkDeleteVisibility();
      });
    }
    // Atualizar visibilidade do botão ao selecionar individualmente
    const tbody = qs('#device-table-body');
    if (tbody) {
      tbody.addEventListener('change', function(e) {
        var t = e.target;
        if (t && t.matches('.select-device')) updateBulkDeleteVisibility();
      });
    }

    const refreshBtn = qs('#refreshBtn');
    if (refreshBtn) {
      refreshBtn.addEventListener('click', function () { fetchAllAssets(); });
    }
    const refreshIntervalSel = qs('#refresh-interval');
    if (refreshIntervalSel) {
      refreshIntervalSel.addEventListener('change', function (e) {
        const ms = parseInt(e.target.value, 10) || 0;
        if (state.autoRefreshId) { clearInterval(state.autoRefreshId); state.autoRefreshId = null; }
        if (ms > 0) { state.autoRefreshId = setInterval(fetchAllAssets, ms); }
      });
    }

    const exportMenu = qsa('.dropdown-menu [data-format]');
    exportMenu.forEach(btn => {
      btn.addEventListener('click', function () {
        const format = btn.getAttribute('data-format');
        const rows = sliceForPage(); // export current page view
        if (format === 'json') {
          const blob = new Blob([JSON.stringify(rows, null, 2)], { type: 'application/json' });
          const a = document.createElement('a');
          a.href = URL.createObjectURL(blob);
          a.download = 'devices.json';
          a.click();
          URL.revokeObjectURL(a.href);
        } else if (format === 'csv') {
          const headers = ['id','ip_address','name','vendor','status','created_at','updated_at'];
          const csv = [headers.join(',')].concat(rows.map(it => headers.map(h => {
            let v = it[h];
            if (h === 'vendor') v = (it.vendor && it.vendor.name) || it.vendor_name || '';
            v = v == null ? '' : String(v).replace(/"/g, '""');
            return '"' + v + '"';
          }).join(','))).join('\n');
          const blob = new Blob([csv], { type: 'text/csv' });
          const a = document.createElement('a');
          a.href = URL.createObjectURL(blob);
          a.download = 'devices.csv';
          a.click();
          URL.revokeObjectURL(a.href);
        }
      });
    });

    // Deleção em massa
    const bulkBtn = qs('#bulkDeleteBtn');
    if (bulkBtn) {
      bulkBtn.addEventListener('click', async function () {
        const ids = qsa('#device-table-body .select-device:checked').map(function(cb){ return cb.getAttribute('data-id'); }).filter(Boolean);
        if (!ids.length) return;
        bulkBtn.querySelector('.btn-text')?.classList.add('d-none');
        bulkBtn.querySelector('.btn-loading')?.classList.remove('d-none');
        try {
          for (var i = 0; i < ids.length; i++) {
            var id = ids[i];
            var resp = await fetch('/assets/' + id + '/delete', { method: 'POST', headers: { 'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest' } });
            if (!resp.ok) { try { console.warn('Failed to delete asset', id); } catch(_){} }
          }
          await fetchAllAssets();
          var allCb = qs('#select-all-table'); if (allCb) allCb.checked = false;
          updateBulkDeleteVisibility();
        } catch (err) {
          try { console.warn('[monitoring.js] bulk delete failed:', err); } catch(_){}
        } finally {
          bulkBtn.querySelector('.btn-text')?.classList.remove('d-none');
          bulkBtn.querySelector('.btn-loading')?.classList.add('d-none');
        }
      });
    }

    // Reset Filters
    const resetBtn = qs('#reset-filters-btn');
    if (resetBtn) {
      resetBtn.addEventListener('click', function () {
        var input = qs('#filter-devices'); if (input) input.value = '';
        var statusSel = qs('#status-filter'); if (statusSel) statusSel.value = 'all';
        state.search = '';
        state.statusFilter = 'all';
        state.page = 1;
        state.view = 'table';
        var toggle = qs('#view-toggle'); if (toggle) { toggle.dataset.view = 'table'; toggle.innerHTML = '<i class="bi bi-list"></i> Table View'; }
        render();
      });
    }

    const deviceForm = qs('#device-form');
    if (deviceForm) {
      deviceForm.addEventListener('submit', async function (e) {
        e.preventDefault();
        const ipEl = qs('#device-ip');
        const nameEl = qs('#device-name');
        const errBox = qs('#form-error-message');
        const addBtn = qs('#addDeviceBtn');
        const ip = ipEl?.value?.trim();
        const name = nameEl?.value?.trim();
        const ipRegex = /^(?:\d{1,3}\.){3}\d{1,3}$/; // simple IPv4 validation
        if (!ip || !ipRegex.test(ip)) {
          errBox?.classList.remove('d-none');
          if (errBox) errBox.textContent = 'Please enter a valid IP address.';
          ipEl?.classList.add('is-invalid');
          return;
        }
        errBox?.classList.add('d-none');
        ipEl?.classList.remove('is-invalid');
        // Loading state
        var _text = addBtn ? addBtn.querySelector('.btn-text') : null;
        var _load = addBtn ? addBtn.querySelector('.btn-loading') : null;
        if (_text) _text.classList.add('d-none');
        if (_load) _load.classList.remove('d-none');
        try {
          var vendorEl = qs('#device-vendor');
      var vendor = (vendorEl && vendorEl.value) ? vendorEl.value.trim() : '';
      const resp = await fetch('/api/v1/assets', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
        body: JSON.stringify({ ip_address: ip, name: name || undefined, vendor: vendor || undefined })
      });
          if (!resp.ok) throw new Error('Failed to create asset');
          // refresh list
          await fetchAllAssets();
          // close modal
          const modalEl = document.getElementById('addDeviceModal');
          if (modalEl) {
      const modal = window.getModalInstance(modalEl);
      modal && modal.hide();
          }
          deviceForm.reset();
        } catch (err) {
          console.warn('[monitoring.js] create asset failed:', err);
          errBox?.classList.remove('d-none');
          if (errBox) errBox.textContent = 'Failed to save device. Please try again.';
        } finally {
          addBtn?.querySelector('.btn-text')?.classList.remove('d-none');
          addBtn?.querySelector('.btn-loading')?.classList.add('d-none');
        }
      });
    }

    // Map modal shown handler to init map
    var modalEl = document.getElementById('map-modal');
    if (modalEl) {
      modalEl.addEventListener('shown.bs.modal', function () {
        if (typeof window.initMap === 'function') window.initMap();
      });
    }
  }

  function bootstrapInitialDataFromDOM() {
    const rows = qsa('#device-table-body tr');
    const items = [];
    rows.forEach(tr => {
      const cb = tr.querySelector('.select-device');
      if (!cb) return; // skip placeholder row
      const tds = tr.querySelectorAll('td');
      const ip = tds[1]?.textContent?.trim() || '';
    const name = tds[2]?.textContent?.trim() || '';
    const vendor_name = tds[3]?.textContent?.trim() || '';
    const statusBadge = tds[4]?.querySelector('.badge');
    const status = statusBadge?.textContent?.trim() || 'unknown';
    const lastSeen = tds[5]?.textContent?.trim() || '-';
    items.push({ id: cb.getAttribute('data-id'), ip_address: ip, name, vendor_name, status, created_at: null, updated_at: lastSeen });
    });
    state.items = items;
    state.total = items.length;
  }

  onReady(function () {
    try {
      console.debug('[monitoring.js] initialized');
      // Defaults from DOM if available
      const pageSizeSel = qs('#page-size');
      if (pageSizeSel) { var v = parseInt(pageSizeSel.value, 10); if (Number.isFinite(v) && v > 0) state.perPage = v; }
      wireEvents();
      bootstrapInitialDataFromDOM();
      render();
      // Attempt to refresh from API to get latest data
      fetchAllAssets();
    } catch (err) {
      console.warn('[monitoring.js] init error:', err);
    }
  });
})();