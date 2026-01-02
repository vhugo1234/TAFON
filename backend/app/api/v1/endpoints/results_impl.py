from fastapi import APIRouter

router = APIRouter()

@router.get("/", summary="Resultados - placeholder")
def results_root():
    return {"message": "Resultados - implementação placeholder. Substitua por results_impl real."}

@router.get("/_status", summary="Status do results")
def results_status():
    return {"status": "ok"}