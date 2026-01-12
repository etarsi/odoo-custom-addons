odoo.define("account_enhancement.afr_export_xlsx", function (require) {
    "use strict";

    const AFRAction = require("account_financial_report.client_action"); // OJO: puede variar
    const _ = require("underscore");

    AFRAction.include({
        start: function () {
            const res = this._super.apply(this, arguments);

            return Promise.resolve(res).then(() => {
                if (!this.$buttons) {
                    console.warn("[XLSX] this.$buttons no existe, no puedo bindear el click.");
                    return;
                }

                this.$buttons.off("click", ".o_report_export_excel");
                this.$buttons.on("click", ".o_report_export_excel", this._onExportExcel.bind(this));
            });
        },

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
