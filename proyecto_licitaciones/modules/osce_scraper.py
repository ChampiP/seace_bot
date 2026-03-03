# OSCE Scraper - consulta APIs de OSCE/OECE para enriquecer ganadores de buena pro
# API 1: eap.oece.gob.pe/perfilprov-bus/1.0/ficha/{ruc}  -> RNP: razon social, tel, email
# API 2: eap.oece.gob.pe/ficha-proveedor-cns/1.0/ficha/{ruc} -> SUNAT: estado, domicilio

import json
import time
import warnings
from pathlib import Path
from typing import Optional

import requests

warnings.filterwarnings("ignore")  # ignorar advertencias de SSL

# ───────────────────────────────────────────────────────── Configuración ──────

BASE_PERFIL = "https://eap.oece.gob.pe/perfilprov-bus/1.0"
BASE_FUP    = "https://eap.oece.gob.pe/ficha-proveedor-cns/1.0"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://apps.osce.gob.pe/perfilprov-ui/",
}

DATA_PATH = Path(__file__).parent.parent / "data" / "adjudicaciones_procesadas.json"


# ─────────────────────────────────────────────────── Funciones de consulta ──

def _get(url: str, timeout: int = 15) -> Optional[dict]:
    # GET a la API de OSCE, retorna JSON o None si falla
    try:
        r = requests.get(url, headers=HEADERS, verify=False, timeout=timeout)
        if r.status_code == 200:
            return r.json()
        print(f"  [WARN] {r.status_code} → {url}")
        return None
    except Exception as e:
        print(f"  [ERROR] {e} → {url}")
        return None


def consultar_proveedor_osce(ruc: str) -> dict:
    # Consulta ambas APIs de OSCE para un RUC y retorna dict con datos enriquecidos
    resultado = {
        "razon_social_ganador": "",
        "telefono": "",
        "email": "",
        "domicilio": "",
        "estado": "",
        "condicion": "",
        "tipo_contribuyente": "",
        "habilitado_rnp": "",
        "cmc": "",
        "especialidades": "",
    }

    # ── API 1: perfilprov-bus (RNP/OSCE) ────────────────────────────────────
    data_perfil = _get(f"{BASE_PERFIL}/ficha/{ruc}")
    if data_perfil:
        prov = data_perfil.get("proveedorT01") or {}
        resultado["razon_social_ganador"] = prov.get("nomRzsProv", "")
        resultado["telefono"] = ", ".join(prov.get("telefonos") or [])
        resultado["email"]    = ", ".join(prov.get("emails") or [])
        resultado["habilitado_rnp"] = str(prov.get("esHabilitado", ""))
        resultado["cmc"] = prov.get("cmcTexto", "")
        especialidades = prov.get("espProvT01s") or []
        resultado["especialidades"] = "; ".join(
            f"{e.get('desCat','')} - {e.get('desEsp','')}" for e in especialidades
        )

    # ── API 2: ficha-proveedor-cns (SUNAT) ──────────────────────────────────
    data_fup = _get(f"{BASE_FUP}/ficha/{ruc}")
    if data_fup:
        sunat = data_fup.get("datosSunat") or {}
        resultado["estado"]            = sunat.get("estado", "")
        resultado["condicion"]         = sunat.get("condicion", "")
        resultado["tipo_contribuyente"] = sunat.get("tipoEmpresa", "")
        # Construir domicilio con departamento / provincia / distrito
        partes_dom = [
            sunat.get("departamento", ""),
            sunat.get("provincia", ""),
            sunat.get("distrito", ""),
        ]
        resultado["domicilio"] = " - ".join(p for p in partes_dom if p)

        # Si no se obtuvo razón social de la primera API, usar la de SUNAT
        if not resultado["razon_social_ganador"]:
            resultado["razon_social_ganador"] = sunat.get("razon", "")

    return resultado


# ──────────────────────────────────────────────────── Función principal ──────

def enriquecer_adjudicaciones(
    json_path: Path = DATA_PATH,
    solo_nuevos: bool = True,
    delay: float = 0.5,
) -> int:
    # Carga el JSON, filtra buenas pro con RUC, consulta OSCE y guarda los cambios
    print(f"\n{'='*65}")
    print("  OSCE SCRAPER - Enriquecimiento de proveedores")
    print(f"{'='*65}")

    with open(json_path, encoding="utf-8") as f:
        adjudicaciones = json.load(f)

    # Filtrar: tiene buena pro + tiene RUC ganador
    candidatos = [
        a for a in adjudicaciones
        if a.get("tiene_buena_pro") is True
        and a.get("ruc_ganador", "").strip()
    ]

    if solo_nuevos:
        candidatos = [c for c in candidatos if not c.get("razon_social_ganador", "").strip()]

    # Agrupar por RUC único para no consultar el mismo RUC múltiples veces
    ruc_a_registros: dict[str, list] = {}
    for adj in candidatos:
        ruc = adj["ruc_ganador"].strip()
        ruc_a_registros.setdefault(ruc, []).append(adj)

    total_rucs = len(ruc_a_registros)
    print(f"  Registros con buena pro:  {len(candidatos)}")
    print(f"  RUCs únicos a consultar:  {total_rucs}")
    print()

    enriquecidos = 0
    for i, (ruc, registros) in enumerate(ruc_a_registros.items(), 1):
        print(f"[{i:3}/{total_rucs}] RUC {ruc} → consultando OSCE...", end=" ")
        datos_osce = consultar_proveedor_osce(ruc)

        # Aplicar datos a todos los registros que comparten ese RUC
        for reg in registros:
            reg.update(datos_osce)

        razon = datos_osce.get("razon_social_ganador") or "?"
        tel   = datos_osce.get("telefono") or "-"
        email = datos_osce.get("email") or "-"
        print(f"{razon}  |  tel: {tel}  |  email: {email}")
        enriquecidos += len(registros)

        if delay > 0 and i < total_rucs:
            time.sleep(delay)

    # Guardar JSON actualizado
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(adjudicaciones, f, indent=2, ensure_ascii=False)

    print(f"\n  {'='*63}")
    print(f"  Registros enriquecidos: {enriquecidos}")
    print(f"  Guardado en: {json_path}")
    print(f"  {'='*63}\n")

    return enriquecidos


# ─────────────────────────────────────────────────────────────────── Main ──

if __name__ == "__main__":
    enriquecidos = enriquecer_adjudicaciones(solo_nuevos=False)
    print(f"Total registros actualizados: {enriquecidos}")
