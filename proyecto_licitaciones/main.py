"""
Orquestador principal del bot SEACE
Une todos los módulos para extraer, procesar y notificar buenas pro
"""
import asyncio
import json
from datetime import datetime
from modules.seace_scraper import extraer_buenas_pro_de_hoy
from modules.pdf_processor import procesar_todos_los_zips
from modules.email_sender import enviar_reporte


async def main():
    """
    Flujo completo:
    1. Extraer buenas pro del SEACE con validación estricta
    2. Procesar ZIPs y extraer adjudicatarios
    3. Enviar reporte por email
    """
    print("="*70)
    print("🤖 BOT SEACE - EXTRACTOR DE BUENAS PRO")
    print("="*70)
    print(f"Fecha de ejecución: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print("-"*70)
    
    try:
        # 1. Extraer buenas pro con validación estricta
        print("\n[PASO 1] Extrayendo buenas pro del SEACE...")
        buenas_pro = await extraer_buenas_pro_de_hoy()
        print(f"✓ Encontradas: {len(buenas_pro)} buenas pro validadas")
        
        if not buenas_pro:
            print("\n⚠ No hay buenas pro para procesar hoy")
            return
        
        # Guardar resultados crudos
        with open("data/adjudicaciones_procesadas.json", 'w', encoding='utf-8') as f:
            json.dump(buenas_pro, f, indent=2, ensure_ascii=False)
        
        # 2. Procesar ZIPs descargados
        print("\n[PASO 2] Procesando archivos ZIP...")
        # TODO: Implementar procesar_todos_los_zips()
        # adjudicatarios = procesar_todos_los_zips(buenas_pro)
        
        # 3. Enviar reporte
        print("\n[PASO 3] Preparando reporte...")
        # TODO: Implementar enviar_reporte()
        # enviar_reporte(buenas_pro, adjudicatarios)
        
        print("\n" + "="*70)
        print("✓ PROCESO COMPLETADO EXITOSAMENTE")
        print("="*70)
        
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())