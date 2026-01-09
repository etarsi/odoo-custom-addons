odoo.define("account_enhancement.afr_export_bridge", function (require) {
    "use strict";

    console.log("[AFR BRIDGE AM] cargado");

    const ActionManager = require("web.ActionManager");

    // instancia activa (widget) del reporte
    window.__activeAFR = null;

    function getXlsxName(str) {
        if (typeof str !== "string") return str;
        const parts = str.split(".");
        return `a_f_r.report_${parts[parts.length - 1]}_xlsx`;
    }

    ActionManager.include({
        doAction: function (action, options) {
            return this._super.apply(this, arguments).then((res) => {
                try {
                    const ctrl = this.getCurrentController && this.getCurrentController();
                    const widget = ctrl && ctrl.widget;

                    // Detectar específicamente el Libro Mayor (AFR)
                    // 1) por tag (si está)
                    const tag = (action && action.tag) || (ctrl && ctrl.action && ctrl.action.tag);

                    if (tag === "account_financial_report.client_action") {
                        window.__activeAFR = widget || null;
                        console.log("[AFR BRIDGE AM] AFR detectado por tag");
                    } else {
                        // 2) fallback: detectar por atributos típicos del ReportAction
                        if (widget && widget.report_name && widget.report_file && widget.do_action) {
                            window.__activeAFR = widget;
                            console.log("[AFR BRIDGE AM] ReportAction detectado por atributos");
                        } else {
                            window.__activeAFR = null;
                        }
                    }
                } catch (e) {
                    window.__activeAFR = null;
                }
                return res;
            });
        },
    });

    // Click del botón global
    $(document).on("click", ".o_report_export_excel", function (ev) {
        ev.preventDefault();

        const afr = window.__activeAFR;

        if (!afr) {
            alert("Este botón solo funciona dentro del Libro Mayor.");
            return;
        }

        // Si tu AFR YA tiene on_click_export, usalo
        if (typeof afr.on_click_export === "function") {
            return afr.on_click_export();
        }

        // Si NO existe on_click_export, forzamos el XLSX via do_action
        const action = {
            type: "ir.actions.report",
            report_type: "xlsx",
            report_name: getXlsxName(afr.report_name),
            report_file: getXlsxName(afr.report_file),
            data: afr.data,
            context: afr.context,
            display_name: afr.title,
        };

        console.log("[AFR BRIDGE AM] export xlsx action:", action);
        return afr.do_action(action);
    });
});
