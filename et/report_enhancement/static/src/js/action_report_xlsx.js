odoo.define("report_enhancement.report_balance_addition_xlsx", function (require) {
    "use strict";

    const ReportAction = require("report.client_action");
    // Tomo jQuery como global (en tu runtime no existe require('jquery') ni require('web.jquery'))
    const $ = window.jQuery || window.$;

    ReportAction.include({
        start: function () {
            return this._super.apply(this, arguments).then(() => {
                // Sólo para el Libro Mayor de AFR (ajustá si querés)
                if (this.report_name !== "report_enhancement.report_balance_addition") {
                    console.warn("No es el reporte de Balance de Sumas y Saldos.");
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

                // Evitar duplicados
                $container.find(".o_report_balance_addition_xlsx").remove();
                $container.find(".o_wizard_balance_addition").remove();
                $container.find(".o_refresh_balance_addition").remove();

                // Insertar como HERMANO del botón imprimir (no adentro)
                const $print = $container.find(".o_report_print").first();
                if ($print.length) {
                    $print.after(`
                        <button type="button"
                                class="btn btn-secondary o_report_balance_addition_xlsx"
                                title="Exportar Excel">
                            Exportar Excel
                        </button>

                        <button type="button"
                                class="btn btn-secondary o_wizard_balance_addition"
                                title="Balance Sumas y Saldos Wizard">
                            Balance Sumas y Saldos Wizard
                        </button>

                        <button type="button" title="Actualizar" class="btn btn-secondary o_refresh_balance_addition">
                            Actualizar
                        </button>
                    `);
                } else {
                    // si no hay print por alguna razón, lo agrego al final
                    $container.append(`
                        <button type="button"
                                class="btn btn-secondary o_report_balance_addition_xlsx"
                                title="Exportar Excel">
                            Exportar Excel
                        </button>

                        <button type="button"
                                class="btn btn-secondary o_wizard_balance_addition"
                                title="Balance Sumas y Saldos Wizard">
                            Balance Sumas y Saldos Wizard
                        </button>

                        <button type="button" title="Actualizar" class="btn btn-secondary o_refresh_balance_addition">
                            Actualizar
                        </button>
                    `);
                }
                
                // Asignar evento al botón
                // evento imprimir XLSX
                this.$buttons.off("click", ".o_report_balance_addition_xlsx");
                this.$buttons.on("click", ".o_report_balance_addition_xlsx", (ev) => {
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
                        report_name: "report_enhancement.report_balance_addition_xlsx",
                        report_file: "report_enhancement.report_balance_addition_xlsx",
                        data: this.data || {},
                        context: ctx,
                        display_name: "Libro mayor XLSX",
                    };
                    return this.do_action(action);
                });

                // evento reabrir wizard libro mayor
                this.$buttons.off("click", ".o_wizard_balance_addition");
                this.$buttons.on("click", ".o_wizard_balance_addition", (ev) => {
                    ev.preventDefault();
                    ev.stopPropagation();
                    ev.stopImmediatePropagation();

                    const wizardId =
                        (this.data && this.data.wizard_id) ||
                        (this.context && this.context.active_ids && this.context.active_ids[0]) ||
                        (this.context && this.context.active_id);

                    if (!wizardId) {
                        this.do_warn("Atención", "No se encontró el wizard_id para reabrir la configuración.");
                        return;
                    }

                    const ctx = Object.assign({}, this.context || {}, {
                        active_model: "report.balance.addition.wizard",
                        active_id: wizardId,
                        active_ids: [wizardId],
                    });

                    const action = {
                        type: "ir.actions.act_window",
                        name: "Libro Mayor - Configuración",
                        res_model: "report.balance.addition.wizard",
                        view_mode: "form",
                        views: [[false, "form"]],
                        res_id: wizardId,     // <-- clave: abre el MISMO wizard con los mismos datos
                        target: "new",
                        context: ctx,
                    };
                    return this.do_action(action);
                });

                // evento refresh libro mayor
                this.$buttons.off("click", ".o_refresh_balance_addition");
                this.$buttons.on("click", ".o_refresh_balance_addition", (ev) => {
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
                        report_type: "qweb-html",
                        report_name: "report_enhancement.report_balance_addition_html",
                        report_file: "report_enhancement.report_balance_addition_html",
                        data: this.data || {},
                        context: ctx,
                        display_name: "Libro mayor",
                    };
                    return this.do_action(action, {
                        clear_breadcrumbs: true, // opcional que no guarde en breadcrumbs
                    });
                });

                // Reinyecto botones al control panel
                this.controlPanelProps.cp_content = { $buttons: this.$buttons };
                this._controlPanelWrapper.update(this.controlPanelProps);
            });
        },
    });
});
