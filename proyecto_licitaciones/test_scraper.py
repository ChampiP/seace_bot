"""
Script de prueba para la función extraer_licitaciones_hoy()
"""
import asyncio
import json
from modules.seace_scraper import extraer_licitaciones_hoy


async def main():
    print("="*60)
    print("EXTRACTOR DE LICITACIONES SEACE")
    print("="*60)
    print(f"\nBuscando licitaciones de OBRA:")
    print(f"  • Estado: Adjudicado")
    print(f"  • Aperturadas: desde 01/01/2026")
    print(f"  • Hasta: hoy (27/02/2026)")
    print("-"*60)
    print()
    
    try:
        # Ejecutar la extracción
        resultados = await extraer_licitaciones_hoy()
        
        # Mostrar resumen
        print("\n" + "="*60)
        print(f"RESUMEN DE EXTRACCIÓN")
        print("="*60)
        print(f"Total de licitaciones encontradas: {len(resultados)}")
        print(f"Licitaciones con ZIP descargado: {sum(1 for r in resultados if r['zip_path'])}")
        
        # Mostrar resumen de cada licitación
        if resultados:
            print("\n" + "-"*60)
            print("DETALLE DE LICITACIONES:")
            print("-"*60)
            for i, licitacion in enumerate(resultados, 1):
                print(f"\n{i}. {licitacion['Nomenclatura']}")
                print(f"   Entidad: {licitacion['Nombre o Sigla de la Entidad']}")
                print(f"   Descripción: {licitacion['Descripción de Objeto'][:80]}...")
                print(f"   Monto: {licitacion['VR / VE / Cuantía de la contratación']} {licitacion['Moneda']}")
                if licitacion['zip_path']:
                    print(f"   ZIP: ✓ Descargado")
                else:
                    print(f"   ZIP: ✗ No disponible")
        
        # Guardar resultados en JSON
        output_file = "data/resultados_licitaciones.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(resultados, f, indent=2, ensure_ascii=False)
        print(f"\n✓ Resultados guardados en: {output_file}")
        
    except Exception as e:
        print(f"\n✗ Error durante la extracción: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
