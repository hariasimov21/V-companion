# Rendimiento y requisitos

Mediciones reales del 2026-11-22. Se usó el prompt completo de Akari (personalidad, contexto
de la app, formato JSON y recordatorio de cada turno) con las mismas opciones que la app:
`num_ctx` 16384, temperatura 0.8, esquema JSON, `think` `low` en gpt-oss y desactivado en
qwen3.

**Equipo de medición:**
- GPU: RTX 5080 con 16 GB de VRAM
- CPU: Ryzen 7 7800X3D (8 núcleos y 16 hilos)
- RAM: 30 GB
- Sistema: Windows 11 + WSL2, con Ollama 0.30.8 corriendo dentro de WSL

## Resumen

- **Casi todo el consumo es del modelo de IA.** El backend y la app de escritorio suman
  menos de 1 GB de RAM y muy poca CPU.
- **Lo que de verdad decide si funciona es la VRAM de la GPU.** Sin GPU funciona, pero
  la primera respuesta tarda unos 4 minutos y cada respuesta siguiente unos 41 s.
- **Mínimo con IA local:** una GPU NVIDIA de 12 GB (mistral-nemo).
  **Recomendado:** 16 GB (gpt-oss o qwen3).

## Consumo de cada componente

| Componente | RAM | CPU en reposo | GPU |
|---|---|---|---|
| Backend (FastAPI) | ~60 MB | ~0 % | — |
| App de escritorio (Electron, 7 procesos) | ~700 MB | ~10 % de un hilo (animaciones del avatar) | mínima |
| Servidor de desarrollo Vite (solo `make desktop`) | ~180 MB | ~0 % | — |
| Ollama (servidor) | ~40 MB | ~0 % | — |
| Ollama con un modelo cargado en la GPU | ~1,5 GB | ~0 % sin peticiones | 9,6–12,7 GB (ver abajo) |
| Base de datos de memoria (`data/memory.sqlite3`) | — | — | — |

La base de datos ocupa 240 KB en disco y crece unos pocos KB por conversación.

Mientras el modelo responde, la GPU trabaja al máximo durante 2–5 s. El backend solo
espera esa respuesta.

Windows y el escritorio ya ocupan unos **2,1 GB de VRAM** sin ningún modelo cargado. Hay
que sumarlos a lo que pide cada modelo.

## Modelos (GPU)

| | gpt-oss | qwen3:14b | mistral-nemo |
|---|---|---|---|
| Parámetros / cuantización | 20,9 B / MXFP4 | 14,8 B / Q4_K_M | 12,2 B / Q4_0 |
| Disco | 13 GB | 9,3 GB | 7,1 GB |
| **VRAM con 16k de contexto** | **12,7 GB** | **11,7 GB** | **9,6 GB** |
| VRAM total de la GPU (con escritorio) | 15,4 GB | 14,1 GB | 11,7 GB |
| Primer mensaje tras cargar | 11–19 s | 10–23 s | 8–18 s |
| Turno normal | 3–5 s | ~2 s | ~2 s |
| Turno con 80 mensajes de historial | 3–9 s | 2–4 s | 2–6 s |
| Velocidad de generación | ~90 tokens/s | ~50 tokens/s | ~50 tokens/s |
| Actualización de memoria a largo plazo | 2–5 s (en segundo plano) | — | — |

- **Turnos normales:** la personalidad (~5.000 tokens) queda en la caché de Ollama, así que
  en un turno normal solo se procesa lo nuevo. Un turno lento (6–9 s) aparece solo cuando
  cambia el principio del historial.
- **gpt-oss** genera más rápido, pero gasta 2–3 s pensando (`think: low`) antes de
  responder.
- **qwen3** con el razonamiento activado tarda **~50 s** por respuesta. Por eso la app lo
  desactiva.

### Contexto y VRAM

`OLLAMA_NUM_CTX` es cuánto texto puede leer el modelo de una vez. Cuanto mayor, más VRAM
necesita:

| `num_ctx` | gpt-oss | qwen3:14b | mistral-nemo |
|---|---|---|---|
| 8192 | 12,7 GB | 10,5 GB | 8,3 GB |
| 16384 (actual) | 12,7 GB | 11,7 GB | 9,6 GB |
| 32768 | 12,8 GB | 14,4 GB | 12,2 GB |

gpt-oss apenas cambia porque usa atención con ventana deslizante. En los otros dos, cada 8k
de contexto cuesta 1,2–2,6 GB más.

**Cuántos tokens usa cada turno:**
- Personalidad, reglas y recordatorio: unos 4.900–5.800 tokens. Varía según el modelo,
  porque cada uno cuenta los tokens a su manera.
- Cada mensaje del historial: unos 50 tokens.
- Con `SHORT_TERM_MEMORY_SIZE=80`, un turno lleva unos 8.700–9.800 tokens. Por eso
  **16k es el mínimo cómodo**.
- Con 8k de contexto habría que bajar `SHORT_TERM_MEMORY_SIZE` a unos 40.

## Voz (Qwen3-TTS)

Servicio de voz (`make tts`): modelo Base 0.6B cuantizado a 8 bits (Q8_0) con
**qwentts.cpp**, clonando la voz de cada personaje. Medido el 2026-11-23 con la GPU libre:

