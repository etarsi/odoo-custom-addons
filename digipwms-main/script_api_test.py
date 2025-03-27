import sys
import requests
import openpyxl
import datetime
import sys
import re
from xmlrpc import client


url = "https://run.sebigus.com.ar"
dbname = "test"
user = "admin"
pwd = "Sebigus123!"
url = "https://ventas.sebigus.com.ar"
dbname = "sebigus_demo"
user = "javierpepe@gmail.com"
pwd = "demo2023"

common = client.ServerProxy('{}/xmlrpc/2/common'.format(url))
res = common.version()
uid = common.authenticate(dbname, user, pwd, {})
print(res,uid)
models = client.ServerProxy('{}/xmlrpc/2/object'.format(url))

from requests.structures import CaseInsensitiveDict
url = "http://api.patagoniawms.com/"
url = "http://app-digipwms-apipublic-dev.azurewebsites.net"
headers = CaseInsensitiveDict()
headers["X-API-KEY"] = "d75ab63e-1831-459f-ae1e-c0930c2c31e1"
#headers["X-API-KEY"] = "Prueba"
headers["X-API-KEY"] = "d96a9a6a-8ffc-488e-83b5-a113ed7e5aBB"
false=False
true=True
null=None
def articulos(default_code=None):
    # Listado de articulos
    if default_code:
        resp = requests.get('%s/v1/Articulos/%s' % (url,default_code), headers=headers)
        lista = [eval(resp.content)]
    else:
        resp = requests.get('%s/v1/Articulos' % url, headers=headers)
        lista = eval(resp.content)
    return lista
def nuevo_articulo(product):
    new = {}
    new["CodigoArticulo"]= product.default_code
    new["Descripcion"]= product.name
    new["DiasVidaUtil"]= 9999
    new["UsaLote"]= True
    new["UsaSerie"]= False
    new["UsaVencimiento"]= False
    new["EsVirtual"]= False
    new["ArticuloTipoRotacion"]= "alta"
    new["Activo"]= True
    new["UsaPesoDeclarado"]= False
    new["PesoDeclaradoPromedio"]= 0
    resp = requests.post('%s/v1/Articulos' % url, headers=headers, json=new)
    return resp

def nuevo_cliente(partner):
    new = {}
    new['Codigo'] = partner.ref
    new['Descripcion'] = partner.name
    new['IdentificadorFiscal'] = partner.vat
    new['Ativo'] = True
    resp = requests.post('%s/v1/Clientes/%s' % (url,new['Codigo']), headers=headers, json=new)
    return resp

def enviar_stock_picking(so):
    # Busco los envios pendiente que tiene el documento de origen de la SO
    # Genero un solo documento do SO

    sp = models.execute_kw(dbname,uid,pwd,'stock.picking','read',[so])[0]
    partner = models.execute_kw(dbname,uid,pwd,'res.partner','read',[sp['partner_id'][0]])[0]
    # Envio cabecera
    newc={}
    newc["Codigo"]= re.sub('\/','_',sp['name'])
    newc["CodigoClienteUbicacion"]= partner['ref']
    newc["PedidoEstado"]= "pendiente"
    newc["Fecha"]= sp['date']
    newc["FechaEstimadaEntrega"]= sp['scheduled_date']
    newc["Observacion"]= sp['origin']
    newc["Importe"]= "0"
    newc["CodigoDespacho"]= "  "
    newc["CodigoDeEnvio"]= "  "
    #newc["ServicioDeEnvioTipo"]= "  "
    newc["PedidoTag"]= []
    #resp = requests.post('%s/v1/Pedidos' % (url), headers=headers, json=newc)
    print('%s/v1/Pedidos/%s' % (url,newc['Codigo']) )
    print(newc)
   #print(resp.content)
    # Envio detalle
    # Busco los codigos pendientes, y los pongo todos juntos, para enviarlos de una sola vez
    for ml in sp['move_ids']:
        det  = models.execute_kw(dbname,uid,pwd,'stock.move','read',[ml])[0]
        product  = models.execute_kw(dbname,uid,pwd,'product.product','read',[det['product_id'][0]])[0]
        new = {}
        new["CodigoPedido"] = newc['Codigo']
        new["CodigoArticulo"]= product['default_code']
        new["Unidades"] = int(det['product_uom_qty'])
        new["PesoDeclarado"] =  1
        new["MinimoDiasVencimiento"] =  1
        resp = requests.post('%s/v1/Pedidos/%s/Detalle' % (url,newc['Codigo']), headers=headers, json=new)
        print(new)
        print(resp)
        print(resp.content)

