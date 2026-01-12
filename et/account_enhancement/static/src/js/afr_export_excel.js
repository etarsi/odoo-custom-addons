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
                const $container = this.$buttons.find("div.o_report_buttons");
                if (!$container.length) {
                    console.warn("[PATCH] No encontré div.o_report_buttons para agregar botón XLSX");
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
                    ev.stopPropagation();
                    ev.stopImmediatePropagation();

                    const wizardId =
                        (this.data && this.data.wizard_id) ||
                        (this.context && this.context.active_ids && this.context.active_ids[0]);

                    const ctx = Object.assign({}, this.context || {}, {
                        active_id: wizardId,
                        active_ids: wizardId ? [wizardId] : [],
                    });

                    const action = {
                        type: "ir.actions.report",
                        report_type: "xlsx",
                        report_name: "a_f_r_report_general_ledger_xlsx",
                        report_file: "a_f_r_report_general_ledger_xlsx",
                        data: this.data || {},
                        context: ctx,
                        display_name: "Libro mayor XLSX",
                    };

                    console.log("[PATCH] XLSX ACTION", action);
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
