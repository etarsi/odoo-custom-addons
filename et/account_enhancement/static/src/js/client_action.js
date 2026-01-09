odoo.define("account_enhancement.afr_override", function (require) {
    "use strict";

    var ReportAction = require("report.client_action");
    var action_registry = require("web.action_registry");
    var core = require("web.core");
    var QWeb = core.qweb;

    const MyAFRReportAction = ReportAction.extend({
        start: function () {
            console.log("[MY AFR] start()", this);  // <- este log debe aparecer sí o sí si se ejecuta la acción

            return this._super.apply(this, arguments).then(() => {
                // Render de TU template (o el original si querés)
                this.$buttons = $(
                    QWeb.render("account_financial_report.client_action.ControlButtons", {})
                    // o tu template: QWeb.render("tu_modulo.ControlButtons", {})
                );

                this.$buttons.on("click", ".o_report_print", this.on_click_print.bind(this));
                this.$buttons.on("click", ".o_report_export", this.on_click_export.bind(this));

                this.controlPanelProps.cp_content = { $buttons: this.$buttons };
                this._controlPanelWrapper.update(this.controlPanelProps);
            });
        },

        on_click_export: function () {
            const action = {
                type: "ir.actions.report",
                report_type: "xlsx",
                report_name: this._get_xlsx_name(this.report_name),
                report_file: this._get_xlsx_name(this.report_file),
                data: this.data,
                context: this.context,
                display_name: this.title,
            };
            return this.do_action(action);
        },

        _get_xlsx_name: function (str) {
            if (!_.isString(str)) return str;
            const parts = str.split(".");
            return `a_f_r.report_${parts[parts.length - 1]}_xlsx`;
        },
    });

    // Clave: registrar con el MISMO tag para reemplazar al original
    action_registry.add("account_financial_report.client_action", MyAFRReportAction);

    return MyAFRReportAction;
});
