odoo.define("account_enhancement.field_monetary_expr", function (require) {
    "use strict";

    const field_registry = require("web.field_registry");
    const basic_fields = require("web.basic_fields");
    const FieldMonetary = basic_fields.FieldMonetary;

    function normalizeExpr(raw) {
        let expr = (raw || "").toString().trim();

        // Formato AR: 1.234.567,89  -> 1234567.89
        if (expr.includes(",")) {
            expr = expr.replace(/\./g, "").replace(/,/g, ".");
        }

        expr = expr.replace(/\s+/g, "");

        // Permitimos solo números, operadores y paréntesis
        if (!/^[0-9+\-*/().]+$/.test(expr)) {
            return null;
        }
        return expr;
    }

    function safeEval(expr) {
        // expr ya viene sanitizada, sin letras
        const v = Function('"use strict"; return (' + expr + ");")();
        if (!isFinite(v)) return null;
        return v;
    }

    const FieldMonetaryExpr = FieldMonetary.extend({
        _parseValue: function (value) {
            if (typeof value === "string" && /[+\-*/()]/.test(value)) {
                const expr = normalizeExpr(value);
                if (expr) {
                    const res = safeEval(expr);
                    if (res !== null) return res;
                }
            }
            return this._super.apply(this, arguments);
        },
    });

    field_registry.add("monetary_expr", FieldMonetaryExpr);
});
