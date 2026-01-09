odoo.define("account_enhancement.afr_bridge_print", function (require) {
    "use strict";

    console.log("[AFR BRIDGE] cargado");

    const AFRAction = require("account_financial_report.client_action");

    // Guardamos la instancia activa del AFR
    let activeAFR = null;

    AFRAction.include({
        start: function () {
            activeAFR = this;
            return this._super.apply(this, arguments).then(() => {
                // Mostrar el botón solo dentro del AFR
                $(".o_report_export_excel").removeClass("d-none");
                console.log("[AFR BRIDGE] AFR activo");
            });
        },
        destroy: function () {
            if (activeAFR === this) {
                activeAFR = null;
            }
            $(".o_report_export_excel").addClass("d-none");
            return this._super.apply(this, arguments);
        },
    });

    // Click global del botón del Control Panel
    $(document).on("click", ".o_report_export_excel", function (ev) {
        ev.preventDefault();

        if (!activeAFR) {
            alert("Este boton solo funciona dentro del Libro Mayor.");
            return;
        }

        // IMPRIMIR “de una”
        if (typeof activeAFR.on_click_print === "function") {
            return activeAFR.on_click_print();
        }

        // Fallback: disparar el click del boton Imprimir si existe
        const $print = activeAFR.$buttons && activeAFR.$buttons.find(".o_report_print");
        if ($print && $print.length) {
            $print.trigger("click");
            return;
        }

        alert("No se encontro metodo de imprimir en este reporte.");
    });
});
