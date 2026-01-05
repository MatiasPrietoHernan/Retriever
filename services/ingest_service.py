from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, SparseVector, Distance, VectorParams, SparseVectorParams
import requests
import re
from lib.config import client, embeddings, sparse_embeddings
from utils.logger import logger

def ingest_properties(company:str, api_key:str) -> str:
    """This services ingests property data into the Qdrant collection."""
    # First things first: delete existing collection. Why? Because we don't know if there are semantic changes.
    try:
        client.delete_collection(collection_name=company)
        logger.info("🗑️ Colección borrada exitosamente")
    except Exception as e:
        logger.info(f"ℹ️ La colección no existía: {e}")
    # Now, let's create the collection.
    try:
        client.create_collection(
        collection_name=company,
        vectors_config={
            "vector": VectorParams(size=1536, distance=Distance.COSINE),  # ¡NOMBRE ORIGINAL!
        },
        sparse_vectors_config={
            "text": SparseVectorParams()  
        })
    except Exception as e:
        logger.error(f"❌ Error al crear la colección: {e}")
        return "Error al crear la colección"
    logger.info(f"✅ Colección '{company}' creada con nombres de vectores originales")
    # Fetch properties from Tokko API
    try:
        logger.info("📡 Obteniendo propiedades desde la API...")
        response = requests.get(
            f"https://www.tokkobroker.com/api/v1/property/?limit=1000&key={api_key}&lang=es_ar",
            headers={"Accept": "application/json"}
        )
        logger.info(f"---- Repuesta recibida: {response.status_code} ----")
        if response.status_code != 200:
            logger.error(f"❌ Error al obtener datos: {response.status_code}")
            return "Error al obtener datos de la API"
        props = response.json().get("objects", [])
        logger.info(f"✅ Se encontraron {len(props)} propiedades.")
    except Exception as e:
        logger.error(f"❌ Error al conectar con la API: {e}")
        return "Error al conectar con la API"
    # Prepare documents
    documents = []
    points = []
    logger.info("🔄 Procesando propiedades...")

    for idx, item in enumerate(props):
        try:
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
                logger.info(f"  📊 Procesadas {idx + 1}/{len(props)} propiedades...")

            logger.info(f"✅ Todas las {len(documents)} propiedades procesadas")
        except Exception as e:
            logger.error(f"❌ Error al procesar la propiedad ID {item.get('id')}: {e}")
            return "Error al procesar las propiedades"
    # Ingest documents into Qdrant
    try:
        logger.info("--- Ingiriendo documentos en Qdrant ---")
        sparse_vectors = list(sparse_embeddings.embed([doc["content"] for doc in documents]))
        logger.info(f"✅ Sparse embeddings generados para {len(sparse_vectors)} documentos")
    except Exception as e:
        logger.error(f"❌ Error generando sparse embeddings: {e}")
        return "Error generando sparse embeddings"
    # Prepare points for hybrid search.
    try:
        logger.info("🔄 Preparando puntos para ingesta...")
        for idx, doc in enumerate(documents):
            dense_vector = embeddings.embed_query(doc["content"])
            sparse_emb = sparse_vectors[idx] 
            sparse_vector = SparseVector(
                indices=sparse_emb.indices.tolist(),
                values=sparse_emb.values.tolist()
            )
            point = PointStruct(
                id=doc["metadata"]["id_propiedad"],
                vector={
                    "vector": dense_vector,
                    "text": sparse_vector
                },
                payload={
                    "content": doc["content"],
                    "metadata": doc["metadata"]
                }
            )
            points.append(point)
            # Let's show the progress
            if (idx + 1) % 25 == 0:
                logger.info("Preparados {}/{} puntos...".format(idx + 1, len(documents)))
    except Exception as e:
        logger.error(f"❌ Error preparando puntos: {e}")
        return "Error preparando puntos para ingesta"
    # Finally, upload points in batches
    try:
        operation_info = client.upsert(
            collection_name=company,
            points=points,
            wait=True
        )
        logger.info(f"✅ Puntos subidos exitosamente: {operation_info}")
    except Exception as e:
        logger.error(f"❌ Error subiendo puntos a Qdrant: {e}")
        return "Error subiendo puntos a Qdrant"
    return "Ingesta completada exitosamente"

            