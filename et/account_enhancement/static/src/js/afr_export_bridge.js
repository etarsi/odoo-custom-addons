odoo.define("account_enhancement.afr_export_bridge", function (require) {
    "use strict";

    console.log("[AFR BRIDGE AM] cargado");


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
