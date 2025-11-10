odoo.define('hr_enhancement.tree_button', function (require) { 
  "use strict"; 

  var ListController = require('web.ListController'); 
  var ListView = require('web.ListView'); 
  var viewRegistry = require('web.view_registry'); 
  var AttendanceListController = ListController.extend({ 
    renderButtons: function () {
      this._super.apply(this, arguments);
      if (this.$buttons) {
        // Evitar duplicar handlers al re-renderizar
        this.$buttons.off('click', '.open_wizard_action');
        this.$buttons.on('click', '.open_wizard_button', this._openWizard.bind(this));
      }
    },
    _openWizard: function (ev) { 

      if (ev) ev.preventDefault();

      return this.do_action({
        type: 'ir.actions.act_window',
        res_model: 'hr.attendance.create.wizard',
        name: 'Registrar Asistencia',
        views: [[false, 'form']],
        target: 'new',
      });
    },
  }); 

  const AttendanceListView = ListView.extend({ 
    config: _.extend({}, ListView.prototype.config, { 
      Controller: AttendanceListController, 
    }), 
  }); 

  viewRegistry.add('button_in_tree', AttendanceListView); 
});
