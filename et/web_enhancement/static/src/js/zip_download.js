/** @odoo-module **/
odoo.define('web_enhancement.gdrive_zip_public', function () {
  'use strict';

  function ensureOverlay() {
    let el = document.getElementById('zip-loading-overlay');
    if (el) return el;

    el = document.createElement('div');
    el.id = 'zip-loading-overlay';
    el.style.position = 'fixed';
    el.style.inset = '0';
    el.style.background = 'rgba(0,0,0,0.45)';
    el.style.display = 'none';
    el.style.zIndex = '99999';
    el.style.alignItems = 'center';
    el.style.justifyContent = 'center';
    el.setAttribute('aria-live', 'polite');

    el.innerHTML = `
      <div id="zip-card" style="background:#fff;padding:18px 22px;border-radius:10px;min-width:280px;
                                box-shadow:0 10px 30px rgba(0,0,0,0.25);text-align:center;font-family:sans-serif;">
        <div id="zip-title" style="margin-bottom:10px;font-weight:600;">Preparando descarga…</div>
        <div id="zip-spinner" style="width:28px;height:28px;border:3px solid #ddd;border-top-color:#333;
                                      border-radius:50%;margin:0 auto;animation:zipspin .8s linear infinite;"></div>

        <div id="zip-error" style="display:none;text-align:left;">
          <p style="margin:12px 0 6px 0;font-weight:600;color:#b00020;">No se pudo generar la descarga, Contacte con un personal de Sebigus</p>
          <div style="display:flex;gap:8px;justify-content:center;">
            <button id="zip-retry" class="btn btn-primary" style="padding:6px 12px;border-radius:8px;">Reintentar</button>
            <button id="zip-close" class="btn btn-secondary" style="padding:6px 12px;border-radius:8px;">Cerrar</button>
          </div>
        </div>
      </div>
      <style>@keyframes zipspin{to{transform:rotate(360deg)}}</style>
    `;
    document.body.appendChild(el);
    return el;
  }

  function showOverlay() {
    const el = ensureOverlay();
    // estado "cargando"
    el.style.display = 'flex';
    el.querySelector('#zip-title').textContent = 'Preparando descarga…';
    el.querySelector('#zip-spinner').style.display = 'block';
    el.querySelector('#zip-error').style.display = 'none';
  }
  function showError(msg, onRetry, onClose) {
    const el = ensureOverlay();
    el.style.display = 'flex';
    el.querySelector('#zip-title').textContent = 'Ocurrió un problema';
    el.querySelector('#zip-spinner').style.display = 'none';
    el.querySelector('#zip-error').style.display = 'block';
    el.querySelector('#zip-error-msg').textContent = msg || 'Se produjo un error al obtener las imágenes.';

    const retryBtn = el.querySelector('#zip-retry');
    const closeBtn = el.querySelector('#zip-close');

    // limpiar listeners anteriores
    const retryCloned = retryBtn.cloneNode(true);
    const closeCloned = closeBtn.cloneNode(true);
    retryBtn.parentNode.replaceChild(retryCloned, retryBtn);
    closeBtn.parentNode.replaceChild(closeCloned, closeBtn);

    retryCloned.addEventListener('click', () => { if (onRetry) onRetry(); });
    closeCloned.addEventListener('click', () => { hideOverlay(); if (onClose) onClose(); });
  }
  function hideOverlay() {
    const el = document.getElementById('zip-loading-overlay');
    if (el) el.style.display = 'none';
  }

  let busy = false;

  /**
   * Llama al endpoint público y dispara la descarga.
   * @param {number} productId
   * @param {HTMLElement} anchor  (el <a> clickeado)
   * @param {Event} ev
   * @param {string} endpoint     (opcional) '/gdrive/zip/public' o '/gdrive/zip/public_xmlrpc'
   */
  function gdrivePublicZip(productId, anchor, ev, endpoint) {
    if (ev && ev.preventDefault) ev.preventDefault();
    if (busy) return;
    busy = true;

    showOverlay();
    if (anchor) anchor.classList.add('disabled');

    const call = () => fetch(endpoint || '/gdrive/zip/public_xmlrpc', {
      method: 'POST',
      credentials: 'same-origin',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ product_id: productId })
    })
    .then(r => r.json())
    .then(data => {
      const res = (data && data.result) ? data.result : data;
      if (!res || !res.ok || !res.url) {
        const msg = (res && res.message) || 'No se pudo generar la descarga.';
        throw new Error(msg);
      }
      hideOverlay();
      if (anchor) anchor.classList.remove('disabled');
      busy = false;
      window.location.href = res.url; // debe traer access_token
    })
    .catch(err => {
      console.error('ZIP público:', err);
      showError(err.message, /* onRetry */ () => {
        showOverlay();
        call(); // reintenta
      }, /* onClose */ () => {
        if (anchor) anchor.classList.remove('disabled');
        busy = false;
      });
    });

    return call();
  }

  // Exponer global para usar en onclick del <a>
  window.gdrivePublicZip = gdrivePublicZip;
});
