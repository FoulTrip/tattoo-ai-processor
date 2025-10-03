from minio import Minio
from minio.error import S3Error
from io import BytesIO
from typing import Optional
from datetime import timedelta
import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Variables de configuración desde .env
MINIO_URL = os.getenv("MINIO_URL", "localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin")
MINIO_SECURE = os.getenv("MINIO_SECURE", "False").lower() == "true"

class MinIOClient:
    """
    Cliente para la gestión de archivos en MinIO (compatible con S3).
    """
    def __init__(self, url: str, access_key: str, secret_key: str, secure: bool = False):
        try:
            # Inicializa el cliente de MinIO. 'http://' se omite en la URL.
            self.client = Minio(
                url,
                access_key=access_key,
                secret_key=secret_key,
                secure=secure
            )
            print(f"✅ Conexión a MinIO establecida en: {url}")
        except Exception as e:
            print(f"❌ Error al inicializar el cliente de MinIO: {e}")
            raise

    # ------------------------------------
    # METODOS DE GESTIÓN DE ARCHIVOS
    # ------------------------------------

    def upload_file(self, bucket_name: str, object_name: str, file_content: bytes, content_type: str = 'application/octet-stream') -> str:
        """Sube contenido binario (bytes) a un bucket específico."""
        try:
            data_stream = BytesIO(file_content)
            
            # 'length' debe ser el tamaño en bytes del contenido
            result = self.client.put_object(
                bucket_name,
                object_name,
                data_stream,
                length=len(file_content),
                content_type=content_type
            )
            return f"Subido con éxito '{result.object_name}' en el bucket '{result.bucket_name}'."
        except S3Error as e:
            raise Exception(f"Error S3 al subir el archivo: {e}")
        except Exception as e:
            raise Exception(f"Error desconocido al subir el archivo: {e}")

    def download_file(self, bucket_name: str, object_name: str) -> Optional[bytes]:
        """Descarga un archivo del bucket."""
        response = None
        try:
            response = self.client.get_object(bucket_name, object_name)
            return response.read()
        except S3Error as e:
            if e.code == 'NoSuchKey':
                return None  # El archivo no existe
            raise Exception(f"Error S3 al descargar el archivo: {e}")
        except Exception as e:
            raise Exception(f"Error desconocido al descargar el archivo: {e}")
        finally:
            if response:
                response.close()
                response.release_conn()

    def delete_file(self, bucket_name: str, object_name: str) -> str:
        """Elimina un archivo del bucket."""
        try:
            self.client.remove_object(bucket_name, object_name)
            return f"Eliminado con éxito '{object_name}' del bucket '{bucket_name}'."
        except S3Error as e:
            if e.code == 'NoSuchKey':
                 return f"Advertencia: El archivo '{object_name}' no existe en '{bucket_name}' (ya eliminado)."
            raise Exception(f"Error S3 al eliminar el archivo: {e}")
        except Exception as e:
            raise Exception(f"Error desconocido al eliminar el archivo: {e}")

    def file_exists(self, bucket_name: str, object_name: str) -> bool:
        """Verifica si un archivo existe."""
        try:
            self.client.stat_object(bucket_name, object_name)
            return True
        except S3Error as e:
            if e.code == 'NoSuchKey':
                return False
            raise Exception(f"Error S3 al verificar existencia: {e}")
        except Exception as e:
            raise Exception(f"Error desconocido al verificar existencia: {e}")

    def list_files(self, bucket_name: str, prefix: str = "") -> list:
        """Lista todos los archivos en un bucket con un prefijo opcional."""
        try:
            objects = self.client.list_objects(bucket_name, prefix=prefix, recursive=True)
            return [obj.object_name for obj in objects]
        except S3Error as e:
            raise Exception(f"Error S3 al listar archivos: {e}")
        except Exception as e:
            raise Exception(f"Error desconocido al listar archivos: {e}")

    def get_file_url(self, bucket_name: str, object_name: str, expires: int = 3600) -> str:
        """Genera una URL pre-firmada para acceder temporalmente a un archivo."""
        try:
            url = self.client.presigned_get_object(
                bucket_name, 
                object_name, 
                expires=timedelta(seconds=expires)
            )
            return url
        except S3Error as e:
            raise Exception(f"Error S3 al generar URL: {e}")
        except Exception as e:
            raise Exception(f"Error desconocido al generar URL: {e}")

# Instancia global del cliente de MinIO
minio_client: Optional[MinIOClient] = None

def get_minio_client() -> MinIOClient:
    """
    Obtiene la instancia global del cliente de MinIO.
    Si no existe, la crea con las configuraciones por defecto.
    """
    global minio_client
    if minio_client is None:
        minio_client = MinIOClient(
            url=MINIO_URL,
            access_key=MINIO_ACCESS_KEY,
            secret_key=MINIO_SECRET_KEY,
            secure=MINIO_SECURE
        )
    return minio_client