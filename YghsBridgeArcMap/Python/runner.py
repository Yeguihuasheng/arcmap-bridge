# -*- coding: utf-8 -*-
"""Runner arcpy OUT-OF-PROCESS del add-in .NET.

Ejecuta en Python 2.7 standalone (C:\\Python27\\ArcGIS10.5\\python.exe) las
operaciones que ArcObjects .NET no cubre: execute_code (arcpy arbitrario), las
3 de Data Driven Pages (solo existen en arcpy) y las 6 ambientales (lógica
arcpy pura, sin añadir-al-mapa: eso lo hace el add-in nativamente sobre la
sesión viva al volver).

Contrato (evita la consola cp1252: NUNCA datos por stdout):
    python runner.py <job.json> <out.json>
    job  = {"op": str, "params": {...}, "mxd": ruta_snapshot_opcional}
    out  = {"ok": true, "result": {...}} | {"ok": false, "error": str, "traceback": str}

El "mxd" es una COPIA (save_mxd_as) de la sesión viva: las operaciones de
documento (execute_code, DDP) leen el estado real de la sesión pero sus
cambios al documento se descartan; las escrituras a DATOS en disco sí son
reales (mismas fuentes que la sesión).
"""
import io
import json
import os
import sys
import time
import traceback
import StringIO

# --------------------------------------------------------------------------- #
# Traza de fase.
#
# El add-in solo puede medir reloj de pared sobre este proceso: desde fuera, un
# runner atascado abriendo un documento y uno reclasificando un ráster de 4 GB
# son el mismo python.exe que no termina. Por eso el runner DICE en qué fase
# está, en un fichero al lado del out. Si salta el timeout, el add-in lee ese
# fichero y el error nombra el punto exacto donde se quedó, en vez de un
# "timeout" mudo. Coste: escribir ~80 bytes cuatro o cinco veces por job.
#
# La ruta se DERIVA del out (out.json -> out.json.fase) para no cambiar el
# contrato de argumentos del runner.
# --------------------------------------------------------------------------- #

_FASE_PATH = sys.argv[2] + ".fase" if len(sys.argv) > 2 else None


def _fase(nombre, detalle=None):
    """Anota la fase actual. NUNCA puede romper el job: si falla, se ignora."""
    if not _FASE_PATH:
        return
    try:
        datos = {"fase": nombre, "ts": time.time()}
        if detalle:
            datos["detalle"] = detalle
        # Mismo cuidado que en _serializar: json.dumps de Py2 con
        # ensure_ascii=False devuelve str si todo es ASCII, y io.open exige unicode.
        texto = json.dumps(datos, ensure_ascii=False)
        if isinstance(texto, str):
            texto = texto.decode("utf-8")
        with io.open(_FASE_PATH, "w", encoding="utf-8") as f:
            f.write(texto)
    except Exception:
        pass


# `import arcpy` NO es gratis: son segundos en frío, y en una máquina con la
# licencia en un servidor lento puede irse mucho más. Se anota ANTES de importar
# para que un cuelgue en el propio import también quede identificado.
_fase(u"importando arcpy")

import arcpy
from arcpy import mapping as MAP

_fase(u"arcpy importado")


def _u(x):
    """Coerción a unicode segura para Python 2.7 (str utf-8 o latin-1)."""
    if x is None:
        return None
    if isinstance(x, unicode):
        return x
    if isinstance(x, str):
        try:
            return x.decode("utf-8")
        except Exception:
            return x.decode("latin-1", "replace")
    return unicode(x)


def _abrir_mxd(job):
    """Abre el snapshot del documento; error accionable si el job no lo trae.

    Es LA fase cara: medido el 2026-07-29, abrir un mxd de 5,9 MB costó 324 s
    frente a 6,4 s del job entero sin documento. Por eso se anota con el tamaño:
    si el timeout salta aquí, el mensaje ya dice por qué.
    """
    ruta = job.get("mxd")
    if not ruta:
        raise ValueError(u"Operación de documento sin snapshot .mxd (bug del add-in).")
    try:
        mb = os.path.getsize(ruta) / (1024.0 * 1024.0)
        detalle = u"%.1f MB" % mb
    except Exception:
        detalle = None
    _fase(u"abriendo documento", detalle)
    doc = MAP.MapDocument(_u(ruta))
    _fase(u"documento abierto", detalle)
    return doc


