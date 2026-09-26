using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using System.Text.RegularExpressions;

namespace YghsBridge.AddIn
{
    /// <summary>
    /// Lee la version que DECLARA un .mxd sin abrirlo y sin arcpy.
    ///
    /// Un .mxd es un Compound File Binary (el contenedor OLE de Office) y lleva un
    /// stream `Version`. Leerlo cuesta milisegundos, no necesita licencia y —lo que
    /// importa— funciona sobre documentos que ArcMap se NIEGA a abrir, que es justo
    /// cuando hace falta.
    ///
    /// Para que sirve: `arcpy.mapping.MapDocument()` falla con un mensaje generico
    /// ("no puede abrir documento de mapa", "Nombre de archivo MXD no valido") que
    /// vale igual para una ruta mala, un fichero corrupto o un documento de version
    /// superior. Con la version declarada delante, ese fallo deja de ser mudo.
    ///
    /// OJO con lo que NO garantiza: es lo que el documento dice de si mismo, no
    /// necesariamente la version de la aplicacion que lo grabo. Se vio un lote entero
    /// declarando 10.5 que aun asi colgaba a arcpy al abrirlo (por fuentes de datos
    /// muertas, no por version). Por eso el diagnostico DESCARTA tanto como acusa.
    /// </summary>
    internal static class MxdVersion
    {
        private static readonly byte[] FirmaCfb =
            { 0xD0, 0xCF, 0x11, 0xE0, 0xA1, 0xB1, 0x1A, 0xE1 };
        private const uint Marca = 0xFFFFFFFA; // de aqui arriba son marcas, no sectores

