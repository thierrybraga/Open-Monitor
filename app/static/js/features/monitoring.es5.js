(function(){
  function onReady(fn){if(document.readyState!=='loading') fn(); else document.addEventListener('DOMContentLoaded', fn, {once:true});}
  onReady(function(){
    try {
      console.log('[monitoring.es5.js] loaded');
      // Do not auto-initialize the map; it will load on modal open
      var refreshBtn = document.getElementById('refreshBtn');
      if (refreshBtn) {
        refreshBtn.addEventListener('click', function(){
          try { window.location.reload(); } catch (e) {}
        });
      }
      var modalEl = document.getElementById('map-modal');
      if (modalEl) {
        modalEl.addEventListener('shown.bs.modal', function(){
          if (typeof window.initMap === 'function') { try { window.initMap(); } catch (e) {} }
        });
      }
    } catch (err) {
      console.warn('[monitoring.es5.js] init error:', err);
    }
  });
})();