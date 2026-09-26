using System;
using System.Threading.Tasks;
using System.Windows.Threading;
using Newtonsoft.Json.Linq;

namespace YghsBridge.AddIn
{
    /// <summary>
    /// Marshal de peticiones al hilo STA de ArcMap vía WPF Dispatcher.
    /// ArcObjects SOLO puede tocarse desde ese hilo.
    /// </summary>
    internal static class StaDispatcher
    {
        private static Dispatcher _ui;

        /// <summary>Llamar UNA vez desde el hilo UI (OnStartup de la extensión).</summary>
        public static void CaptureCurrent()
        {
            _ui = Dispatcher.CurrentDispatcher;
        }

        public static bool IsCaptured
        {
            get { return _ui != null; }
        }

        /// <summary>
        /// Ejecuta el handler en el hilo STA con timeout. Si expira, devuelve un
        /// error JSON SIN matar el listener: si la operación ya empezó en ArcMap,
        /// seguirá corriendo allí; si aún estaba encolada, se aborta.
        /// </summary>
        public static JObject Invoke(Func<JObject> handler, TimeSpan timeout)
        {
            if (_ui == null)
                return Protocol.Error("STA 调度器未捕获（扩展是否未能加载？）");

            DispatcherOperation<JObject> op = _ui.InvokeAsync(delegate
            {
                // Ninguna excepción escapa al message pump de ArcMap — eso
                // sería un crash de la aplicación entera.
                try
                {
                    return handler();
                }
                catch (Exception ex)
                {
                    Log.Error("处理程序在 STA 线程抛出异常", ex);
                    // Sobre de error del protocolo: error = mensaje + traceback.
                    return Protocol.Error(ex.Message, ex);
                }
            });

            Task<JObject> task = op.Task;
            if (!task.Wait(timeout))
            {
                op.Abort();
                Log.Error("超时 " + timeout.TotalSeconds + " 秒，等待 STA 线程");
                return Protocol.Error(
                    "超时（" + timeout.TotalSeconds + " 秒）等待 ArcMap 线程 "
                    + "（是否正在执行耗时的地理处理、WMS 绘制或打开了模态对话框？）");
            }
            return task.Result;
        }

        /// <summary>
        /// Encola una acción en el hilo UI para que corra DESPUÉS de que termine el
        /// evento en curso, sin bloquear. Necesario para mostrar un diálogo modal
        /// fuera del OnSelChange de un ComboBox de add-in: hacerlo dentro hace que
        /// ArcMap revierta la selección del combo al cerrarse el diálogo y vuelva a
        /// disparar el evento. Prioridad Background: se ejecuta cuando la cola de
        /// entrada (incluido cualquier re-disparo espurio del combo) ya se ha drenado.
        /// </summary>
        public static void Post(Action action)
        {
            if (action == null) return;
            if (_ui == null) { action(); return; }  // sin dispatcher: mejor síncrono que nada
            _ui.BeginInvoke(DispatcherPriority.Background, action);
        }
    }
}