        /// <summary>Version declarada ("10.5") o null si no se pudo leer.</summary>
        public static string Leer(string ruta, out string error)
        {
            error = null;
            byte[] d;
            try
            {
                d = File.ReadAllBytes(ruta);
            }
            catch (Exception ex)
            {
                error = "无法读取文件：" + ex.Message;
                return null;
            }

            if (d.Length < 512 || !EmpiezaPor(d, FirmaCfb))
            {
                error = "不是有效的 .mxd（不是复合文档）";
                return null;
            }

            try
            {
                int ssz = 1 << BitConverter.ToUInt16(d, 30);
                int mssz = 1 << BitConverter.ToUInt16(d, 32);
                uint dir0 = BitConverter.ToUInt32(d, 48);
                uint mfat0 = BitConverter.ToUInt32(d, 60);
                uint difat0 = BitConverter.ToUInt32(d, 68);
                uint nDifat = BitConverter.ToUInt32(d, 72);

                // La DIFAT trae 109 entradas en la cabecera; un documento de mas de
                // ~7 MB (sectores de 512 B) necesita mas y esas cuelgan de una CADENA
                // de sectores. Saltarsela no da error: deja la FAT corta, las cadenas
                // se truncan y los streams salen VACIOS. Paso con 92 de 400 .mxd al
                // validar la version Python de esto.
                var difat = new List<uint>();
                for (int i = 0; i < 109; i++)
                    difat.Add(BitConverter.ToUInt32(d, 76 + i * 4));
                uint sec = difat0;
                int vueltas = 0;
                while (sec < Marca && vueltas <= nDifat + 1)
                {
                    int off = 512 + (int)sec * ssz;
                    int cuantos = ssz / 4;
                    for (int i = 0; i < cuantos - 1; i++)
                        difat.Add(BitConverter.ToUInt32(d, off + i * 4));
                    sec = BitConverter.ToUInt32(d, off + (cuantos - 1) * 4);
                    vueltas++;
                }

                var fat = new List<uint>();
                foreach (uint s in difat)
                {
                    if (s >= Marca) continue;
                    int off = 512 + (int)s * ssz;
                    if (off + ssz > d.Length) continue;
                    for (int i = 0; i < ssz / 4; i++)
                        fat.Add(BitConverter.ToUInt32(d, off + i * 4));
                }

                Func<uint, List<uint>> cadena = inicio =>
                {
                    var salida = new List<uint>();
                    uint s = inicio;
                    int n = 0;
                    while (s < Marca && n < 2000000)
                    {
                        salida.Add(s);
                        s = s < fat.Count ? fat[(int)s] : 0xFFFFFFFE;
                        n++;
                    }
                    return salida;
                };

                Func<uint, int, byte[]> leerSectores = (inicio, size) =>
                {
                    var ms = new MemoryStream();
                    foreach (uint s in cadena(inicio))
                    {
                        int off = 512 + (int)s * ssz;
                        if (off + ssz > d.Length) break;
                        ms.Write(d, off, ssz);
                    }
                    byte[] todo = ms.ToArray();
                    if (todo.Length <= size) return todo;
                    var recorte = new byte[size];
                    Array.Copy(todo, recorte, size);
                    return recorte;
                };

                var entradas = new List<object[]>(); // nombre, tipo, inicio, tamano
                foreach (uint s in cadena(dir0))
                {
                    int off = 512 + (int)s * ssz;
                    if (off + ssz > d.Length) break;
                    for (int i = 0; i < ssz / 128; i++)
                    {
                        int e = off + i * 128;
                        int nlen = BitConverter.ToUInt16(d, e + 64);
                        if (nlen < 2) continue;
                        string nombre = Encoding.Unicode.GetString(d, e, nlen - 2);
                        entradas.Add(new object[]
                        {
                            nombre, d[e + 66],
                            BitConverter.ToUInt32(d, e + 116),
                            (int)BitConverter.ToUInt32(d, e + 120)
                        });
                    }
                }
                if (entradas.Count == 0)
                {
                    error = ".mxd 没有可读取的目录";
                    return null;
                }

                object[] raiz = entradas[0];
                byte[] mini = leerSectores((uint)raiz[2], (int)raiz[3]);
                var mfat = new List<uint>();
                foreach (uint s in cadena(mfat0))
                {
                    int off = 512 + (int)s * ssz;
                    if (off + ssz > d.Length) break;
                    for (int i = 0; i < ssz / 4; i++)
                        mfat.Add(BitConverter.ToUInt32(d, off + i * 4));
                }

                Func<uint, int, byte[]> leerMini = (inicio, size) =>
                {
                    var ms = new MemoryStream();
                    uint s = inicio;
                    int n = 0;
                    while (s < Marca && n < 2000000)
                    {
                        int off = (int)s * mssz;
                        if (off + mssz > mini.Length) break;
                        ms.Write(mini, off, mssz);
                        s = s < mfat.Count ? mfat[(int)s] : 0xFFFFFFFE;
                        n++;
                    }
                    byte[] todo = ms.ToArray();
                    if (todo.Length <= size) return todo;
                    var recorte = new byte[size];
                    Array.Copy(todo, recorte, size);
                    return recorte;
                };

                foreach (object[] ent in entradas)
                {
                    if ((string)ent[0] != "Version" || (byte)ent[1] != 2) continue;
                    int size = (int)ent[3];
                    if (size < 6) continue;
                    byte[] raw = size < 4096
                        ? leerMini((uint)ent[2], size)
                        : leerSectores((uint)ent[2], size);
                    if (raw.Length < 4)
                    {
                        error = "Version 数据流为空";
                        return null;
                    }
                    int nbytes = (int)BitConverter.ToUInt32(raw, 0);
                    if (nbytes <= 0 || nbytes > raw.Length - 4)
                    {
                        error = "Version 流长度不一致";
                        return null;
                    }
                    string txt = Encoding.Unicode.GetString(raw, 4, nbytes).TrimEnd('\0').Trim();
                    if (txt.Length == 0)
                    {
                        error = "版本号为空";
                        return null;
                    }
                    return txt;
                }

                error = ".mxd 没有 Version 流";
                return null;
            }
            catch (Exception ex)
            {
                error = ".mxd 结构不可读：" + ex.Message;
                return null;
            }
        }

        /// <summary>"10.5" -> [10, 5]; null si no tiene forma de version.</summary>
        public static int[] ATupla(string version)
        {
            if (string.IsNullOrEmpty(version)) return null;
            var partes = new List<int>();
            foreach (string trozo in version.Split('.'))
            {
                int v;
                if (!int.TryParse(trozo.Trim(), out v)) break;
                partes.Add(v);
            }
            return partes.Count > 0 ? partes.ToArray() : null;
        }

        /// <summary>Compara versiones numericamente. "10.10" &gt; "10.9", que como texto seria falso.</summary>
        public static int Comparar(int[] a, int[] b)
        {
            int n = Math.Max(a.Length, b.Length);
            for (int i = 0; i < n; i++)
            {
                int va = i < a.Length ? a[i] : 0;
                int vb = i < b.Length ? b[i] : 0;
                if (va != vb) return va.CompareTo(vb);
            }
            return 0;
        }

