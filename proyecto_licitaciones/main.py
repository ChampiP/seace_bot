# Orquestador principal
# Flujo: SEACE scraper -> OSCE scraper -> (email pendiente)
# Ejecutar siempre desde aqui: python main.py

import sys
import os
import traceback
from datetime import datetime

# Asegurar que los modulos se encuentren
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from modules.extraer_simple import extraer_buenas_pro
from modules.osce_scraper import enriquecer_adjudicaciones


def main():
    inicio = datetime.now()
    sep = "=" * 62

    print(sep)
    print("  BOT SEACE - INICIO")
    print(f"  {inicio.strftime('%d/%m/%Y %H:%M:%S')}")
    print(sep)

    # ── PASO 1: SEACE scraper ─────────────────────────────────────────
    # Abre el navegador, recorre todas las paginas del SEACE,
    # descarga ZIPs de buena pro, extrae RUC con regex y
    # guarda todo en data/adjudicaciones_procesadas.json
    print("\n[PASO 1] SEACE - extrayendo buenas pro...")
    try:
        resultados = extraer_buenas_pro()
        con_bp = sum(1 for r in resultados if r.get("tiene_buena_pro"))
        print(f"  -> {len(resultados)} registros totales | {con_bp} con buena pro")
    except Exception as e:
        print(f"  ERROR en PASO 1: {e}")
        traceback.print_exc()
        print("  Abortando.")
        return

    # ── PASO 2: OSCE scraper ──────────────────────────────────────────
    # Toma los registros nuevos con buena pro + RUC ganador y
    # consulta la API de OSCE para obtener: razon social, telefono,
    # email, domicilio, estado SUNAT, condicion, tipo contribuyente.
    # solo_nuevos=True -> no vuelve a consultar los que ya tienen datos
    print("\n[PASO 2] OSCE - enriqueciendo proveedores...")
    try:
        enriquecidos = enriquecer_adjudicaciones(solo_nuevos=True)
        print(f"  -> {enriquecidos} registros enriquecidos con datos OSCE")
    except Exception as e:
        print(f"  ERROR en PASO 2: {e}")
        traceback.print_exc()

    # ── PASO 3: Email (pendiente) ─────────────────────────────────────
    # TODO: enviar_reporte()

    duracion = datetime.now() - inicio
    print(f"\n{sep}")
    print(f"  PROCESO COMPLETADO en {str(duracion).split('.')[0]}")
    print(sep)


if __name__ == "__main__":
    main()