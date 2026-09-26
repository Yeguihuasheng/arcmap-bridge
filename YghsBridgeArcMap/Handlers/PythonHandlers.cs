using System;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Text;
using System.Text.RegularExpressions;
using ESRI.ArcGIS.ArcMapUI;
using ESRI.ArcGIS.Carto;
using ESRI.ArcGIS.Framework;
using ESRI.ArcGIS.Geometry;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using Path = System.IO.Path; // ESRI.ArcGIS.Geometry también define Path

namespace YghsBridge.AddIn.Handlers
{
    /// <summary>
    /// Tools que ArcObjects .NET no cubre, resueltas OUT-OF-PROCESS con el arcpy
    /// standalone de la máquina: execute_arcpy + las 3 DDP (solo existen en
    /// arcpy) + las 6 ambientales (lógica arcpy en Python\runner.py, recurso
    /// embebido).
    ///
    /// Estos handlers corren en el THREAD DE FONDO del listener (no en STA): el
    /// subprocess no congela la GUI de ArcMap — un GP pesado in-process
    /// bloquearía la aplicación y podría matar el puente.
    /// Solo los pasos ArcObjects (snapshot, añadir al mapa, extent) van al STA.
    ///
    /// Semántica de snapshot: execute_arcpy y DDP operan sobre una COPIA
    /// (SaveAsDocument) del documento vivo — leen su estado real, pero los cambios
    /// al DOCUMENTO se descartan; las escrituras a datos en disco sí son reales.
    /// </summary>
    internal static class PythonHandlers
    {
        private static readonly TimeSpan SubprocessTimeout = LeerTimeout("ARCMAP_SUBPROCESS_TIMEOUT", 1800);
        private static readonly TimeSpan StaStepTimeout = TimeSpan.FromSeconds(60);

        // Margen para que los pipes del runner den EOF una vez el proceso ya ha salido.
        // Generoso para el caso normal (milisegundos) y acotado para el patológico: un
        // nieto que heredó la salida y no muere. Ver el uso, más abajo.
        private static readonly TimeSpan FlushSalidaTimeout = TimeSpan.FromSeconds(10);

        // PIDs de los runners arrancados y aún no terminados. Se guardan PIDs y no
        // objetos Process porque el Process se libera al salir de su `using`, y esto
        // tiene que sobrevivir a eso. Sirven para un caso concreto: al cerrarse ArcMap,
        // un runner vivo IMPIDE que el proceso acabe de salir, y ArcMap se queda sin
        // ventana pero vivo, sujetando el puerto (incidente del 2026-08-27).
        private static readonly System.Collections.Generic.HashSet<int> _runnersVivos =
            new System.Collections.Generic.HashSet<int>();

        private static int RegistrarRunner(Process p)
        {
            try
            {
                int pid = p.Id;
                lock (_runnersVivos) _runnersVivos.Add(pid);
                return pid;
            }
            catch { return 0; }   // proceso ya muerto: nada que registrar
        }

        private static void OlvidarRunner(int pid)
        {
            if (pid == 0) return;
            lock (_runnersVivos) _runnersVivos.Remove(pid);
        }

        /// <summary>
        /// Mata los runners que sigan vivos. Se llama al parar el puente: si ArcMap se
        /// está cerrando, un runner vivo lo deja a medio salir — vivo, sin ventana y
        /// sujetando el puerto—, que es el cuadro del ArcMap zombi. Devuelve cuántos
        /// mató. El trabajo que estuviera haciendo se pierde, pero al cerrarse ArcMap ya
        /// no había nadie que fuera a leer su resultado.
        /// </summary>
        public static int MatarRunnersVivos()
        {
            int[] pids;
            lock (_runnersVivos)
            {
                pids = new int[_runnersVivos.Count];
                _runnersVivos.CopyTo(pids);
                _runnersVivos.Clear();
            }
            int muertos = 0;
            foreach (int pid in pids)
            {
                try
                {
                    using (Process p = Process.GetProcessById(pid))
                    {
                        if (p.HasExited) continue;
                        p.Kill();
                        muertos++;
                        Log.Info("arcpy 运行器（PID " + pid + "）已随桥接停止而终止。");
                    }
                }
                catch { /* ya no existe, o no se deja: no hay nada mejor que hacer */ }
            }
            return muertos;
        }

