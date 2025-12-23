odoo.define("account_enhancement.afr_patch_by_require", function (require) {
    "use strict";

    console.log("[AFR PATCH] 1) JS cargado: afr_patch_by_require");

    let AFRAction;
    try {
        AFRAction = require("account_financial_report.client_action");
        console.log("[AFR PATCH] 2) Módulo base cargado:", AFRAction);
    } catch (e) {
        console.error("[AFR PATCH] ERROR al require del módulo base", e);
        return;
    }

    try {
        AFRAction.include({
            start: function () {
                console.log("[AFR PATCH] 3) start() antes de _super - INSTANCIA:", this);

                const res = this._super.apply(this, arguments);

                return Promise.resolve(res).then(() => {
                    console.log("[AFR PATCH] 4) start() después de _super - INSTANCIA:", this);
                    console.log("[AFR PATCH] 5) this.$buttons:", this.$buttons);

                    if (!this.$buttons) {
                        console.warn("[AFR PATCH] ATENCIÓN: this.$buttons no existe. El módulo base no está inyectando botones como esperás.");
                        return;
                    }

                    // Rebind de handlers
                    this.$buttons.off("click", ".o_report_print");
                    this.$buttons.off("click", ".o_report_export");

                    this.$buttons.on("click", ".o_report_print", (ev) => {
                        console.log("[AFR PATCH] 6) CLICK Print -> Export XLSX");
                        ev.preventDefault();
                        return this.on_click_export(ev);
                    });

                    this.$buttons.on("click", ".o_report_export", (ev) => {
                        console.log("[AFR PATCH] 7) CLICK Export -> Export XLSX");
                        ev.preventDefault();
                        return this.on_click_export(ev);
                    });

                    console.log("[AFR PATCH] 8) Handlers OK");
                });
            },

            on_click_export: function (ev) {
                console.log("[AFR PATCH] 9) on_click_export() llamado", {
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

                console.log("[AFR PATCH] 10) do_action:", action);
                return this.do_action(action);
            },

            _get_xlsx_name: function (str) {
                if (!_.isString(str)) return str;
                const parts = str.split(".");
                return `a_f_r.report_${parts[parts.length - 1]}_xlsx`;
            },
        });

        console.log("[AFR PATCH] 11) include() aplicado correctamente");
    } catch (e) {
        console.error("[AFR PATCH] ERROR aplicando include()", e);
    }
});
