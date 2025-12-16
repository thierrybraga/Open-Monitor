// navbar.js
// Atualiza badge de sincronização na navbar com estado "Gravando X% (Y/Z)" quando aplicável
(function(){
  function $(sel){ return document.querySelector(sel); }

  function formatPct(val){ try{ return Number(val).toFixed(2); }catch(_){ return String(val); } }

  function updateSyncBadge(prog){
    var badge = $('.sync-badge');
    var clock = $('#lastSyncTime');
    if (!badge) return;
    var status = prog && prog.status ? String(prog.status).toLowerCase() : null;
    var sp = (typeof prog.saving_percentage === 'number') ? prog.saving_percentage : null;
    var sc = (typeof prog.saving_count === 'number') ? prog.saving_count : null;
    var cur = (typeof prog.current==='number') ? prog.current : null;
    var tot = (typeof prog.total==='number') ? prog.total : null;
    var pct = (typeof prog.percentage==='number') ? prog.percentage : null;
    if (status === 'saving' && sc && sc > 0){
      var overallTxt = (typeof pct==='number') ? formatPct(pct) : '--';
      var txt = 'Gravando lote: ' + sc + ' · Geral: ' + overallTxt + '% (' + (cur||0) + '/' + (tot||0) + ')';
      if (clock) { clock.textContent = txt; }
      try { badge.classList.add('saving'); badge.setAttribute('aria-label', txt); } catch(_){ }
    } else {
      try {
        (typeof window.fetchWithRetry==='function'? window.fetchWithRetry('/api/v1/sync/status', {}, 2, 300) : fetch('/api/v1/sync/status'))
          .then(function(r){ return r.json(); })
          .then(function(s){ if(clock && s && s.last_sync_formatted){ clock.textContent = s.last_sync_formatted; } })
          .catch(function(){});
      } catch(_){}
      try { badge.classList.remove('saving'); } catch(_){}
    }
  }

  function updateBadgeVisibility(){
    try{
      var badge = $('.sync-badge');
      if (!badge) return;
      var api = '/api/v1/system/bootstrap';
      var fetcher = (typeof window.fetchWithRetry==='function'? window.fetchWithRetry(api, {}, 2, 300) : fetch(api));
      fetcher
        .then(function(r){ return r.json(); })
        .then(function(b){
          var done = !!(b && b.first_sync_completed === true);
          var inProg = !!(b && b.sync_in_progress === true);
          if (done && !inProg) {
            try { badge.style.display = 'none'; } catch(_) {}
          } else {
            try { badge.style.display = ''; } catch(_) {}
          }
        })
        .catch(function(){ /* ignore */ });
    }catch(_){ /* ignore */ }
  }

  function poll(){
    try{
      var getProg = (typeof window.getSyncProgress==='function') ? window.getSyncProgress() : (fetch('/api/v1/sync/progress').then(function(r){return r.json()}).then(function(j){ return (typeof window.normalizeSyncProgressPayload==='function'? window.normalizeSyncProgressPayload(j) : j); }));
      getProg
        .then(function(prog){ updateSyncBadge(prog||{}); schedule(prog||{}); })
        .catch(function(){ schedule(null); });
    }catch(_){ schedule(null); }
  }

  function schedule(json){
    try{
      var status = (json && json.status) ? String(json.status).toLowerCase() : null;
      var interval = (typeof window.computeSyncPollingInterval==='function'? window.computeSyncPollingInterval(status) : ((status==='processing' || status==='saving') ? 10000 : 600000));
      if (window.__navbarPoll) { clearTimeout(window.__navbarPoll); }
      window.__navbarPoll = setTimeout(poll, interval);
    }catch(_){ if (window.__navbarPoll) { clearTimeout(window.__navbarPoll); } window.__navbarPoll = setTimeout(poll, 30000); }
  }

  document.addEventListener('DOMContentLoaded', function(){ updateBadgeVisibility(); poll(); });
})();
