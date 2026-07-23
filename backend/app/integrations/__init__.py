"""Capa de conectores externos (Fase 8).

Cada conector es un adaptador *simulado* y determinista: implementa la forma
del contrato real (payload de entrada, efecto de dominio, evento de salida)
pero sin credenciales ni red — el punto de enganche real de cada proveedor
queda documentado en el docstring del módulo. Todos los conectores:

  1. se habilitan/deshabilitan por clínica vía IntegrationConfig (un conector
     apagado rechaza el evento), y
  2. dejan traza en integration_events (bandeja de entrada/salida).

Así el resto de la plataforma (agenda, ledger, ficha) se integra con el
mundo exterior por una única frontera tipada y auditable.
"""

SUPPORTED = ("whatsapp", "lab", "farmacia", "pago", "mapas", "push")
