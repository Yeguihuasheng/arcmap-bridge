using System;
using System.Threading;

namespace YghsBridge.AddIn
{
    /// <summary>
    /// Contadores de la sesión en curso, para que el botón "Estado" pueda responder
    /// a la pregunta que de verdad importa cuando algo no va: ¿está llegando el
    /// agente hasta aquí? Se reinician al cerrar ArcMap; no se persisten.
    /// </summary>
    internal static class Estadisticas
    {
        private static int _peticiones;
        private static int _errores;
        private static readonly object _lock = new object();
        private static string _ultimoComando;
        private static DateTime _ultimaHora;
        private static readonly DateTime _inicio = DateTime.Now;

        public static int Peticiones { get { return _peticiones; } }
        public static int Errores { get { return _errores; } }
        public static DateTime Inicio { get { return _inicio; } }

        public static void RegistrarComando(string comando)
        {
            Interlocked.Increment(ref _peticiones);
            lock (_lock)
            {
                _ultimoComando = comando;
                _ultimaHora = DateTime.Now;
            }
        }

        public static void RegistrarError()
        {
            Interlocked.Increment(ref _errores);
        }

        /// <summary>"list_layers (14:32:07)", o "（暂无）".</summary>
        public static string UltimoComando
        {
            get
            {
                lock (_lock)
                {
                    if (_ultimoComando == null) return "（暂无）";
                    return _ultimoComando + " (" + _ultimaHora.ToString("HH:mm:ss") + ")";
                }
            }
        }
    }
}
