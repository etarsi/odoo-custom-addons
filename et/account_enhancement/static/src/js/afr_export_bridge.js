odoo.define("account_enhancement.afr_export_bridge", function (require) {
    "use strict";

    console.log("[AFR BRIDGE] cargado");

    const ActionManager = require("web.ActionManager");

    // Instancia activa del reporte (Libro Mayor / AFR)
    window.__activeAFR = null;

    function getXlsxName(str) {
        if (typeof str !== "string") return str;
        const parts = str.split(".");
        return `a_f_r.report_${parts[parts.length - 1]}_xlsx`;
    }

    // Captura del widget actual cada vez que Odoo ejecuta acciones
    ActionManager.include({
        doAction: function (action, options) {
            // Log útil para saber cuál tag estás ejecutando
            try {
                console.log("[AFR BRIDGE] doAction tag:", action && action.tag);
            } catch (e) {}

            return this._super.apply(this, arguments).then((res) => {
                try {
                    const ctrl = this.getCurrentController && this.getCurrentController();
                    const widget = ctrl && ctrl.widget;

                    // Heurística robusta: el AFR suele tener report_name/report_file y botón imprimir
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
                    } else {
                        // Si salís del reporte, podés limpiar (opcional)
                        // window.__activeAFR = null;
                    }
                } catch (e) {
                    console.warn("[AFR BRIDGE] Error capturando AFR:", e);
                }
                return res;
            });
        },
    });

    // Click del botón global
    $(document).on("click", ".o_report_export_excel", function (ev) {
        ev.preventDefault();

        const afr = window.__activeAFR;
        console.log("[AFR BRIDGE] click export excel, afr:", afr);

        if (!afr || !afr.do_action) {
            alert("Entrá al Libro Mayor y volvé a intentar (no se detectó el reporte activo).");
            return;
        }

        // Si tu AFR tiene on_click_export, usarlo directamente
        if (typeof afr.on_click_export === "function") {
            console.log("[AFR BRIDGE] usando afr.on_click_export()");
            return afr.on_click_export();
        }

        // Si no existe, forzamos el XLSX por ir.actions.report
        const report_name_xlsx = getXlsxName(afr.report_name);
        const report_file_xlsx = getXlsxName(afr.report_file);

        const action = {
            type: "ir.actions.report",
            report_type: "xlsx",
            report_name: report_name_xlsx,
            report_file: report_file_xlsx,
            data: afr.data,
            context: afr.context,
            display_name: afr.title,
        };

        console.log("[AFR BRIDGE] export xlsx action:", action);

        return afr.do_action(action);
    });
});
