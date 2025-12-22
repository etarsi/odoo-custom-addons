odoo.define("account_enhancement.afr_client_action_patch", function (require) {
    "use strict";

    const core = require("web.core");

    // Tomo la acción YA registrada por account_financial_report
    const AFRAction = core.action_registry.get("account_financial_report.client_action");
    console.log("AFRAction:", AFRAction);
    if (!AFRAction) {
        // Si no existe, es que el módulo no cargó o el tag es otro
        return;
    }

    AFRAction.include({
        /**
         * Rebind de eventos para asegurar que 'this' sea correcto
         * y que el botón "Print" dispare XLSX.
         */
        start: function () {
            const res = this._super.apply(this, arguments);

            return Promise.resolve(res).then(() => {
                if (!this.$buttons) return;

                // Evitar duplicados
                this.$buttons.off("click", ".o_report_print");
                this.$buttons.off("click", ".o_report_export");

                // Bind correcto
                this.$buttons.on("click", ".o_report_print", this.on_click_print.bind(this));
                this.$buttons.on("click", ".o_report_export", this.on_click_export.bind(this));
            });
        },

        /**
         * Print -> Export XLSX
         */
        on_click_print: function (ev) {
            if (ev) ev.preventDefault();
            return this.on_click_export(ev);
        },
    });
});
