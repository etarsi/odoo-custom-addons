odoo.define("account_enhancement.afr_client_action_patch", function (require) {
    "use strict";

    console.log("[AFR PATCH] JS cargado: account_enhancement.afr_client_action_patch");

    const core = require("web.core");
    const QWeb = core.qweb;

    const TAG = "account_financial_report.client_action";

    // 1) Confirmar que el tag existe en el registry
    const AFRAction = core.action_registry.get(TAG);
    if (!AFRAction) {
        console.error(`[AFR PATCH] NO existe el tag en action_registry: ${TAG}`);
        return;
    }

    console.log(`[AFR PATCH] Tag encontrado en action_registry: ${TAG}`, AFRAction);

    // 2) Parchar (NO re-registrar)
    AFRAction.include({
        start: function () {
            console.log("[AFR PATCH] start() ejecutándose - antes de _super", this);

            const res = this._super.apply(this, arguments);

            return Promise.resolve(res).then(() => {
                console.log("[AFR PATCH] start() - después de _super", this);

                // Render botones (para confirmar que el template existe)
                let html;
                try {
                    html = QWeb.render("account_financial_report.client_action.ControlButtons", {});
                    console.log("[AFR PATCH] QWeb.render OK (ControlButtons)");
                } catch (e) {
                    console.error("[AFR PATCH] QWeb.render FALLÓ (ControlButtons). ¿Existe el template?", e);
                    return;
                }

                this.$buttons = $(html);
                console.log("[AFR PATCH] Botones renderizados:", this.$buttons);

                // Limpieza por si se ejecuta más de una vez
                this.$buttons.off("click", ".o_report_print");
                this.$buttons.off("click", ".o_report_export");

                // Bind seguro (con log)
                this.$buttons.on("click", ".o_report_print", (ev) => {
                    console.log("[AFR PATCH] CLICK Print -> se redirige a Export XLSX");
                    ev.preventDefault();
                    return this.on_click_export(ev);
                });

                this.$buttons.on("click", ".o_report_export", (ev) => {
                    console.log("[AFR PATCH] CLICK Export -> handler ejecutado");
                    ev.preventDefault();
                    return this.on_click_export(ev);
                });

                // Insertar en control panel
                this.controlPanelProps.cp_content = { $buttons: this.$buttons };
                this._controlPanelWrapper.update(this.controlPanelProps);

                console.log("[AFR PATCH] Control panel actualizado con botones");
            });
        },

        on_click_export: function (ev) {
            console.log("[AFR PATCH] on_click_export() llamado", {
                report_name: this.report_name,
                report_file: this.report_file,
                title: this.title,
                data: this.data,
                context: this.context,
            });

            const action = {
                type: "ir.actions.report",
                report_type: "xlsx",
                report_name: this._get_xlsx_name(this.report_name),
                report_file: this._get_xlsx_name(this.report_file),
                data: this.data,
                context: this.context,
                display_name: this.title,
            };
            console.log("[AFR PATCH] do_action con:", action);

            return this.do_action(action);
        },

        _get_xlsx_name: function (str) {
            if (!_.isString(str)) return str;
            const parts = str.split(".");
            return `a_f_r.report_${parts[parts.length - 1]}_xlsx`;
        },
    });

    console.log("[AFR PATCH] include() aplicado correctamente");
});