        // execute_arcpy es INTERACTIVO: al otro lado hay alguien esperando la
        // respuesta, no un batch nocturno. Con el techo de 1800 s de los jobs
        // pesados, un execute_arcpy atascado es indistinguible de un cuelgue
        // permanente (el cliente MCP se rinde mucho antes) y no deja ni un error
        // que leer. Ya costó dos sesiones enteras: 2026-07-27 y 2026-07-29.
        // Los jobs legítimamente largos (DDP, hidrología, índices) NO pasan por
        // aquí: conservan SubprocessTimeout.
        // 900 s y no 300: abrir un mxd de 5,9 MB costó 324 s medidos el 2026-07-29, o
        // sea que un tope de 300 mataría un usar_documento=true legítimo. Esto es una
        // RED DE SEGURIDAD contra runners eternos, no un presupuesto de rendimiento:
        // quien informa de si avanza o está pillado es la traza de fase del runner.
        private static readonly TimeSpan ExecuteTimeout = LeerTimeout("ARCMAP_EXEC_TIMEOUT", 900);

        // Cada cuánto se mira la fase del runner mientras corre. 1 s es ruido
        // despreciable frente a jobs de segundos o minutos.
        private static readonly TimeSpan SondeoFase = TimeSpan.FromSeconds(1);

        /// <summary>Timeout en segundos desde variable de entorno, con defecto.
        /// Un valor ilegible o &lt;= 0 no rompe el add-in: se usa el defecto.</summary>
        private static TimeSpan LeerTimeout(string variable, int defectoSegundos)
        {
            int segundos;
            string bruto = Environment.GetEnvironmentVariable(variable);
            if (string.IsNullOrEmpty(bruto) || !int.TryParse(bruto, out segundos) || segundos <= 0)
                segundos = defectoSegundos;
            return TimeSpan.FromSeconds(segundos);
        }

        // Copiar el documento (SaveAsDocument) es lo unico que puede tardar de verdad
        // en el hilo STA: un mxd con decenas de capas y rasters pesados se va a varios
        // minutos, y durante ese rato ArcMap parece colgado y el puente, muerto.
        private static readonly TimeSpan SnapshotTimeout = TimeSpan.FromSeconds(600);

        private const string AvisoSnapshot =
            "execute_arcpy 在 ArcMap 进程之外、基于文档副本运行：读取、"
            + "分析和导出针对真实状态，但对 mxd 的修改"
            + "不会影响活动会话（此类操作请使用原生工具）。";

        private const string AvisoSnapshotDisco =
            " 副本取自磁盘上保存的 .mxd，速度快且不占用 ArcMap："
            + "如果会话中做了修改却未保存，那部分改动不在此副本中。"
            + "要包含这些改动，请保存文档（save_mxd）或用 serializar_sesion=true 重试。";

        private static string PythonExe()
        {
            string exe = Environment.GetEnvironmentVariable("ARCMAP_PYTHON27");
            if (string.IsNullOrEmpty(exe))
                exe = @"C:\Python27\ArcGIS10.5\python.exe";
            if (!File.Exists(exe))
                throw new InvalidOperationException(
                    "未找到 ArcGIS 的 Python 2.7（" + exe + "). "
                    + "请用正确的路径设置 ARCMAP_PYTHON27。");
            return exe;
        }

        private static string WorkDir()
        {
            string dir = Path.Combine(Path.GetTempPath(), "yghs-bridge");
            Directory.CreateDirectory(dir);
            return dir;
        }

        /// <summary>Extrae el runner embebido a %TEMP%\yghsBridge\runner.py (cada
        /// llamada: barato y a prueba de versiones de DLL conviviendo).</summary>
        private static string ExtraerRunner()
        {
            string destino = Path.Combine(WorkDir(), "runner.py");
            Assembly asm = Assembly.GetExecutingAssembly();
            using (Stream s = asm.GetManifestResourceStream("YghsBridge.AddIn.Python.runner.py"))
            {
                if (s == null)
                    throw new InvalidOperationException(
                        "程序集中缺少嵌入资源 Python\\runner.py（构建错误）。");
                using (FileStream f = File.Create(destino))
                    s.CopyTo(f);
            }
            return destino;
        }

