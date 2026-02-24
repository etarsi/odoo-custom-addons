# -*- coding: utf-8 -*-
import re
from urllib.parse import quote

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools.safe_eval import safe_eval
import base64, os, hashlib, mimetypes

MAIL_IMG_DIR = "/opt/odoo15/mail_image"

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
    main_img = fields.Binary(string="Imagen principal", tracking=True)
    main_filename = fields.Char()
    main_link = fields.Char(string="Link de la imagen principal (opcional)", tracking=True)
    
    main_file = fields.Char(readonly=True, copy=False)
    wa_button_file = fields.Char(readonly=True, copy=False)

    whatsapp_number = fields.Char(
        string="WhatsApp (E.164)",
        help="Ej AR móvil: 54911xxxxxxxx (sin +, sin espacios).",
        tracking=True,
    )
    whatsapp_text = fields.Char(string="Mensaje precargado (opcional)", tracking=True)
    whatsapp_button_image = fields.Binary(string="Imagen botón WhatsApp", tracking=True, required=True)
    extra_html = fields.Html(string="Texto/Contenido adicional", sanitize=False, tracking=True)

    # Infra
    template_id = fields.Many2one("mail.template", string="Plantilla vinculada", readonly=True, copy=False)
    last_sent = fields.Datetime(string="Último envío", readonly=True, copy=False)
    sent_qty = fields.Integer(string="Cantidad enviada", readonly=True, copy=False)

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

    def _build_html(self, main_url, wa_url, wa_btn_url=None):
        preheader = (self.preheader or "").strip()
        extra = self.extra_html or ""

        base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url") or ""
        if not base_url:
            raise UserError(_("No está configurado web.base.url"))
        if self.main_file:
            main_url = f"{base_url}/mail_image/{self.main_file}"
        wa_btn_url = f"{base_url}/mail_image/{self.wa_button_file}" if self.wa_button_file else False

        # Hero clickeable si hay link
        if self.main_link:
            hero_block = f"""
            <a href="{self.main_link}" target="_blank" style="text-decoration:none; display:block;">
                <img src="{main_url}" alt="Promo"
                    style="display:block; border:0; width:100%; height:auto; margin:0; padding:0;"/>
            </a>
            """
        else:
            hero_block = f"""
              <img src="{main_url}" alt="Promo"
                   style="display:block; border:0; width:100%; height:auto; margin:0; padding:0;"/>
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
    <div style="max-width:720px; margin:0 auto; padding:0;">
    <div style="display:none; max-height:0; overflow:hidden; opacity:0; color:transparent;">
      {preheader}
    </div>

    <div style="overflow:hidden; background:#ffffff;">

      <div style="padding:0; margin:0;">
        {hero_block}
      </div>

      <div style="padding:18px 18px 6px 18px;">

        {wa_block}

        <div style="font-size:11px; line-height:1.4; color:#98A2B3; margin-top:18px;">
            Este e-mail es una publicidad de 
            <a href="https://one.sebigus.com.ar" target="_blank" rel="noopener noreferrer" style="color:#98A2B3; text-decoration:underline;">
                https://one.sebigus.com.ar
            </a> 
            SEBIGUS S.A. CUIT: 30-7080770-34. Domicilio Legal Lavalle 2540, C.A.B.A. 
            Si no desea recibir esta información contáctenos a través de nuestro Centro de Ayuda de su vendedor. 
            El titular podrá en cualquier momento solicitar el retiro o bloqueo de su nombre de los bancos de datos a los que se refiere el presente artículo. 
            decreto 1558/01- art. 27 3er párrafo: en toda comunicación con fines de publicidad que se realice por correo, teléfono, correo electrónico, 
            internet u otro medio a distancia a conocer, se deberá indicar, en forma expresa y destacada la posibilidad del titular del dato de solicitar 
            el retiro o bloqueo, total o parcial, de su nombre de la base de datos. a pedido del interesado, se deberá informar el nombre del responsable o usuario 
            del banco de datos que proveyó la información. 
            <a href="https://one.sebigus.com.ar" target="_blank" rel="noopener noreferrer" style="color:#98A2B3; text-decoration:underline;">
                https://one.sebigus.com.ar
            </a> 
            a través de este sitio web. 
            El titular de los datos personales tiene la facultad de ejercer el derecho de acceso a los mismos en forma gratuita a intervalos no inferiores a seis meses,
            salvo que se acredite un interés legítimo al efecto conforme lo establecido en el artículo 14, inciso 3 de la Ley 25.326. 
            La DIRECCION NACIONAL DE PROTECCION DE DATOS PERSONALES, Órgano de Control de la Ley 25.326, 
            tiene la atribución de atender las denuncias y reclamos que se interpongan con relación al incumplimiento de las normas sobre protección de datos personales. 
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
            if not rec.main_img:
                raise UserError(_("Tenés que cargar la imagen principal."))
            wa_url = rec._wa_link()
            if not wa_url:
                raise UserError(_("Tenés que completar el WhatsApp (E.164)."))

            # Asegurar archivos
            if not rec.main_file:
                rec.main_file = rec._bin_to_file(rec.main_img, rec.main_filename or "main.png", prefix="main")
            if not rec.wa_button_file and rec.whatsapp_button_image:
                rec.wa_button_file = rec._bin_to_file(rec.whatsapp_button_image, "btn_whatsapp.png", prefix="wa")

            # Construir HTML (main_url se resuelve adentro si main_file existe)
            body = rec._build_html(main_url="", wa_url=wa_url, wa_btn_url=False)

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
    
    def _get_email_from_header(self):
        self.ensure_one()
        name = ("SEBIGUS").replace('"', "").strip()
        email = (self.mail_from_id.smtp_user).strip()
        if not email:
            raise UserError(_("Definí Email remitente o company email."))
        return f"\"{name}\" <{email}>"

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
                    force_send=True,
                    email_values={
                        # opcional: override dinámicos por envío
                        "email_to": p.mail_alternative or p.mail_alternative_b,
                        "email_from": rec._get_email_from_header(),
                        "mail_server_id": rec.mail_from_id.id,
                    },
                    raise_exception=False,
                )
                sent += 1
            rec.last_sent = fields.Datetime.now()
            rec.sent_qty = (rec.sent_qty or 0) + sent
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("¡Envío en proceso!"),
                "message": _("Los correos se están enviando en segundo plano. Total destinatarios: %s") % sent,
                "sticky": False,
            },
        }

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

    def _bin_to_file(self, b64, filename_hint="image.png", prefix="img"):
        self.ensure_one()
        if not b64:
            return False

        raw = base64.b64decode(b64)
        digest = hashlib.sha1(raw).hexdigest()[:16]  # corto
        ext = os.path.splitext(filename_hint or "")[1].lower() or ".png"
        if ext not in [".png", ".jpg", ".jpeg", ".gif", ".webp"]:
            ext = ".png"

        fname = f"{prefix}_{self.id}_{digest}{ext}"
        path = os.path.join(MAIL_IMG_DIR, fname)

        # escribir
        with open(path, "wb") as f:
            f.write(raw)

        return fname
    
    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            if "main_img" in vals and rec.main_img:
                rec.main_file = rec._bin_to_file(rec.main_img, rec.main_filename or "main.png", prefix="main")
            if "whatsapp_button_image" in vals and rec.whatsapp_button_image:
                rec.wa_button_file = rec._bin_to_file(rec.whatsapp_button_image, "btn_whatsapp.png", prefix="wa")
        return res
    
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec, vals in zip(records, vals_list):
            if vals.get("main_img") and rec.main_img:
                rec.main_file = rec._bin_to_file(rec.main_img, rec.main_filename or "main.png", prefix="main")
            if vals.get("whatsapp_button_image") and rec.whatsapp_button_image:
                rec.wa_button_file = rec._bin_to_file(rec.whatsapp_button_image, "btn_whatsapp.png", prefix="wa")
        return records