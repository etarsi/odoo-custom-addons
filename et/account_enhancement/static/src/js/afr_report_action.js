odoo.define("account_enhancement.afr_report_action", function (require) {
    "use strict";

    const ReportAction = require("report.client_action");
    const core = require("web.core");
    const QWeb = core.qweb;

    const AFRReportAction = ReportAction.extend({
        start: function () {
            return this._super.apply(this, arguments).then(() => {
                // Render de botones (usa el template ya heredado)
                this.$buttons = $(
                    QWeb.render("account_financial_report.client_action.ControlButtons", {})
                );

                // MUY IMPORTANTE: bind(this)
                this.$buttons.on("click", ".o_report_print", this.on_click_print.bind(this));
                this.$buttons.on("click", ".o_report_export", this.on_click_export.bind(this));

                this.controlPanelProps.cp_content = { $buttons: this.$buttons };
                this._controlPanelWrapper.update(this.controlPanelProps);
            });
        },

        /**
         * “Print” ahora exporta XLSX.
         */
        on_click_print: function (ev) {
            ev.preventDefault();
            return this.on_click_export(ev);
        },

        /**
         * Export XLSX
         * Nota: acá tenés que usar tu lógica real. Dejo ejemplo típico.
         */
        on_click_export: function (ev) {
            ev.preventDefault();

            const action = {
                type: "ir.actions.report",
                report_type: "xlsx",
                report_name: this._get_xlsx_name(this.report_name),
                report_file: this._get_xlsx_name(this.report_file),
                data: this._get_report_data ? this._get_report_data() : {},
            };

            return this.do_action(action);
        },

        _get_xlsx_name: function (name) {
            return (name || "").replace(/\.pdf$/i, "").replace(/\s+/g, "_");
        },
    });

    core.action_registry.add("account_financial_report.client_action", AFRReportAction);
    return AFRReportAction;
});
