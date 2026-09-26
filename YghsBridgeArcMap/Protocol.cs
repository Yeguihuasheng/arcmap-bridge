using System;
using Newtonsoft.Json.Linq;

namespace YghsBridge.AddIn
{
    /// <summary>
    /// Contrato con el servidor MCP (src/yghsbridge_server.py):
    /// request  = un objeto JSON UTF-8 {"type": str, "params": {...}} en una conexión nueva;
    /// response = un único objeto JSON y cierre de la conexión (el servidor lee hasta EOF).
    /// Sobre: éxito = {"ok": true, "result": {...}};
    ///        error  = {"ok": false, "error": str[, "traceback": str]}.
    /// </summary>
    internal static class Protocol
    {
        public static JObject Result(JObject inner)
        {
            return new JObject { ["ok"] = true, ["result"] = inner };
        }

        public static JObject Error(string message)
        {
            return new JObject { ["ok"] = false, ["error"] = message };
        }

        public static JObject Error(string message, Exception ex)
        {
            return new JObject
            {
                ["ok"] = false,
                ["error"] = message,
                ["traceback"] = ex.ToString()
            };
        }
    }
}
