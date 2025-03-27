document.getElementById('codigo').focus();
document.getElementById('codigo').addEventListener("keyup", (function (e) {
    if (e.key == "Enter") {
        console.log('Ingreso Codigo');
        var codigo = document.getElementById('codigo').value;
        window.location.replace("cantidad/?pedido_id=" + pedido_id + "&codigo=" + codigo);
    }
}));
function volver() {
    window.location.replace("pedido/?pedido_id=" + pedido_id);
}
function cargar() {
    console.log('Ingreso Codigo');
    var codigo = document.getElementById('codigo').value;
    window.location.replace("cantidad/?pedido_id=" + pedido_id + "&codigo=" + codigo);
}