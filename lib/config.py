from qdrant_client import QdrantClient
from langchain_openai import OpenAIEmbeddings
from fastembed import SparseTextEmbedding
from dotenv import load_dotenv
import os

load_dotenv()

config = {
    "qdrant_url": os.getenv("QDRANT_URL"),
    "qdrant_key": os.getenv("QDRANT_API_KEY"),
    "embedding_model": os.getenv("MODEL_EMBEDDING", "text-embedding-3-small"),
    "collection": os.getenv("COLLECTION_NAME", "HogarFe"),
    "api_key": os.getenv("API_KEY")
}

client = QdrantClient(url=config["qdrant_url"], api_key=config["qdrant_key"])
embeddings = OpenAIEmbeddings(model=config["embedding_model"])
sparse_embeddings = SparseTextEmbedding(model_name="Qdrant/bm25")