        /// <summary>Copia del documento vivo a %TEMP% (SaveAsDocument en STA).
        /// Se cronometra siempre: si un documento tarda, el log lo dice en vez de
        /// dejar la impresion de que el puente se ha caido.</summary>
        private static string Snapshot(bool serializarSesion)
        {
            string ruta = Path.Combine(WorkDir(), "snap_" + Guid.NewGuid().ToString("N") + ".mxd");

            // Vía barata y SEGURA por defecto: copiar el .mxd del disco.
            // SaveAsDocument es la única parte de execute_arcpy que corre DENTRO de
            // ArcMap, y serializar un documento con capas pesadas o fuentes rotas
            // puede tumbar el proceso entero (el subproceso arcpy, en cambio, muere
            // solo). Copiar un fichero no puede hacer eso. El precio: no incluye los
            // cambios que la sesión aún no ha guardado, y eso se avisa al llamante.
            string origen = serializarSesion ? null : SnapshotDesdeDisco();
            if (origen != null)
            {
                var relojDisco = Stopwatch.StartNew();
                File.Copy(origen, ruta, true);
                relojDisco.Stop();
                Log.Info("已从磁盘复制文档，用时 " + relojDisco.Elapsed.TotalSeconds.ToString("0.0")
                         + " 秒（未占用 ArcMap）：" + origen);
                return ruta;
            }

            Log.Info("正在复制文档到 " + ruta + "（期间 ArcMap 会被占用）");
            var reloj = Stopwatch.StartNew();
            JObject r = StaDispatcher.Invoke(delegate
            {
                IApplication app = ArcSession.App();
                app.SaveAsDocument(ruta, true); // true = copia: el doc activo no cambia
                return Protocol.Result(new JObject());
            }, SnapshotTimeout);
            reloj.Stop();

            if (!(bool)r["ok"])
            {
                Log.Error("文档复制失败，用时 " + reloj.Elapsed.TotalSeconds.ToString("0.0")
                          + " 秒：" + (string)r["error"]);
                throw new InvalidOperationException(
                    "无法复制文档（" + reloj.Elapsed.TotalSeconds.ToString("0.0") + " 秒）："
                    + (string)r["error"]
                    + "。如果 mxd 较大，且代码不需要会话，请改用 execute_arcpy 并设置 usar_documento=false"
                    + "（即不需要 mxd 或 df）。");
            }

            long mb = 0;
            try { mb = new FileInfo(ruta).Length / (1024 * 1024); } catch { }
            Log.Info("文档已复制，用时 " + reloj.Elapsed.TotalSeconds.ToString("0.0") + " 秒（" + mb + " MB）");
            return ruta;
        }

        /// <summary>
        /// Ruta del .mxd tal y como está EN DISCO, si existe. ArcObjects no permite
        /// consultar si el documento tiene cambios sin guardar (IDocumentDirty2 solo
        /// deja marcarlo), así que la diferencia se comunica en el aviso del
        /// resultado en vez de intentar adivinarla.
        /// </summary>
        private static string SnapshotDesdeDisco()
        {
            JObject r = StaDispatcher.Invoke(delegate
            {
                IApplication app = ArcSession.App();
                return Protocol.Result(new JObject { ["ruta"] = ArcSession.MxdPath(app) });
            }, StaStepTimeout);

            if (!(bool)r["ok"]) return null;
            string mxd = (string)r["result"]["ruta"];
            if (string.IsNullOrEmpty(mxd) || !File.Exists(mxd))
            {
                Log.Info("文档未保存到磁盘：需从 ArcMap 序列化。");
                return null;
            }
            return mxd;
        }