def _get_ddp(mxd):
    try:
        ddp = mxd.dataDrivenPages
    except Exception:
        ddp = None
    if ddp is None:
        raise ValueError(u"El documento no tiene Data Driven Pages habilitadas "
                         u"(Vista > Data Driven Pages en ArcMap).")
    return ddp


def _contar_paginas_rango(s):
    n = 0
    for parte in s.split(","):
        parte = parte.strip()
        if not parte:
            continue
        if "-" in parte:
            a, b = parte.split("-", 1)
            try:
                n += int(b) - int(a) + 1
            except ValueError:
                n += 1
        else:
            n += 1
    return n


def _checkout(ext):
    """Activa una extensión (Spatial/3D). Error accionable si no hay licencia."""
    try:
        estado = arcpy.CheckExtension(ext)
    except Exception:
        estado = u"(desconocido)"
    if estado != "Available":
        raise ValueError(u"Extensión '%s' no disponible (estado: %s). Revisa la "
                         u"licencia de la extensión." % (_u(ext), _u(estado)))
    arcpy.CheckOutExtension(ext)


# --------------------------------------------------------------------------- #
# Operaciones de documento (necesitan snapshot).
# --------------------------------------------------------------------------- #

def _df_de_mxd(mxd):
    """Data frame del snapshot.

    OJO: `MapDocument.activeDataFrame` SOLO existe sobre la sesion CURRENT de
    ArcMap; sobre un .mxd abierto desde disco (que es siempre el caso aqui, el
    runner corre fuera de proceso) lanza
    "The attribute 'activeDataFrame' is not supported on this instance of
    MapDocument." y mataba execute_code/usar_documento=true ANTES de ejecutar
    el codigo del usuario. Fallback: el primer data frame del documento.
    """
    try:
        return mxd.activeDataFrame
    except Exception:
        pass
    try:
        dfs = arcpy.mapping.ListDataFrames(mxd)
        return dfs[0] if dfs else None
    except Exception:
        return None


def op_execute_code(job):
    """Código arcpy arbitrario. Variables: arcpy, MAP/mapping, mxd (SNAPSHOT de la
    sesión), df. Asignar RESULT. NO incluir '# -*- coding -*-' (llega unicode).

    Sin snapshot en el job, `mxd` y `df` sencillamente no existen: el add-in solo
    copia el documento cuando el código lo necesita, porque copiarlo cuesta
    segundos o minutos en sesiones grandes.
    """
    code = job["params"].get("code", u"")
    mxd = _abrir_mxd(job) if job.get("mxd") else None
    buff = StringIO.StringIO()
    old_stdout = sys.stdout
    sys.stdout = buff
    ns = {"arcpy": arcpy, "MAP": MAP, "mapping": MAP, "RESULT": None}
    if mxd is not None:
        ns["mxd"] = mxd
        ns["df"] = _df_de_mxd(mxd)
    _fase(u"ejecutando codigo")
    try:
        exec(code, ns)
    finally:
        sys.stdout = old_stdout
        del mxd
    return {"result": ns.get("RESULT"), "stdout": buff.getvalue()}


