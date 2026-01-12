odoo.define("account_enhancement.afr_export_xlsx", function (require) {
    "use strict";

    console.log("[XLSX] afr_export_xlsx cargado");

    const AFRAction = require("account_financial_report.client_action");

    AFRAction.include({
        start: function () {
            const res = this._super.apply(this, arguments);

            return Promise.resolve(res).then(() => {
                if (!this.$buttons) {
                    console.warn("[XLSX] No existe this.$buttons, no puedo bindear.");
                    return;
                }

                // Verificación: si esto da 0, tu botón NO está en el template correcto
                console.log("[XLSX] botones encontrados:", this.$buttons.find(".o_report_export_excel").length);

                this.$buttons.off("click", ".o_report_export_excel");
                this.$buttons.on("click", ".o_report_export_excel", this._onExportExcel.bind(this));
            });
        },

        _onExportExcel: function (ev) {
            ev.preventDefault();
            console.log("[XLSX] click export");

            // OJO: acá tenés que llamar el XLSX real (ver punto 3)
            return this.do_action({
                type: "ir.actions.report",
                report_type: "xlsx",
                report_name: "a_f_r_report_general_ledger_xlsx",
                data: { options: this.report_options || {} },
                context: this.context,
            });
        },
    });
});
