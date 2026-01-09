odoo.define("account_enhancement.afr_export_bridge", function (require) {
    "use strict";

    console.log("[AFR BRIDGE] cargado");

    const ActionManager = require("web.ActionManager");

    window.__activeAFR = null;

    function captureAFR(self) {
        try {
            const ctrl = self.getCurrentController && self.getCurrentController();
            const widget = ctrl && ctrl.widget;

            if (
                widget &&
                widget.report_name &&
                widget.report_file &&
                widget.do_action &&
                widget.$buttons &&
                widget.$buttons.find(".o_report_print").length
            ) {
                window.__activeAFR = widget;
                console.log("[AFR BRIDGE] Capturado AFR:", widget.report_name, widget.report_file);
            }
        } catch (e) {
            console.warn("[AFR BRIDGE] Error capturando AFR:", e);
        }
    }

    ActionManager.include({
        doAction: function (action, options) {
            // Ejecuta acción normal
            const result = this._super.apply(this, arguments);

            // Captura luego de que el controlador cambie/renderice
            const after = () => setTimeout(() => captureAFR(this), 0);

            // Si result es Promise/Deferred => esperar; si no, seguir sin romper
            if (result && typeof result.then === "function") {
                return result.then((res) => {
                    after();
                    return res;
                });
            }

            after();
            return result;
        },
    });

    // Botón global: por ahora solo loguea que hay AFR capturado
    $(document).on("click", ".o_report_export_excel", function (ev) {
        ev.preventDefault();
        console.log("[AFR BRIDGE] click, activeAFR:", window.__activeAFR);
        alert(window.__activeAFR ? "AFR detectado" : "No estas en Libro Mayor");
    });
});
