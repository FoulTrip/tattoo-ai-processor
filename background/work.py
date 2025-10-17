"""
Worker para procesamiento de tatuajes con IA usando REVE API.
Ejecutar con: python worker.py
"""

from handlers.rabbitmq_client import get_rabbitmq_client
from handlers.cloudinary_client import get_cloudinary_client
from handlers.ai_client import get_ai_client
from PIL import Image
from io import BytesIO
import traceback
import requests
import os
import time
import json
from typing import Dict, Any, Optional

def send_webhook_result(job_id: str, result_data: Dict[str, Any], socket_id: Optional[str] = None):
    """
    Envía el resultado del procesamiento al webhook del backend principal
    """
    import httpx

    webhook_url = os.getenv('WEBHOOK_URL', "http://core:8000/preview/webhook")

    payload = {
        "jobId": job_id,
        "data": result_data
    }

    if socket_id:
        payload["socketId"] = socket_id

    print(f"Enviando webhook a: {webhook_url}")
    print(f"Payload: {json.dumps(payload, indent=2)}")

    try:
        response = httpx.post(
            webhook_url,
            json=payload,
            timeout=30.0
        )

        if response.status_code == 200:
            print(f"Webhook enviado exitosamente para job {job_id}")
        else:
            print(f"Error en webhook: {response.status_code} - {response.text}")

    except Exception as e:
        print(f"Error enviando webhook: {str(e)}")
        print(f"Tipo de error: {type(e).__name__}")

