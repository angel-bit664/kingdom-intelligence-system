import pandas as pd
import os
import zipfile
from io import BytesIO

async def procesar_kvk_por_dia(rutas_archivos):
    """
    Recibe: lista de rutas ['temp_archivo1.xlsx', 'temp_archivo2.xlsx']
    Regresa: string con el resultado o None si falla
    """
    try:
        dataframes = []
        
        for ruta in rutas_archivos:
            if ruta.endswith('.zip'):
                with zipfile.ZipFile(ruta, 'r') as zip_ref:
                    for nombre in zip_ref.namelist():
                        if nombre.endswith('.xlsx'):
                            with zip_ref.open(nombre) as f:
                                df = pd.read_excel(BytesIO(f.read()))
                                dataframes.append(df)
            elif ruta.endswith('.xlsx'):
                df = pd.read_excel(ruta)
                dataframes.append(df)
        
        if len(dataframes) < 2:
            return "Error: Necesito mínimo 2 archivos Excel para comparar"
        
        # TODO: Aquí va tu lógica real de KVK
        # Por ahora solo confirmo que leí los archivos
        total_filas = sum(len(df) for df in dataframes)
        return f"KVK procesado. Leí {len(dataframes)} archivos con {total_filas} filas totales."
        
    except Exception as e:
        return f"Error procesando KVK: {str(e)[:500]}"
