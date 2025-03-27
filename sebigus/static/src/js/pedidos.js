async function fetchHtmlAsText(url) {
    return ( fetch(url));
}
var next_in=0;
var pagina_actual = 0;
$(document).ready( function () {
    var categoria = location.search.split('categoria=')[1]
    table = $('#productos').DataTable({
        responsive: true,
        processing: true,
        ordering: false,
        scroller: true,
        scrollY: '70vh',
        searching: true,
        serverSide: true,
        language: {
            'loadingRecords': 'Cargando articulos, aguarde unos instantes...',
            'processing': 'Cargando articulos, aguarde unos instantes...',
            'search': 'Buscar',
            'info': 'mostrando _START_ a _END_ de _TOTAL_',
            'infoEmpty': '0',
        },
        columns: [{data: 'DT_RowId', visible: 0},
                  {data: 'Imagen', className: "dt-center"},
                  {data: 'Codigo'},
                  {data: 'Descripcion'},
                  {data: 'Dimensiones',className: "dt-right"},
                  {data: 'Bulto', className: "dt-right"},
                  {data: 'Precio', render: $.fn.dataTable.render.number(',', '.', 2, '$ '), className: "dt-right dt-nowrap"},
                  {data: 'Pedido', className: "dt-right"},
                  {data: 'Unidades_Pedidas', className: "dt-right"},
                  {data: 'Stock', title:' '},
                ],
        ajax: "/sebigus/pedidos/productos?categoria=" + categoria,
        drawCallback: function(settings) {
            var search = table.search()
            if (!search.includes('SUGERIDOS')) {
                if (pagina_actual > 0) {
                    table.scroller.toPosition(pagina_actual);
                }
                var pagina_actual = 0;
                $('#' + next_in).focus();
            }
        },
        createdRow: function(row, data, dataIndex) {
        if(data['DT_RowId'] === 'categoria'){
            // Add COLSPAN attribute
            $('td:eq(0)', row).attr('colspan', 9);
            // Hide required number of columns
            // next to the cell with COLSPAN attribute
            $('td:eq(1)', row).css('display', 'none');
            $('td:eq(2)', row).css('display', 'none');
            $('td:eq(3)', row).css('display', 'none');
            $('td:eq(4)', row).css('display', 'none');
            $('td:eq(5)', row).css('display', 'none');
            $('td:eq(6)', row).css('display', 'none');
            $('td:eq(7)', row).css('display', 'none');
            $('td:eq(8)', row).css('display', 'none');
        }
        if (data['Unidades_Pedidas']) {
            reg=/>\d+</;
            found =data['Unidades_Pedidas'].match(reg); 
            if (found) {            
                $(row).addClass('bg-primary bg-opacity-25 ');
            }
        }
    }
    }
    );
    table.on('click','tbody tr', function() {
        data = table.row(this).data();
        console.log('+',data.Codigo,'+');
        contentDiv = document.getElementById('detalle_producto');

        if (data.Codigo > 0) {
            fetch("pedidos/detalle?codigo=" + data.Codigo )
            .then(response => response.text())
            .then(data => { contentDiv.innerHTML = data; htmx.process(contentDiv); } );
        }
    });
} );
function update_codigo(evt) {
    var inputs = $(':input').keypress(function(e){ 
        if (e.which == 13) {
            e.preventDefault();
            nextInput = inputs.get(inputs.index(this) + 1);
            var unidades = document.getElementById(evt).value;
            var stock = document.getElementById('stock_'+ evt).innerText;
            if (nextInput) {
                if (unidades > 0) {
                  if (stock >= 0) {
                      nextInput.focus();
                  } else {
                    pagina_actual = table.ajax.params()['start'] + table.ajax.params()['length'];
                    table.search('SUGERIDOS_'  + evt).draw();
                  }
                } else {
                    nextInput.focus();
                }
            }
        }
    });
    console.log("actualizo imagen", evt);
    var unidades = document.getElementById(evt).value;
    var stock = document.getElementById('stock_'+ evt).innerText;
    contentDiv = document.getElementById('detalle_producto');
        fetch("pedidos/detalle?codigo=" + evt )
        .then(response => response.text())
        .then(data => { contentDiv.innerHTML = data; htmx.process(contentDiv); } );
    if  (stock <=0) {
         console.log('no hay stock');
         console.log(pagina_actual);
    }

}
function continuar(evt) {
    console.log('Continuar' + evt);
    next_in = evt;
    table.search('').draw(evt);
    
}

function cantidad_pedida(evt) {
    var categoria = location.search.split('categoria=')[1]
    e = document.getElementById(evt);
    e.value = parseFloat(e.step) / 2 + parseFloat(e.value);
    e.stepUp();
    e.stepDown();
    var unidades = document.getElementById(evt).value;
    var uxb = document.getElementById('uxb_'+ evt).innerText;
    var stock = document.getElementById('stock_'+ evt).innerText;
    contentDiv = document.getElementById('tot_' + evt);
    console.log("new value", unidades);
    var cantidad = unidades * uxb;
    fetch("pedidos/cargar_unidades?codigo=" + evt + "&cantidad=" + cantidad + "&catalogo=" + categoria + "&stock=" + stock  )
        .then(response => response.text())
        .then(data => { contentDiv.innerHTML = data; htmx.process(contentDiv); } );

    if (parseFloat(unidades) > 0) {
        $("#row_" +evt).addClass('bg-primary bg-opacity-25 ');
        contentDiv.innerText = unidades * uxb;
        if (stock <= 0) {
                console.log('No hay stock');
                pagina_actual = table.ajax.params()['start'] + table.ajax.params()['length'];
                table.search('SUGERIDOS_'  + evt).draw();
            }
    } else {
        $("#row_" +evt).removeClass('bg-primary bg-opacity-25 ');
        contentDiv.innerText = ' ' ;
    }
};
      
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
function seguir() {
    $('#modalConfirm').modal('hide');
}
function enviar() {
    $('#modalConfirm').modal('show');
}
function confirm() {
    var categoria = location.search.split('categoria=')[1]
    console.log(categoria);
    window.location.replace("pedidos-enviar/?catalogo="+categoria);
    }
function volver() {
        window.location.replace("cargar/?pedido_id="+pedido_id);
}


