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
    
def float_to_hhmmss(hours):
    """Convierte horas float (ej 1.5) a string HH:MM:SS (01:30:00)."""
    total_seconds = int(round((hours or 0.0) * 3600))
    h = total_seconds // 3600
    m = (total_seconds % 3600) // 60
    s = total_seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"