        /// <summary>Lanza el runner con el job y devuelve su JSON de salida.
        /// Timeout duro con Kill: sin zombies de python.exe.</summary>
        private static JObject RunJob(string op, JObject parameters, string mxdSnapshot,
                                      TimeSpan? timeout = null)
        {
            TimeSpan tope = timeout ?? SubprocessTimeout;
            string runner = ExtraerRunner();
            string stamp = Guid.NewGuid().ToString("N");
            string jobPath = Path.Combine(WorkDir(), "job_" + stamp + ".json");
            string outPath = Path.Combine(WorkDir(), "out_" + stamp + ".json");
            // El runner deriva esta misma ruta de su segundo argumento: no hace falta
            // pasarla, y así el contrato de argumentos del runner no cambia.
            string fasePath = outPath + ".fase";

            var job = new JObject { ["op"] = op, ["params"] = parameters ?? new JObject() };
            if (mxdSnapshot != null)
                job["mxd"] = mxdSnapshot;
            // UTF-8 sin BOM por fichero (nunca stdout: la consola Py2.7 en cp1252
            // rompería ñ/tildes, igual que un header '# -*- coding -*-' mal puesto).
            File.WriteAllText(jobPath, job.ToString(Formatting.None), new UTF8Encoding(false));

            // Ante salida ilegible se CONSERVAN job y out: son la única evidencia
            // para diagnosticar (se borraban siempre, y con ellos la pista).
            bool conservarEvidencia = false;
            int pidRunner = 0;
            try
            {
                var psi = new ProcessStartInfo
                {
                    FileName = PythonExe(),
                    Arguments = "\"" + runner + "\" \"" + jobPath + "\" \"" + outPath + "\"",
                    UseShellExecute = false,
                    CreateNoWindow = true,
                    RedirectStandardError = true,
                    RedirectStandardOutput = true,
                };
                int exitCode;
                string stderr;
                using (Process p = Process.Start(psi))
                {
                    pidRunner = RegistrarRunner(p);
                    // AMBOS flujos en asíncrono: leer uno solo con ReadToEnd cuelga el
                    // subprocess si el otro pipe se llena (~4 KB de mensajes de arcpy).
                    var salida = new StringBuilder();
                    var errores = new StringBuilder();
                    p.OutputDataReceived += delegate (object s, DataReceivedEventArgs e)
                    { if (e.Data != null) salida.AppendLine(e.Data); };
                    p.ErrorDataReceived += delegate (object s, DataReceivedEventArgs e)
                    { if (e.Data != null) errores.AppendLine(e.Data); };
                    p.BeginOutputReadLine();
                    p.BeginErrorReadLine();

                    // Sondeo en vez de una espera ciega: el runner va anotando su fase
                    // y aquí se registra cada cambio. Así el log dice DÓNDE se quedó
                    // pillado, que desde fuera es indistinguible de estar trabajando.
                    var reloj = Stopwatch.StartNew();
                    string fase = null;
                    TimeSpan faseDesde = TimeSpan.Zero;
                    bool termino = false;
                    while (reloj.Elapsed < tope)
                    {
                        if (p.WaitForExit((int)SondeoFase.TotalMilliseconds)) { termino = true; break; }
                        string nueva = LeerFase(fasePath);
                        if (nueva != null && nueva != fase)
                        {
                            fase = nueva;
                            faseDesde = reloj.Elapsed;
                            Log.Info("runner '" + op + "' [" + reloj.Elapsed.TotalSeconds.ToString("0")
                                     + " 秒] 阶段：" + fase);
                        }
                    }

                    if (!termino)
                    {
                        string donde = fase == null
                            ? "没能记录任何阶段（解释器启动即退出）"
                            : "卡在阶段 '" + fase + "'，已持续 "
                              + (reloj.Elapsed - faseDesde).TotalSeconds.ToString("0") + " 秒";
                        try { p.Kill(); } catch { /* ya muerto */ }
                        Log.Error("runner '" + op + "' 执行超过 " + tope.TotalSeconds
                                  + " 秒：" + donde + "。进程 " + PidSeguro(p)
                                  + " 已结束。证据：" + jobPath);
                        conservarEvidencia = true;
                        return Protocol.Error("超时（" + tope.TotalSeconds
                            + " 秒）arcpy 子进程在执行 '" + op + "'：" + donde
                            + "。进程已结束（无僵尸进程）。"
                            + (fase != null && fase.StartsWith("abriendo documento")
                                ? " 卡在打开文档阶段。打开本身并不慢（实测 0.7 秒"
                                  + "，36 个图层的 .mxd）：真正阻塞的是许可"
                                  + "争用，即另一个进程占用了 Desktop 许可。"
                                  + " 同一文档在 ArcMap 打开时被阻塞达 180 秒，而"
                                  + "ArcMap 关闭时仅 0.7 秒。请先检查还有什么在使用 arcpy，再"
                                  + "调大超时——那只会延长等待。如果你的代码不使用"
                                  + " mxd 或 df，请传 usar_documento=false。"
                                : op == "execute_code"
                                    ? " 如果操作确实耗时较长，请调大 ARCMAP_EXEC_TIMEOUT（秒）。"
                                    : " 如果操作确实耗时较长，请调大 ARCMAP_SUBPROCESS_TIMEOUT（秒）。")
                            + " 已保留证据：" + jobPath);
                    }
                    // Con salida redirigida en asíncrono hay que rematar con un WaitForExit
                    // final para que los buffers acaben de vaciarse. PERO **nunca sin
                    // argumentos**: esa llamada no espera a que muera el hijo (que aquí ya
                    // murió), espera al EOF de LOS DOS PIPES, y un NIETO que heredó los
                    // descriptores y sigue vivo impide ese EOF para siempre. Reproducido en
                    // aislado el 2026-08-28 sobre .NET Framework 4.8: hijo muerto a los
                    // 0,0 s, `WaitForExit()` bloqueado 12,1 s, exactamente lo que vivió el
                    // nieto. Con un nieto que no muera, bloquea indefinidamente, el handler
                    // no vuelve y el puente se queda inservible. arcpy lanza procesos
                    // auxiliares, así que el nieto no es hipotético.
                    // Se acota: como mucho FlushSalidaTimeout esperando el vaciado. Si no
                    // llega, se sigue con lo que haya — perder unas líneas de stderr es
                    // barato; colgar el puente, no.
                    if (!p.WaitForExit((int)FlushSalidaTimeout.TotalMilliseconds))
                        Log.Error("runner '" + op + "' 已结束，但管道在 "
                                  + FlushSalidaTimeout.TotalSeconds + " 秒内未返回 EOF：有进程继承了输出且仍在"
                                  + "运行（arcpy 的辅助进程）。继续处理；已捕获的输出"
                                  + "可能不完整。");
                    exitCode = p.ExitCode;
                    stderr = errores.ToString();
                    if (salida.Length > 0)
                        Log.Info("runner '" + op + "' 标准输出：" + Recortar(salida.ToString()));
                }

                if (!File.Exists(outPath))
                    return Protocol.Error("arcpy 运行器未产生输出（exit "
                        + exitCode + "）。stderr：" + Recortar(stderr));

                string texto = File.ReadAllText(outPath, Encoding.UTF8);
                if (string.IsNullOrEmpty(texto.Trim()))
                {
                    conservarEvidencia = true;
                    Log.Info("runner '" + op + "' 输出为空；证据见 " + jobPath + " / " + outPath);
                    return Protocol.Error("arcpy 运行器已结束（exit " + exitCode
                        + "）输出为空：操作未能完成。"
                        + "stderr：" + Recortar(stderr)
                        + " | 已保留证据：" + jobPath + " y " + outPath);
                }

                JObject respuesta;
                try
                {
                    respuesta = JObject.Parse(texto);
                }
                catch (Exception ex)
                {
                    conservarEvidencia = true;
                    Log.Info("runner '" + op + "' 输出无法读取；证据见 " + jobPath + " / " + outPath);
                    return Protocol.Error("arcpy 运行器返回的输出无法解析（exit "
                        + exitCode + "): " + ex.Message
                        + " | 前几个字节：" + Recortar(texto.Length > 200 ? texto.Substring(0, 200) : texto)
                        + " | stderr：" + Recortar(stderr)
                        + " | 已保留证据：" + jobPath + " y " + outPath);
                }
                if (respuesta["ok"] == null)
                {
                    conservarEvidencia = true;
                    return Protocol.Error("arcpy 运行器返回的 JSON 缺少字段 'ok'（exit "
                        + exitCode + "）。已保留证据：" + outPath);
                }
                // Sobre de error estándar del runner (error + traceback) o resultado.
                return respuesta;
            }
            finally
            {
                OlvidarRunner(pidRunner);
                // La traza de fase es de usar y tirar salvo que haya que diagnosticar:
                // cuando se conserva evidencia, dice dónde se quedó el runner.
                if (!conservarEvidencia)
                {
                    Borrar(jobPath);
                    Borrar(outPath);
                    Borrar(fasePath);
                }
            }
        }

