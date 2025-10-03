"""
Worker para procesamiento de tatuajes con IA usando Google Gemini.
Ejecutar con: python worker.py
"""

from handlers.rabbitmq_client import get_rabbitmq_client
from handlers.minio_client import get_minio_client
from handlers.ai_client import get_ai_client
from PIL import Image
from io import BytesIO
import traceback

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
    try:
        # Extraer datos del mensaje
        task_type = message.get("task_type")
        body_filename = message.get("body_filename")
        tattoo_filename = message.get("tattoo_filename")
        input_bucket = message.get("input_bucket", "input-images")
        output_bucket = message.get("output_bucket", "output-images")
        metadata = message.get("metadata", {})
        
        # Validaciones
        if not task_type:
            print(f"❌ Error: 'task_type' no encontrado en el mensaje")
            return
        
        if task_type != "tattoo_application":
            print(f"⚠️  Tipo de tarea desconocido: {task_type}")
            return
        
        if not body_filename:
            print(f"❌ Error: 'body_filename' no encontrado en el mensaje")
            return
            
        if not tattoo_filename:
            print(f"❌ Error: 'tattoo_filename' no encontrado en el mensaje")
            return
        
        # Mostrar información de la tarea
        print(f"\n{'='*70}")
        print(f"🎨 PROCESANDO TAREA DE APLICACIÓN DE TATUAJE CON IA")
        print(f"{'='*70}")
        print(f"📁 Imagen del cuerpo: {body_filename}")
        print(f"🖼️  Imagen del tatuaje: {tattoo_filename}")
        print(f"📂 Bucket entrada: {input_bucket}")
        print(f"📂 Bucket salida: {output_bucket}")
        print(f"{'='*70}\n")
        
        # Obtener clientes
        minio_client = get_minio_client()
        ai_client = get_ai_client()
        
        # Paso 1: Descargar imagen del cuerpo desde MinIO
        print(f"⬇️  [1/5] Descargando imagen del cuerpo desde MinIO...")
        body_data = minio_client.download_file(input_bucket, body_filename)
        
        if body_data is None:
            print(f"❌ Error: Imagen del cuerpo '{body_filename}' no encontrada en bucket '{input_bucket}'")
            return
        
        print(f"✅ Imagen del cuerpo descargada: {len(body_data)} bytes")
        
        # Paso 2: Descargar imagen del tatuaje desde MinIO
        print(f"⬇️  [2/5] Descargando imagen del tatuaje desde MinIO...")
        tattoo_data = minio_client.download_file(input_bucket, tattoo_filename)
        
        if tattoo_data is None:
            print(f"❌ Error: Imagen del tatuaje '{tattoo_filename}' no encontrada en bucket '{input_bucket}'")
            return
        
        print(f"✅ Imagen del tatuaje descargada: {len(tattoo_data)} bytes")
        
        # Paso 3: Aplicar tatuaje con IA
        print(f"🤖 [3/5] Aplicando tatuaje con Google Gemini AI...")
        print(f"⏳ Esto puede tardar 10-30 segundos...")
        
        result_bytes = ai_client.apply_tattoo_to_body(
            body_image_bytes=body_data,
            tattoo_image_bytes=tattoo_data
        )
        
        print(f"✅ IA procesó la imagen exitosamente: {len(result_bytes)} bytes")
        
        # Paso 4: Validar que la imagen generada sea válida
        print(f"🔍 [4/5] Validando imagen generada...")
        try:
            result_img = Image.open(BytesIO(result_bytes))
            width, height = result_img.size
            img_format = result_img.format or 'PNG'
            print(f"✅ Imagen válida: {width}x{height}, formato: {img_format}")
        except Exception as e:
            print(f"❌ Error: La imagen generada no es válida: {e}")
            return
        
        # Paso 5: Guardar resultado en MinIO
        print(f"⬆️  [5/5] Guardando resultado en MinIO...")
        result_filename = f"result_{body_filename}.png"
        
        minio_client.upload_file(
            bucket_name=output_bucket,
            object_name=result_filename,
            file_content=result_bytes,
            content_type='image/png'
        )
        
        print(f"✅ Imagen con tatuaje guardada en: {output_bucket}/{result_filename}")
        
        # Generar URL temporal para visualizar el resultado
        try:
            result_url = minio_client.get_file_url(
                bucket_name=output_bucket,
                object_name=result_filename,
                expires=3600  # URL válida por 1 hora
            )
            print(f"🔗 URL temporal (1h): {result_url}")
        except Exception as e:
            print(f"⚠️  No se pudo generar URL temporal: {e}")
        
        # Resumen final
        print(f"\n{'='*70}")
        print(f"✅ ¡TAREA COMPLETADA EXITOSAMENTE!")
        print(f"{'='*70}")
        print(f"📊 Resumen:")
        print(f"   • Entrada cuerpo: {input_bucket}/{body_filename}")
        print(f"   • Entrada tatuaje: {input_bucket}/{tattoo_filename}")
        print(f"   • Salida resultado: {output_bucket}/{result_filename}")
        print(f"   • Tamaño resultado: {len(result_bytes)} bytes")
        print(f"   • Resolución: {width}x{height}")
        print(f"{'='*70}\n")
            
    except Exception as e:
        print(f"\n{'='*70}")
        print(f"❌ ERROR FATAL AL PROCESAR TAREA")
        print(f"{'='*70}")
        print(f"Error: {str(e)}")
        print(f"\nStack trace completo:")
        print(traceback.format_exc())
        print(f"{'='*70}\n")
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
            print(f"❌ Error: 'filename' no encontrado en el mensaje")
            return
        
        if not bucket:
            print(f"❌ Error: 'bucket' no encontrado en el mensaje")
            return
        
        print(f"\n{'='*60}")
        print(f"🔧 Procesando tarea legacy (sin IA)")
        print(f"📁 Archivo: {filename}")
        print(f"🗂️  Bucket: {bucket}")
        print(f"{'='*60}\n")
        
        # Obtener el cliente de MinIO
        minio_client = get_minio_client()
        
        # Descargar la imagen
        print(f"⬇️  Descargando imagen desde MinIO...")
        image_data = minio_client.download_file(bucket, filename)
        
        if image_data is None:
            print(f"❌ Error: Imagen '{filename}' no encontrada")
            return
        
        # Procesar con Pillow (thumbnail simple)
        print(f"🖼️  Creando thumbnail...")
        img = Image.open(BytesIO(image_data))
        img.thumbnail((300, 300))
        
        # Guardar
        output_buffer = BytesIO()
        img.save(output_buffer, format=img.format or 'PNG')
        output_buffer.seek(0)
        
        processed_filename = f"processed_{filename}"
        minio_client.upload_file(
            bucket_name=bucket,
            object_name=processed_filename,
            file_content=output_buffer.getvalue(),
            content_type=metadata.get('content_type', 'image/png')
        )
        
        print(f"✅ Tarea legacy completada: {processed_filename}\n")
        
    except Exception as e:
        print(f"❌ Error en tarea legacy: {e}")
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
        print(f"⚠️  Tipo de tarea desconocido: {task_type}")


