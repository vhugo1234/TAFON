from pydantic import BaseModel

class Token(BaseModel):
    access_token: str
    token_type: str
    schema_name: str
    is_superuser: bool = False # 🚨 NOVO CAMPO