        private static string Recortar(string s)
        {
            if (string.IsNullOrEmpty(s)) return "(vacío)";
            s = s.Trim();
            return s.Length <= 2000 ? s : s.Substring(s.Length - 2000);
        }

        /// <summary>
        /// Lee la fase que el runner dice estar ejecutando. Best-effort por diseño: el
        /// fichero se está reescribiendo desde el otro proceso, así que una lectura a
        /// medias es normal y se ignora (en el siguiente sondeo se lee bien). Jamás
        /// puede tumbar el job que está vigilando.
        /// </summary>
        private static string LeerFase(string ruta)
        {
            try
            {
                if (!File.Exists(ruta)) return null;
                string texto;
                using (var fs = new FileStream(ruta, FileMode.Open, FileAccess.Read, FileShare.ReadWrite))
                using (var sr = new StreamReader(fs, Encoding.UTF8))
                    texto = sr.ReadToEnd();
                if (string.IsNullOrEmpty(texto.Trim())) return null;
                JObject j = JObject.Parse(texto);
                string fase = (string)j["fase"];
                if (string.IsNullOrEmpty(fase)) return null;
                string detalle = (string)j["detalle"];
                return string.IsNullOrEmpty(detalle) ? fase : fase + " (" + detalle + ")";
            }
            catch { return null; }
        }

