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
    el.innerHTML =
      '<div style="background:#fff;padding:18px 22px;border-radius:10px;min-width:260px;'+
      'box-shadow:0 10px 30px rgba(0,0,0,0.25);text-align:center;font-family:sans-serif;">' +
        '<div style="margin-bottom:10px;font-weight:600">Preparando descarga…</div>' +
        '<div style="width:28px;height:28px;border:3px solid #ddd;border-top-color:#333;'+
        'border-radius:50%;margin:0 auto;animation:spin .8s linear infinite;"></div>' +
      '</div>' +
      '<style>@keyframes spin{to{transform:rotate(360deg)}}</style>';
    document.body.appendChild(el);
    return el;
  }
  function showOverlay(){ ensureOverlay().style.display = 'flex'; }
  function hideOverlay(){ ensureOverlay().style.display = 'none'; }

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
    if (anchor) { anchor.classList.add('disabled'); }

    fetch(endpoint || '/gdrive/zip/public_xmlrpc', {
      method: 'POST',
      credentials: 'same-origin',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ product_id: productId })
    })
    .then(r => r.json())
    .then(data => {
      console.log('ZIP público:', data);
      /*       if (!data || !data.ok || !data.url) {
        const msg = (data && data.message) || 'No se pudo generar la descarga.';
        throw new Error(msg);
      } */
      window.location.href = data.url; // descarga
    })
    .catch(err => {
      console.error('ZIP público:', err);
      alert('Se produjo un error al obtener las imágenes.');
    })
    .finally(() => {
      hideOverlay();
      if (anchor) { anchor.classList.remove('disabled'); }
      busy = false;
    });
  }

  // Exponer global para usar en onclick del <a>
  window.gdrivePublicZip = gdrivePublicZip;
});
