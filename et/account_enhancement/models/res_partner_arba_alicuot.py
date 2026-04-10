# -*- coding: utf-8 -*-
from odoo import api, fields, models
import logging
from calendar import monthrange
from psycopg2.extras import execute_values
from pyafipws.iibb import IIBB
_logger = logging.getLogger(__name__)


ARBA_PROD_URL = "https://dfe.arba.gov.ar/DomicilioElectronicoFramework/SeguridadCliente/dfeServicioConsulta.do"
ARBA_LOCK_KEY = 987654321  # sirve para evitar que el cron se ejecute concurrentemente en varios workers, lo que podría causar problemas de integridad y performance al procesar los mismos CUITs simultáneamente.


class ResPartnerArbaAlicuot(models.Model):
    _inherit = "res.partner.arba_alicuot"

    @api.model
    def _to_float_ar_sql_cron(self, value):
        if value in (None, False, ""):
            return 0.0
        try:
            return float(str(value).replace(",", "."))
        except Exception:
            return 0.0

    @api.model
    def _get_arba_params(self):
        user = "30708077034"
        password = "Funtoys0205"
        batch_size = 500
        batches_per_run = 5

        return {
            "user": user,
            "password": password,
            "batch_size": batch_size,
            "batches_per_run": batches_per_run,
        }

    @api.model
    def _get_current_period_dates(self):
        today = fields.Date.to_date(fields.Date.context_today(self))
        desde = today.replace(day=1)
        hasta = today.replace(day=monthrange(today.year, today.month)[1])
        period_key = "%02d-%04d" % (today.month, today.year)
        return desde, hasta, period_key

    @api.model
    def _get_or_reset_period_state(self):
        ICP = self.env["ir.config_parameter"].sudo()
        _, _, current_period = self._get_current_period_dates()
        saved_period = ICP.get_param("account_enhancement.arba_iibb_period") or ""
        last_cuit = ICP.get_param("account_enhancement.arba_iibb_last_cuit") or ""

        if saved_period != current_period:
            ICP.set_param("account_enhancement.arba_iibb_period", current_period)
            ICP.set_param("account_enhancement.arba_iibb_last_cuit", "")
            last_cuit = ""
        return last_cuit

    @api.model
    def _set_last_cuit_state(self, last_cuit):
        self.env["ir.config_parameter"].sudo().set_param(
            "account_enhancement.arba_iibb_last_cuit", last_cuit or ""
        )

    @api.model
    def _fetch_next_padron_cuits(self, last_cuit, batch_size):
        """
        Lee CUITs únicos desde ar_padron_iibb usando last_cuit, sin OFFSET.
        OJO: la tabla real en PostgreSQL es ar_padron_iibb, no ar.padron.iibb
        """
        self.env.cr.execute("""
            SELECT sub.cuit
              FROM (
                    SELECT DISTINCT p.cuit
                      FROM ar_padron_iibb p
                     WHERE p.cuit IS NOT NULL
                       AND p.cuit ~ '^[0-9]{11}$'
                       AND p.cuit > %s
                     ORDER BY p.cuit
                     LIMIT %s
                   ) sub
             ORDER BY sub.cuit
        """, (last_cuit or "", batch_size))
        return [row[0] for row in self.env.cr.fetchall()]

    @api.model
    def _sql_update_padron_arba_results(self, rows):
        """
        rows = [(cuit, percepcion_arba, retention_arba), ...]
        Actualiza ar_padron_iibb por cuit en lote.
        """
        if not rows:
            return 0

        cr = self.env.cr

        cr.execute("DROP TABLE IF EXISTS tmp_arba_padron_result")
        cr.execute("""
            CREATE TEMP TABLE tmp_arba_padron_result (
                cuit VARCHAR(11) NOT NULL,
                percepcion_arba NUMERIC,
                retention_arba NUMERIC
            ) ON COMMIT DROP
        """)

        execute_values(
            cr,
            """
            INSERT INTO tmp_arba_padron_result (
                cuit,
                percepcion_arba,
                retention_arba
            ) VALUES %s
            """,
            rows,
            page_size=1000
        )

        cr.execute("""
            UPDATE ar_padron_iibb p
            SET percepcion_arba = t.percepcion_arba,
                retention_arba = t.retention_arba
            FROM tmp_arba_padron_result t
            WHERE p.cuit = t.cuit
            AND (
                    p.percepcion_arba IS DISTINCT FROM t.percepcion_arba
                    OR p.retention_arba IS DISTINCT FROM t.retention_arba
            )
        """)

        return cr.rowcount

    @api.model
    def cron_consultar_arba_iibb_desde_padron(self):
        """
        Cron principal.
        Procesa varios lotes por corrida.
        Guarda last_cuit para reanudar.
        """
        cr = self.env.cr

        cr.execute("SELECT pg_try_advisory_lock(%s)", (ARBA_LOCK_KEY,))
        locked = cr.fetchone()[0]
        if not locked:
            _logger.warning("ARBA IIBB cron ya está corriendo en otro worker. Se omite esta ejecución.")
            return

        try:
            params = self._get_arba_params()
            desde, hasta, period_key = self._get_current_period_dates()
            last_cuit = self._get_or_reset_period_state()
            url = ARBA_PROD_URL
            iibb = IIBB()
            iibb.Usuario = params["user"]
            iibb.Password = params["password"]
            iibb.Conectar(url=url)

            total_api_ok = 0
            total_rows_upsert = 0
            total_cuits_leidos = 0
            total_partners_afectados = 0
            error_count = 0

            for batch_number in range(params["batches_per_run"]):
                cuits = self._fetch_next_padron_cuits(last_cuit, params["batch_size"])
                if not cuits:
                    _logger.warning(
                        "ARBA IIBB cron finalizó barrido completo del período %s. Reiniciando last_cuit.",
                        period_key
                    )
                    self._set_last_cuit_state("")
                    cr.commit()
                    break

                rows = []
                batch_api_ok = 0
                batch_errors = []

                for cuit in cuits:
                    try:
                        ok = iibb.ConsultarContribuyentes(
                            desde.strftime("%Y%m%d"),
                            hasta.strftime("%Y%m%d"),
                            cuit
                        )
                    except Exception as e:
                        batch_errors.append("CUIT %s: %s" % (cuit, str(e)))
                        continue

                    if not ok:
                        continue

                    leido = iibb.LeerContribuyente()
                    if not leido:
                        continue

                    alicuota_percepcion = self._to_float_ar_sql_cron(iibb.AlicuotaPercepcion)
                    alicuota_retencion = self._to_float_ar_sql_cron(iibb.AlicuotaRetencion)

                    if alicuota_percepcion == 0 and alicuota_retencion == 0:
                        continue

                    rows.append((
                        cuit,
                        alicuota_percepcion,
                        alicuota_retencion,
                    ))
                    batch_api_ok += 1

                padron_affected = self._sql_update_padron_arba_results(rows=rows)
                last_cuit = cuits[-1]
                self._set_last_cuit_state(last_cuit)
                total_api_ok += batch_api_ok
                total_rows_upsert += padron_affected
                total_cuits_leidos += len(cuits)
                total_partners_afectados += len(rows)
                error_count += len(batch_errors)

                if batch_errors:
                    _logger.warning(
                        "ARBA IIBB lote %s con %s errores. Primeros 20:\n%s",
                        batch_number + 1,
                        len(batch_errors),
                        "\n".join(batch_errors[:20]),
                    )

                _logger.warning(
                    "ARBA IIBB lote %s | período=%s | cuits=%s | consultas_ok=%s | filas_con_datos=%s | update_padron=%s | last_cuit=%s",
                    batch_number + 1,
                    period_key,
                    len(cuits),
                    batch_api_ok,
                    len(rows),
                    padron_affected,
                    last_cuit,
                )

                cr.commit()

            _logger.warning(
                "ARBA IIBB cron terminado | período=%s | cuits_leidos=%s | consultas_ok=%s | partners_afectados=%s | filas_upsert=%s | errores=%s | last_cuit=%s",
                period_key,
                total_cuits_leidos,
                total_api_ok,
                total_partners_afectados,
                total_rows_upsert,
                error_count,
                last_cuit,
            )

        finally:
            cr.execute("SELECT pg_advisory_unlock(%s)", (ARBA_LOCK_KEY,))       
            