| | qwentts.cpp Q8_0 (actual) | Antes: PyTorch (`faster-qwen3-tts`) |
|---|---|---|
| VRAM del proceso | **~3,0–3,4 GB** | 3,8 GB |
| Arranque (carga + preparar 5 voces) | **~7 s** | ~20 s |
| Velocidad | **6–8× tiempo real** | ~3× (1,5× con la GPU casi llena) |
| Primer audio | **0,13–0,30 s** | 0,4 s |
| Entorno de Python | **~300 MB** | 6,3 GB |

La calidad es la misma de oído (comparado lado a lado). Reservar menos memoria en PyTorch
(`max_seq_len` 1024/768) solo ahorraba 0,14–0,27 GB, y la versión a 4 bits (Q4_K_M) apenas
0,2 GB más que la de 8 bits. qwentts.cpp reserva un búfer fijo de 896 MB (4.096 pasos) que
no se puede ajustar.

**Voz + modelo de chat a la vez** (voz cargada primero; ventana de Electron cerrada):

| Modelo de chat | GPU total (de 16,3 GB) | Primer audio | Holgura |
|---|---|---|---|
| qwen3:14b, `num_ctx` 16384 | 15,8 GB | 0,9 s | muy justa |
| **qwen3:14b, `num_ctx` 8192** | **15,3 GB** | **0,4 s** | buena (configuración elegida) |
| mistral-nemo, `num_ctx` 16384 | 14,6 GB | 0,5 s | cómoda |
| gpt-oss, `num_ctx` 8192 | 15,7 GB | 0,7–1 s | justa |

Si la VRAM se desborda, Windows no da error: usa RAM compartida y todo se ralentiza. Con
la app de escritorio abierta se suma ~1 GB más: si va lento, baja el contexto o desactiva la
voz.

Otros motores probados en español (2026-11-22): Kokoro (CPU, muy rápido pero una sola voz
femenina en español), Chatterbox Multilingual (≈ tiempo real, 3,7 GB, sin mantenimiento) y
Qwen3-TTS con la librería oficial (2–3,6× más lento que tiempo real).

## Sin GPU (solo CPU)

Prueba con mistral-nemo, el modelo más liviano, en el Ryzen 7 7800X3D:

| | Tiempo |
|---|---|
| Primer mensaje (carga + leer la personalidad) | **240 s** (188 s solo para leer el prompt) |
| Turno normal | **41 s** |
| Velocidad de generación | 2,7 tokens/s |
| RAM | 9,4 GB |

Funciona, pero no sirve para conversar.

## Disco

| Elemento | Tamaño | ¿Hace falta? |
|---|---|---|
| Dependencias del frontend (`node_modules`) | 457 MB | Siempre |
| Entorno del backend (`.venv`) | 162 MB | Siempre |
| Cada modelo de Ollama | 7–13 GB | Con IA local; uno como mínimo |
| Herramienta de sprites (`tools/avatar/.venv`) | 591 MB | Solo para procesar imágenes |
| Modelo para quitar fondos (`~/.rembg`, birefnet) | 928 MB | Solo para procesar imágenes |
| Entorno de voz (`apps/tts/.venv`, qwentts.cpp) | ~300 MB | Solo con voz |
| Modelos de voz GGUF (Hugging Face, `~/.cache/huggingface`) | ~1 GB (0.6B Q8_0) + ~2 GB (diseño 1.7B Q8_0) | Solo con voz |
| Personajes, sprites y base de datos | ~25 MB | Siempre |

Ahora mismo tienes 55 GB de modelos en Ollama. Si no los usas, puedes borrar
`glm-4.7-flash` (19 GB, no cabe en la GPU) y `qwen2.5-coder` (9 GB, es para programar):
`ollama rm <modelo>`.

## Requisitos

| | Solo desarrollo (IA simulada) | Mínimo con IA local | Recomendado |
|---|---|---|---|
| GPU | No hace falta | NVIDIA con **12 GB de VRAM** | NVIDIA con **16 GB de VRAM** |
| Modelo | `AI_PROVIDER=mock` | mistral-nemo (16k) | gpt-oss o qwen3:14b |
| RAM | 4 GB | 16 GB | 16–32 GB |
| CPU | 2 núcleos | 4 núcleos | 6+ núcleos |
| Disco | 1 GB | 10 GB | 25 GB (dos modelos) |
| Sistema | Linux o WSL2 con Python 3.12 y Node 22+ | igual | igual |

- **12 GB de VRAM:** mistral-nemo ocupa 9,6 GB más ~2 GB del escritorio. Entra justo. Si la
  pantalla está conectada a otra GPU, sobra margen.
- **8 GB de VRAM: no está medido y no lo recomiendo.** Incluso con `num_ctx` 8192,
  mistral-nemo necesita 8,3 GB más lo que use el escritorio, así que parte del modelo iría a
  la CPU y las respuestas se ralentizarían mucho. Habría que usar un modelo más pequeño (7–8
  B), con el que la personalidad se nota menos.
- **RAM:** al cargar un modelo, el sistema lee el archivo entero (7–13 GB). Con 16 GB de RAM
  funciona; con 32 GB las cargas son más rápidas.
- **IA remota (`AI_PROVIDER=openai`):** solo pide los requisitos de "Solo desarrollo", pero
  la conversación y la memoria salen de tu PC.
