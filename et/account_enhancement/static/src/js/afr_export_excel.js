odoo.define("account_enhancement.afr_export_bridge", function (require) {
    "use strict";

    const _ = require("underscore");
    const AFRAction = require("account_financial_report.client_action"); // AJUSTAR al JS real
    // a veces el require real es: 'account_financial_report.client_action_report' o similar

    AFRAction.include({
        events: _.extend({}, AFRAction.prototype.events, {
            "click .o_report_export_excel": "_onExportExcel",
        }),

        _onExportExcel: function (ev) {
            ev.preventDefault();

            // Si el reporte maneja opciones (filtros), normalmente están en algo como this.report_options / this.report_options
            const data = this.report_options || {}; // AJUSTAR según tu action

            return this.do_action({
                type: "ir.actions.report",
                report_type: "xlsx",
                report_name: "account_enhancement.report_general_ledger_xlsx", // debe existir en ir.actions.report
                data: data,
                context: this.context,
            });
        },
    });
});