def process_tattoo_task(message: dict):
    """
    Procesa una tarea de aplicación de tatuaje con IA.

    Args:
        message: Diccionario con los datos de la tarea desde RabbitMQ

    Estructura esperada del mensaje:
    {
        "task_type": "tattoo_application",
        "body_filename": "body_xxxxx",
        "tattoo_filename": "tattoo_xxxxx",
        "input_bucket": "input-images",
        "output_bucket": "output-images",
        "metadata": {...}
    }
    """
    start_time = time.time()
    result_url = None
    try:
        # Extraer datos del mensaje
        task_type = message.get("task_type")
        body_filename = message.get("body_filename")
        tattoo_filename = message.get("tattoo_filename")
        input_folder = message.get("input_folder", "input-images")
        output_folder = message.get("output_folder", "output-images")
        metadata = message.get("metadata", {})
        
        # Validaciones
        if not task_type:
            print(f"Error: 'task_type' no encontrado en el mensaje")
            return

        if task_type != "tattoo_application":
            print(f"Tipo de tarea desconocido: {task_type}")
            return

        if not body_filename:
            print(f"Error: 'body_filename' no encontrado en el mensaje")
            return

        if not tattoo_filename:
            print(f"Error: 'tattoo_filename' no encontrado en el mensaje")
            return
        
        # Mostrar información de la tarea
        print(f"\n{'='*70}")
        print(f"PROCESANDO TAREA DE APLICACIÓN DE TATUAJE CON IA")
        print(f"{'='*70}")
        print(f"Imagen del cuerpo: {body_filename}")
        print(f"Imagen del tatuaje: {tattoo_filename}")
        print(f"Carpeta entrada: {input_folder}")
        print(f"Carpeta salida: {output_folder}")
        print(f"{'='*70}\n")
        
        # Obtener clientes
        cloudinary_client = get_cloudinary_client()
        ai_client = get_ai_client()

        # Paso 1: Descargar imagen del cuerpo desde Cloudinary
        print(f"[1/5] Descargando imagen del cuerpo desde Cloudinary...")
        body_public_id = f"{input_folder}/{body_filename}"
        body_data = cloudinary_client.download_file(body_public_id)

        if body_data is None:
            print(f"Error: Imagen del cuerpo '{body_filename}' no encontrada en carpeta '{input_folder}'")
            return

        print(f"Imagen del cuerpo descargada: {len(body_data)} bytes")

        # Paso 2: Descargar imagen del tatuaje desde Cloudinary
        print(f"[2/5] Descargando imagen del tatuaje desde Cloudinary...")
        tattoo_public_id = f"{input_folder}/{tattoo_filename}"
        tattoo_data = cloudinary_client.download_file(tattoo_public_id)

        if tattoo_data is None:
            print(f"Error: Imagen del tatuaje '{tattoo_filename}' no encontrada en carpeta '{input_folder}'")
            return

        print(f"Imagen del tatuaje descargada: {len(tattoo_data)} bytes")

        # Paso 3: Aplicar tatuaje con IA
        print(f"[3/5] Aplicando tatuaje con REVE AI...")
        print(f"Esto puede tardar 10-30 segundos...")
        
        # Extraer estilos y colores del mensaje si existen
        styles = message.get("styles", [])
        colors = message.get("colors", [])
        description = message.get("description", "")

        result_bytes = ai_client.apply_tattoo_to_body(
            body_image_bytes=body_data,
            tattoo_image_bytes=tattoo_data,
            styles=styles,
            colors=colors,
            description=description
        )

        print(f"IA procesó la imagen exitosamente: {len(result_bytes)} bytes")

        # Paso 4: Validar que la imagen generada sea válida
        print(f"[4/5] Validando imagen generada...")
        try:
            result_img = Image.open(BytesIO(result_bytes))
            width, height = result_img.size
            img_format = result_img.format or 'PNG'
            print(f"Imagen válida: {width}x{height}, formato: {img_format}")
        except Exception as e:
            print(f"Error: La imagen generada no es válida: {e}")
            return

        # Paso 5: Guardar resultado en Cloudinary
        print(f"[5/5] Guardando resultado en Cloudinary...")
        result_filename = f"result_{body_filename}"

        result_public_id = f"{output_folder}/{result_filename}"
        cloudinary_client.upload_file(
            folder=output_folder,
            public_id=result_filename,
            file_content=result_bytes,
            content_type='image/png'
        )

        print(f"Imagen con tatuaje guardada en: {output_folder}/{result_filename}")

        # Generar URL simple para visualizar el resultado
        try:
            result_url = cloudinary_client.get_file_url(
                result_public_id,
                use_presigned=False  # Usar URL simple sin firma
            )
            print(f"URL simple: {result_url}")
        except Exception as e:
            print(f"No se pudo generar URL: {e}")

        processing_time = time.time() - start_time

        # Resumen final
        print(f"\n{'='*70}")
        print(f"TAREA COMPLETADA EXITOSAMENTE!")
        print(f"{'='*70}")
        print(f"Resumen:")
        print(f"   • Entrada cuerpo: {input_folder}/{body_filename}")
        print(f"   • Entrada tatuaje: {input_folder}/{tattoo_filename}")
        print(f"   • Salida resultado: {output_folder}/{result_filename}")
        print(f"   • Tamaño resultado: {len(result_bytes)} bytes")
        print(f"   • Resolución: {width}x{height}")
        print(f"{'='*70}\n")

        # Enviar resultado al webhook
        job_id = metadata.get("jobId")
        socket_id = metadata.get("socketId")
        print(f"Intentando enviar webhook - jobId: {job_id}, socketId: {socket_id}")
        if job_id:
            result_data = {
                "result_url": result_url,
                "processing_time": processing_time,
                "status": "completed",
                "original_body_filename": body_filename,
                "original_tattoo_filename": tattoo_filename
            }
            send_webhook_result(job_id, result_data, socket_id)
        else:
            print("No se envio webhook: jobId no encontrado en metadata")

    except Exception as e:
        print(f"\n{'='*70}")
        print(f"ERROR FATAL AL PROCESAR TAREA")
        print(f"{'='*70}")
        print(f"Error: {str(e)}")
        print(f"\nStack trace completo:")
        print(traceback.format_exc())
        print(f"{'='*70}\n")

        # No enviar webhook en caso de error, solo en éxito

        # Re-lanzar la excepción para que RabbitMQ reencole el mensaje
        raise


