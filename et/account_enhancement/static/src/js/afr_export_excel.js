odoo.define("account_enhancement.report_client_action_export_xlsx", function (require) {
    "use strict";

    const ReportAction = require("report.client_action");

    // Tomo jQuery como global (en tu runtime no existe require('jquery') ni require('web.jquery'))
    const $ = window.jQuery || window.$;

    ReportAction.include({
        start: function () {
            console.log("[PATCH] report.client_action start ENTER", {
                href: window.location.href,
                report_name: this.report_name,
                report_type: this.report_type,
            });

            return this._super.apply(this, arguments).then(() => {
                // Sólo para el Libro Mayor de AFR (ajustá si querés)
                if (this.report_name !== "account_financial_report.general_ledger") {
                    return;
                }

                if (!this.$buttons || !$) {
                    console.warn("[PATCH] No hay this.$buttons o no hay jQuery global");
                    return;
                }

                // Agrego botón al lado de Imprimir
                const $container = this.$buttons.find(".o_report_buttons");
                if (!$container.length) {
                    console.warn("[PATCH] No encontré .o_report_buttons");
                    return;
                }

                // Evitar duplicados
                $container.find(".o_report_export_excel").remove();

                $container.append(`
                    <button type="button" class="btn btn-secondary o_report_export_excel">
                        Exportar Excel
                    </button>
                `);

                this.$buttons.off("click", ".o_report_export_excel");
                this.$buttons.on("click", ".o_report_export_excel", (ev) => {
                    ev.preventDefault();

                    console.log("[PATCH] CLICK Exportar Excel", {
                        report_name: this.report_name,
                        data: this.data,
                        context: this.context,
                    });

                    // En tu BD el template XLSX se llama así (según tu captura de Informes)
                    const action = {
                        type: "ir.actions.report",
                        report_type: "xlsx",
                        report_name: "a_f_r_report_general_ledger_xlsx",
                        data: this.data,        // acá ya venía wizard_id
                        context: this.context,  // acá venían active_ids
                        display_name: "Libro mayor XLSX",
                    };

                    console.log("[PATCH] do_action XLSX:", action);
                    return this.do_action(action);
                });

                // Reinyecto botones al control panel
                this.controlPanelProps.cp_content = { $buttons: this.$buttons };
                this._controlPanelWrapper.update(this.controlPanelProps);

                console.log("[PATCH] Botón XLSX agregado al control panel");
            });
        },
    });
});
