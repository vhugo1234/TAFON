from importlib import import_module
from fastapi import APIRouter
import traceback

# Tenta reusar um router já definido em uma implementação real (por exemplo results_impl)
# ou outro nome; procura por 'router' no próprio módulo se possível.
def _find_router():
    # 1) se houver um módulo implemente separado, tente importá-lo
    candidates = [
        "app.api.v1.endpoints.results_impl",
        "app.api.v1.endpoints._results",
        "app.api.v1.endpoints.results_module",
        "app.api.v1.endpoints.results",  # tentativa de reimportar próprio módulo (circular safe guard)
    ]
    for name in candidates:
        try:
            mod = import_module(name)
            r = getattr(mod, "router", None)
            if r is not None:
                return r
        except Exception:
            # ignora e tenta próximo candidato
            traceback.print_exc()
    return None

_router = _find_router()
if _router is None:
    # Fallback: cria um router placeholder para manter a aplicação no ar.
    _router = APIRouter()

    @_router.get("/taf/results/_placeholder", tags=["TAF - Resultados"])
    def _results_placeholder():
        return {"warning": "Placeholder router for TAF results — implement real endpoints in app.api.v1.endpoints.results or results_impl."}

# Expor o router com o nome esperado por api_router
router = _router