        /// <summary>PID para el log sin arriesgar una excepción sobre un proceso ya muerto.</summary>
        private static string PidSeguro(Process p)
        {
            try { return "PID " + p.Id; } catch { return "（PID 未知）"; }
        }

        private static void Borrar(string ruta)
        {
            try { if (ruta != null && File.Exists(ruta)) File.Delete(ruta); } catch { }
        }

        /// <summary>Job de documento: snapshot + runner + limpieza del snapshot.</summary>
        private static JObject RunJobConSnapshot(string op, JObject parameters, bool serializarSesion = false,
                                                 TimeSpan? timeout = null)
        {
            string snap = Snapshot(serializarSesion);
            try
            {
                return RunJob(op, parameters, snap, timeout);
            }
            finally
            {
                Borrar(snap);
            }
        }

        /// <summary>Añade la salida al mapa: best-effort, nunca rompe la
        /// tool. Corre en STA sobre la sesión viva.</summary>
        private static bool AddToMap(string ruta)
        {
            JObject r = StaDispatcher.Invoke(delegate
            {
                IMxDocument doc;
                IMap map = MapHandlers.FocusMap(out doc);
                ILayer lyr = DataAccess.CrearCapaDesdeRuta(ruta);
                ((IMapLayers)map).InsertLayer(lyr, true, 0);
                doc.UpdateContents();
                doc.ActiveView.Refresh();
                return Protocol.Result(new JObject());
            }, StaStepTimeout);
            if (!(bool)r["ok"])
                Log.Info("anadir_al_mapa 尽力添加失败：'" + ruta + "': " + (string)r["error"]);
            return (bool)r["ok"];
        }

        // ------------------------------------------------------------------ //
        // Handlers (nombre de comando y contrato JSON de los schemas del servidor MCP).
        // ------------------------------------------------------------------ //