def process_legacy_image_task(message: dict):
    """
    Procesa tareas antiguas de image_processing (sin IA).
    Mantiene compatibilidad con el formato anterior.
    """
    try:
        filename = message.get("filename")
        bucket = message.get("bucket")
        metadata = message.get("metadata", {})
        
        # Validaciones
        if not filename:
            print(f"Error: 'filename' no encontrado en el mensaje")
            return

        if not bucket:
            print(f"Error: 'bucket' no encontrado en el mensaje")
            return
        
        print(f"\n{'='*60}")
        print(f"Procesando tarea legacy (sin IA)")
        print(f"Archivo: {filename}")
        print(f"Bucket: {bucket}")
        print(f"{'='*60}\n")
        
        # Obtener el cliente de Cloudinary
        cloudinary_client = get_cloudinary_client()

        # Descargar la imagen
        print(f"Descargando imagen desde Cloudinary...")
        public_id = f"{bucket}/{filename}"
        image_data = cloudinary_client.download_file(public_id)
        
        if image_data is None:
            print(f"Error: Imagen '{filename}' no encontrada")
            return

        # Procesar con Pillow (thumbnail simple)
        print(f"Creando thumbnail...")
        img = Image.open(BytesIO(image_data))
        img.thumbnail((300, 300))
        
        # Guardar
        output_buffer = BytesIO()
        img.save(output_buffer, format=img.format or 'PNG')
        output_buffer.seek(0)
        
        processed_filename = f"processed_{filename}"
        cloudinary_client.upload_file(
            folder=bucket,
            public_id=processed_filename,
            file_content=output_buffer.getvalue(),
            content_type=metadata.get('content_type', 'image/png')
        )
        
        print(f"Tarea legacy completada: {processed_filename}\n")
        
    except Exception as e:
        print(f"Error en tarea legacy: {e}")
        raise


def route_message(message: dict):
    """
    Enruta el mensaje al procesador correcto según el tipo de tarea.
    """
    task_type = message.get("task_type")

    if task_type == "tattoo_application":
        process_tattoo_task(message)
    elif task_type == "image_processing":
        process_legacy_image_task(message)
    else:
        print(f"Tipo de tarea desconocido: {task_type}")


def main():
    """Función principal del worker."""
    print("\n" + "="*70)
    print("WORKER DE PROCESAMIENTO DE TATUAJES CON IA")
    print("="*70)
    print("Powered by REVE")
    print("="*70 + "\n")
    
    try:
        # Inicializar clientes
        print("Inicializando servicios...\n")
        
        rabbitmq_client = get_rabbitmq_client()
        print(f"RabbitMQ conectado")

        cloudinary_client = get_cloudinary_client()
        print(f"Cloudinary conectado")

        ai_client = get_ai_client()
        print(f"REVE AI conectado")

        print(f"\n{'='*70}")
        print(f"ESPERANDO TAREAS EN LA COLA: '{rabbitmq_client.queue_name}'")
        print(f"{'='*70}")
        print(f"Presiona CTRL+C para detener el worker\n")
        
        # Consumir mensajes de forma continua
        rabbitmq_client.consume_messages(
            callback=route_message,
            auto_ack=False  # Confirmar manualmente después de procesar
        )
        
    except KeyboardInterrupt:
        print(f"\n\n{'='*70}")
        print(f"WORKER DETENIDO POR EL USUARIO")
        print(f"{'='*70}\n")
    except Exception as e:
        print(f"\n\n{'='*70}")
        print(f"ERROR FATAL EN EL WORKER")
        print(f"{'='*70}")
        print(f"Error: {str(e)}")
        print(f"\nStack trace:")
        print(traceback.format_exc())
        print(f"{'='*70}\n")
        raise
    finally:
        print("Worker finalizado\n")


if __name__ == "__main__":
    main()