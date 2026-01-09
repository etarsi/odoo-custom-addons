odoo.define("account_enhancement.afr_export_bridge", function (require) {
    "use strict";

    console.log("[CP XLSX] cargado");

    $(document).on("click", ".o_report_export_excel", function (ev) {
        ev.preventDefault();

        // Botones del reporte que el AFR mete en el control panel
        const $reportButtons = $(".o_control_panel .o_cp_buttons .o_report_buttons:visible").first();

        // Verifica que estes en un reporte AFR (porque existe el print del AFR)
        if (!$reportButtons.length || !$reportButtons.find(".o_report_print").length) {
            alert("Este boton solo funciona dentro del Libro Mayor.");
            return;
        }
        console.log("[CP XLSX] detectado boton exportar XLSX");
        console.log($reportButtons);
        //agregar un ir_action_report para exportar xlsx
        const xlsxAction = {
            type: "ir.actions.report",
            report_type: "xlsx",
            report_name: "account_financial_reporting.report_general_ledger_xlsx",
            data: {},
        };
        // Ejecutar la accion
        this.do_action(xlsxAction);
    });
});