        /// <summary>
        /// Version de ArcMap de ESTA sesion, sacada de la ruta del ejecutable que
        /// nos esta corriendo (".../ArcGIS/Desktop10.5/bin/ArcMap.exe"). Se prefiere
        /// esto a mirar el disco o el registro porque describe el proceso real, no
        /// "alguna instalacion de la maquina".
        /// </summary>
        public static string VersionArcMapSesion()
        {
            try
            {
                string exe = System.Diagnostics.Process.GetCurrentProcess().MainModule.FileName;
                Match m = Regex.Match(exe, @"Desktop(\d+\.\d+)", RegexOptions.IgnoreCase);
                return m.Success ? m.Groups[1].Value : null;
            }
            catch (Exception)
            {
                return null;
            }
        }

        private static bool EmpiezaPor(byte[] datos, byte[] firma)
        {
            for (int i = 0; i < firma.Length; i++)
                if (datos[i] != firma[i]) return false;
            return true;
        }

        // Rutas .mxd dentro del codigo del usuario: entre comillas simples o dobles.
        private static readonly Regex RutasMxd = new Regex(
            "[\"']([^\"'\\r\\n]+?\\.mxd)[\"']",
            RegexOptions.IgnoreCase | RegexOptions.Compiled);

        /// <summary>
        /// Mensajes de arcpy (es/en) para "no puedo abrir el documento". Son genericos
        /// a proposito por parte de Esri: no distinguen ruta mala de version superior.
        /// </summary>
        private static readonly string[] SintomasApertura =
        {
            "no puede abrir documento de mapa",
            "cannot open map document",
            "nombre de archivo mxd no v",   // "no valido", sin acento por si acaso
            "invalid mxd filename",
            "createobject",
            // El caso que MAS rinde y el menos obvio: el documento no da error, se
            // CUELGA, y lo que llega es el timeout del runner con su fase. Ahi es
            // justo donde hace falta saber que .mxd era y que declara.
            "abriendo el documento",
            "abriendo documento",
        };

        public static bool PareceFalloDeApertura(string mensaje)
        {
            if (string.IsNullOrEmpty(mensaje)) return false;
            string m = mensaje.ToLowerInvariant();
            foreach (string s in SintomasApertura)
                if (m.Contains(s)) return true;
            return false;
        }

        /// <summary>
        /// Dado el codigo del usuario, busca las rutas .mxd que menciona y devuelve un
        /// diagnostico legible, o null si no hay nada que decir.
        /// </summary>
        public static string DiagnosticarCodigo(string codigo, string versionArcMap)
        {
            if (string.IsNullOrEmpty(codigo)) return null;
            int[] app = ATupla(versionArcMap);

            var partes = new List<string>();
            var vistas = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            foreach (Match m in RutasMxd.Matches(codigo))
            {
                string ruta = m.Groups[1].Value.Replace("\\\\", "\\");
                if (!vistas.Add(ruta)) continue;
                if (partes.Count >= 5) break;  // no convertir el error en una parrafada

                if (!File.Exists(ruta))
                {
                    partes.Add("'" + Path.GetFileName(ruta) + "'：该路径下不存在。");
                    continue;
                }
                string err;
                string ver = Leer(ruta, out err);
                if (ver == null)
                {
                    partes.Add("'" + Path.GetFileName(ruta) + "': " + err + ".");
                    continue;
                }
                int[] doc = ATupla(ver);
                if (doc != null && app != null && Comparar(doc, app) > 0)
                {
                    partes.Add("'" + Path.GetFileName(ruta) + "'：声明版本为 " + ver
                        + "，当前会话为 " + versionArcMap
                        + "。ArcMap 无法打开更高版本文档：这就是原因。");
                }
                else
                {
                    partes.Add("'" + Path.GetFileName(ruta) + "'：声明版本为 " + ver
                        + (app != null ? "（会话 " + versionArcMap + "），即版本"
                                         + " 无法解释此故障" : "")
                        + "。如果你看到的是等待而非错误，请怀疑许可"
                        + "争用（另一进程占用了 Desktop 许可）：打开本身"
                        + "不到一秒。如果是立即报错，请检查权限、"
                        + "路径，或文件是否损坏。");
                }
            }

            if (partes.Count == 0) return null;
            return "代码中提及的 .mxd 诊断 → " + string.Join(" | ", partes.ToArray());
        }
    }
}