        /// <summary>
        /// ¿El código necesita el documento? Solo si menciona `mxd`, `df` o el módulo
        /// de mapping. Copiar el .mxd de una sesión cargada cuesta segundos o minutos,
        /// y la mayoría del arcpy útil (geoprocesar rásters, recorrer tablas, calcular
        /// índices) trabaja sobre ficheros en disco y no lo toca.
        /// </summary>
        private static bool NecesitaDocumento(string code)
        {
            if (string.IsNullOrEmpty(code)) return false;
            return Regex.IsMatch(code, @"\b(mxd|df|MAP|mapping)\b");
        }

        public static JObject ExecuteArcpy(JObject parameters)
        {
            // El usuario manda: usar_documento fuerza el comportamiento en ambos
            // sentidos. Sin él, se decide leyendo el código.
            bool conDocumento;
            JToken explicito = parameters["usar_documento"];
            if (explicito != null && explicito.Type != JTokenType.Null)
                conDocumento = (bool)explicito;
            else
                conDocumento = NecesitaDocumento((string)parameters["code"]);

            // serializar_sesion fuerza la vía SaveAsDocument (la única que recoge
            // cambios sin guardar, y la única capaz de tumbar ArcMap).
            JToken serializar = parameters["serializar_sesion"];
            bool serializarSesion = serializar != null && serializar.Type != JTokenType.Null && (bool)serializar;

            JObject r = conDocumento
                ? RunJobConSnapshot("execute_code", parameters, serializarSesion, ExecuteTimeout)
                : RunJob("execute_code", parameters, null, ExecuteTimeout);

            if (!(bool)r["ok"])
            {
                // "no puede abrir documento de mapa" / "Nombre de archivo MXD no valido"
                // sirven igual para una ruta mala, un fichero corrupto o una version
                // superior a la de la sesion: Esri no los distingue. Aqui se leen los
                // .mxd que menciona el codigo y se dice lo que se sabe de cada uno, para
                // que el diagnostico sea inmediato en vez de media conversacion. Cuesta
                // milisegundos y solo se hace cuando YA ha fallado.
                try
                {
                    if (MxdVersion.PareceFalloDeApertura((string)r["error"]))
                    {
                        string diag = MxdVersion.DiagnosticarCodigo(
                            (string)parameters["code"], MxdVersion.VersionArcMapSesion());
                        if (diag != null)
                            r["diagnostico_mxd"] = diag;
                    }
                }
                catch (Exception ex)
                {
                    // Un diagnostico que falla no puede tapar el error de verdad.
                    Log.Error(".mxd 诊断失败", ex);
                }
                return r;
            }

            if ((bool)r["ok"])
            {
                r["result"]["aviso"] = conDocumento
                    ? (serializarSesion ? AvisoSnapshot : AvisoSnapshot + AvisoSnapshotDisco)
                    : "未复制文档即执行（代码未使用 mxd 或 df）：更快且不"
                      + "占用 ArcMap。若需要会话，请传 usar_documento=true。";

                // El código puede "funcionar" y no cambiar nada: los cambios de
                // renderer sobre la copia se descartan por diseño (ADR-004), y hasta
                // ahora nadie lo decía. Un agente perdió una sesión entera contra
                // este límite, que está documentado pero no se menciona al devolver
                // un resultado que no ha surtido efecto. Se avisa, no se bloquea:
                // la detección es por texto y puede dar falsos positivos.
                string aviso = AvisoSimbologia((string)parameters["code"]);
                if (aviso != null)
                    r["result"]["aviso_simbologia"] = aviso;
            }
            return r;
        }

        /// <summary>
        /// Si el código toca simbología, devuelve el aviso que REDIRIGE a la
        /// herramienta que sí muta la sesión viva; null si no la toca.
        /// </summary>
        private static string AvisoSimbologia(string code)
        {
            if (string.IsNullOrEmpty(code))
                return null;
            string c = code.ToLowerInvariant();
            bool toca = c.Contains("renderer") || c.Contains("symbology")
                        || c.Contains("symbol") || c.Contains("colorramp");
            if (!toca)
                return null;

            return "注意：你的代码涉及符号系统（renderer/symbology），而 execute_arcpy "
                 + "基于文档副本运行：这些修改不会进入活动会话，"
                 + "并在结束时被丢弃，即使调用本身成功。"
                 + "要真正修改符号系统，请使用 set_graduated_symbology（分级）、"
                 + "set_unique_values_symbology（唯一值）、set_raster_symbology（栅格）或 "
                 + "apply_symbology_from_layer（.lyr 模板）。"
                 + "如果只是读取符号系统，可忽略此提示。";
        }