def recibir_stock_picking(so):
    sp = models.execute_kw(dbname,uid,pwd,'stock.picking','read',[so])[0]
    partner = models.execute_kw(dbname,uid,pwd,'res.partner','read',[sp['partner_id'][0]])[0]
    # Envio cabecera
    newc={}
    newc["Codigo"]= re.sub('\/','_',sp['name'])
    resp = requests.get('%s/v1/Pedidos/%s/Detalle' % (url,newc['Codigo']), headers=headers)
    print(resp.content)
    r = eval(resp.content)
    for i in r:
        print(i)

def enviar_recepcion(po):
    resp = requests.post('%s/v1/DocumentoRecepcion' % (url), headers=headers, json=new)
    return True

def recibir_recepcion(po):
    resp = requests.post('%s/v1/DocumentoRecepcion/%s' % (url,po.name), headers=headers, json=new)
    return True

def pedido_completo(so,cant):
    sp = models.execute_kw(dbname,uid,pwd,'stock.picking','read',[so])[0]
    partner = models.execute_kw(dbname,uid,pwd,'res.partner','read',[sp['partner_id'][0]])[0]
    # Envio cabecera
    newc={}
    newc["Codigo"]= re.sub('\/','_',sp['name'])
    newc["CodigoClienteUbicacion"]= partner['ref']
    newc["PedidoEstado"]= "preparacion"
    newc["Fecha"]= sp['date']
    newc["FechaEstimadaEntrega"]= sp['scheduled_date']
    newc["Observacion"]= sp['origin']
    newc["Importe"]= "0"
    newc["CodigoDespacho"]= "  "
    newc["CodigoDeEnvio"]= "  "
    #newc["ServicioDeEnvioTipo"]= "  "
    newc["PedidoTag"]= []
    resp = requests.put('%s/v1/Pedidos/%s' % (url,newc['Codigo']), headers=headers, json=newc)
    print('%s/v1/Pedidos/%s' % (url,newc['Codigo']) )
    print(newc)
    print(resp.content)
    # Envio detalle
    # Busco los codigos pendientes, y los pongo todos juntos, para enviarlos de una sola vez
    for ml in sp['move_ids']:
        det  = models.execute_kw(dbname,uid,pwd,'stock.move','read',[ml])[0]
        product  = models.execute_kw(dbname,uid,pwd,'product.product','read',[det['product_id'][0]])[0]
        new = {}
        new["CodigoPedido"] = newc['Codigo']
        new["CodigoArticulo"]= product['default_code']
        new["Unidades"] = int(det['product_uom_qty'])
        new["UnidadesSatisfecha"] = int(det['product_uom_qty'] * cant)
        new["PesoDeclarado"] =  1
        new["MinimoDiasVencimiento"] =  1
        print(new)
        resp = requests.put('%s/v1/Pedidos/%s/Detalle/%s' % (url,newc['Codigo'],new['CodigoArticulo']), headers=headers, json=new)
        print(resp)
        print(resp.content)
    newc["PedidoEstado"]= "completo"
    resp = requests.put('%s/v1/Pedidos/%s' % (url,newc['Codigo']), headers=headers, json=newc)
    print('%s/v1/Pedidos/%s' % (url,newc['Codigo']) )
    print(newc)
    print(resp.content)

def remitido(so):
    sp = models.execute_kw(dbname,uid,pwd,'stock.picking','read',[so])[0]
    partner = models.execute_kw(dbname,uid,pwd,'res.partner','read',[sp['partner_id'][0]])[0]
    # Envio cabecera
    newc={}
    newc["Codigo"]= re.sub('\/','_',sp['name'])
    resp = requests.put('%s/v1/Pedidos/%s/Remitido' % (url,newc['Codigo']), headers=headers)
    print('%s/v1/Pedidos/%s/Remitido' % (url,newc['Codigo']) )
    print(resp)

pedido_completo(118,1)
#remitido(117)


sys.exit()
# Alta de codigos
