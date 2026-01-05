from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, SparseVector, Distance, VectorParams, SparseVectorParams
from langchain_openai import OpenAIEmbeddings
from fastembed import SparseTextEmbedding
import requests
import os
import re
from dotenv import load_dotenv
 
# Cargar variables de entorno
load_dotenv()

# Inicializar clientes
client = QdrantClient(
    url=os.getenv("QDRANT_URL"),
    api_key=os.getenv("QDRANT_API_KEY")
)

embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
sparse_embeddings = SparseTextEmbedding(model_name="Qdrant/bm25")

# Opción 1: Borrar colección existente
try:
    client.delete_collection(collection_name="HogarFe")
    print("🗑️ Colección borrada exitosamente")
except Exception as e:
    print(f"ℹ️ La colección no existía: {e}")

# Crear colección con los nombres de vectores ORIGINALES
client.create_collection(
    collection_name="HogarFe",
    vectors_config={
        "vector": VectorParams(size=1536, distance=Distance.COSINE),  # ¡NOMBRE ORIGINAL!
    },
    sparse_vectors_config={
        "text": SparseVectorParams()  # ¡NOMBRE ORIGINAL!
    }
)

print("✅ Colección 'HogarFe' creada con nombres de vectores originales")

# Fetch propiedades desde Tokko
print("📡 Obteniendo propiedades desde la API...")
response = requests.get(
    "https://www.tokkobroker.com/api/v1/property/?limit=1000&key=d06386b691e6bbb68bcee1b51b7d44f39ccc6ee1&lang=es_ar",
    headers={"Accept": "application/json"}
)

if response.status_code != 200:
    print(f"❌ Error al obtener datos: {response.status_code}")
    exit(1)

props = response.json().get("objects", [])
print(f"✅ Se encontraron {len(props)} propiedades.")

# Preparar documentos
documents = []
points = []

print("🔄 Procesando propiedades...")

for idx, item in enumerate(props):
    # Extraer campos COMO EN EL NODO N8N
    id_prop = item.get("id")
    titulo = item.get("publication_title", "")
    
    # Descripción (limpia como en n8n)
    descripcion = item.get("rich_description") or item.get("description", "")
    if descripcion:
        descripcion = re.sub(r'<[^>]*>', '', descripcion)
        descripcion = descripcion.replace('&nbsp;', ' ').strip()
    
    direccion = item.get("real_address") or item.get("address", "")
    ubicacion = item.get("location", {}).get("full_location", "")
    tipo = item.get("type", {}).get("name", "")
    
    # Precio y moneda
    precio = ""
    moneda = ""
    tipo_operation = "unknown"
    
    if item.get("operations") and len(item["operations"]) > 0:
        operation = item["operations"][0]
        tipo_operation = operation.get("operation_type", "").lower()
        if operation.get("prices") and len(operation["prices"]) > 0:
            precio = operation["prices"][0].get("price", "")
            moneda = operation["prices"][0].get("currency", "")
    
    link = item.get("public_url", "")
    superficie = item.get("surface", "")
    ambientes = item.get("room_amount", "")
    banos = item.get("bathroom_amount", "")
    
    # Teléfono sucursal (armado como en n8n)
    branch = item.get("branch", {})
    telefono_sucursal_codigo = branch.get("alternative_phone_country_code", "")
    telefono_sucursal_area = branch.get("alternative_phone_area", "")
    telefono_sucursal_numero = branch.get("alternative_phone", "")
    
    telefono_sucursal = ''.join([
        telefono_sucursal_codigo,
        telefono_sucursal_area,
        telefono_sucursal_numero
    ])
    
    # Teléfono productor
    telefono_productor = item.get("producer", {}).get("phone", "")
    
    # Construir texto EXACTAMENTE como en n8n
    texto = f"""🏡 {titulo} 💰 Precio: {moneda} {precio}
📍 {direccion} - {ubicacion}
📐 Tipo: {tipo} | Sup: {superficie} m²
🛏️ Ambientes: {ambientes} | 🚿 Baños: {banos}
☎️ Sucursal: {telefono_sucursal or 'No informado'}
👤 Productor: {telefono_productor or 'No informado'}
🔗 Link: {link}

{descripcion}
--------------------------"""
    
    # Metadata completo (puedes ajustar según lo que necesites)
    metadata = {
        "empresa": "hogarfe",
        "id_propiedad": id_prop,
        "tipo_operacion": tipo_operation,
        "precio": precio,
        "moneda": moneda,
        "telefono_sucursal": telefono_sucursal,
        "telefono_productor": telefono_productor,
        "titulo": titulo,
        "direccion": direccion,
        "ubicacion": ubicacion,
        "tipo": tipo,
        "superficie": superficie,
        "ambientes": ambientes,
        "banos": banos,
        "link": link
    }
    
    documents.append({
        "content": texto,
        "metadata": metadata
    })
    
    # Mostrar progreso
    if (idx + 1) % 50 == 0:
        print(f"  📊 Procesadas {idx + 1}/{len(props)} propiedades...")

