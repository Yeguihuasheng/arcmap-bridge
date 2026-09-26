using System;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace YghsBridge.AddIn
{
    /// <summary>
    /// Servidor TCP del add-in: atiende al servidor MCP externo (FastMCP) por el
    /// puerto 27179. El listener corre en thread de fondo; cada petición se
    /// marshalea al hilo STA vía StaDispatcher.
    /// </summary>
    internal class McpServer
    {
        // BIND: solo loopback, y NO configurable a propósito (ADR-006, aceptada
        // 2026-08-28). `execute_arcpy` es ejecución de código arbitrario sin
        // autenticación, sin usuarios y sin TLS: quien alcance este puerto ejecuta lo
        // que quiera con los permisos de quien tenga ArcMap abierto. El loopback no es
        // un descuido pendiente de arreglar, es la única barrera que hay. El acceso a
        // un ArcMap remoto se hace por TÚNEL (SSH o Tailscale con reenvío de puerto),
        // que termina en el 127.0.0.1 del destino y además cifra y autentica: ya
        // alcanza este listener sin abrir nada.
        private static readonly IPAddress Bind = IPAddress.Loopback;

        // PUERTO: este sí es configurable, por `ARCMAP_BRIDGE_PORT` — el MISMO nombre
        // que lee el servidor Python (src/yghsbridge_server.py), de modo que una sola
        // variable mueve los dos extremos. No es una comodidad: cuando una instancia de
        // ArcMap se queda zombi sujetando el 27179 sin ventana que cerrar, sin puerto
        // alternativo el sistema entero se queda sin vía de escape hasta matar el
        // proceso por PID (incidente del 2026-08-27). Cambiar el puerto NO saca nada de
        // local: se sigue escuchando solo en loopback, en otro número.
        public const int PuertoPorDefecto = 27179;
        public static readonly int Port;

        // Qué contar sobre el puerto cuando arranque el puente. Se decide aquí y se
        // escribe en Start(): un inicializador estático no es sitio para tocar el log.
        private static readonly string _avisoPuerto;

        static McpServer()
        {
            string crudo = null;
            try { crudo = Environment.GetEnvironmentVariable("ARCMAP_BRIDGE_PORT"); }
            catch { /* si el entorno no se deja leer, el puerto por defecto sirve */ }

            if (crudo == null || crudo.Trim().Length == 0)
            {
                Port = PuertoPorDefecto;
                return;
            }

            int puerto;
            // Se rechazan los privilegiados (<1024): ArcMap corre como usuario normal y
            // el bind fallaría con un error que no explicaría por qué.
            if (!int.TryParse(crudo.Trim(), out puerto) || puerto < 1024 || puerto > 65535)
            {
                Port = PuertoPorDefecto;
                _avisoPuerto = "ARCMAP_BRIDGE_PORT='" + crudo + "' 不是有效端口"
                    + "（允许范围 1024-65535）。改用默认端口 " + PuertoPorDefecto + ".";
                return;
            }

            Port = puerto;
            if (puerto != PuertoPorDefecto)
            {
                _avisoPuerto = "端口取自 ARCMAP_BRIDGE_PORT：" + puerto
                    + "（默认为 " + PuertoPorDefecto + "）。MCP 服务端不会去"
                    + "猜测：请在它运行的环境中导出相同的变量，否则双方无法互相发现。";
            }
        }

        private const int ReadTimeoutMs = 5000;
        private const int MaxRequestBytes = 1024 * 1024; // los requests son pequeños; 1MB = algo va mal
        private static readonly TimeSpan HandlerTimeout = TimeSpan.FromSeconds(60);

        private TcpListener _listener;
        private Thread _acceptThread;
        private volatile bool _running;

        // UNA petición en vuelo. Si llega otra mientras ArcMap trabaja, respuesta
        // "busy" inmediata — nunca encolar: encolar a ciegas degrada en cascada
        // cuando el dibujado (p. ej. servicios WMS lentos) retiene el hilo STA.
        private readonly SemaphoreSlim _gate = new SemaphoreSlim(1, 1);

        // Quién tiene el gate y desde cuándo. Sirve para que `ping` pueda decir
        // "ocupado desde hace N s con el comando X" en vez de un "busy" pelado.
        // Es la diferencia entre diagnosticar en segundos y en media hora: el
        // 2026-08-27 un handler se quedó sin volver y desde fuera era imposible
        // distinguirlo de trabajo legítimo en curso.
        private volatile string _comandoEnCurso;
        private long _inicioComandoTicks;

        // Conexiones ACEPTADAS y todavía abiertas. Hacen falta porque `_listener.Stop()`
        // cierra el socket de escucha pero NO las conexiones ya aceptadas, y una conexión
        // viva mantiene ocupado el 127.0.0.1:27179. El 2026-08-27 eso dejó el puerto
        // cogido por un ArcMap que ya había descargado su extensión ("Servidor TCP
        // detenido" en el log a las 11:49:49) mientras un handler seguía bloqueado
        // sujetando su conexión: las instancias siguientes fallaban al bindear con
        // "Solo se permite un uso de cada dirección de socket". Cerrarlas en Stop()
        // desbloquea de paso al cliente, que deja de esperar una respuesta que no llega.
        private readonly System.Collections.Generic.List<TcpClient> _conexiones =
            new System.Collections.Generic.List<TcpClient>();

        /// <summary>Segundos que lleva ocupado, o -1 si está libre.</summary>
        private double SegundosOcupado()
        {
            long ticks = Interlocked.Read(ref _inicioComandoTicks);
            if (ticks == 0)
                return -1;
            return (DateTime.UtcNow - new DateTime(ticks, DateTimeKind.Utc)).TotalSeconds;
        }

        public bool IsRunning
        {
            get { return _running; }
        }

        public void Start()
        {
            if (_avisoPuerto != null)
                Log.Info(_avisoPuerto);
            _listener = new TcpListener(Bind, Port);
            _listener.Start();
            _running = true;
            _acceptThread = new Thread(AcceptLoop)
            {
                IsBackground = true,
                Name = "YghsBridge.Accept"
            };
            _acceptThread.Start();
            Log.Info("TCP 服务已监听 " + Bind + ":" + Port);
            BridgeLog.Note("桥接已就绪：127.0.0.1:" + Port + "（外部 AI 可连接）");
        }

        public void Stop()
        {
            _running = false;
            try { _listener.Stop(); } catch { /* ya cerrado */ }

            // Cerrar el listener NO basta: una conexión ya aceptada sigue ocupando el
            // puerto, y si su handler está bloqueado nadie la va a cerrar. Sin esto, un
            // ArcMap que ya descargó la extensión deja el 27179 cogido y ninguna instancia
            // nueva puede levantar el puente (incidente del 2026-08-27).
            TcpClient[] abiertas;
            lock (_conexiones)
            {
                abiertas = _conexiones.ToArray();
                _conexiones.Clear();
            }
            foreach (TcpClient c in abiertas)
                try { c.Close(); } catch { /* el handler ya la cerró */ }
            if (abiertas.Length > 0)
                Log.Info("已关闭 " + abiertas.Length + " 个在途连接以释放端口 "
                         + Port + "。若其中有执行到一半的命令，其工作可能仍在 ArcMap 内继续。");

            // Un runner arcpy vivo impide que ArcMap acabe de salir, y ahí es donde nace
            // el zombi: proceso vivo, sin ventana, con el puerto cogido. Si el puente se
            // para, nadie va a leer ya el resultado de ese runner, así que se corta.
            try
            {
                int muertos = Handlers.PythonHandlers.MatarRunnersVivos();
                if (muertos > 0)
                    Log.Info("已终止 " + muertos + " 个仍在运行的 arcpy 进程。");
            }
            catch (Exception ex)
            {
                Log.Error("无法终止仍在运行的 runner", ex);
            }

            Log.Info("TCP 服务已停止");
            BridgeLog.Note("桥接已停止：外部 AI 暂时无法连接");
        }

        private void AcceptLoop()
        {
            while (_running)
            {
                TcpClient client;
                try
                {
                    client = _listener.AcceptTcpClient();
                }
                catch
                {
                    break; // Stop() cierra el listener y rompe el Accept: salida limpia
                }
                ThreadPool.QueueUserWorkItem(delegate { HandleClient(client); });
            }
        }

        private void HandleClient(TcpClient client)
        {
            lock (_conexiones) _conexiones.Add(client);
            try
            {
                AtenderCliente(client);
            }
            finally
            {
                lock (_conexiones) _conexiones.Remove(client);
            }
        }

        private void AtenderCliente(TcpClient client)
        {
            using (client)
            {
                NetworkStream stream = client.GetStream();
                JObject response;
                try
                {
                    JObject request = ReadRequest(stream);
                    if (request == null)
                    {
                        response = Protocol.Error("请求不合法（未收到有效的 JSON 对象）");
                    }
                    else if (!_gate.Wait(0))
                    {
                        // OCUPADO. `ping` NO se queda aquí: un chequeo de salud que
                        // solo contesta cuando todo va bien no sirve para nada, y es
                        // justo cuando hay algo atascado cuando hace falta saber QUÉ.
                        // Se responde sin tocar el STA (que puede ser lo atascado),
                        // así que esta rama contesta siempre y al instante.
                        double seg = SegundosOcupado();
                        string cual = _comandoEnCurso ?? "未知";
                        if ("ping".Equals((string)request["type"]))
                        {
                            response = Protocol.Result(new JObject
                            {
                                { "estado", "ocupado" },
                                { "comando_en_curso", cual },
                                { "ocupado_desde_s", Math.Round(seg, 1) },
                                { "nota", "桥接仍在运行；ArcMap 正在处理 '" + cual
                                          + "'，已持续 " + seg.ToString("0") + " 秒。如果这是一个耗时的地理处理"
                                          + "任务，它仍在运行：请等待，不要重复发起。若耗时"
                                          + "明显超出合理范围，请查看插件日志。" },
                            });
                        }
                        else
                        {
                            response = Protocol.Error("忙：ArcMap 已用 " + seg.ToString("0")
                                + " 秒处理 '" + cual + "'；请稍后重试"
                                + "（调用 ping 可立即查看状态，无需等待）");
                        }
                    }
                    else
                    {
                        _comandoEnCurso = (string)request["type"] ?? "?";
                        Interlocked.Exchange(ref _inicioComandoTicks, DateTime.UtcNow.Ticks);
                        try
                        {
                            response = Dispatch(request);
                        }
                        finally
                        {
                            Interlocked.Exchange(ref _inicioComandoTicks, 0);
                            _comandoEnCurso = null;
                            _gate.Release();
                        }
                    }
                }
                catch (Exception ex)
                {
                    Log.Error("处理客户端时出错", ex);
                    response = Protocol.Error("插件内部错误：" + ex.Message);
                }

                // 用户可见「人话」：按响应 ok 状态回显 ✅/❌（对齐 Pro 版面板）。
                try { NotaResultado(response); }
                catch { /* 回显失败不影响响应本身 */ }

                try
                {
                    byte[] payload = Encoding.UTF8.GetBytes(response.ToString(Formatting.None));
                    stream.Write(payload, 0, payload.Length);
                }
                catch (Exception ex)
                {
                    Log.Error("写入响应时出错", ex);
                }
                // El using cierra la conexión => EOF para el servidor MCP.
            }
        }

        /// <summary>
        /// El relay envía UN objeto JSON y espera SIN cerrar su lado de envío
        /// (no hay shutdown): no se puede leer hasta EOF. Se acumula y se intenta
        /// el parse tras cada chunk hasta que el JSON está completo.
        /// </summary>
        private static JObject ReadRequest(NetworkStream stream)
        {
            stream.ReadTimeout = ReadTimeoutMs;
            var buf = new MemoryStream();
            var chunk = new byte[8192];
            while (buf.Length < MaxRequestBytes)
            {
                int n;
                try
                {
                    n = stream.Read(chunk, 0, chunk.Length);
                }
                catch (IOException)
                {
                    break; // timeout de lectura sin JSON completo
                }
                if (n <= 0)
                    break;
                buf.Write(chunk, 0, n);
                try
                {
                    return JObject.Parse(Encoding.UTF8.GetString(buf.ToArray()));
                }
                catch (JsonReaderException)
                {
                    // JSON aún incompleto (o byte multibyte cortado): seguir leyendo.
                }
            }
            return null;
        }

        // Comandos nativos ArcObjects. Corren en el hilo STA vía StaDispatcher;
        // el nombre y contrato JSON de cada comando es el que esperan los schemas
        // del servidor MCP (src/yghsbridge_server.py).
        private static readonly System.Collections.Generic.Dictionary<string, Func<JObject, JObject>> _handlers =
            new System.Collections.Generic.Dictionary<string, Func<JObject, JObject>>
            {
                { "ping",                  Handlers.PingHandler.Run },
                { "get_arcmap_info",       Handlers.InfoHandlers.GetArcmapInfo },
                { "list_layers",           Handlers.InfoHandlers.ListLayers },
                { "zoom_to_layer",         Handlers.InfoHandlers.ZoomToLayer },
                { "set_text_element",      Handlers.LayoutHandlers.SetTextElement },
                { "get_canvas_screenshot", Handlers.ScreenshotHandler.Run },
                { "list_layout_elements",  Handlers.LayoutHandlers.ListLayoutElements },
                { "export_pdf",            Handlers.ExportHandlers.ExportPdf },
                { "export_jpg",            Handlers.ExportHandlers.ExportJpg },
                { "export_view_png",       Handlers.ExportHandlers.ExportViewPng },
                { "refresh",               Handlers.MapHandlers.Refresh },
                { "set_scale",             Handlers.MapHandlers.SetScale },
                { "set_extent",            Handlers.MapHandlers.SetExtent },
                { "set_layer_visibility",  Handlers.MapHandlers.SetLayerVisibility },
                { "set_definition_query",  Handlers.MapHandlers.SetDefinitionQuery },
                { "save_mxd",              Handlers.DocumentHandlers.SaveMxd },
                { "save_mxd_as",           Handlers.DocumentHandlers.SaveMxdAs },
                // Geoprocesamiento nativo sobre la sesión viva.
                { "run_geoprocessing",     Handlers.GeoprocessingHandlers.RunGeoprocessing },
                { "calculate_geometry",    Handlers.GeoprocessingHandlers.CalculateGeometry },
                // Capas y datos.
                { "select_by_attribute",        Handlers.QueryHandlers.SelectByAttribute },
                { "clear_selection",            Handlers.QueryHandlers.ClearSelection },
                { "get_unique_values",          Handlers.QueryHandlers.GetUniqueValues },
                { "count_features",             Handlers.QueryHandlers.CountFeatures },
                { "list_fields",                Handlers.QueryHandlers.ListFields },
                { "get_layer_info",             Handlers.QueryHandlers.GetLayerInfo },
                { "get_layer_features",         Handlers.QueryHandlers.GetLayerFeatures },
                { "add_layer",                  Handlers.LayerHandlers.AddLayer },
                { "remove_layer",               Handlers.LayerHandlers.RemoveLayer },
                { "apply_symbology_from_layer", Handlers.LayerHandlers.ApplySymbologyFromLayer },
                { "set_graduated_symbology",    Handlers.LayerHandlers.SetGraduatedSymbology },
                { "set_raster_symbology",       Handlers.RasterSymbologyHandlers.SetRasterSymbology },
                { "set_unique_values_symbology", Handlers.UniqueValuesHandlers.SetUniqueValuesSymbology },
                { "get_bookmarks",              Handlers.BookmarkHandlers.GetBookmarks },
                { "add_bookmark",               Handlers.BookmarkHandlers.AddBookmark },
                { "remove_bookmark",            Handlers.BookmarkHandlers.RemoveBookmark },
                { "goto_bookmark",              Handlers.BookmarkHandlers.GotoBookmark },
                { "describe_data",              Handlers.WorkspaceHandlers.DescribeData },
                { "list_data_frames",           Handlers.DataFrameHandlers.ListDataFrames },
                { "set_active_df",              Handlers.DataFrameHandlers.SetActiveDf },
                { "get_workspace",              Handlers.WorkspaceHandlers.GetWorkspace },
                { "set_workspace",              Handlers.WorkspaceHandlers.SetWorkspace },
                { "list_feature_classes",       Handlers.WorkspaceHandlers.ListFeatureClasses },
                { "list_tables",                Handlers.WorkspaceHandlers.ListTables },
                { "list_rasters",               Handlers.WorkspaceHandlers.ListRasters },
                { "list_broken_data_sources",   Handlers.SourceHandlers.ListBrokenDataSources },
                { "repair_data_source",         Handlers.SourceHandlers.RepairDataSource },
            };

        // Comandos que ArcObjects no cubre (código arcpy arbitrario, Data Driven
        // Pages, análisis ambiental), resueltos OUT-OF-PROCESS con el arcpy
        // standalone sobre un snapshot del documento. Corren en ESTE thread de
        // fondo — el subprocess no congela la GUI de ArcMap — y por dentro
        // marshalean al STA solo los pasos ArcObjects (snapshot, añadir al mapa,
        // extent). El gate busy sigue garantizando UNA petición en vuelo.
        private static readonly System.Collections.Generic.Dictionary<string, Func<JObject, JObject>> _handlersFondo =
            new System.Collections.Generic.Dictionary<string, Func<JObject, JObject>>
            {
                { "execute_code",         Handlers.PythonHandlers.ExecuteArcpy },
                { "list_ddp",             Handlers.PythonHandlers.ListDdp },
                { "export_ddp",           Handlers.PythonHandlers.ExportDdp },
                { "goto_ddp_page",        Handlers.PythonHandlers.GotoDdpPage },
                { "raster_index",         Handlers.PythonHandlers.RasterIndex },
                { "hydrology",            Handlers.PythonHandlers.Hydrology },
                { "contours",             Handlers.PythonHandlers.Contours },
                { "topographic_profile",  Handlers.PythonHandlers.TopographicProfile },
                { "least_cost_path",      Handlers.PythonHandlers.LeastCostPath },
            };

        // Exports a disco y GP nativos pueden tardar mucho más de 60s (layouts densos,
        // dpi alto, geoprocesos): timeout STA amplio, filosofía del ARCMAP_GP_TIMEOUT.
        private static readonly System.Collections.Generic.HashSet<string> _comandosLargos =
            new System.Collections.Generic.HashSet<string> { "export_pdf", "export_jpg", "export_view_png", "run_geoprocessing" };
        private static readonly TimeSpan LongHandlerTimeout = TimeSpan.FromSeconds(1800);

        // Techo de SEGURIDAD para los handlers de fondo. No compite con sus timeouts
        // internos: el peor caso legítimo es snapshot (600 s) + subprocess (1800 s) =
        // 2400 s, así que esto va deliberadamente por encima. Si salta, no es que la
        // operación fuera larga: es que el handler no volvió, y sin este techo eso
        // deja el puente muerto sin recuperación (incidente del 2026-08-27).
        private static readonly TimeSpan FondoTimeout = TimeSpan.FromSeconds(2700);

        private static JObject Dispatch(JObject request)
        {
            string type = (string)request["type"];
            JObject parameters = request["params"] as JObject ?? new JObject();
            Log.Info("收到命令：" + type);
            Estadisticas.RegistrarComando(type);
            // 用户可见「人话」：每个命令在面板里记一行 ⇒，让用户知道外部 AI 在做什么。
            BridgeLog.Note("⇒ " + type);

            Func<JObject, JObject> handler;
            if (type != null && _handlersFondo.TryGetValue(type, out handler))
            {
                // Out-of-process: el handler gestiona su propio timeout de subprocess
                // y sus pasos STA internos. PERO eso no basta: el 2026-08-27 un
                // handler de fondo NO VOLVIÓ, el `finally` que suelta el gate nunca
                // llegó, y el puente quedó inservible hasta matar ArcMap por PID.
                // De ahí este techo exterior: si el handler se pasa de largo, se
                // devuelve un error y el gate se libera. El trabajo huérfano puede
                // seguir vivo por dentro (no se puede abortar un thread ajeno sin
                // riesgo), pero el puente vuelve a atender, que es lo que importa.
                Func<JObject, JObject> handlerLocal = handler;
                JObject parametrosLocal = parameters;
                JObject resultado = null;
                Exception fallo = null;
                var terminado = new ManualResetEventSlim(false);

                ThreadPool.QueueUserWorkItem(delegate
                {
                    try { resultado = handlerLocal(parametrosLocal); }
                    catch (Exception ex) { fallo = ex; }
                    finally { try { terminado.Set(); } catch { /* ya liberado */ } }
                });

                if (!terminado.Wait(FondoTimeout))
                {
                    Log.Error("后台处理程序 '" + type + "' 超过安全上限 "
                              + FondoTimeout.TotalSeconds + " 秒且未返回。已释放闸门 "
                              + "以免桥接不可用；但可能残留孤立任务。");
                    return Protocol.Error("命令 '" + type + "' 超过安全上限 " + FondoTimeout.TotalSeconds
                        + " 秒未返回任何结果。桥接仍可用，但 ArcMap 内可能残留孤立任务：请查看插件日志；"
                        + "若 ArcMap 表现异常请重启。常见原因：打开的 .mxd 数据源无响应"
                        + "（盲目打开前先用 describe_mxd 检查）。");
                }
                if (fallo != null)
                {
                    Log.Error("后台处理程序抛出异常", fallo);
                    return Protocol.Error(fallo.Message, fallo);
                }
                return resultado;
            }
            if (type == null || !_handlers.TryGetValue(type, out handler))
            {
                var implementados = new System.Collections.Generic.List<string>(_handlers.Keys);
                implementados.AddRange(_handlersFondo.Keys);
                return Protocol.Error(
                    "未知命令：'" + type + "'。已实现的命令："
                    + string.Join(", ", implementados));
            }
            TimeSpan timeout = _comandosLargos.Contains(type) ? LongHandlerTimeout : HandlerTimeout;
            return StaDispatcher.Invoke(delegate { return handler(parameters); }, timeout);
        }

        /// <summary>
        /// 按响应 ok 状态在面板回显一行「人话」结果（对齐 Pro 版）：
        ///   成功 → ✅ + result 里的 summary（若有）；失败 → ❌ + error 消息（截断）。
        /// 仅作面板提示，不改动响应内容。
        /// </summary>
        private static void NotaResultado(JObject response)
        {
            if (response == null) return;
            bool ok = response["ok"] != null && (bool)response["ok"];
            if (ok)
            {
                JObject result = response["result"] as JObject;
                string summary = result != null && result["summary"] != null
                    ? (string)result["summary"] : null;
                BridgeLog.Note("✅ " + (string.IsNullOrEmpty(summary) ? "完成" : summary));
            }
            else
            {
                string error = response["error"] != null ? (string)response["error"] : "未知错误";
                if (error.Length > 160) error = error.Substring(0, 160) + " …";
                BridgeLog.Note("❌ " + error);
            }
        }
    }
}
