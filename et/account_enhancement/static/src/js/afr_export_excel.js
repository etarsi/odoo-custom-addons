odoo.define("account_enhancement.afr_export_excel", function (require) {
    "use strict";

    const ReportAction = require("report.client_action"); // Base de acciones de reportes
    const core = require("web.core");
    const _t = core._t;

    /**
     * Nota importante:
     * AFR suele extender ReportAction. El include sobre ReportAction es una forma robusta
     * de enganchar el start() y bindeo de botones.
     *
     * Si tu instancia concreta NO usa ReportAction, hay que incluir el módulo exacto
     * (account_financial_report.client_action) y extender esa clase. Pero en muchos AFR,
     * esto funciona.
     */
    ReportAction.include({
        start: function () {
            const res = this._super.apply(this, arguments);

            return Promise.resolve(res).then(() => {
                // En algunos casos, los botones están en this.$buttons
                if (!this.$buttons || !this.$buttons.length) {
                    // Fallback: buscar botones visibles en el control panel
                    this.$buttons = $(".o_control_panel .o_cp_buttons .o_report_buttons:visible").first();
                }

                if (!this.$buttons || !this.$buttons.length) {
                    // Si no hay botones, no estamos en un AFR compatible
                    return;
                }

                // Evitar doble bind
                this.$buttons.off("click", ".o_report_export_excel");

                // Bind del Excel
                this.$buttons.on("click", ".o_report_export_excel", this._onClickExportExcel.bind(this));
            });
        },

        /**
         * Handler del botón Excel
         */
        _onClickExportExcel: function (ev) {
            ev.preventDefault();
            ev.stopPropagation();

            // Acción XLSX (ajusta report_name al tuyo)
            const action = {
                type: "ir.actions.report",
                report_type: "xlsx",
                report_name: "account_financial_reporting.report_general_ledger_xlsx",
                data: {}, // si tu reporte necesita data, aquí se pasa
            };

            /**
             * Odoo 15 (legacy) normalmente soporta do_action en acciones.
             * Si por tu caso no existe, usamos trigger_up como fallback.
             */
            if (typeof this.do_action === "function") {
                return this.do_action(action);
            }
            this.trigger_up("do_action", { action: action });
        },
    });
});
