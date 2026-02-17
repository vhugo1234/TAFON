# backend/app/schemas/_compat.py
from pydantic import BaseModel
import pydantic

class OrmModeBase(BaseModel):
    """
    Classe base para modelos que precisam de comportamento 'orm_mode'.
    Para Pydantic v2 definimos model_config; para v1 definimos Config.orm_mode.
    Use: class X(OrmModeBase): ...
    """
    # para pydantic v2
    try:
        # pydantic v2 define __version__ ou version info
        if tuple(map(int, pydantic.__version__.split(".")[:2])) >= (2, 0):
            model_config = {"from_attributes": True}
        else:
            raise Exception()
    except Exception:
        class Config:
            orm_mode = True