        public static JObject ListDdp(JObject parameters)
        {
            return RunJobConSnapshot("list_ddp", parameters);
        }

        public static JObject ExportDdp(JObject parameters)
        {
            return RunJobConSnapshot("export_ddp", parameters);
        }

        /// <summary>goto_ddp_page APROXIMADO: el runner calcula el extent de la página
        /// sobre el snapshot y aquí se aplica al data frame vivo. La sesión viva NO
        /// cambia de página de atlas (DDP no existe en .NET): textos dinámicos y
        /// definition queries por página no se actualizan — se avisa siempre.</summary>
        public static JObject GotoDdpPage(JObject parameters)
        {
            JObject r = RunJobConSnapshot("ddp_page_extent", parameters);
            if (!(bool)r["ok"])
                return r;
            JObject info = (JObject)r["result"];
            JArray ext = (JArray)info["extent"];

            JObject aplicado = StaDispatcher.Invoke(delegate
            {
                IMxDocument doc;
                IMap map = MapHandlers.FocusMap(out doc);
                IEnvelope env = new EnvelopeClass();
                env.PutCoords((double)ext[0], (double)ext[1], (double)ext[2], (double)ext[3]);
                ((IActiveView)map).Extent = env;
                doc.ActiveView.Refresh();
                return Protocol.Result(new JObject { ["escala"] = map.MapScale });
            }, StaStepTimeout);
            if (!(bool)aplicado["ok"])
                return aplicado;

            return Protocol.Result(new JObject
            {
                ["page_id"] = info["page_id"],
                ["valor"] = info["valor"],
                ["escala"] = aplicado["result"]["escala"],
                ["aviso"] = "近似处理：将页面范围应用到数据框 "
                    + "（活动会话），但会话中的地图册不会翻页（DDP 仅存在于 "
                    + "arcpy）：动态文本和按页查询不会更新。要"
                    + "导出图纸请使用 export_ddp，它会真正翻页。",
            });
        }

        /// <summary>Fábrica de los 5 handlers ambientales de datos-en-disco: runner
        /// out-of-process + anadir_al_mapa nativo sobre la sesión viva al volver.</summary>
        private static JObject Ambiental(string op, JObject parameters, params string[] camposSalida)
        {
            bool anadir = parameters["anadir_al_mapa"] == null
                || parameters["anadir_al_mapa"].Type == JTokenType.Null
                || (bool)parameters["anadir_al_mapa"];
            JObject r = RunJob(op, parameters, null);
            if (!(bool)r["ok"] || !anadir)
                return r;
            JObject res = (JObject)r["result"];
            string salida = null;
            foreach (string campo in camposSalida)
            {
                if (res[campo] != null && res[campo].Type == JTokenType.String)
                {
                    salida = (string)res[campo];
                    break;
                }
            }
            if (salida != null)
                res["anadida_al_mapa"] = AddToMap(salida);
            return r;
        }

        public static JObject RasterIndex(JObject parameters)
        {
            return Ambiental("raster_index", parameters, "salida");
        }

        public static JObject Hydrology(JObject parameters)
        {
            return Ambiental("hydrology", parameters, "salida");
        }

        public static JObject Contours(JObject parameters)
        {
            return Ambiental("contours", parameters, "salida");
        }

        public static JObject TopographicProfile(JObject parameters)
        {
            return Ambiental("topographic_profile", parameters, "salida");
        }

        public static JObject LeastCostPath(JObject parameters)
        {
            return Ambiental("least_cost_path", parameters, "salida");
        }

        // calculate_geometry NO va por subprocess: la sesión viva mantiene un schema
        // lock sobre las fuentes cargadas en la TOC y AddGeometryAttributes añade
        // campos → nativo in-process en GeoprocessingHandlers.CalculateGeometry.
    }
}
