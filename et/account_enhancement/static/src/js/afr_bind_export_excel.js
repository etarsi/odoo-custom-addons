odoo.define("account_enhancement.afr_bind_export_excel", function (require) {
    "use strict";

    const AFRAction = require("account_financial_report.client_action");

    AFRAction.include({
        start: function () {
            return this._super.apply(this, arguments).then(() => {
                // Control Panel DOM
                const $cp = this._controlPanelWrapper && this._controlPanelWrapper.$el;
                if (!$cp) return;
                console.log("AFRAction: bind export to excel button");
                console.log($cp);
                console.log(this);

                // Evitar duplicar handlers
                $cp.off("click", ".o_report_export_excel");

                // Click => export xlsx del AFR
                $cp.on("click", ".o_report_export_excel", (ev) => {
                    ev.preventDefault();
                    if (typeof this.on_click_export === "function") {
                        return this.on_click_export();
                    }
                });
            });
        },
    });
});
