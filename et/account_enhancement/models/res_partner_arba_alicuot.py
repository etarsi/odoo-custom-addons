# -*- coding: utf-8 -*-
import logging
from calendar import monthrange
from collections import defaultdict

from psycopg2.extras import execute_values

from odoo import api, fields, models, _
from odoo.exceptions import UserError

from .iibb import IIBB  # ajustá el import según tu módulo

_logger = logging.getLogger(__name__)

COMPANY_IDS = [2, 3, 4]

ARBA_TEST_URL = "https://dfe.test.arba.gov.ar/DomicilioElectronicoFramework/SeguridadCliente/dfeServicioConsulta.do"
ARBA_PROD_URL = "https://dfe.arba.gov.ar/DomicilioElectronicoFramework/SeguridadCliente/dfeServicioConsulta.do"

ARBA_LOCK_KEY = 987654321  # cualquier entero fijo


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
        period_key = "%04d-%02d" % (today.year, today.month)
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
    def _map_active_partners_by_cuit(self, cuits):
        """
        Devuelve {cuit: [partner_ids]}.
        Mantiene un comportamiento parecido al actual:
        si hay varios partners activos con el mismo VAT limpio, los procesa a todos.
        """
        if not cuits:
            return {}

        self.env.cr.execute("""
            SELECT regexp_replace(COALESCE(rp.vat, ''), '[^0-9]', '', 'g') AS cuit,
                   rp.id
              FROM res_partner rp
             WHERE rp.active = TRUE
               AND rp.vat IS NOT NULL
               AND regexp_replace(COALESCE(rp.vat, ''), '[^0-9]', '', 'g') = ANY(%s)
        """, (cuits,))

        result = defaultdict(list)
        for cuit, partner_id in self.env.cr.fetchall():
            result[cuit].append(partner_id)
        return result

    @api.model
    def _sql_upsert_arba_results(self, rows, tag_id, desde, hasta):
        """
        rows = [(partner_id, alicuota_percepcion, alicuota_retencion), ...]
        Hace INSERT/UPDATE masivo en res_partner_arba_alicuot para todas las compañías.
        """
        if not rows:
            return 0

        cr = self.env.cr

        cr.execute("DROP TABLE IF EXISTS tmp_arba_ws_result")
        cr.execute("""
            CREATE TEMP TABLE tmp_arba_ws_result (
                partner_id INTEGER NOT NULL,
                alicuota_percepcion NUMERIC,
                alicuota_retencion NUMERIC
            ) ON COMMIT DROP
        """)

        execute_values(
            cr,
            """
            INSERT INTO tmp_arba_ws_result (
                partner_id,
                alicuota_percepcion,
                alicuota_retencion
            ) VALUES %s
            """,
            rows,
            page_size=1000
        )

        cr.execute("""
            INSERT INTO res_partner_arba_alicuot (
                partner_id,
                company_id,
                tag_id,
                from_date,
                to_date,
                alicuota_percepcion,
                alicuota_retencion,
                create_uid,
                create_date,
                write_uid,
                write_date
            )
            SELECT
                t.partner_id,
                c.company_id,
                %s,
                %s,
                %s,
                t.alicuota_percepcion,
                t.alicuota_retencion,
                %s,
                NOW(),
                %s,
                NOW()
            FROM tmp_arba_ws_result t
            CROSS JOIN unnest(%s::int[]) AS c(company_id)
            ON CONFLICT (partner_id, company_id, tag_id, from_date, to_date)
            DO UPDATE
               SET alicuota_percepcion = EXCLUDED.alicuota_percepcion,
                   alicuota_retencion = EXCLUDED.alicuota_retencion,
                   write_uid = EXCLUDED.write_uid,
                   write_date = EXCLUDED.write_date
             WHERE res_partner_arba_alicuot.alicuota_percepcion IS DISTINCT FROM EXCLUDED.alicuota_percepcion
                OR res_partner_arba_alicuot.alicuota_retencion IS DISTINCT FROM EXCLUDED.alicuota_retencion
        """, (
            tag_id,
            desde,
            hasta,
            self.env.uid,
            self.env.uid,
            COMPANY_IDS,
        ))

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

            tag = self.env["account.account.tag"].search(
                [("name", "=", "Ret/Perc IIBB ARBA")],
                limit=1
            )
            if not tag:
                raise UserError(_("No se encontró el tag 'Ret/Perc IIBB ARBA'."))

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

                partner_map = self._map_active_partners_by_cuit(cuits)

                rows = []
                batch_api_ok = 0
                batch_errors = []

                for cuit in cuits:
                    partner_ids = partner_map.get(cuit) or []
                    if not partner_ids:
                        continue

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

                    for partner_id in partner_ids:
                        rows.append((
                            partner_id,
                            alicuota_percepcion,
                            alicuota_retencion,
                        ))

                    batch_api_ok += 1

                affected = self._sql_upsert_arba_results(
                    rows=rows,
                    tag_id=tag.id,
                    desde=desde,
                    hasta=hasta,
                )

                last_cuit = cuits[-1]
                self._set_last_cuit_state(last_cuit)

                total_api_ok += batch_api_ok
                total_rows_upsert += affected
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
                    "ARBA IIBB lote %s | período=%s | cuits=%s | consultas_ok=%s | partners_con_datos=%s | upsert=%s | last_cuit=%s",
                    batch_number + 1,
                    period_key,
                    len(cuits),
                    batch_api_ok,
                    len(rows),
                    affected,
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