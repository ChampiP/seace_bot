"""
Script de prueba para la función extraer_buenas_pro_de_hoy()
Con validación estricta de fecha del Cronograma
"""
import asyncio
import json
from datetime import datetime
from modules.seace_scraper import extraer_buenas_pro_de_hoy


async def main():
    print("="*70)
    print("EXTRACTOR DE BUENAS PRO DEL SEACE - VALIDACIÓN ESTRICTA")
    print("="*70)
    print(f"\nParámetros de búsqueda:")
    print(f"  • Tipo: OBRA")
    print(f"  • Estado: Adjudicado")
    print(f"  • Ventana móvil: Últimos 30 días hasta hoy")
    print(f"  • Fecha actual: {datetime.now().strftime('%d/%m/%Y')}")
    print(f"\n  ⚠ VALIDACIÓN ESTRICTA:")
    print(f"    - Solo procesos donde la fecha de 'Otorgamiento de la Buena Pro'")
    print(f"      ya haya pasado (fecha <= hoy)")
    print(f"    - Navega a página 2 de documentos si es necesario")
    print(f"    - Descarga solo archivos .zip")
    print("-"*70)
    print()
    
    try:
        # Ejecutar la extracción con validación estricta
        resultados = await extraer_buenas_pro_de_hoy()
        
        # Mostrar resumen
        print("\n" + "="*70)
        print(f"RESUMEN DE EXTRACCIÓN")
        print("="*70)
        print(f"Total de buenas pro validadas: {len(resultados)}")
        print(f"Con descarga exitosa: {sum(1 for r in resultados if r['zip_path'])}")
        
        # Mostrar detalle de cada buena pro validada
        if resultados:
            print("\n" + "-"*70)
            print("DETALLE DE BUENAS PRO VALIDADAS:")
            print("-"*70)
            for i, proceso in enumerate(resultados, 1):
                print(f"\n{i}. {proceso['Nomenclatura']}")
                print(f"   Entidad: {proceso['Nombre o Sigla de la Entidad']}")
                print(f"   Objeto: {proceso['Descripción de Objeto'][:70]}...")
                print(f"   Monto: {proceso['VR / VE / Cuantía de la contratación']} {proceso['Moneda']}")
                print(f"   Estado: {proceso['estado_validado']}")
                print(f"   Fecha Buena Pro: {proceso['fecha_buena_pro']}")
                if proceso['zip_path']:
                    print(f"   ZIP: ✓ {proceso['zip_path'].split('\\\\')[-1]}")
                else:
                    print(f"   ZIP: ✗ No se pudo descargar")
        else:
            print("\n⚠ No se encontraron buenas pro con fecha de hoy o ayer")
        
        # Guardar resultados en JSON
        output_file = "data/adjudicaciones_procesadas.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(resultados, f, indent=2, ensure_ascii=False)
        print(f"\n✓ Resultados guardados en: {output_file}")
        
    except Exception as e:
        print(f"\n✗ Error durante la extracción: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
