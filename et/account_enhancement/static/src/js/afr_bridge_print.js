odoo.define("account_enhancement.afr_bridge_print", function (require) {
    "use strict";

    console.log("[AFR XLSX] bridge cargado");

    const AFRAction = require("account_financial_report.client_action");

    let activeAFR = null;

    function getXlsxName(str) {
        if (typeof str !== "string") return str;
        const parts = str.split(".");
        return `a_f_r.report_${parts[parts.length - 1]}_xlsx`;
    }

    AFRAction.include({
        start: function () {
            activeAFR = this;
            return this._super.apply(this, arguments).then(() => {
                // opcional: mostrar tu boton solo dentro del AFR
                $(".o_report_export_excel").removeClass("d-none");
                console.log("[AFR XLSX] AFR activo:", this.report_name, this.report_file);
            });
        },
        destroy: function () {
            if (activeAFR === this) activeAFR = null;
            $(".o_report_export_excel").addClass("d-none");
            return this._super.apply(this, arguments);
        },
    });

    $(document).on("click", ".o_report_export_excel", function (ev) {
        ev.preventDefault();

        if (!activeAFR) {
            alert("Este botón solo funciona dentro del Libro Mayor (AFR).");
            return;
        }

        const action = {
            type: "ir.actions.report",
            report_type: "xlsx",
            report_name: getXlsxName(activeAFR.report_name),
            report_file: getXlsxName(activeAFR.report_file),
            data: activeAFR.data,
            context: activeAFR.context,
            display_name: activeAFR.title,
        };

        console.log("[AFR XLSX] do_action:", action);
        return activeAFR.do_action(action);
    });
});
