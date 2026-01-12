odoo.define("account_enhancement.afr_export_xlsx", function (require) {
    "use strict";

    console.log("[XLSX] afr_export_xlsx cargado");

    const AFRAction = require("account_financial_report.client_action"); // tu require actual

    AFRAction.include({
        // en vez de _.extend(...)
        events: Object.assign({}, AFRAction.prototype.events, {
            "click .o_report_export_excel": "_onExportExcel",
        }),

        _onExportExcel: function (ev) {
            ev.preventDefault();
            console.log("[XLSX] click export");

            return this.do_action({
                type: "ir.actions.report",
                report_type: "xlsx",
                report_name: "account_enhancement.report_general_ledger_xlsx",
                data: { options: this.report_options || {} },
            });
        },
    });
});
