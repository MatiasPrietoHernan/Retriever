from qdrant_client import QdrantClient
from langchain_openai import OpenAIEmbeddings
from fastembed import SparseTextEmbedding
from dotenv import load_dotenv
import os

load_dotenv()

config = {
    "embedding_model": os.getenv("MODEL_EMBEDDING", "text-embedding-3-small"),
    "api_key": os.getenv("API_KEY"),
    "qdrant_host": os.getenv("QDRANT_HOST", "localhost"),
    "qdrant_port": os.getenv("QDRANT_PORT", 6333)
}

client = QdrantClient(host=config["qdrant_host"], port=config["qdrant_port"])
embeddings = OpenAIEmbeddings(model=config["embedding_model"])
sparse_embeddings = SparseTextEmbedding(model_name="Qdrant/bm25")