def op_list_ddp(job):
    """Contrato JSON de la tool list_ddp del servidor MCP, sobre el snapshot."""
    params = job["params"]
    mxd = _abrir_mxd(job)
    try:
        try:
            ddp = mxd.dataDrivenPages
        except Exception:
            ddp = None
        if ddp is None:
            return {"habilitado": False}
        campo = ddp.pageNameField.name if ddp.pageNameField else None
        capa_idx = ddp.indexLayer.name if ddp.indexLayer else None
        maximo = int(params.get("max_valores", 500))
        valores = []
        truncado = False
        if campo and ddp.indexLayer is not None:
            try:
                for row in arcpy.da.SearchCursor(ddp.indexLayer, [campo]):
                    if len(valores) >= maximo:
                        truncado = True
                        break
                    valores.append(row[0])
            except Exception:
                valores = []
        return {"habilitado": True,
                "num_paginas": ddp.pageCount,
                "campo_nombre": campo,
                "capa_indice": capa_idx,
                "valores": valores,
                "valores_truncados": truncado}
    finally:
        del mxd


def op_export_ddp(job):
    """Contrato JSON de la tool export_ddp del servidor MCP, sobre el snapshot."""
    params = job["params"]
    mxd = _abrir_mxd(job)
    try:
        ddp = _get_ddp(mxd)
        salida = params["salida"]
        if not salida.lower().endswith(".pdf"):
            salida += ".pdf"
        dpi = int(params.get("dpi", 300))
        modo = (params.get("modo") or "ALL").upper()
        rango = params.get("rango")
        valores = params.get("valores")
        un_por_pagina = bool(params.get("un_pdf_por_pagina", False))

        page_range_string = u""
        if valores:
            ids = []
            for v in valores:
                pid = ddp.getPageIDFromName(_u(v))
                if pid:
                    ids.append(pid)
            if not ids:
                raise ValueError(u"Ningún valor coincide con páginas del atlas: %s"
                                 % u", ".join(_u(v) for v in valores))
            page_range_string = u",".join(str(i) for i in ids)
            range_type = "RANGE"
        elif rango:
            page_range_string = _u(rango)
            range_type = "RANGE"
        elif modo == "CURRENT":
            range_type = "CURRENT"
        else:
            range_type = "ALL"

        multiple = "PDF_MULTIPLE_FILES_PAGE_NAME" if un_por_pagina else "PDF_SINGLE_FILE"
        ddp.exportToPDF(salida, range_type, page_range_string, multiple, dpi)

        if range_type == "ALL":
            num = ddp.pageCount
        elif range_type == "CURRENT":
            num = 1
        else:
            num = _contar_paginas_rango(page_range_string)
        return {"salida": salida, "modo_efectivo": range_type,
                "page_range": page_range_string, "num": num,
                "un_pdf_por_pagina": un_por_pagina, "dpi": dpi}
    finally:
        del mxd


def op_ddp_page_extent(job):
    """goto_ddp_page out-of-process: sitúa el atlas del SNAPSHOT en la página y
    devuelve el extent/escala resultantes para que el add-in los aplique al data
    frame VIVO (aproximación: la sesión viva no cambia de página de atlas)."""
    params = job["params"]
    mxd = _abrir_mxd(job)
    try:
        ddp = _get_ddp(mxd)
        pagina = params.get("pagina")
        valor = params.get("valor")
        if valor is not None:
            pid = ddp.getPageIDFromName(_u(valor))
            if not pid:
                raise ValueError(u"Valor de índice no encontrado en el atlas: %s" % _u(valor))
        elif pagina is not None:
            pid = int(pagina)
        else:
            raise ValueError(u"Indica 'pagina' (ID 1-based) o 'valor' (campo índice).")
        ddp.currentPageID = pid
        try:
            nombre_pagina = ddp.pageRow.getValue(ddp.pageNameField.name)
        except Exception:
            nombre_pagina = None
        df = _df_de_mxd(mxd)
        if df is None:
            raise ValueError(u"El documento no tiene data frames: no hay extent que devolver.")
        ext = df.extent
        return {"page_id": pid, "valor": nombre_pagina, "escala": df.scale,
                "extent": [ext.XMin, ext.YMin, ext.XMax, ext.YMax]}
    finally:
        del mxd


# --------------------------------------------------------------------------- #
# Ambientales (datos en disco; sin snapshot). Solo arcpy: el añadir-al-mapa lo hace el add-in.
# --------------------------------------------------------------------------- #

