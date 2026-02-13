# -*- coding: utf-8 -*-
from datetime import datetime
from odoo import fields, models, _
from odoo.exceptions import ValidationError, AccessError


class FiscalLockMixin(models.AbstractModel):
    _name = "fiscal.lock.mixin"
    _description = "Mixin bloqueo fiscal por fecha con excepción"

    # Excepción manual (solo grupo autorizado)
    fiscal_lock_exception = fields.Boolean(
        string="Excepción Bloqueo Gestión",
        copy=False,
        groups="account_enhancement.group_fiscal_lock_exception",
        help="Permite modificar/eliminar este registro aunque esté bloqueado por fecha de gestión."
    )
    fiscal_lock_exception_reason = fields.Char(
        string="Motivo excepción",
        copy=False,
        groups="account_enhancement.group_fiscal_lock_exception",
    )
    fiscal_lock_exception_user_id = fields.Many2one(
        "res.users",
        string="Autorizado por",
        readonly=True,
        copy=False,
        groups="account_enhancement.group_fiscal_lock_exception",
    )
    fiscal_lock_exception_date = fields.Datetime(
        string="Fecha autorización",
        readonly=True,
        copy=False,
        groups="account_enhancement.group_fiscal_lock_exception",
    )

    # ----------------------------
    # Helpers excepción
    # ----------------------------
    def _can_manage_exception(self):
        return self.env.user.has_group("account_enhancement.group_fiscal_lock_exception")

    def _normalize_exception_vals(self, vals):
        """
        Sanitiza/valida vals de excepción.
        - Bloquea que usuarios sin grupo toquen campos de excepción.
        - Si se activa excepción => motivo obligatorio + metadata.
        """
        vals = dict(vals or {})
        exception_fields = {
            "fiscal_lock_exception",
            "fiscal_lock_exception_reason",
            "fiscal_lock_exception_user_id",
            "fiscal_lock_exception_date",
        }

        touched = exception_fields.intersection(vals.keys())
        if touched and not self._can_manage_exception():
            raise AccessError(_("No tenés permisos para gestionar excepciones de bloqueo de gestión."))

        # Evitar spoof de metadata
        if "fiscal_lock_exception_user_id" in vals and "fiscal_lock_exception" not in vals:
            vals.pop("fiscal_lock_exception_user_id", None)
        if "fiscal_lock_exception_date" in vals and "fiscal_lock_exception" not in vals:
            vals.pop("fiscal_lock_exception_date", None)

        if "fiscal_lock_exception" in vals:
            enable = bool(vals.get("fiscal_lock_exception"))
            if enable:
                reason = (vals.get("fiscal_lock_exception_reason") or "").strip()
                if not reason:
                    raise ValidationError(_("Debe indicar un motivo para habilitar la excepción."))
                vals["fiscal_lock_exception_user_id"] = self.env.user.id
                vals["fiscal_lock_exception_date"] = fields.Datetime.now()
            else:
                vals["fiscal_lock_exception_user_id"] = False
                vals["fiscal_lock_exception_date"] = False
                vals.setdefault("fiscal_lock_exception_reason", False)

        return vals

    def _exception_active(self, rec=None, vals=None, parent=None):
        """
        Excepción válida SOLO para usuarios del grupo.
        Se considera activa si:
        - en vals viene fiscal_lock_exception=True
        - o el rec tiene excepción
        - o el parent (ej move) tiene excepción
        """
        if not self._can_manage_exception():
            return False
        vals = vals or {}
        if vals.get("fiscal_lock_exception") is True:
            return True
        if rec and getattr(rec, "fiscal_lock_exception", False):
            return True
        if parent and getattr(parent, "fiscal_lock_exception", False):
            return True
        return False

    # ----------------------------
    # Helpers bloqueo por fecha
    # ----------------------------
    def _to_date(self, value):
        if not value:
            return False
        if isinstance(value, datetime):
            return value.date()
        try:
            return fields.Date.to_date(value)
        except Exception:
            return fields.Datetime.to_datetime(value).date()

    def _get_lock_start_date(self, company_id):
        """
        Toma la gestión activa (hoy entre start/end) de la compañía.
        Si no hay activa, toma la más reciente por date_start.
        """
        if not company_id:
            return False

        Config = self.env["account.fiscal.period.config"].sudo()
        today = fields.Date.today()

        conf = Config.search([
            ("company_id", "=", company_id),
            ("date_start", "<=", today),
            ("date_end", ">=", today),
        ], order="date_start desc, id desc", limit=1)

        if not conf:
            conf = Config.search(
                [("company_id", "=", company_id)],
                order="date_start desc, id desc",
                limit=1
            )

        return conf.date_start if conf else False

    def _is_locked_by_period(self, company_id, date_value):
        d = self._to_date(date_value)
        if not company_id or not d:
            return False
        start = self._get_lock_start_date(company_id)
        return bool(start and d < start)

    def _raise_if_locked(self, company_id, date_value, operation, model_label, rec=None, vals=None, parent=None):
        d = self._to_date(date_value)
        if not d or not company_id:
            return
        start = self._get_lock_start_date(company_id)
        if start and d < start and not self._exception_active(rec=rec, vals=vals, parent=parent):
            raise ValidationError(_(
                "No se puede %(op)s en %(model)s.\n"
                "Fecha del registro: %(d)s\n"
                "Inicio de gestión vigente: %(start)s"
            ) % {
                "op": operation,
                "model": model_label,
                "d": fields.Date.to_string(d),
                "start": fields.Date.to_string(start),
            })

    def _raise_if_block_accounting(self, move, operation, rec=None, vals=None, parent=None):
        """
        Respeta block_accounting de account.move.
        Solo deja pasar con excepción válida.
        """
        if not move:
            return
        if getattr(move, "block_accounting", False):
            if not self._exception_active(rec=rec, vals=vals, parent=parent or move):
                raise ValidationError(_(
                    "No se puede %(op)s porque el asiento tiene 'Bloqueo de Contabilidad' activo."
                ) % {"op": operation})
