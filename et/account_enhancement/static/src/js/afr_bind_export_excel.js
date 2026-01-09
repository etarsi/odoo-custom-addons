odoo.define("account_enhancement.afr_bind_export_excel", function (require) {
    "use strict";

    console.log("[CP ALERT] cargado");

    // Delegación global: funciona aunque el control panel se re-renderice
    $(document).on("click", ".o_report_export_excel", function (ev) {
        ev.preventDefault();
        alert("Hola! Click en Exportar Excel");
        console.log("[CP ALERT] click en Exportar Excel");
    });
});