print(f"✅ Todas las {len(documents)} propiedades procesadas")
print("🔄 Generando embeddings...")

# Generar sparse embeddings en batch
try:
    sparse_vectors = list(sparse_embeddings.embed([doc["content"] for doc in documents]))
    print(f"✅ Sparse embeddings generados para {len(sparse_vectors)} documentos")
except Exception as e:
    print(f"❌ Error generando sparse embeddings: {e}")
    exit(1)

# Preparar puntos con HYBRID SEARCH - USANDO NOMBRES ORIGINALES
print("🔧 Preparando puntos para Qdrant...")

for idx, doc in enumerate(documents):
    try:
        # Dense vector (OpenAI)
        dense_vector = embeddings.embed_query(doc["content"])
        
        # Sparse vector (BM25)
        sparse_emb = sparse_vectors[idx]
        sparse_vector = SparseVector(
            indices=sparse_emb.indices.tolist(),
            values=sparse_emb.values.tolist()
        )
        
        # ¡¡IMPORTANTE!! Usar nombres ORIGINALES: "vector" y "text"
        point = PointStruct(
            id=doc["metadata"]["id_propiedad"],
            vector={
                "vector": dense_vector,    # ¡NOMBRE ORIGINAL para dense!
                "text": sparse_vector       # ¡NOMBRE ORIGINAL para sparse!
            },
            payload={
                "content": doc["content"],
                "metadata": doc["metadata"]
            }
        )
        points.append(point)
        
        # Mostrar progreso
        if (idx + 1) % 25 == 0:
            print(f"  🔄 Preparado punto {idx + 1}/{len(documents)}...")
            
    except Exception as e:
        print(f"⚠️  Error procesando documento {idx}: {e}")
        continue

print(f"✅ {len(points)} puntos preparados para subir")

# Subir puntos
print("📤 Subiendo puntos a Qdrant...")
try:
    operation_info = client.upsert(
        collection_name="HogarFe",
        points=points,
        wait=True
    )
    print(f"✅ {len(points)} propiedades subidas exitosamente!")
    
except Exception as e:
    print(f"❌ Error subiendo puntos: {e}")
    exit(1)

# Verificar colección
try:
    collection_info = client.get_collection("HogarFe")
    print(f"🎯 Total de puntos en colección: {collection_info.points_count}")
    
    # Verificar nombres de vectores
    print(f"📊 Nombres de vectores configurados:")
    if hasattr(collection_info.config.params, 'vectors'):
        print(f"  - Dense vectors: {list(collection_info.config.params.vectors.keys())}")
    if hasattr(collection_info.config.params, 'sparse_vectors'):
        print(f"  - Sparse vectors: {list(collection_info.config.params.sparse_vectors.keys())}")
        
except Exception as e:
    print(f"⚠️  Error obteniendo información de la colección: {e}")

# Opción 2: Si NO quieres borrar toda la colección, usa esto en lugar de delete/create
# Simplemente haz upsert y Qdrant actualizará los puntos existentes

print("\n✅ ¡Script ejecutado! Tu microservicio debería funcionar ahora.")
print("🔍 Los vectores se llaman 'vector' (dense) y 'text' (sparse)")