_INDICE_BANDAS = {
    "NDVI":  ("NIR", "RED"),
    "GNDVI": ("NIR", "GREEN"),
    "NDRE":  ("NIR", "REDEDGE"),
    "NDWI":  ("GREEN", "NIR"),
    "MNDWI": ("GREEN", "SWIR1"),
    "NDMI":  ("NIR", "SWIR1"),
    "NBR":   ("NIR", "SWIR2"),
    "SAVI":  ("NIR", "RED"),
    "EVI":   ("NIR", "RED", "BLUE"),
}


def op_raster_index(job):
    params = job["params"]
    indice = (params.get("indice") or u"").upper()
    bandas = params.get("bandas") or {}
    salida = params.get("salida")
    banda_a = params.get("banda_a")
    banda_b = params.get("banda_b")
    if not salida:
        raise ValueError(u"Indica 'salida' (ruta del ráster de índice).")
    _checkout("Spatial")
    try:
        from arcpy.sa import Raster, Float

        def R(rol):
            ruta = bandas.get(rol)
            if not ruta:
                req = _INDICE_BANDAS.get(indice, ())
                raise ValueError(u"Falta la banda '%s' para %s (requiere: %s). "
                                 u"Pásala en 'bandas', ej. {'NIR': ruta, 'RED': ruta}."
                                 % (_u(rol), _u(indice), u", ".join(req)))
            return Float(Raster(_u(ruta)))

        if indice == "NDVI":
            nir, red = R("NIR"), R("RED"); idx = (nir - red) / (nir + red)
        elif indice == "GNDVI":
            nir, grn = R("NIR"), R("GREEN"); idx = (nir - grn) / (nir + grn)
        elif indice == "NDRE":
            nir, re = R("NIR"), R("REDEDGE"); idx = (nir - re) / (nir + re)
        elif indice == "NDWI":
            grn, nir = R("GREEN"), R("NIR"); idx = (grn - nir) / (grn + nir)
        elif indice == "MNDWI":
            grn, s1 = R("GREEN"), R("SWIR1"); idx = (grn - s1) / (grn + s1)
        elif indice == "NDMI":
            nir, s1 = R("NIR"), R("SWIR1"); idx = (nir - s1) / (nir + s1)
        elif indice == "NBR":
            nir, s2 = R("NIR"), R("SWIR2"); idx = (nir - s2) / (nir + s2)
        elif indice == "SAVI":
            L = float(params.get("L", 0.5))
            nir, red = R("NIR"), R("RED")
            idx = ((nir - red) / (nir + red + L)) * (1 + L)
        elif indice == "EVI":
            nir, red, blue = R("NIR"), R("RED"), R("BLUE")
            idx = 2.5 * ((nir - red) / (nir + 6 * red - 7.5 * blue + 1))
        elif indice in (u"", u"CUSTOM"):
            if not (banda_a and banda_b):
                raise ValueError(u"Índice genérico: indica banda_a y banda_b "
                                 u"(o usa 'indice' con un nombre conocido).")
            a = Float(Raster(_u(banda_a))); b = Float(Raster(_u(banda_b)))
            idx = (a - b) / (a + b)
            indice = u"CUSTOM"
        else:
            raise ValueError(u"Índice no soportado: %s. Disponibles: %s, CUSTOM."
                             % (_u(indice), u", ".join(sorted(_INDICE_BANDAS))))
        idx.save(_u(salida))
    finally:
        arcpy.CheckInExtension("Spatial")
    return {"indice": indice, "salida": salida}


