document.getElementById('cajas').focus();
    document.getElementById('cajas').value =  cantidad_pedida_bultos;
    document.getElementById('unidades').value =  cantidad_pedida;
    console.log(cantidad_pedida)
document.getElementById('cajas').addEventListener("change", (function (e) {
        var cajas = document.getElementById('cajas').value;
        var unidades = cajas * uom_po;
        u_field = document.getElementById('unidades')
        u_field.value = unidades
})) ;
document.getElementById('cajas').addEventListener("keyup", (function (e) {
    if (e.key == "Enter") {
        console.log('Ingreso cantidad');
        console.log(codigo);
        console.log(pedido_id);
        var cajas = document.getElementById('cajas').value;
        var unidades = cajas * uom_po;
        u_field = document.getElementById('unidades')
        u_field.value = unidades
        console.log(cajas);
        console.log(unidades);
        window.location.replace("procesar_carga/?pedido_id="+pedido_id+"&codigo="+codigo+"&cajas="+cajas+"&unidades="+unidades);
    }
})) ;
document.getElementById('unidades').addEventListener("change", (function (e) {
        console.log('Ingreso cantidad');
        console.log(codigo);
        console.log(pedido_id);
        var unidades = document.getElementById('unidades').value;
        var cajas = unidades  / uom_po;
        u_field = document.getElementById('cajas');
        u_field.value = cajas;
        console.log(cajas);
        console.log(unidades);
        window.location.replace("procesar_carga/?pedido_id="+pedido_id+"&codigo="+codigo+"&cajas="+cajas+"&unidades="+unidades);
})) ;
function cargar() {
        var unidades = document.getElementById('unidades').value;
        var cajas = document.getElementById('cajas').value;
        if  (!unidades) {
            unidades = 0;
        }
        if  (!cajas) {
            cajas = 0;
        }
        window.location.replace("procesar_carga/?pedido_id="+pedido_id+"&codigo="+codigo+"&cajas="+cajas+"&unidades="+unidades);
}
function volver() {
        window.location.replace("cargar/?pedido_id="+pedido_id);
}