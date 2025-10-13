def formato_encabezado(workbook):
    return workbook.add_format({
        'bold': True,
        'border': 1,
        'align': 'center',
        'valign': 'vcenter',
    })

def formato_celda_izquierda(workbook):
    return workbook.add_format({
        'border': 1,
        'align': 'left',
        'valign': 'vcenter',
    })

def formato_celda_derecha(workbook):
    return workbook.add_format({
        'border': 1,
        'align': 'right',
        'valign': 'vcenter',
    })

def formato_celda_decimal(workbook):
    return workbook.add_format({
        'border': 1,
        'align': 'right',
        'valign': 'vcenter',
        'num_format': '#,##0.00',
    })