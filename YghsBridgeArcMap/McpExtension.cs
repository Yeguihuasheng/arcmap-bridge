using System.Diagnostics;
using System.Threading;
using System.Windows.Forms;
using ESRI.ArcGIS.Desktop.AddIns;

namespace YghsBridge.AddIn
{
    /// <summary>
    /// Extensión del add-in (autoLoad). Captura el Dispatcher del hilo UI/STA en
    /// OnStartup (corre en ese hilo) y gestiona el ciclo de vida del servidor TCP.
    /// </summary>
    public class McpExtension : Extension
    {
        private static McpExtension _instance;

        // ArcMap instancia la extensión VARIAS veces por arranque (3-4 en el log del
        // 27-jul). Con el servidor en un campo de instancia, las cargas 2..N veían su
        // propio _server a null, intentaban bindear el 27179 y morían con
        // SocketException: el log se llenaba de "Autoarranque activo pero el puente no
        // arrancó", que era FALSO — la primera carga lo había levantado bien.
        // El servidor es un recurso del PROCESO, así que su estado va en estático.
        private static McpServer _server;

        // Quién levantó el puente: solo esa carga puede pararlo en su OnShutdown, para
        // que la descarga de una instancia espuria no tumbe el puente de la buena.
        private static McpExtension _duenoServidor;

        // La comprobación de versión también es del proceso: 4 cargas = 4 llamadas a la
        // API de GitHub por arranque, que además tiene rate-limit.
        private static bool _actualizacionComprobada;

        public static McpExtension Instance
        {
            get { return _instance; }
        }

        public bool IsRunning
        {
            get { return _server != null && _server.IsRunning; }
        }

        protected override void OnStartup()
        {
            _instance = this;
            // Capturar el dispatcher AQUÍ (hilo UI), jamás desde el thread del
            // listener: es la única vía segura hacia ArcObjects.
            StaDispatcher.CaptureCurrent();
            Log.Info("扩展已加载；STA 调度器已捕获（线程 "
                     + Thread.CurrentThread.ManagedThreadId + ", "
                     + Thread.CurrentThread.GetApartmentState() + ")");

            // Guard de instancia única: si otra carga de la extensión ya levantó el
            // puente en este proceso, no hay nada que hacer y desde luego nada que
            // reportar como error.
            if (IsRunning)
            {
                Log.Info("桥接已由该扩展的上一次加载启动，"
                         + "本进程内不再重试（ArcMap 会多次加载该扩展）。");
                return;
            }

            bool auto = Ajustes.Autoarranque;
            Log.Info("读取自动启动偏好：" + (auto ? "是" : "否"));
            if (auto)
            {
                // Nunca romper el arranque de ArcMap por el puente: si el puerto está
                // ocupado (otro ArcMap abierto), se registra y el usuario sigue trabajando.
                string error = StartServer();
                Log.Info(error == null
                    ? "自动启动已生效：打开 ArcMap 时已启动桥接"
                    : "自动启动已开启，但桥接未启动：" + error);
            }

            if (!_actualizacionComprobada)
            {
                _actualizacionComprobada = true;
                LanzarComprobacionActualizacion();
            }
        }

        /// <summary>
        /// Comprueba en un hilo de fondo si hay una versión nueva en GitHub. Jamás
        /// bloquea el arranque de ArcMap: sin internet o con rate-limit, no pasa nada.
        /// Si hay versión nueva (y no se ha avisado ya de ELLA), muestra un aviso una
        /// sola vez, marshalado al hilo UI (un MessageBox no puede lanzarse desde el
        /// hilo de fondo).
        /// </summary>
        private static void LanzarComprobacionActualizacion()
        {
            var hilo = new Thread(delegate ()
            {
                Actualizaciones.ComprobarEnSegundoPlano(delegate (string versionNueva)
                {
                    StaDispatcher.Post(delegate
                    {
                        try
                        {
                            DialogResult r = MessageBox.Show(
                                "yghsBridge 有新版本可用：v" + versionNueva + "。\n"
                                + "你当前安装的是 v" + Diagnostico.VersionAddin() + "。\n\n"
                                + "更新方法：关闭 ArcMap 后，双击仓库目录下的\n"
                                + "ACTUALIZAR.bat（等价于 git pull + install.ps1）。\n\n"
                                + "ArcMap 打开期间无法安装：它一直持有已加载的插件。\n\n"
                                + "现在打开更新说明？",
                                "yghsBridge · 发现新版本",
                                MessageBoxButtons.YesNo, MessageBoxIcon.Information);
                            if (r == DialogResult.Yes)
                                Process.Start(new ProcessStartInfo
                                {
                                    FileName = Actualizaciones.ActualizarUrl,
                                    UseShellExecute = true
                                });
                        }
                        catch (System.Exception ex)
                        {
                            Log.Error("无法显示更新提示", ex);
                        }
                    });
                });
            });
            hilo.IsBackground = true;
            hilo.Name = "yghs-bridge-update-check";
            hilo.Start();
        }

        protected override void OnShutdown()
        {
            // Solo la carga que levantó el puente lo para. Si ArcMap descarga una de las
            // instancias espurias, el puente de la buena tiene que sobrevivir.
            if (_duenoServidor == null || ReferenceEquals(_duenoServidor, this))
            {
                StopServer();
                _duenoServidor = null;
            }
            else
            {
                Log.Info("扩展已卸载（二次加载）：桥接仍在运行，"
                         + "由启动它的那次加载负责停止。");
            }
            if (ReferenceEquals(_instance, this))
                _instance = null;
            Log.Info("扩展已卸载");
        }

        /// <summary>Arranca el servidor. Devuelve null si OK, o el mensaje de error.</summary>
        public string StartServer()
        {
            if (IsRunning)
                return null; // ya activo: para el usuario es un éxito idempotente
            try
            {
                _server = new McpServer();
                _server.Start();
                _duenoServidor = this;
                return null;
            }
            catch (System.Exception ex)
            {
                Log.Error("无法启动服务", ex);
                // El caso habitual no es "otra instancia legítima": es un ArcMap zombi,
                // vivo y sin ventana principal, sujetando el puerto sin nada que cerrar.
                // Por eso se nombran las dos salidas, no solo la de matar el proceso.
                return ex.Message + "\n\n通常是因为端口 " + McpServer.Port
                    + " 已被其他 ArcMap 占用。两种解决办法：\n"
                    + "  · 换端口：导出 ARCMAP_BRIDGE_PORT=<其他端口> 后重新打开"
                    + " ArcMap（并在 MCP 服务端运行的环境中设置相同变量）。\n"
                    + "  · 若占用端口的 ArcMap 已成僵尸进程（进程存活但无窗口），"
                    + " 将其结束：Stop-Process -Id <PID> -Force。";
            }
        }

        public void StopServer()
        {
            if (_server != null && _server.IsRunning)
                _server.Stop();
            // Liberar la propiedad: si el usuario lo para desde el botón, cualquier carga
            // puede volver a arrancarlo después.
            _duenoServidor = null;
        }
    }
}
