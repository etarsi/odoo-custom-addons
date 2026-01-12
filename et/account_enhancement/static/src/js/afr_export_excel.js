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

                // --- encontrar contenedor real de botones ---
                let $container = this.$buttons;

                // Caso 1: this.$buttons YA es el contenedor
                if (!$container || !$container.length) {
                    console.warn("[PATCH] this.$buttons vacío");
                    return;
                }
                if (!$container.hasClass("o_report_buttons")) {
                    // Caso 2: el contenedor está dentro
                    const $inside = $container.find(".o_report_buttons");
                    if ($inside.length) {
                        $container = $inside.first();
                    } else {
                        // Caso 3: fallback al Control Panel real (DOM)
                        const $cp = $(".o_control_panel .o_cp_buttons .o_report_buttons:visible").first();
                        if ($cp.length) {
                            $container = $cp;
                        } else {
                            console.warn("[PATCH] No encontré .o_report_buttons (ni en this.$buttons ni en control panel). HTML root:", $container[0] && $container[0].outerHTML);
                            return;
                        }
                    }
                }

                console.log("[PATCH] Contenedor botones OK:", $container[0].outerHTML);

                // Evitar duplicados
                $container.find(".o_report_export_excel").remove();

                // Insertar como HERMANO del botón imprimir (no adentro)
                const $print = $container.find(".o_report_print").first();
                if ($print.length) {
                    $print.after(`
                        <button type="button"
                                class="btn btn-secondary o_report_export_excel"
                                title="Exportar Excel">
                            Exportar Excel
                        </button>
                    `);
                } else {
                    // si no hay print por alguna razón, lo agrego al final
                    $container.append(`
                        <button type="button"
                                class="btn btn-secondary o_report_export_excel"
                                title="Exportar Excel">
                            Exportar Excel
                        </button>
                    `);
                }

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
