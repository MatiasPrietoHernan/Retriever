from qdrant_client.models import SparseVector, Prefetch, Fusion
from typing import List, Dict, Any
from qdrant_client import QdrantClient
from qdrant_client.models import FusionQuery
from langchain_openai import OpenAIEmbeddings
from fastembed import SparseTextEmbedding
from qdrant_client.models import Filter, FieldCondition, MatchValue, Range

class HybridSearchService:
    def __init__(self, client, embeddings, sparse_embeddings, collection: str):
        self.client = client
        self.embeddings = embeddings
        self.sparse_embeddings = sparse_embeddings
        self.collection = collection
    
    def search(self, query: str, limit: int = 10) -> List[Dict]:
        """
        Búsqueda híbrida usando dense + sparse vectors con RRF
        """
        dense_vector = self.embeddings.embed_query(query)
        
        sparse_emb = list(self.sparse_embeddings.embed([query]))[0]
        sparse_vector = SparseVector(
            indices=sparse_emb.indices.tolist(),
            values=sparse_emb.values.tolist()
        )
        
        results = self.client.query_points(
            collection_name=self.collection,
            prefetch=[
                Prefetch(query=dense_vector, using="vector", limit=limit * 2),
                Prefetch(query=sparse_vector, using="text", limit=limit * 2)
            ],
            query=FusionQuery(fusion="rrf"),  
            limit=limit,
            with_payload=True
        )
        
        return [
            {
                "id": point.id,
                "score": point.score,
                "content": point.payload.get("content"),
                "metadata": point.payload.get("metadata")
            }
            for point in results.points
        ]
    
    def search_with_filters(self, query: str, tipo_operacion: str = None, 
                           precio_max: float = None, limit: int = 10) -> List[Dict]:
        """
        Búsqueda híbrida con filtros
        """

        
        # Esto construye los filtros basados en los parámetros
        conditions = []
        if tipo_operacion:
            conditions.append(
                FieldCondition(
                    key="metadata.tipo_operacion",
                    match=MatchValue(value=tipo_operacion.lower()) # Aqui definimos las condiciones, en esta coso tipo 
                    # de operación (Venta o Alquiler)
                )
            )
        if precio_max:
            conditions.append(
                FieldCondition(
                    key="metadata.precio",
                    range=Range(lte=precio_max) # En este caso definimos el filtro de precio máximo. Esto es una puta locura. Ya
                ) # no se pasa más del precio proporcionado.
            )
        
        filter_query = Filter(must=conditions) if conditions else None # Aquí armamos la condición final del filtro.
        
        dense_vector = self.embeddings.embed_query(query) # Estos son los vectores densos (Embeddings normales: Capturan semántica)
        sparse_emb = list(self.sparse_embeddings.embed([query]))[0] # Estos son los vectores dispersos (Capturan keywords)
        sparse_vector = SparseVector(
            indices=sparse_emb.indices.tolist(),
            values=sparse_emb.values.tolist()
        )
        
        results = self.client.query_points(
            collection_name=self.collection,
            prefetch=[
                Prefetch(query=dense_vector, using="vector", limit=limit * 2, filter=filter_query),
                Prefetch(query=sparse_vector, using="text", limit=limit * 2, filter=filter_query)
            ],
            query=FusionQuery(fusion="rrf"),
            limit=limit,
            with_payload=True
        )
        
        return [
            {
                "id": point.id,
                "score": point.score,
                "content": point.payload.get("content"),
                "metadata": point.payload.get("metadata")
            }
            for point in results.points
        ]