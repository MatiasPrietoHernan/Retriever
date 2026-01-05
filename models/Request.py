from pydantic import BaseModel
from typing import Optional, List

class SearchRequest(BaseModel):
    query: str
    tipo_operacion: Optional[str] = None
    precio_max: Optional[float] = None
    limit: int = 10

class SearchResponse(BaseModel):
    results: List[dict]
    count: int

class TaskResponse(BaseModel):
    task_id: str
    status: str
    check_url: str

class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    results: Optional[List[dict]] = None
    count: Optional[int] = None
    error: Optional[str] = None
    meta: Optional[dict] = None

class IngestsProperties(BaseModel):
    company:str
    tokko_api_key:str
    