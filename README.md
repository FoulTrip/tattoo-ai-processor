# Servicio de Tatuajes con Inteligencia Artificial

Aplicar diseños de tatuajes en fotos de cuerpos utilizando Reve API. Se utiliza una arquitectura de microservicios con FastAPI, RabbitMQ para colas de mensajes, Cloudinary para almacenamiento de objetos y un worker que procesa las imágenes con IA.

## 🚀 Características

- **API REST**: FastAPI para recepción de imágenes y gestión de archivos
- **Procesamiento Asíncrono**: RabbitMQ para encolado de tareas
- **Almacenamiento**: Cloudinary para gestión de imágenes
- **IA Avanzada**: Reve API para aplicación realista de tatuajes
- **Arquitectura Escalable**: Separación entre API, worker y servicios externos

## 📋 Requisitos del Sistema

- Python 3.8+
- Docker y Docker Compose (para servicios externos)
- Cuenta de Reve (para API key)

## 🛠️ Instalación y Configuración

### 1. Clonar el repositorio

```bash
git clone https://github.com/FoulTrip/tattoo-ai-processor.git
cd tatto-ai-processor
```

### 2. Instalar dependencias de Python

```bash
pip install -r requirements.txt
```

### 3. Configurar servicios externos

#### Cloudinary (Almacenamiento de objetos)
- Crea una cuenta en [Cloudinary](https://cloudinary.com)
- Obtén tu `cloud_name`, `api_key` y `api_secret` del dashboard
- Configura estas credenciales en el archivo `.env`

#### RabbitMQ (Sistema de colas)
```bash
# Usando Docker
docker run -d \
  --name rabbitmq \
  -p 5672:5672 \
  -p 15672:15672 \
  -e RABBITMQ_DEFAULT_USER=admin \
  -e RABBITMQ_DEFAULT_PASS=admin123 \
  rabbitmq:3-management
```

### 4. Configurar variables de entorno

Copia el archivo `.env` y configura las variables necesarias:

```bash
cp .env .env.local
```

Edita `.env.local` con tus configuraciones:

```env
# Cloudinary
CLOUDINARY_CLOUD_NAME=tu_cloud_name
CLOUDINARY_API_KEY=tu_api_key
CLOUDINARY_API_SECRET=tu_api_secret

# RabbitMQ
RABBITMQ_HOST=localhost
RABBITMQ_PORT=5672
RABBITMQ_USER=admin
RABBITMQ_PASSWORD=admin123

# Reve API (obtén tu API key de https://reve.com)
REVE_API_KEY=tu_api_key_aqui

# FastAPI
APP_HOST=0.0.0.0
APP_PORT=8000
```

## 🚀 Ejecución

### Opción 1: Ejecutar API y Worker por separado

#### Terminal 1: Iniciar la API
```bash
python main.py
```

#### Terminal 2: Iniciar el Worker
```bash
python worker/work.py
```

### Opción 2: Usar Docker Compose (recomendado para desarrollo)

```bash
# Ejecutar todos los servicios
docker-compose up --build

# O en segundo plano:
docker-compose up -d --build
```

#### Configurar carpetas en Cloudinary

Cloudinary crea automáticamente las carpetas cuando subes archivos. Las carpetas utilizadas son:
   - `input-images` (para imágenes de entrada)
   - `output-images` (para resultados procesados)

## 📖 Uso de la API

### Health Check
```bash
GET /
```
Verifica el estado de los servicios conectados.

### Subir imágenes para procesamiento
```bash
POST /upload/
Content-Type: multipart/form-data

body_image: <archivo_imagen>
tattoo_image: <archivo_imagen>
```

**Parámetros:**
- `body_image`: Foto del cuerpo con zona roja marcada donde irá el tatuaje
- `tattoo_image`: Diseño del tatuaje (PNG preferiblemente sin fondo)

### Listar archivos
```bash
GET /files/?bucket=input-images&prefix=body_
```

### Obtener URL de descarga
```bash
GET /files/{bucket}/{filename}
```

### Eliminar archivo
```bash
DELETE /files/{bucket}/{filename}
```

### Estado de la cola
```bash
GET /queue/status
```

## 🏗️ Arquitectura

```
Cliente HTTP ──► FastAPI Server
                      │
                      ├─► Cloudinary (Almacenamiento)
                      │
                      └─► RabbitMQ ──► Worker
                                        │
                                        └─► Reve API
```

### Flujo de procesamiento:

1. **Recepción**: API recibe dos imágenes vía POST
2. **Validación**: Verifica formatos y tipos de archivo
3. **Almacenamiento**: Sube imágenes a Cloudinary
4. **Encolado**: Envía tarea a RabbitMQ
5. **Procesamiento**: Worker descarga imágenes y aplica IA
6. **Resultado**: Guarda imagen procesada en Cloudinary

## 🔧 Desarrollo

### Estructura del proyecto

```
tatto-ia/
├── main.py                 # API principal FastAPI
├── background/
│   └── work.py            # Worker de procesamiento
├── handlers/
│   ├── ai_client.py       # Cliente para Reve API
│   ├── cloudinary_client.py # Cliente para Cloudinary
│   └── rabbitmq_client.py # Cliente para RabbitMQ
├── .env                    # Variables de entorno
├── .gitignore             # Archivos ignorados por Git
└── README.md              # Este archivo
```

### Agregar nuevas funcionalidades

- **Nuevos endpoints**: Editar `main.py`
- **Nueva lógica de procesamiento**: Modificar `worker/work.py`
- **Nuevos clientes**: Agregar en `handlers/`

## 🐛 Solución de problemas

### Error de conexión a Cloudinary
- Verificar que las credenciales de Cloudinary sean correctas en `.env`
- Comprobar que la cuenta de Cloudinary esté activa

### Error de conexión a RabbitMQ
- Verificar que RabbitMQ esté ejecutándose en el puerto 5672
- Comprobar credenciales y vhost en `.env`

### Error de API de Reve
- Verificar que `REVE_API_KEY` sea válida
- Comprobar límites de uso de la API

### Logs de depuración
- La API muestra logs en la consola
- El worker muestra logs detallados de procesamiento