from fastapi import FastAPI, File, UploadFile, HTTPException
from PIL import Image
from io import BytesIO
from minio.error import S3Error
from handlers.minio_client import get_minio_client
from handlers.rabbitmq_client import get_rabbitmq_client
from dotenv import load_dotenv
from contextlib import asynccontextmanager
import os
from uuid import uuid4


# Cargar variables de entorno
load_dotenv()

# Nombre de los buckets
INPUT_BUCKET = os.getenv("INPUT_BUCKET", "input-images")
OUTPUT_BUCKET = os.getenv("OUTPUT_BUCKET", "output-images")

# ------------------------------------
# LIFESPAN EVENTS
# ------------------------------------

@asynccontextmanager
async def lifespan(_: FastAPI):
    """Gestiona el ciclo de vida de la aplicación."""
    # STARTUP
    try:
        # Inicializar MinIO
        minio_client = get_minio_client()
        
        # Verifica y crea los buckets si no existen
        for bucket in [INPUT_BUCKET, OUTPUT_BUCKET]:
            if not minio_client.client.bucket_exists(bucket):
                minio_client.client.make_bucket(bucket)
                print(f"✅ Bucket '{bucket}' creado.")
            else:
                print(f"✅ Bucket '{bucket}' ya existe.")
        
        # Inicializar RabbitMQ
        rabbitmq_client = get_rabbitmq_client()
        print(f"✅ RabbitMQ inicializado correctamente")
        
    except Exception as e:
        print(f"❌ FATAL: Error al inicializar servicios: {e}")
        raise
    
    # Aquí la aplicación está corriendo y manejando requests
    yield
    
    # SHUTDOWN
    try:
        # Cerrar conexión de RabbitMQ
        rabbitmq_client = get_rabbitmq_client()
        rabbitmq_client.close()
    except Exception as e:
        print(f"⚠️  Error al cerrar RabbitMQ: {e}")
    
    print("🔴 Aplicación apagándose.")


# --- Configuración de la Aplicación ---
app = FastAPI(lifespan=lifespan)

# ------------------------------------
# ENDPOINTS
# ------------------------------------

@app.get("/")
def home():
    """Endpoint de health check."""
    try:
        minio_client = get_minio_client()
        rabbitmq_client = get_rabbitmq_client()
        
        # Verificar MinIO
        input_exists = minio_client.client.bucket_exists(INPUT_BUCKET)
        output_exists = minio_client.client.bucket_exists(OUTPUT_BUCKET)
        
        # Verificar RabbitMQ
        queue_size = rabbitmq_client.get_queue_size()
        
        return {
            "status": "ok",
            "services": {
                "minio": {
                    "status": "conectado",
                    "input_bucket": INPUT_BUCKET,
                    "input_status": "disponible" if input_exists else "no encontrado",
                    "output_bucket": OUTPUT_BUCKET,
                    "output_status": "disponible" if output_exists else "no encontrado"
                },
                "rabbitmq": {
                    "status": "conectado",
                    "queue": rabbitmq_client.queue_name,
                    "messages_pending": queue_size
                }
            }
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }


