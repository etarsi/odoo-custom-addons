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
        // Si el boton export NO existe, lo inyectamos oculto.
        // Si el JS del AFR tiene el handler delegado (.on('click', '.o_report_export', ...)),
        // este boton nuevo lo va a tomar automaticamente.
        if (!$reportButtons.find(".o_report_export").length) {
            $("<button/>", {
                type: "button",
                class: "btn btn-secondary o_report_export",
                title: "Exportar Excel",
                text: "Exportar",
                css: { display: "none" }, // oculto (no ensucia UI)
            }).appendTo($reportButtons);
        }

        // Disparar export XLSX
        $reportButtons.find(".o_report_export").trigger("click");
    });
});