def op_hydrology(job):
    params = job["params"]
    op = (params.get("operacion") or u"").lower()
    p = params.get("parametros") or {}
    _checkout("Spatial")
    try:
        from arcpy.sa import (Raster, Fill, FlowDirection, FlowAccumulation,
                              Watershed, Basin, Con, StreamToFeature, SnapPourPoint)
        res = {"operacion": op}
        if op == "cuenca":
            out_dir = p["salida_dir"]
            if not os.path.isdir(out_dir):
                os.makedirs(out_dir)
            relleno = Fill(Raster(_u(p["mdt"])))
            fdir = FlowDirection(relleno)
            facc = FlowAccumulation(fdir)
            fdir.save(os.path.join(_u(out_dir), "fdir"))
            facc.save(os.path.join(_u(out_dir), "facc"))
            if p.get("pour_points"):
                pp = _u(p["pour_points"])
                if p.get("snap_dist"):
                    pp = SnapPourPoint(pp, facc, float(p["snap_dist"]))
                cuencas = Watershed(fdir, pp)
            else:
                cuencas = Basin(fdir)
            cuencas.save(_u(p["salida"]))
            res["salida"] = p["salida"]
            res["fdir"] = os.path.join(_u(out_dir), "fdir")
            res["facc"] = os.path.join(_u(out_dir), "facc")
        elif op == "red_drenaje":
            if p.get("fdir") and p.get("facc"):
                fdir = Raster(_u(p["fdir"]))
                facc = Raster(_u(p["facc"]))
            else:
                fdir = FlowDirection(Fill(Raster(_u(p["mdt"]))))
                facc = FlowAccumulation(fdir)
            rios = Con(facc > float(p["umbral"]), 1)
            StreamToFeature(rios, fdir, _u(p["salida"]), "NO_SIMPLIFY")
            res["salida"] = p["salida"]
        elif op == "inundacion":
            agua = Con(Raster(_u(p["mdt"])) <= float(p["nivel"]), 1)
            agua.save(_u(p["salida"]))
            res["salida"] = p["salida"]
        else:
            raise ValueError(u"Operación hidrológica no soportada: %s "
                             u"(usa cuenca | red_drenaje | inundacion)." % _u(op))
        res["mensajes"] = arcpy.GetMessages()
    finally:
        arcpy.CheckInExtension("Spatial")
    return res


def op_contours(job):
    params = job["params"]
    mdt = params.get("mdt")
    salida = params.get("salida")
    intervalo = params.get("intervalo")
    base = params.get("base", 0)
    dxf = params.get("dxf")
    if not (mdt and salida and intervalo is not None):
        raise ValueError(u"Indica 'mdt', 'salida' e 'intervalo' (equidistancia).")
    _checkout("3D")
    try:
        arcpy.ddd.Contour(_u(mdt), _u(salida), float(intervalo), float(base))
        out = {"salida": salida, "intervalo": intervalo, "base": base}
        if dxf:
            arcpy.conversion.ExportCAD([_u(salida)], "DXF_R2010", _u(dxf))
            out["dxf"] = dxf
    finally:
        arcpy.CheckInExtension("3D")
    return out


def op_topographic_profile(job):
    params = job["params"]
    superficie = params.get("superficie")
    lineas = params.get("lineas")
    salida = params.get("salida")
    if not (superficie and lineas and salida):
        raise ValueError(u"Indica 'superficie' (ráster/TIN), 'lineas' (2D) y 'salida'.")
    _checkout("3D")
    try:
        arcpy.ddd.InterpolateShape(_u(superficie), _u(lineas), _u(salida))
    finally:
        arcpy.CheckInExtension("3D")
    return {"salida": salida, "superficie": superficie, "lineas": lineas}


def op_least_cost_path(job):
    params = job["params"]
    coste = params.get("coste")
    origen = params.get("origen")
    destino = params.get("destino")
    salida = params.get("salida")
    salida_dir = params.get("salida_dir")
    if not (coste and origen and destino and salida):
        raise ValueError(u"Indica 'coste' (ráster de fricción), 'origen', 'destino' y 'salida'.")
    _checkout("Spatial")
    try:
        from arcpy.sa import CostDistance, CostPath, Raster
        out_dir = salida_dir or os.path.dirname(_u(salida)) or arcpy.env.scratchFolder
        backlink = os.path.join(_u(out_dir), "lcp_backlink")
        cdist = CostDistance(_u(origen), _u(coste), out_backlink_raster=backlink)
        lcp = CostPath(_u(destino), cdist, Raster(backlink), "EACH_CELL")
        lcp.save(_u(salida))
        return {"salida": salida, "backlink": backlink}
    finally:
        arcpy.CheckInExtension("Spatial")