@app.post("/upload/")
async def upload_tattoo_images(
    body_image: UploadFile = File(..., description="Imagen del cuerpo con zona roja marcada"),
    tattoo_image: UploadFile = File(..., description="Imagen del tatuaje (PNG preferiblemente sin fondo)")
):
    """
    Recibe dos imágenes para aplicación de tatuaje con IA:
    
    - **body_image**: Foto del cuerpo con la zona roja marcada donde irá el tatuaje
    - **tattoo_image**: Diseño del tatuaje (preferiblemente PNG sin fondo)
    
    Proceso:
    1. Valida que ambos archivos sean imágenes
    2. Extrae metadata (resolución, formato, tamaño)
    3. Sube ambas imágenes a MinIO (bucket: input-images)
    4. Encola tarea de procesamiento con IA en RabbitMQ
    
    Returns:
        Información detallada de ambas imágenes y confirmación de encolado
    """
    
    try:
        minio_client = get_minio_client()
        rabbitmq_client = get_rabbitmq_client()
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Los servicios no están disponibles: {str(e)}"
        )

    # Validación de tipo de archivo para la imagen del cuerpo
    if not body_image.content_type or not body_image.content_type.startswith('image/'):
        raise HTTPException(
            status_code=400,
            detail=f"Tipo de archivo no válido para body_image: {body_image.content_type}. Solo se admiten imágenes."
        )
    
    # Validación de tipo de archivo para la imagen del tatuaje
    if not tattoo_image.content_type or not tattoo_image.content_type.startswith('image/'):
        raise HTTPException(
            status_code=400,
            detail=f"Tipo de archivo no válido para tattoo_image: {tattoo_image.content_type}. Solo se admiten imágenes."
        )

    try:
        # Leer contenido binario de ambas imágenes
        body_content = await body_image.read()
        tattoo_content = await tattoo_image.read()
        
        # Procesar y extraer metadata de la imagen del cuerpo
        body_stream = BytesIO(body_content)
        body_img = Image.open(body_stream)
        body_format = body_img.format
        body_width, body_height = body_img.size
        body_size = len(body_content)
        
        # Procesar y extraer metadata de la imagen del tatuaje
        tattoo_stream = BytesIO(tattoo_content)
        tattoo_img = Image.open(tattoo_stream)
        tattoo_format = tattoo_img.format
        tattoo_width, tattoo_height = tattoo_img.size
        tattoo_size = len(tattoo_content)

        # Generar nombres únicos con prefijos descriptivos
        body_filename = f"body_{uuid4()}"
        tattoo_filename = f"tattoo_{uuid4()}"
        
        # Subir imagen del cuerpo a MinIO
        print(f"⬆️  Subiendo imagen del cuerpo: {body_filename}")
        body_upload_result = minio_client.upload_file(
            bucket_name=INPUT_BUCKET,
            object_name=body_filename,
            file_content=body_content,
            content_type=body_image.content_type
        )
        
        # Subir imagen del tatuaje a MinIO
        print(f"⬆️  Subiendo imagen del tatuaje: {tattoo_filename}")
        tattoo_upload_result = minio_client.upload_file(
            bucket_name=INPUT_BUCKET,
            object_name=tattoo_filename,
            file_content=tattoo_content,
            content_type=tattoo_image.content_type
        )
        
        # Preparar metadata completa para la tarea
        metadata = {
            "body_image": {
                "filename": body_filename,
                "resolution": f"{body_width}x{body_height}",
                "format": body_format,
                "size_bytes": body_size,
                "content_type": body_image.content_type
            },
            "tattoo_image": {
                "filename": tattoo_filename,
                "resolution": f"{tattoo_width}x{tattoo_height}",
                "format": tattoo_format,
                "size_bytes": tattoo_size,
                "content_type": tattoo_image.content_type
            }
        }
        
        # Encolar tarea de procesamiento con IA en RabbitMQ
        print(f"📤 Encolando tarea de aplicación de tatuaje con IA...")
        task_published = rabbitmq_client.publish_message({
            "task_type": "tattoo_application",
            "body_filename": body_filename,
            "tattoo_filename": tattoo_filename,
            "input_bucket": INPUT_BUCKET,
            "output_bucket": OUTPUT_BUCKET,
            "metadata": metadata
        })
        
        if not task_published:
            raise HTTPException(
                status_code=500,
                detail="Error al encolar la tarea en RabbitMQ"
            )
        
        print(f"✅ Tarea encolada exitosamente")
        
        # Respuesta exitosa con información detallada
        return {
            "status": "success",
            "message": "Imágenes recibidas y tarea encolada para procesamiento con IA",
            "body_image": {
                "filename": body_filename,
                "resolution": f"{body_width}x{body_height}",
                "format": body_format,
                "size_bytes": body_size,
                "content_type": body_image.content_type
            },
            "tattoo_image": {
                "filename": tattoo_filename,
                "resolution": f"{tattoo_width}x{tattoo_height}",
                "format": tattoo_format,
                "size_bytes": tattoo_size,
                "content_type": tattoo_image.content_type
            },
            "storage": {
                "input_bucket": INPUT_BUCKET,
                "output_bucket": OUTPUT_BUCKET,
                "body_upload_status": body_upload_result,
                "tattoo_upload_status": tattoo_upload_result
            },
            "queue": {
                "task_queued": task_published,
                "queue_name": rabbitmq_client.queue_name,
                "expected_output": f"result_{body_filename}.png"
            }
        }
        
    except HTTPException:
        raise
    except S3Error as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al subir a MinIO: {e.message}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al procesar o subir las imágenes: {str(e)}"
        )


