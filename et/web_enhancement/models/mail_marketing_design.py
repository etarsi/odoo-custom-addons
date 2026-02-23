# -*- coding: utf-8 -*-
import re
from urllib.parse import quote

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools.safe_eval import safe_eval


class MailMarketingDesign(models.Model):
    _name = "mail.marketing.design"
    _description = "Diseño de campaña de marketing por email"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(required=True, tracking=True)
    active = fields.Boolean(default=True, string="Activo", tracking=True)

    use_case = fields.Selection(
        [("sales", "Ventas"), ("purchase", "Compras"), ("marketing", "Marketing")],
        default="marketing",
        required=True,
        tracking=True,
    )

    subject = fields.Char(string="Asunto", required=True, default="Promo Sebigus", tracking=True)
    mail_from_id = fields.Many2one(
        string="Servidor de correo saliente",
        comodel_name="ir.mail_server",
        ondelete='restrict',
        tracking=True,
    )
    
    reply_to = fields.Char(string="Responder a", tracking=True)
    recipient_count = fields.Integer(compute="_compute_recipient_count", string="Destinatarios")

    # Contenido
    preheader = fields.Char(default="Promo Sebigus - mirá los destacados")
    hero_image = fields.Binary(string="Imagen principal (Hero)", tracking=True)
    hero_filename = fields.Char()
    hero_link = fields.Char(string="Link del Hero (opcional)")

    whatsapp_number = fields.Char(
        string="WhatsApp (E.164)",
        help="Ej AR móvil: 54911xxxxxxxx (sin +, sin espacios).",
        tracking=True,
    )
    whatsapp_text = fields.Char(string="Mensaje precargado (opcional)")
    whatsapp_button_image = fields.Binary(string="Imagen botón WhatsApp", tracking=True, required=True)
    extra_html = fields.Html(string="Texto/Contenido adicional", sanitize=False)

    # Infra
    template_id = fields.Many2one("mail.template", string="Plantilla vinculada", readonly=True, copy=False)
    last_sent = fields.Datetime(readonly=True, copy=False)
    sent_qty = fields.Integer(readonly=True, copy=False)

    # -------------------------
    # Helpers
    # -------------------------
    def _clean_digits(self, s):
        return re.sub(r"\D+", "", (s or ""))

    def _wa_link(self):
        digits = self._clean_digits(self.whatsapp_number)
        if not digits:
            return False
        if self.whatsapp_text:
            return "https://wa.me/%s?text=%s" % (digits, quote(self.whatsapp_text))
        return "https://wa.me/%s" % digits

    def _public_image_url(self, attachment):
        base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url") or ""
        if not base_url:
            raise UserError(_("No está configurado web.base.url"))
        return "%s/web/content/%s?download=false" % (base_url, attachment.id)

    def _ensure_public_attachment(self, bin_field, filename, mimetype_guess="image/png"):
        if not bin_field:
            return False

        # Si ya existe un attachment "igual" podrías optimizar; acá lo mantenemos simple.
        att = self.env["ir.attachment"].sudo().create({
            "name": filename or "image.png",
            "type": "binary",
            "datas": bin_field,
            "mimetype": mimetype_guess,
            "public": True,  # importante para destinatarios externos
        })
        return att

    def _build_html(self, hero_url, wa_url, wa_btn_url=None):
        preheader = (self.preheader or "").strip()
        extra = self.extra_html or ""

        # Hero clickeable si hay link
        if self.hero_link:
            hero_block = f"""
              <a href="{self.hero_link}" target="_blank" style="text-decoration:none;">
                <img src="{hero_url}" alt="Promo"
                     style="display:block; border:0; width:100%; max-width:600px; height:auto; margin:0 auto;"/>
              </a>
            """
        else:
            hero_block = f"""
              <img src="{hero_url}" alt="Promo"
                   style="display:block; border:0; width:100%; max-width:600px; height:auto; margin:0 auto;"/>
            """

        # WhatsApp como imagen o como link
        if wa_btn_url:
            wa_block = f"""
              <div style="padding:14px 0 0 0; text-align:center;">
                <a href="{wa_url}" target="_blank" style="text-decoration:none; display:inline-block;">
                  <img src="{wa_btn_url}" alt="WhatsApp"
                       style="display:block; border:0; width:100%; max-width:280px; height:auto; margin:0 auto;"/>
                </a>
              </div>
            """
        else:
            wa_block = f"""
              <div style="margin-top:14px; text-align:center;">
                <a href="{wa_url}" target="_blank"
                   style="font-family:Arial, sans-serif; font-size:14px; font-weight:700; color:#2563EB; text-decoration:none;">
                  Hablar por WhatsApp →
                </a>
              </div>
            """

        html = f"""
<div style="margin:0; padding:0; background:#f6f7fb;">
  <div style="max-width:720px; margin:0 auto; padding:18px;">
    <div style="display:none; max-height:0; overflow:hidden; opacity:0; color:transparent;">
      {preheader}
    </div>

    <div style="border-radius:16px; overflow:hidden; border:1px solid #EAECF0; background:#ffffff;">

      <div style="padding:0; margin:0;">
        {hero_block}
      </div>

      <div style="padding:18px 18px 6px 18px;">
        <div style="font-family:Arial, sans-serif; font-size:18px; font-weight:700; color:#101828;">
          Hola, {{ object.name }}
        </div>

        <div style="font-family:Arial, sans-serif; font-size:14px; line-height:1.6; color:#344054; margin-top:10px;">
          {extra}
        </div>

        {wa_block}

        <div style="font-family:Arial, sans-serif; font-size:12px; color:#98A2B3; margin-top:18px;">
          Este correo fue generado automáticamente por Sebigus.
        </div>
      </div>

    </div>
  </div>
</div>
"""
        return html

    def _get_recipients(self):
        self.ensure_one()
        try:
            domain = safe_eval("['|', ('mail_alternative','!=',False), ('mail_alternative_b','!=',False)]")
        except Exception as e:
            raise UserError(_("Dominio inválido: %s") % e)

        # Seguridad: forzamos email != False
        domain = list(domain)
        partners = self.env["res.partner"].search(domain)
        return partners

    def _compute_recipient_count(self):
        for rec in self:
            try:
                domain = safe_eval("['|', ('mail_alternative','!=',False), ('mail_alternative_b','!=',False)]")
                domain = list(domain)
                rec.recipient_count = self.env["res.partner"].search_count(domain)
            except Exception:
                rec.recipient_count = 0

    # -------------------------
    # Acciones
    # -------------------------
    def action_sync_template(self):
        for rec in self:
            if not rec.hero_image:
                raise UserError(_("Tenés que cargar la imagen principal (Hero)."))
            wa_url = rec._wa_link()
            if not wa_url:
                raise UserError(_("Tenés que completar el WhatsApp (E.164)."))

            hero_att = rec._ensure_public_attachment(rec.hero_image, rec.hero_filename or "hero.png")
            hero_url = rec._public_image_url(hero_att)

            wa_btn_url = False
            if rec.whatsapp_button_image:
                wa_att = rec._ensure_public_attachment(rec.whatsapp_button_image, "btn_whatsapp.png")
                wa_btn_url = rec._public_image_url(wa_att)

            body = rec._build_html(hero_url=hero_url, wa_url=wa_url, wa_btn_url=wa_btn_url)

            vals_tmpl = {
                "name": f"Sebigus | {rec.name}",
                "model_id": self.env.ref("base.model_res_partner").id,
                "subject": rec.subject,
                "email_from": rec.mail_from_id.smtp_user if rec.mail_from_id else (self.env.company.email or self.env.user.email_formatted or ""),
                "reply_to": rec.reply_to or False,
                "body_html": body,
                "auto_delete": False,
            }

            if rec.template_id:
                rec.template_id.write(vals_tmpl)
            else:
                rec.template_id = self.env["mail.template"].create(vals_tmpl)

        return True

    def action_send_mail(self):
        """Envía a todos los partners que matchean el domain. No wizard."""
        for rec in self:
            if not rec.template_id:
                rec.action_sync_template()

            partners = rec._get_recipients()
            if not partners:
                raise UserError(_("No hay destinatarios con ese filtro."))

            sent = 0
            # Encola mails (no force_send) para que los mande el scheduler/queue
            for p in partners:
                rec.template_id.send_mail(
                    p.id,
                    force_send=False,
                    email_values={
                        # opcional: override dinámicos por envío
                        "email_to": p.mail_alternative or p.mail_alternative_b,
                    },
                    raise_exception=False,
                )
                sent += 1

            rec.last_sent = fields.Datetime.now()
            rec.sent_qty = (rec.sent_qty or 0) + sent

        return True

    def action_open_recipients(self):
        self.ensure_one()
        partners = self._get_recipients()
        return {
            "type": "ir.actions.act_window",
            "name": _("Destinatarios"),
            "res_model": "res.partner",
            "view_mode": "tree,form",
            "domain": [("id", "in", partners.ids)],
            "target": "current",
        }