def main():
    """Función principal del worker."""
    print("\n" + "="*70)
    print("🚀 WORKER DE PROCESAMIENTO DE TATUAJES CON IA")
    print("="*70)
    print("🤖 Powered by Google Gemini")
    print("="*70 + "\n")
    
    try:
        # Inicializar clientes
        print("🔧 Inicializando servicios...\n")
        
        rabbitmq_client = get_rabbitmq_client()
        print(f"✅ RabbitMQ conectado")
        
        minio_client = get_minio_client()
        print(f"✅ MinIO conectado")
        
        ai_client = get_ai_client()
        print(f"✅ Google Gemini AI conectado")
        
        print(f"\n{'='*70}")
        print(f"🔄 ESPERANDO TAREAS EN LA COLA: '{rabbitmq_client.queue_name}'")
        print(f"{'='*70}")
        print(f"⏹️  Presiona CTRL+C para detener el worker\n")
        
        # Consumir mensajes de forma continua
        rabbitmq_client.consume_messages(
            callback=route_message,
            auto_ack=False  # Confirmar manualmente después de procesar
        )
        
    except KeyboardInterrupt:
        print(f"\n\n{'='*70}")
        print(f"🛑 WORKER DETENIDO POR EL USUARIO")
        print(f"{'='*70}\n")
    except Exception as e:
        print(f"\n\n{'='*70}")
        print(f"❌ ERROR FATAL EN EL WORKER")
        print(f"{'='*70}")
        print(f"Error: {str(e)}")
        print(f"\nStack trace:")
        print(traceback.format_exc())
        print(f"{'='*70}\n")
        raise
    finally:
        print("👋 Worker finalizado\n")


if __name__ == "__main__":
    main()