@app.get("/files/")
def list_files(bucket: str = INPUT_BUCKET, prefix: str = ""):
    """
    Lista todos los archivos en un bucket específico.
    
    - **bucket**: Nombre del bucket (input-images u output-images)
    - **prefix**: Filtro opcional por prefijo (ej: "body_", "tattoo_", "result_")
    """
    try:
        minio_client = get_minio_client()
        files = minio_client.list_files(bucket, prefix=prefix)
        return {
            "bucket": bucket,
            "prefix": prefix,
            "count": len(files),
            "files": files
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al listar archivos: {str(e)}"
        )


@app.get("/files/{bucket}/{filename}")
def get_file_url(bucket: str, filename: str, expires: int = 3600):
    """
    Genera una URL temporal para descargar un archivo.
    
    - **bucket**: Nombre del bucket
    - **filename**: Nombre del archivo
    - **expires**: Tiempo de expiración en segundos (default: 3600 = 1 hora)
    """
    try:
        minio_client = get_minio_client()
        
        # Verificar que el archivo existe
        if not minio_client.file_exists(bucket, filename):
            raise HTTPException(
                status_code=404,
                detail=f"Archivo '{filename}' no encontrado en bucket '{bucket}'"
            )
        
        # Generar URL pre-firmada
        url = minio_client.get_file_url(bucket, filename, expires=expires)
        
        return {
            "bucket": bucket,
            "filename": filename,
            "url": url,
            "expires_in_seconds": expires
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al generar URL: {str(e)}"
        )


@app.delete("/files/{bucket}/{filename}")
def delete_file(bucket: str, filename: str):
    """
    Elimina un archivo del bucket especificado.
    
    - **bucket**: Nombre del bucket
    - **filename**: Nombre del archivo a eliminar
    """
    try:
        minio_client = get_minio_client()
        result = minio_client.delete_file(bucket, filename)
        return {
            "status": "success",
            "message": result
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al eliminar archivo: {str(e)}"
        )


@app.get("/queue/status")
def queue_status():
    """
    Obtiene el estado actual de la cola de RabbitMQ.
    Muestra el número de mensajes pendientes de procesamiento.
    """
    try:
        rabbitmq_client = get_rabbitmq_client()
        queue_size = rabbitmq_client.get_queue_size()
        
        return {
            "queue_name": rabbitmq_client.queue_name,
            "messages_pending": queue_size,
            "status": "active" if queue_size >= 0 else "error"
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al obtener estado de la cola: {str(e)}"
        )


@app.post("/queue/purge")
def purge_queue():
    """
    Elimina todos los mensajes pendientes de la cola de RabbitMQ.
    ⚠️ Usar con precaución: esta acción no se puede deshacer.
    """
    try:
        rabbitmq_client = get_rabbitmq_client()
        result = rabbitmq_client.purge_queue()
        
        if result:
            return {
                "status": "success",
                "message": "Cola purgada exitosamente",
                "queue_name": rabbitmq_client.queue_name
            }
        else:
            raise HTTPException(
                status_code=500,
                detail="No se pudo purgar la cola"
            )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al purgar la cola: {str(e)}"
        )