odoo.define("account_financial_report.client_action", function (require) {
    "use strict";

    var $ = require("jquery");
    var ReportAction = require("report.client_action");
    var core = require("web.core");

    var QWeb = core.qweb;

    // 1) Log inmediato: confirma que ESTE archivo es el que está cargando el navegador
    console.log("### AFR CLIENT_ACTION MODIFICADO (LOAD) ###", new Date().toISOString());
    window.__afr_test = (window.__afr_test || 0) + 1;
    console.log("### AFR LOAD COUNT ###", window.__afr_test);

    // 2) Log global de click: NO depende de que start() corra
    //    Si al hacer click en Print NO aparece esto, entonces el botón que tocás no es .o_report_print
    $(document).off("click.afrtest", ".o_report_print");
    $(document).on("click.afrtest", ".o_report_print", function (ev) {
        console.log("[AFR][GLOBAL] CLICK .o_report_print", {
            href: window.location.href,
            text: (ev.target && ev.target.innerText) || null,
            time: new Date().toISOString(),
        });
    });

    $(document).off("click.afrtest", ".o_report_export");
    $(document).on("click.afrtest", ".o_report_export", function (ev) {
        console.log("[AFR][GLOBAL] CLICK .o_report_export", {
            href: window.location.href,
            text: (ev.target && ev.target.innerText) || null,
            time: new Date().toISOString(),
        });
    });

    const AFRReportAction = ReportAction.extend({
        start: function () {
            // 3) Log al entrar: si NO ves esto, tu acción NO está usando esta clase
            console.log("[AFR] start() ENTER", {
                href: window.location.href,
                report_name: this.report_name,
                report_file: this.report_file,
                title: this.title,
            });

            return this._super.apply(this, arguments)
                .then(() => {
                    console.log("[AFR] start() AFTER _super");

                    // Render de botones del Control Panel
                    this.$buttons = $(
                        QWeb.render("account_financial_report.client_action.ControlButtons", {})
                    );

                    // Confirmación de que existen los botones
                    console.log("[AFR] botones encontrados en template:", {
                        print: this.$buttons.find(".o_report_print").length,
                        export: this.$buttons.find(".o_report_export").length,
                    });
                    console.log("[AFR] this.$buttons:", this.$buttons);

                    // MUY IMPORTANTE: bind(this) para que this sea la acción, no el botón DOM
                    this.$buttons.off("click", ".o_report_print");
                    this.$buttons.on("click", ".o_report_print", (ev) => {
                        ev.preventDefault();
                        console.log("[AFR] CLICK PRINT (bound)", {
                            href: window.location.href,
                            report_name: this.report_name,
                            report_file: this.report_file,
                            title: this.title,
                            context: this.context,
                            data: this.data,
                        });
                        return this.on_click_print(ev);
                    });

                    this.$buttons.off("click", ".o_report_export");
                    this.$buttons.on("click", ".o_report_export", (ev) => {
                        ev.preventDefault();
                        console.log("[AFR] CLICK EXPORT (bound)", {
                            href: window.location.href,
                            report_name: this.report_name,
                            report_file: this.report_file,
                            title: this.title,
                            context: this.context,
                            data: this.data,
                        });
                        return this.on_click_export(ev);
                    });

                    // Inyectar botones al Control Panel
                    this.controlPanelProps.cp_content = { $buttons: this.$buttons };
                    this._controlPanelWrapper.update(this.controlPanelProps);

                    console.log("[AFR] Control Panel actualizado con botones");
                })
                .catch((err) => {
                    console.error("[AFR] start() ERROR", err);
                    throw err;
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
            // Evito underscore (_), para no depender de librerías externas
            if (typeof str !== "string") {
                return str;
            }
            const parts = str.split(".");
            return `a_f_r.report_${parts[parts.length - 1]}_xlsx`;
        },
    });

    core.action_registry.add("account_financial_report.client_action", AFRReportAction);

    // 4) Confirmar qué clase quedó registrada en el action_registry
    console.log(
        "[AFR] registry class actual:",
        core.action_registry.get("account_financial_report.client_action")
    );

    return AFRReportAction;
});
