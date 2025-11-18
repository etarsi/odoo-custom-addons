/** @odoo-module **/

import { registry } from '@web/core/registry';
import { listView } from '@web/views/list/list_view';
import { ListRenderer } from '@web/views/list/list_renderer';

class RowNumberListRenderer extends ListRenderer {
    /**
     * En Odoo 15 el ListRenderer usa getCellValue para obtener el valor a mostrar.
     * Interceptamos cuando el widget es "row_number".
     */
    getCellValue(record, column) {
        if (column.widget === 'row_number') {
            // posición del record dentro de la lista actual
            const idx = this.props.list.records.indexOf(record);
            // sumamos 1 para que arranque en 1 (no en 0)
            return idx >= 0 ? idx + 1 : '';
        }
        return super.getCellValue(record, column);
    }
}

export const rowNumberListView = {
    ...listView,
    Renderer: RowNumberListRenderer,
};

registry.category('views').add('row_number_list', rowNumberListView);