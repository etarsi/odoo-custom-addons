odoo.define("account_financial_report.client_action", function (require) {
    "use strict";

    var ReportAction = require("report.client_action");
    var core = require("web.core");
    var QWeb = core.qweb;

    console.log("### AFR CLIENT_ACTION MODIFICADO (LOAD) ###", new Date().toISOString());

    // jQuery como global (Odoo 15 backend normalmente lo tiene)
    var $ = window.jQuery || window.$;
    if (!$) {
        console.error("[AFR] No existe jQuery global (window.$/window.jQuery). No se pueden bindear eventos.");
    }

    const AFRReportAction = ReportAction.extend({
        start: function () {
            console.log("[AFR] start() ENTER", {
                href: window.location.href,
                report_name: this.report_name,
                report_file: this.report_file,
                title: this.title,
            });

            return this._super.apply(this, arguments).then(() => {
                console.log("[AFR] start() AFTER _super");

                this.$buttons = $(
                    QWeb.render("account_financial_report.client_action.ControlButtons", {})
                );

                console.log("[AFR] template buttons:", {
                    print: this.$buttons.find(".o_report_print").length,
                    export: this.$buttons.find(".o_report_export").length,
                });

                // IMPORTANTE: usar arrow/bind para conservar "this" de la acción
                this.$buttons.off("click", ".o_report_print");
                this.$buttons.on("click", ".o_report_print", (ev) => {
                    console.log("[AFR] CLICK IMPRIMIR", {
                        href: window.location.href,
                        report_name: this.report_name,
                        report_file: this.report_file,
                        title: this.title,
                        context: this.context,
                        data: this.data,
                    });
                    // NO preventDefault aquí, dejá que el print haga su flujo normal
                    return this.on_click_print(ev);
                });

                this.$buttons.off("click", ".o_report_export");
                this.$buttons.on("click", ".o_report_export", (ev) => {
                    console.log("[AFR] CLICK EXPORT", {
                        href: window.location.href,
                        report_name: this.report_name,
                        report_file: this.report_file,
                        title: this.title,
                        context: this.context,
                        data: this.data,
                    });
                    // Si export funciona, acá entra
                    return this.on_click_export(ev);
                });

                this.controlPanelProps.cp_content = { $buttons: this.$buttons };
                this._controlPanelWrapper.update(this.controlPanelProps);

                console.log("[AFR] Control Panel actualizado con botones");
            });
        },

        on_click_export: function () {
            console.log("[AFR] on_click_export() ejecutando");

            const action = {
                type: "ir.actions.report",
                report_type: "xlsx",
                report_name: this._get_xlsx_name(this.report_name),
                report_file: this._get_xlsx_name(this.report_file),
                data: this.data,
                context: this.context,
                display_name: this.title,
            };

            console.log("[AFR] do_action XLSX:", action);
            return this.do_action(action);
        },

        _get_xlsx_name: function (str) {
            // sin underscore
            if (typeof str !== "string") return str;
            const parts = str.split(".");
            return `a_f_r.report_${parts[parts.length - 1]}_xlsx`;
        },
    });

    core.action_registry.add("account_financial_report.client_action", AFRReportAction);

    console.log("[AFR] registry class actual:", core.action_registry.get("account_financial_report.client_action"));

    return AFRReportAction;
});
