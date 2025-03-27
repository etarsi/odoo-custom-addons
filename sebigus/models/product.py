from odoo import tools, models, fields, api, _
import base64
import logging
_logger = logging.getLogger(__name__)

class UpdateImage(models.Model):
    _inherit = "product.template"
        
    def update_image(self):
        def run(cmd):
            import subprocess
            print(' '.join(cmd))
            p = subprocess.Popen(cmd,stdout = subprocess.PIPE,stderr = subprocess.PIPE)
            output,error = p.communicate()
            p.wait()
            print(output)
            if error:
                raise NameError(error)
        import glob
        for rec in self:
            image_1920=None
            images_ids = []
            codigo = rec.default_code
            for i in glob.glob('/opt/imagenes/*/*%s*' % codigo,recursive=True):
            # Convierto la imagen  a 1024 y la dejo en el mismo lugar
                if not image_1920:
                    _logger.info('Imagen %s ' % i)
                    run(['/usr/bin/convert','-geometry','1024x','%s' % i, '/opt/odoo16/16.0/extra-addons/sebigus/static/images/%s.jpg' % codigo])
                    try:
                        image = open('/opt/odoo16/16.0/extra-addons/sebigus/static/images/%s.jpg' % codigo,'rb')
                        imageBase64 = base64.b64encode(image.read())
                        image_1920 = imageBase64.decode('ascii')
                        rec.update({'image_1920': image_1920})
                    except:
                        image_1920=None
                else:
                    run(['/usr/bin/convert','-geometry','1024x','%s' % i, '/opt/odoo16/16.0/extra-addons/sebigus/static/images/%s_%s.jpg' % (codigo,len(images_ids))])
                    img = '/opt/odoo16/16.0/extra-addons/sebigus/static/images/%s_%s.jpg' % (codigo,len(images_ids))
                    try:
                       image = open(img,'rb')
                       imageBase64 = base64.b64encode(image.read())
                       image_extra = imageBase64.decode('ascii')
                       self.env['product.image'].create({'image_1920': image_extra,'product_tmpl_id': rec.id,'name': rec.id})
                    except:
                       image_extra=None