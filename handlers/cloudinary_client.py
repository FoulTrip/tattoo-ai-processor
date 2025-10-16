import cloudinary
import cloudinary.uploader
import cloudinary.api
from io import BytesIO
from typing import Optional
import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Variables de configuración desde .env
CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY")
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET")

class CloudinaryClient:
    """
    Cliente para la gestión de archivos en Cloudinary.
    """
    def __init__(self, cloud_name: str, api_key: str, api_secret: str):
        try:
            # Configurar Cloudinary
            cloudinary.config(
                cloud_name=cloud_name,
                api_key=api_key,
                api_secret=api_secret
            )
            print(f"✅ Conexión a Cloudinary establecida para cloud: {cloud_name}")
        except Exception as e:
            print(f"❌ Error al inicializar el cliente de Cloudinary: {e}")
            raise

    # ------------------------------------
    # METODOS DE GESTIÓN DE ARCHIVOS
    # ------------------------------------

    def upload_file(self, folder: str, public_id: str, file_content: bytes, content_type: str = 'auto') -> str:
        """Sube contenido binario (bytes) a Cloudinary."""
        try:
            data_stream = BytesIO(file_content)

            result = cloudinary.uploader.upload(
                data_stream,
                folder=folder,
                public_id=public_id,
                resource_type='auto',
                use_filename=False,
                unique_filename=False
            )
            return f"Subido con éxito '{result['public_id']}' en la carpeta '{folder}'."
        except Exception as e:
            raise Exception(f"Error al subir el archivo: {e}")

    def download_file(self, public_id: str) -> Optional[bytes]:
        """Descarga un archivo de Cloudinary."""
        try:
            # Cloudinary no tiene descarga directa, usamos la URL para obtener el contenido
            url = cloudinary.utils.cloudinary_url(public_id)[0]
            import requests
            response = requests.get(url)
            if response.status_code == 200:
                return response.content
            else:
                return None
        except Exception as e:
            raise Exception(f"Error al descargar el archivo: {e}")

    def delete_file(self, public_id: str) -> str:
        """Elimina un archivo de Cloudinary."""
        try:
            result = cloudinary.uploader.destroy(public_id)
            if result['result'] == 'ok':
                return f"Eliminado con éxito '{public_id}'."
            else:
                return f"Advertencia: El archivo '{public_id}' no se pudo eliminar."
        except Exception as e:
            raise Exception(f"Error al eliminar el archivo: {e}")

    def file_exists(self, public_id: str) -> bool:
        """Verifica si un archivo existe en Cloudinary."""
        try:
            # Intentar obtener información del archivo
            cloudinary.api.resource(public_id)
            return True
        except Exception as e:
            # Cloudinary lanza una excepción genérica cuando no encuentra el recurso
            if "not found" in str(e).lower() or "404" in str(e):
                return False
            raise Exception(f"Error al verificar existencia: {e}")

    def list_files(self, folder: str, prefix: str = "") -> list:
        """Lista todos los archivos en una carpeta con un prefijo opcional."""
        try:
            result = cloudinary.api.resources(
                type='upload',
                prefix=f"{folder}/{prefix}" if prefix else folder,
                max_results=500
            )
            return [resource['public_id'] for resource in result['resources']]
        except Exception as e:
            raise Exception(f"Error al listar archivos: {e}")

    def get_file_url(self, public_id: str, expires: int = 3600, use_presigned: bool = False) -> str:
        """
        Genera una URL para acceder a un archivo.

        Args:
            public_id: ID público del archivo
            expires: Segundos de expiración (solo para URLs pre-firmadas)
            use_presigned: Si True, genera URL pre-firmada (segura pero requiere sincronización de reloj)
                           Si False, genera URL simple (pública, sin firma)

        Returns:
            URL para acceder al archivo
        """
        try:
            if use_presigned:
                # URL pre-firmada (requiere sincronización perfecta de credenciales y reloj)
                import time
                expires_at = int(time.time()) + expires

                url, options = cloudinary.utils.cloudinary_url(
                    public_id,
                    sign_url=True,
                    expires_at=expires_at
                )
                return url
            else:
                # URL simple (pública, sin firma)
                url, options = cloudinary.utils.cloudinary_url(
                    public_id,
                    sign_url=False
                )
                return url
        except Exception as e:
            raise Exception(f"Error al generar URL: {e}")

# Instancia global del cliente de Cloudinary
cloudinary_client: Optional[CloudinaryClient] = None

def get_cloudinary_client() -> CloudinaryClient:
    """
    Obtiene la instancia global del cliente de Cloudinary.
    Si no existe, la crea con las configuraciones por defecto.
    """
    global cloudinary_client
    if cloudinary_client is None:
        if not CLOUDINARY_CLOUD_NAME or not CLOUDINARY_API_KEY or not CLOUDINARY_API_SECRET:
            raise ValueError("Las variables de entorno de Cloudinary no están configuradas correctamente.")
        cloudinary_client = CloudinaryClient(
            cloud_name=CLOUDINARY_CLOUD_NAME,
            api_key=CLOUDINARY_API_KEY,
            api_secret=CLOUDINARY_API_SECRET
        )
    return cloudinary_client