odoo.define("account_enhancement.afr_bridge_print", function (require) {
    "use strict";

    console.log("[CP DO PRINT] cargado");

    $(document).on("click", ".o_report_export_excel", function (ev) {
        ev.preventDefault();

        // 1) Si estás en el Libro Mayor, existe el botón Imprimir del AFR:
        const $print = $(".o_control_panel .o_cp_buttons .o_report_buttons .o_report_print:visible");
        if ($print.length) {
            $print.trigger("click");   // imprime "de una"
            return;
        }

        // 2) Si preferís exportar, y existe Exportar:
        const $export = $(".o_control_panel .o_cp_buttons .o_report_buttons .o_report_export:visible");
        if ($export.length) {
            $export.trigger("click");  // exporta "de una"
            return;
        }

        // 3) Si no estás en el reporte, avisar
        alert("Este botón solo funciona dentro del reporte (Libro Mayor).");
    });
});
