/** @odoo-module **/

import { registry } from "@web/core/registry";
import { UncaughtPromiseError } from "@web/core/errors/error_service";
import { ConnectionLostError } from "@web/core/network/rpc_service";

/**
 * Handler con mayor prioridad que el original (que tiene sequence: 98).
 * Si detecta pérdida de conexión, simplemente consume el error y NO muestra nada.
 */
function silenceConnectionLostHandler(env, error, originalError) {
    if (!(error instanceof UncaughtPromiseError)) {
        return false;
    }
    if (originalError instanceof ConnectionLostError) {
        // Consumimos el evento: NO mostramos toast, dejamos que Odoo reconecte solo.
        return true;
    }
    return false;
}

// Menor que 98 => corre antes que lostConnectionHandler
registry.category("error_handlers").add("silenceConnectionLostHandler", silenceConnectionLostHandler, {
    sequence: 10,
});
