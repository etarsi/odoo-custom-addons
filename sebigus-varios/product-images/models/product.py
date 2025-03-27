from odoo import tools, models, fields, api, _
import base64
import logging
_logger = logging.getLogger(__name__)

class UpdateImage(models.Model):
    _inherit = "product.template"
        
    def update_image(self):
        def run(cmd):
            import subprocess
            _logger.info(' '.join(cmd))
            p = subprocess.Popen(cmd,stdout = subprocess.PIPE,stderr = subprocess.PIPE)
            output,error = p.communicate()
            p.wait()
            _logger.info(output)
            if error:
                raise NameError(error)
        import glob
        for rec in self:
            image_1920=None
            images_ids = []
            codigo = rec.default_code
            try:
                if rec.route_ids.name == 'Fabricar':
                    codigo = codigo[1:]
            except:
                codigo = codigo
            image_folder = self.env['ir.config_parameter'].sudo().get_param('product.image_folder')
            image_folder_convert = self.env['ir.config_parameter'].sudo().get_param('product.image_folder_convert')
            for i in glob.glob('/%s/*/%s*' % (image_folder,codigo),recursive=True):
                _logger.info('Imagen %s ' % i)
                if not image_1920:
                    try:
                        run(['/usr/bin/convert','-geometry','1024x','%s' % i, '/%s/%s.jpg' % (image_folder_convert, codigo)])
                        image = open('/%s/%s.jpg' % (image_folder_convert,codigo),'rb')
                        imageBase64 = base64.b64encode(image.read())
                        image_1920 = imageBase64.decode('ascii')
                        rec.update({'image_1920': image_1920})
                    except:
                        image_1920=None
                else:
                    try:
                       run(['/usr/bin/convert','-geometry','1024x','%s' % i, '/%s/%s_%s.jpg' % (image_folder_convert, codigo,len(images_ids))])
                       img = '/%s/%s_%s.jpg' % (image_folder_convert, codigo,len(images_ids))
                       image = open(img,'rb')
                       imageBase64 = base64.b64encode(image.read())
                       image_extra = imageBase64.decode('ascii')
                       self.env['product.image'].create({'image_1920': image_extra,'product_tmpl_id': rec.id,'name': rec.id})
                    except:
                       image_extra=None
