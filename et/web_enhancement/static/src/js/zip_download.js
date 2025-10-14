/** @odoo-module **/

odoo.define('web_enhancement.zip_download', function (require) {
  'use strict';

  // ===== Overlay simple =====
  function ensureOverlay() {
    let el = document.getElementById('zip-loading-overlay');
    if (el) { return el; }
    el = document.createElement('div');
    el.id = 'zip-loading-overlay';
    el.style.position = 'fixed';
    el.style.inset = '0';
    el.style.background = 'rgba(0,0,0,0.45)';
    el.style.display = 'none';
    el.style.zIndex = '99999';
    el.style.alignItems = 'center';
    el.style.justifyContent = 'center';
    el.setAttribute('aria-busy', 'true');
    el.setAttribute('aria-live', 'polite');
    el.innerHTML =
      '<div style="background:#fff;padding:18px 22px;border-radius:10px;min-width:260px;'+
      'box-shadow:0 10px 30px rgba(0,0,0,0.25);text-align:center;font-family:sans-serif;">' +
        '<div style="margin-bottom:10px;font-weight:600">Preparando descarga…</div>' +
        '<div style="width:28px;height:28px;border:3px solid #ddd;border-top-color:#333;'+
        'border-radius:50%;margin:0 auto;animation:spin .8s linear infinite;"></div>' +
        '<div style="margin-top:10px;font-size:12px;color:#555">Esto puede tardar unos segundos</div>' +
      '</div>' +
      '<style>@keyframes spin{to{transform:rotate(360deg)}}</style>';
    document.body.appendChild(el);
    return el;
  }
  function showOverlay() { ensureOverlay().style.display = 'flex'; }
  function hideOverlay() { ensureOverlay().style.display = 'none'; }

  // Evitar doble click
  let busy = false;

  /**
   * Llama al método de Odoo y bloquea la UI hasta que comience la descarga.
   * @param {Number} productId
   * @param {HTMLElement} [btn] - (opcional) botón que dispara la acción para deshabilitarlo
   */
  function downloadZipViaRpc(productId, btn) {
    if (busy) { return; }
    busy = true;

    // Deshabilitar botón (opcional)
    if (btn) {
      btn.disabled = true;
      btn.dataset._origText = btn.textContent;
      btn.textContent = 'Generando…';
    }

    showOverlay();

    var payload = {
      jsonrpc: '2.0',
      method: 'call',
      params: {
        model: 'product.template',
        method: 'action_zip_by_default_code_from_main_folder',
        args: [[productId]],
        kwargs: {}
      },
      id: Date.now()
    };

    fetch('/web/dataset/call_kw', {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': (window.odoo && odoo.csrf_token) || ''
      },
      body: JSON.stringify(payload)
    })
    .then(function (r) { return r.json(); })
    .then(function (data) {
      if (!data || data.error) {
        throw new Error((data && data.error && data.error.data && data.error.data.message) || 'RPC error');
      }
      if (!data.result || !data.result.url) {
        throw new Error('Se produjo un error al obtener las imágenes, por favor contáctese con soporte.');
      }
      // Dispara la descarga
      window.location.href = data.result.url;
    })
    .catch(function (err) {
      console.error('Fallo descarga ZIP:', err);
      alert('Se produjo un error al obtener las imágenes, por favor contáctese con soporte.');
    })
    .finally(function () {
      hideOverlay();
      if (btn) {
        btn.disabled = false;
        btn.textContent = btn.dataset._origText || 'Descargar';
      }
      busy = false;
    });
  }

  // Exponer global para usarla desde templates/HTML (onclick)
  window.downloadZipViaRpc = downloadZipViaRpc;
});
