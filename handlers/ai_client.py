"""
Cliente para procesamiento de imágenes con IA usando Reve API.
Combina un tatuaje con una foto de cuerpo en la zona roja marcada.
"""

import os
from dotenv import load_dotenv
from typing import Optional
import requests
import base64
from io import BytesIO

load_dotenv()

# Configuración
REVE_API_KEY = os.getenv("REVE_API_KEY")


class AITattooClient:
    """
    Cliente para aplicar tatuajes en fotos usando IA.
    Usa Reve API con capacidad de remix de imágenes.
    """
    
    def __init__(self, api_token: Optional[str] = None):
        self.api_token = api_token or REVE_API_KEY
        
        if not self.api_token:
            raise ValueError("REVE_API_KEY no está configurado en .env")
        
        self.base_url = "https://api.reve.com/v1/image"
        
        print(f"✅ Cliente de Reve API inicializado")
    
    def _image_bytes_to_base64(self, image_bytes: bytes) -> str:
        """Convierte bytes de imagen a base64 string."""
        return base64.b64encode(image_bytes).decode('utf-8')
    
    def apply_tattoo_to_body(
        self,
        body_image_bytes: bytes,
        tattoo_image_bytes: bytes,
        styles: Optional[list] = None,
        colors: Optional[list] = None,
        description: str = "",
    ) -> bytes:
        """
        Aplica un tatuaje a una foto de cuerpo usando IA.
        La imagen del cuerpo debe tener una zona roja marcada donde irá el tatuaje.

        Args:
            body_image_bytes: Imagen del cuerpo con zona roja marcada
            tattoo_image_bytes: Imagen del tatuaje (PNG sin fondo)
            styles: Lista opcional de estilos para personalizar el tatuaje
            colors: Lista opcional de colores para aplicar al tatuaje
            description: Descripción opcional del usuario sobre cómo quiere el tatuaje

        Returns:
            bytes: Imagen resultante con el tatuaje aplicado de forma hiperrealista

        Raises:
            ValueError: Si la API no genera una imagen válida
            requests.exceptions.RequestException: Si hay error en la petición HTTP
        """
        print(f"🎨 Procesando con IA...")

        # Debug logs
        print(f"🔍 Debug: API Key presente: {'Sí' if self.api_token else 'No'}")
        print(f"🔍 Debug: Tamaño imagen cuerpo: {len(body_image_bytes)} bytes")
        print(f"🔍 Debug: Tamaño imagen tatuaje: {len(tattoo_image_bytes)} bytes")
        
        # Convertir imágenes a base64
        body_base64 = self._image_bytes_to_base64(body_image_bytes)
        tattoo_base64 = self._image_bytes_to_base64(tattoo_image_bytes)
        
        # Construir prompt base
        prompt = (
            "Apply the tattoo design from <img>1</img> onto the body in <img>0</img>, "
            "placing it EXACTLY in the RED MARKED AREA. "
            "Create a photorealistic result with: "
            "- The tattoo seamlessly blended into the skin texture "
            "- Natural lighting and shadows matching the original photo "
            "- Realistic skin texture overlaying the tattoo "
            "- Professional, high-quality tattoo appearance "
            "- The rest of the body unchanged from the original "
            "- Complete removal of the red marking "
            "Generate a hyperrealistic image showing how this tattoo would naturally look on that body part."
        )

        # Agregar descripción del usuario si se proporciona
        if description and description.strip():
            prompt += f" Additional user instructions: {description.strip()}."

        # Agregar estilos si se proporcionan
        if styles and len(styles) > 0:
            styles_text = ", ".join(styles)
            prompt += f" Apply the following styles to the tattoo: {styles_text}."

        # Agregar colores si se proporcionan
        if colors and len(colors) > 0:
            colors_text = ", ".join(colors)
            prompt += f" Use the following colors for the tattoo: {colors_text}."
        
        # Preparar headers
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        
        # Preparar payload
        payload = {
            "prompt": prompt,
            "reference_images": [body_base64, tattoo_base64],
            "aspect_ratio": "1:1",
            "version": "latest"
        }
        
        print(f"🤖 Enviando a Reve API (remix endpoint)...")

        try:
            # Hacer petición a Reve API
            response = requests.post(
                f"{self.base_url}/remix",
                headers=headers,
                json=payload,
                timeout=60  # 60 segundos de timeout
            )
            
            # Verificar status code
            response.raise_for_status()
            
            print(f"✅ Respuesta recibida de Reve API")
            
        except requests.exceptions.HTTPError as e:
            error_msg = f"Error HTTP {e.response.status_code if e.response else 'desconocido'}"
            try:
                if e.response:
                    error_data = e.response.json()
                    error_msg += f": {error_data.get('message', 'Error desconocido')}"
                    if 'error_code' in error_data:
                        error_msg += f" (Código: {error_data['error_code']})"
                else:
                    error_msg += f": {str(e)}"
            except:
                error_msg += f": {e.response.text if e.response else str(e)}"

            print(f"❌ {error_msg}")
            raise ValueError(error_msg)
            
        except requests.exceptions.Timeout:
            print(f"❌ Timeout: La petición tardó más de 60 segundos")
            raise ValueError("Timeout en la petición a Reve API")
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Error en llamada a Reve API: {str(e)}")
            print(f"🔍 Debug: Tipo de error: {type(e).__name__}")
            raise
        
        # Parsear respuesta JSON
        try:
            result = response.json()
        except ValueError as e:
            print(f"❌ Error parseando JSON: {str(e)}")
            raise ValueError("Respuesta inválida de Reve API")
        
        # Verificar violación de políticas de contenido
        if result.get('content_violation', False):
            print(f"⚠️ Advertencia: Violación de política de contenido detectada")
            raise ValueError(
                "La imagen generada viola las políticas de contenido de Reve API"
            )
        
        # Extraer información de la respuesta
        print(f"ℹ️ Request ID: {result.get('request_id', 'N/A')}")
        print(f"ℹ️ Créditos usados: {result.get('credits_used', 'N/A')}")
        print(f"ℹ️ Créditos restantes: {result.get('credits_remaining', 'N/A')}")
        print(f"ℹ️ Versión del modelo: {result.get('version', 'N/A')}")
        
        # Verificar que hay imagen en la respuesta
        if 'image' not in result or not result['image']:
            raise ValueError(
                "Reve API no devolvió una imagen en la respuesta. "
                f"Response: {result}"
            )
        
        # Decodificar imagen de base64 a bytes
        try:
            image_data = base64.b64decode(result['image'])
            print(f"⬇️ Imagen generada decodificada ({len(image_data)} bytes)")
            return image_data
            
        except Exception as e:
            print(f"❌ Error decodificando imagen base64: {str(e)}")
            raise ValueError(f"Error decodificando la imagen generada: {str(e)}")


# Instancia global
ai_client: Optional[AITattooClient] = None


def get_ai_client() -> AITattooClient:
    """Obtiene la instancia global del cliente de IA."""
    global ai_client
    if ai_client is None:
        ai_client = AITattooClient()
    return ai_client