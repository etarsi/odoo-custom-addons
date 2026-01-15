odoo.define("account_enhancement.report_client_action_export_xlsx", function (require) {
    "use strict";

    const ReportAction = require("report.client_action");
    const actionManager = require("web.action_manager");
    // Tomo jQuery como global (en tu runtime no existe require('jquery') ni require('web.jquery'))
    const $ = window.jQuery || window.$;

    ReportAction.include({
        start: function () {
            return this._super.apply(this, arguments).then(() => {
                // Sólo para el Libro Mayor de AFR (ajustá si querés)
                if (this.report_name !== "account_financial_report.general_ledger") {
                    console.warn("[PATCH] No es libro mayor, saliendo.");
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
                $container.find(".o_report_export_excel").remove();
                $container.find(".o_wizard_general_ledger").remove();
                $container.find(".o_refresh_general_ledger").remove();

                // Insertar como HERMANO del botón imprimir (no adentro)
                const $print = $container.find(".o_report_print").first();
                if ($print.length) {
                    $print.after(`
                        <button type="button"
                                class="btn btn-secondary o_report_export_excel"
                                title="Exportar Excel">
                            Exportar Excel
                        </button>

                        <button type="button"
                                class="btn btn-secondary o_wizard_general_ledger"
                                title="Libro Mayor Wizard">
                            Libro Mayor Wizard
                        </button>

                        <button type="button" title="Actualizar" class="btn btn-secondary o_refresh_general_ledger">
                            Actualizar
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

                        <button type="button"
                                class="btn btn-secondary o_wizard_general_ledger"
                                title="Libro Mayor Wizard">
                            Libro Mayor Wizard
                        </button>

                        <button type="button" title="Actualizar" class="btn btn-secondary o_refresh_general_ledger">
                            Actualizar
                        </button>
                    `);
                }
                
                // Asignar evento al botón
                // evento imprimir XLSX
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
                        report_name: "a_f_r.report_general_ledger_xlsx",
                        report_file: "a_f_r.report_general_ledger_xlsx",
                        data: this.data || {},
                        context: ctx,
                        display_name: "Libro mayor XLSX",
                    };
                    return this.do_action(action);
                });

                // evento reabrir wizard libro mayor
                this.$buttons.off("click", ".o_wizard_general_ledger");
                this.$buttons.on("click", ".o_wizard_general_ledger", (ev) => {
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
                        active_model: "general.ledger.report.wizard",
                        active_id: wizardId,
                        active_ids: [wizardId],
                    });

                    const action = {
                        type: "ir.actions.act_window",
                        name: "Libro Mayor - Configuración",
                        res_model: "general.ledger.report.wizard",
                        view_mode: "form",
                        views: [[false, "form"]],
                        res_id: wizardId,     // <-- clave: abre el MISMO wizard con los mismos datos
                        target: "new",
                        context: ctx,
                    };
                    return this.do_action(action);
                });

                // evento refresh libro mayor
                this.$buttons.off("click", ".o_refresh_general_ledger");
                this.$buttons.on("click", ".o_refresh_general_ledger", (ev) => {
                    ev.preventDefault();
                    ev.stopPropagation();
                    ev.stopImmediatePropagation();

                    console.log("[REFRESH] solicitado");

                    const ctrl = actionManager.getCurrentController && actionManager.getCurrentController();
                    const currentAction = ctrl && ctrl.action;

                    console.log("[REFRESH] currentAction:", currentAction);

                    if (currentAction) {
                        return actionManager.doAction(currentAction, {
                            clear_breadcrumbs: false,
                            replace_last_action: true,
                        });
                    }

                    // fallback duro
                    window.location.reload();


                });

                // Reinyecto botones al control panel
                this.controlPanelProps.cp_content = { $buttons: this.$buttons };
                this._controlPanelWrapper.update(this.controlPanelProps);
            });
        },
    });
});