# calculate_geometry NO vive aquí: la sesión viva mantiene un schema lock sobre
# las fuentes cargadas en la TOC y AddGeometryAttributes añade campos → imposible
# out-of-process. Va nativo por IGeoProcessor2 dentro del add-in.

OPS = {
    "execute_code": op_execute_code,
    "list_ddp": op_list_ddp,
    "export_ddp": op_export_ddp,
    "ddp_page_extent": op_ddp_page_extent,
    "raster_index": op_raster_index,
    "hydrology": op_hydrology,
    "contours": op_contours,
    "topographic_profile": op_topographic_profile,
    "least_cost_path": op_least_cost_path,
}


def _json_default(o):
    """RESULT puede traer objetos arcpy no serializables: degradar a texto."""
    try:
        return unicode(o)
    except Exception:
        return repr(o)


def _serializar(respuesta):
    """JSON como UNICODE, siempre.

    Con ensure_ascii=False, json.dumps de Py2 devuelve `str` (bytes) cuando el
    payload es ASCII puro y `unicode` en cuanto aparece un no-ASCII. Escribir ese
    `str` en un fichero abierto con io.open(encoding=...) lanza
    "write() argument 1 must be unicode" → el fichero de salida quedaba VACÍO y el
    add-in fallaba con "Error reading JObject ... line 0, position 0". La coerción
    explícita es obligatoria: no la quites.
    """
    texto = json.dumps(respuesta, ensure_ascii=False, default=_json_default)
    if isinstance(texto, str):
        texto = texto.decode("utf-8")
    return texto


def _escribir_salida(out_path, respuesta):
    """Escritura ATÓMICA: serializa entero, escribe a .tmp y renombra.

    El add-in solo ve el fichero cuando está completo, así que un fallo a mitad
    nunca puede presentarse como 'salida vacía'.
    """
    texto = _serializar(respuesta)
    tmp = out_path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        f.write(texto)
    if os.path.exists(out_path):
        os.remove(out_path)
    os.rename(tmp, out_path)


def main():
    if len(sys.argv) != 3:
        sys.stderr.write("uso: runner.py <job.json> <out.json>\n")
        return 2
    job_path, out_path = sys.argv[1], sys.argv[2]
    try:
        _fase(u"leyendo job")
        with io.open(job_path, "r", encoding="utf-8") as f:
            job = json.loads(f.read())
        op = OPS.get(job.get("op"))
        if op is None:
            raise ValueError(u"Operación desconocida: %s" % _u(job.get("op")))
        _fase(u"ejecutando op", _u(job.get("op")))
        respuesta = {"ok": True, "result": op(job)}
    except Exception as ex:
        respuesta = {"ok": False,
                     "error": _u(ex.message if getattr(ex, "message", None) else ex),
                     "traceback": _u(traceback.format_exc())}
    try:
        _fase(u"serializando salida")
        _escribir_salida(out_path, respuesta)
        _fase(u"terminado")
    except Exception:
        # Último recurso: el resultado no era serializable o el disco falló. Se
        # responde un sobre de error válido (ASCII puro) en vez de dejar el
        # fichero vacío, que es lo que el add-in no sabe interpretar.
        fallback = {"ok": False,
                    "error": u"El runner no pudo serializar la respuesta de la operación.",
                    "traceback": _u(traceback.format_exc())}
        try:
            _escribir_salida(out_path, fallback)
        except Exception:
            with io.open(out_path, "w", encoding="utf-8") as f:
                f.write(u'{"ok": false, "error": "El runner no pudo escribir su salida."}')
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
