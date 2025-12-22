odoo.define("account_enhancement.afr_patch_by_require", function (require) {
    "use strict";

    console.log("[AFR PATCH] JS cargado (patch por require)");

    // Esto carga el módulo original (AMD) y te devuelve la clase
    const AFRAction = require("account_financial_report.client_action");

    console.log("[AFR PATCH] Módulo base cargado:", AFRAction);

    AFRAction.include({
        start: function () {
            console.log("[AFR PATCH] start() antes de _super");
            const res = this._super.apply(this, arguments);

            return Promise.resolve(res).then(() => {
                console.log("[AFR PATCH] start() después de _super");

                if (!this.$buttons) {
                    console.warn("[AFR PATCH] this.$buttons no existe. El módulo base quizá no renderiza botones como esperás.");
                    return;
                }

                // Re-bind para asegurarnos de que 'this' sea correcto
                this.$buttons.off("click", ".o_report_print");
                this.$buttons.off("click", ".o_report_export");

                this.$buttons.on("click", ".o_report_print", (ev) => {
                    console.log("[AFR PATCH] CLICK Print -> Export XLSX");
                    ev.preventDefault();
                    return this.on_click_export(ev);
                });

                this.$buttons.on("click", ".o_report_export", (ev) => {
                    console.log("[AFR PATCH] CLICK Export -> XLSX");
                    ev.preventDefault();
                    return this.on_click_export(ev);
                });

                console.log("[AFR PATCH] Handlers re-bindeados OK");
            });
        },

        on_click_export: function (ev) {
            console.log("[AFR PATCH] on_click_export() llamado", {
                report_name: this.report_name,
                report_file: this.report_file,
                title: this.title,
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

            console.log("[AFR PATCH] do_action:", action);
            return this.do_action(action);
        },
    });

    console.log("[AFR PATCH] include() aplicado correctamente");
});
