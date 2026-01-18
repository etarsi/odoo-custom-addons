odoo.define("account_enhancement.move_line_footer_balance", function (require) {
    "use strict";

    const ListRenderer = require("web.ListRenderer");
    const field_utils = require("web.field_utils");
    const core = require("web.core");
    const _t = core._t;

    ListRenderer.include({
        _renderFooter: function () {
            const $footer = this._super.apply(this, arguments);

            try {
                const cls = (this.arch && this.arch.attrs && this.arch.attrs.class) || "";
                if (!cls.split(" ").includes("o_show_balance_diff")) {
                    return $footer;
                }

                // Sumar debe/haber desde las filas del list actual
                let debe = 0.0;
                let haber = 0.0;
                (this.state.data || []).forEach((r) => {
                    const d = (r.data && r.data.debit) || 0.0;
                    const h = (r.data && r.data.credit) || 0.0;
                    debe += d;
                    haber += h;
                });
                console.log("Footer balance diff - debe:", debe, "haber:", haber);

                const diff = Math.abs(haber - debe);
                if (!diff) return $footer;

                const falta = haber > debe ? _t("Falta Debe") : _t("Falta Haber");
                const diffFmt = field_utils.format.float(diff, {}, { digits: [16, 2] });

                // Buscar la celda del total de "credit" en el footer y anexar el texto
                const $creditCell = $footer
                    .find("td[data-name='credit']")
                    .last();

                if ($creditCell.length) {
                    $creditCell.append(
                        $("<span/>", {
                            class: "o_move_balance_diff",
                            text: "  (" + falta + ": " + diffFmt + ")",
                        })
                    );
                }
            } catch (e) {
                console.warn("[BALANCE DIFF] Error renderizando footer:", e);
            }

            return $footer;
        },
    });
});
