# Virtual Companion 

Aplicación de escritorio con un personaje anime interactivo: mezcla de VTuber, asistente de
IA y personaje persistente. Diseñada de forma modular para crecer por fases: chat → avatar
Live2D → voz → cámara → memoria → comportamiento autónomo.

## Arquitectura

```
Electron / React  ──WebSocket (JSON tipado)──►  FastAPI
  avatar (AvatarController)                       ├── ConversationService
  chat + estado                                   ├── AIProvider (mock | openai | ollama)
                                                  ├── CharacterRegistry (characters/<id>/)
                                                  └── CharacterStateStore (máquina de estados)
```

- **El backend es el cerebro**: orquesta IA, personalidad, estado y (en el futuro) memoria,
  visión y eventos. Es la única fuente de verdad del estado del personaje.
- **El frontend es el cuerpo**: muestra el avatar, el chat y el estado. Nunca llama a una IA.
- Detalles, diagramas y decisiones: [docs/architecture.md](docs/architecture.md).
- Consumo de recursos y requisitos mínimos: [docs/rendimiento.md](docs/rendimiento.md).

```
.
├── apps/
│   ├── backend/              FastAPI (Python 3.12)
│   │   ├── app/
│   │   │   ├── ai/           AIProvider, proveedores, parser de respuestas
│   │   │   ├── api/          WebSocket + ConnectionManager
│   │   │   ├── character/    config YAML, CharacterService, CharacterStateStore
│   │   │   ├── config/       Settings (pydantic-settings)
│   │   │   ├── conversation/ ConversationService (un turno de chat)
│   │   │   ├── core/         errores y logging
│   │   │   ├── memory/       conversaciones por personaje (SQLite)
│   │   │   ├── models/       protocolo, emociones/gestos, estados
│   │   │   ├── container.py  composition root
│   │   │   └── main.py
│   │   └── tests/
│   └── desktop/              Electron + React + Vite + TypeScript
│       └── src/
│           ├── main/         proceso principal Electron
│           ├── preload/      puente mínimo (contextIsolation)
│           └── renderer/src/
│               ├── avatar/   AvatarController, AvatarDirector, sprites, placeholder SVG
│               ├── components/
│               ├── config/   AppConfig
│               ├── protocol/ tipos + validación del protocolo
│               ├── session/  hook que conecta todo
│               ├── speech/   SpeechOutput (texto hoy, TTS en Fase 3)
│               ├── state/    reducer de UI
│               └── websocket/ BackendClient con reconexión
├── characters/<id>/          un personaje por carpeta: personalidad y avatar
│   ├── character.yaml        nombre, idioma, rasgos
│   ├── prompt.md             personalidad completa (system prompt)
│   ├── avatar.yaml           cómo generar su avatar de sprites
│   └── art/                  imágenes fuente (gitignored)
├── shared/protocol-fixtures/ ejemplos de mensajes validados por ambos test suites
├── docs/architecture.md
├── docs/rendimiento.md       consumo medido y requisitos mínimos
├── .env.example
└── Makefile
```

¿Por qué esta estructura en lugar de la propuesta original? Es prácticamente la misma, con
tres cambios: `conversation/` separa la orquestación del turno de la capa WebSocket;
`shared/protocol-fixtures/` mantiene sincronizados los contratos TS/Python sin generar código;
y las carpetas `audio/`, `vision/`, `events/`, `behavior/` se crearán en su fase, para no
dejar módulos vacíos.

## Requisitos

- Python **3.12+**
- Node.js **22+** y npm
- Linux, macOS, Windows o WSL2 con WSLg (para mostrar la ventana de Electron)

## Instalación

```bash
cp .env.example .env     # ajusta si hace falta; por defecto usa el proveedor mock
make setup               # crea apps/backend/.venv e instala dependencias npm
```

Sin `make`:

```bash
cd apps/backend && python3.12 -m venv .venv && .venv/bin/pip install -e ".[dev]"
cd apps/desktop && npm install
```

> npm 11 bloquea scripts de instalación por defecto. `esbuild` ya está aprobado en
> `apps/desktop/package.json` (`allowScripts`). Electron descarga su binario la primera vez
> que se ejecuta.

## Variables de entorno

Todas en `.env` en la raíz (ver `.env.example`). El backend las lee solo a través de
`Settings`; el frontend solo ve las que empiezan por `VITE_`.

| Variable | Default | Descripción |
|---|---|---|
| `AI_PROVIDER` | `mock` | `mock`, `ollama` o `openai` (stub) |
| `AI_TIMEOUT_SECONDS` | `30` | Timeout de cada petición a la IA |
| `OPENAI_API_KEY` | — | Requerida si `AI_PROVIDER=openai` |
| `OPENAI_MODEL` | `gpt-4o-mini` | |
| `OLLAMA_URL` | `http://localhost:11434` | |
| `OLLAMA_MODEL` | — | Requerido si `AI_PROVIDER=ollama` (p. ej. `gpt-oss:latest`). Modelo inicial: el que elijas en la app lo sustituye y se recuerda |
| `OLLAMA_THINK` | vacío | Razonamiento en modelos "thinking": `low`, `medium`, `high`, `true`, `false`. Los niveles solo los entiende gpt-oss; en otros (qwen3) significan "sin razonar" |
| `OLLAMA_KEEP_ALIVE` | `30m` | Tiempo que el modelo queda en VRAM tras cada mensaje |
| `OLLAMA_NUM_CTX` | `16384` | Ventana de contexto en tokens. Las personalidades ocupan ~5–6k. Con voz en una GPU de 16 GB: `8192` (y `SHORT_TERM_MEMORY_SIZE=30`). Si el historial no cabe, el backend descarta los mensajes más antiguos |
| `BACKEND_HOST` / `BACKEND_PORT` | `127.0.0.1` / `8000` | |
| `LOG_LEVEL` | `INFO` | `DEBUG` muestra transiciones de estado |
| `CHARACTERS_DIR` | `characters` | Carpeta de personajes, relativa a la raíz del repo |
| `DEFAULT_CHARACTER` | `akari` | Personaje con el que arranca la app (nombre de su carpeta) |
| `SHORT_TERM_MEMORY_SIZE` | `30` | Mensajes recientes del personaje activo enviados como contexto |
| `TTS_URL` | `http://127.0.0.1:8010` | Servicio de voz local (`make tts`). Sin él, solo texto |
| `VOICE_ENABLED` | `true` | Estado inicial del botón de voz; lo que elijas en la app se recuerda |
| `MEMORY_PERSIST` | `true` | Guarda las conversaciones en disco (`false` = solo en RAM) |
| `MEMORY_DB` | `data/memory.sqlite3` | Archivo SQLite de conversaciones (ignorado por git) |
| `LONG_TERM_MEMORY_ENABLED` | `true` | Memoria a largo plazo (datos tuyos + resumen) |
| `MEMORY_BATCH_MESSAGES` | `20` | Mensajes que se resumen en cada actualización de esa memoria |
| `PRIVACY_MICROPHONE_ENABLED` | `false` | |
| `PRIVACY_CAMERA_ENABLED` | `false` | |
| `PRIVACY_REMOTE_VISION_ENABLED` | `false` | |
| `VITE_BACKEND_WS_URL` | `ws://127.0.0.1:8000/ws` | URL del backend para el frontend |
| `VITE_AVATAR_RENDERER` | `sprite` | `sprite` o `placeholder` (un personaje sin sprites usa el placeholder) |

## Arrancar todo (recomendado)

```bash
make dev              # voz (si está instalada) + backend + app, en una sola terminal
make dev NO_VOICE=1   # sin voz (libera ~3 GB de VRAM)
make dev WEB=1        # versión de navegador en vez de la ventana (recomendado en WSL)
make web              # solo la página, en http://127.0.0.1:5173
```

> **En WSL, usa la versión de navegador para oír la voz.** El sonido de la ventana de
> escritorio pasa por el canal de audio de WSLg (PulseAudio → RDP → Windows), que se
> entrecorta y llega a atascarse (comprobado: un clip de 9,5 s no terminaba de sonar). Un
> navegador de Windows reproduce la voz directamente. Abre **`http://127.0.0.1:5173`**: con
> la red "mirrored" de WSL, `localhost` puede quedarse colgado.

Cada línea lleva la etiqueta de su servicio (`[voz]`, `[backend]`, `[app]`) y **Ctrl+C
detiene los tres**. Si prefieres terminales separadas, siguen existiendo `make tts`,
`make backend` y `make desktop`.

## Cómo ejecutar el backend

```bash
make backend        # o: cd apps/backend && .venv/bin/python -m app.main
make backend-dev    # con autoreload
```

Comprobación: `curl http://127.0.0.1:8000/health` → `{"status":"ok"}`.

## Voz (opcional)

Cada personaje habla con su propia voz, generada en tu PC con **Qwen3-TTS** (clonando una
muestra de voz del personaje), cuantizado a 8 bits y ejecutado con **qwentts.cpp** (GGML +
CUDA, sin PyTorch). El audio se envía por partes mientras se genera: empieza a sonar ~0,2 s
después del texto, y la boca del avatar sigue el volumen real de la voz.

```bash
make setup-tts                # una vez: entorno propio (~300 MB; descarga ~1 GB de modelos)
make tts                      # servicio en 127.0.0.1:8010; listo en ~7 s
```

- Requiere GPU NVIDIA con drivers para CUDA 12.8+: el servicio usa ~3 GB de VRAM. Con 16 GB y un modelo de chat
  grande, usa `OLLAMA_NUM_CTX=8192` (ver [docs/rendimiento.md](docs/rendimiento.md)).
- El orden de arranque da igual: el backend detecta el servicio cuando está listo. Si no
  está, la app funciona solo con texto.
- Botón **Voz ON/OFF** en la barra de estado (se recuerda). Escribir mientras habla la
  interrumpe.

**Voz de cada personaje** (`characters/<id>/`, ignorado por git):

| Archivo | Qué es |
|---|---|
| `voice.yaml` | Descripción de la voz (en inglés) y una frase de muestra |
| `voice.wav` + `voice.txt` | La muestra que se clona y su transcripción exacta |
| `voice-candidates/` | Candidatas generadas por `make voice` |

```bash
make voice CHARACTER=mimi            # diseña 3 candidatas desde voice.yaml (~35 s)
make voice CHARACTER=mimi PICK=2     # usar la candidata 2; luego reinicia make tts
```

Si la GPU va justa al diseñar, detén antes `make tts` o libera el modelo de chat (`ollama stop <modelo>`).

## Cómo ejecutar el frontend

En otra terminal, con el backend corriendo:

```bash
make desktop        # o: cd apps/desktop && npm run dev
```

Se abre la ventana de Electron. Si el backend no está activo, la UI muestra **Offline** y
reintenta la conexión automáticamente con backoff exponencial.

> **WSL**: la app desactiva la aceleración gráfica de la ventana (con ella, maximizar la
> ventana la colgaba y dejaba WSLg sin poder mostrar ventanas hasta `wsl --shutdown`). La IA y
> la voz siguen usando la GPU en sus propios procesos. Para volver a activarla:
> `MALFOID_GPU=1 make desktop`. Si WSLg queda roto (la app aparece en la barra de tareas pero
> no se ve), usa la versión de navegador: `make dev WEB=1` y `http://127.0.0.1:5173`.

> **VS Code**: su terminal integrada exporta `ELECTRON_RUN_AS_NODE=1`, lo que rompe Electron.
> `npm run dev` / `npm run preview` ya lo eliminan (`scripts/electron-vite.mjs`). Si lanzas
> `electron` a mano, usa `env -u ELECTRON_RUN_AS_NODE`.

### Usar un modelo local con Ollama (recomendado)

Con [Ollama](https://ollama.com) instalado y corriendo:

```env
AI_PROVIDER=ollama
OLLAMA_MODEL=gpt-oss:latest
OLLAMA_THINK=low
```

Al arrancar, el backend precarga el modelo en segundo plano (`[AI] Model loaded`); la
primera carga tarda unos segundos (~20 s para gpt-oss en una RTX 5080) y después cada
respuesta toma ~1 s. Se usan *structured outputs* de Ollama: el esquema JSON de la
respuesta se envía en cada petición, así que el modelo siempre devuelve `speech`,
`emotion`, `gesture`, etc.

**Cambiar de modelo desde la app.** La barra de estado tiene un selector con los modelos de
chat instalados en Ollama (solo locales; los de embeddings se ocultan). El modelo es el mismo
para todos los personajes y la elección se guarda para el próximo arranque. Al cambiar, el
backend saca el modelo anterior de la GPU y carga el nuevo; mientras tanto la app muestra
*Cargando modelo…* y no deja enviar mensajes (10–30 s). Conversaciones y memoria no se
pierden: son texto en `data/memory.sqlite3` y el nuevo modelo las lee en su siguiente turno.
Para añadir modelos: `ollama pull <modelo>` y reconecta la app.

Comparativa en una RTX 5080 (16 GB) con los 5 personajes (2 preguntas cada uno):

| Modelo | VRAM | Latencia | Comentario |
|---|---|---|---|
| `gpt-oss:latest` (think `low`) | 12,7 GB | 2–4 s | Recomendado: el más marcado en personalidad y respuestas de 35–65 palabras. |
| `qwen3:14b` (sin razonar) | 11,7 GB | 2–6 s | Muy cerca: buen personaje, algo más contenido. Con razonamiento tarda ~50 s. Tiende a repetir muletillas de su propio historial (la app le aplica `presence_penalty` 1.0, que lo reduce sin eliminarlo). |
| `mistral-nemo:latest` | 9,6 GB | 1–7 s | En personaje pero más breve (12–57 palabras) y más suave (Mimi pierde sarcasmo). |
| `qwen2.5-coder:14b` | ~9 GB | ~1 s | JSON correcto pero respuestas planas (modelo para código). |
| `glm-4.7-flash` | 19 GB | >5 min | No cabe en 16 GB de VRAM. |

Errores típicos que verás en la UI: Ollama apagado (`Cannot reach Ollama…`) o modelo no
descargado (`…Run: ollama pull <modelo>`).

### Probar el mock

El `MockAIProvider` responde `"Hola, estoy funcionando."` (happy + nod). Algunas palabras
clave permiten ver otras emociones: `triste`, `sorpresa`, `enoja`, `piensa`, `sueño`,
`vergüenza`, `chiste`, `pregunta`, `hola`. Escribe exactamente `/error` para simular un fallo
de la IA y ver el manejo de errores.

## Personajes

Cada carpeta de `characters/` es un personaje; la app los lista en un selector bajo el
avatar. **Cada personaje tiene su propia conversación**: al cambiar, el nuevo personaje
retoma la suya donde la dejaste y nunca ve la de los demás. Las conversaciones y el
último personaje elegido se guardan en `data/memory.sqlite3`, así que sobreviven a
reinicios.

**Memoria a largo plazo.** Al modelo solo le llegan los últimos `SHORT_TERM_MEMORY_SIZE`
mensajes. Justo antes de que un bloque de `MEMORY_BATCH_MESSAGES` salga de esa ventana, el
backend pide al modelo (en segundo plano, sin hacerte esperar) que actualice la memoria del
personaje: una lista de datos tuyos que vale la pena recordar (nombre, mascotas, trabajo,
planes…) y un resumen de lo hablado. Esa memoria va en cada turno junto a la personalidad,
así que recuerda lo importante aunque la conversación tenga cientos de mensajes. Cada
personaje tiene la suya.

El botón **Olvidar conversación** (bajo el selector, pide confirmación) borra
la del personaje activo y su memoria a largo plazo; para borrar todas, cierra el backend y elimina ese archivo.

`characters/` es **personal y está ignorada por git** (personalidades e imágenes no se
suben). En un clon nuevo hay que crear al menos un personaje (ver abajo) y apuntar
`DEFAULT_CHARACTER` a él; si no, el backend no arranca. Un personaje genérico de ejemplo
llegará más adelante.

Avatar según lo que tenga cada personaje: sprites por capas (expresiones, parpadeo, boca),
imagen fija (respira, hace gestos y se mueve al hablar) o placeholder SVG si no tiene imagen.

### Añadir un personaje

1. Crea `characters/<id>/` (`id` en minúsculas: letras, números, `-`, `_`).
2. `character.yaml`:
   ```yaml
   character:
     name: Nombre
     language: es
     prompt_file: prompt.md   # opcional: personalidad completa en Markdown
     description: Una línea.  # esencia del personaje (se repite en cada turno)
     reply_length: medium     # short | medium | long (por defecto medium)
   personality: { affectionate: 0.5, sarcasm: 0.2 }  # 0..1
   ```
   Si hay `prompt_file`, ese texto es la personalidad. El backend añade al final el
   contexto de la app (cámara y micrófono apagados, sin acciones entre asteriscos) y el
   formato JSON de respuesta. Además, en cada turno manda justo después de tu mensaje un
   recordatorio corto (nombre, `description`, mantenerse en personaje, longitud) para que
   la personalidad no se diluya en conversaciones largas; no se guarda en el historial.
3. Avatar (opcional): pon la imagen en `characters/<id>/art/base.png`, crea
   `characters/<id>/avatar.yaml` con `base: base` y ejecuta `make avatar CHARACTER=<id>`.
4. Reinicia backend y frontend.

## Avatar

La app tiene dos renderers detrás de la misma interfaz `AvatarController`. El set de
sprites de cada personaje se llama igual que su carpeta.

- **Sprites**:
  - *static*: una sola imagen. Respira, hace gestos y se mueve mientras habla.
  - *layered*: cuerpo + ojos + boca por capas. Parpadea, cambia de expresión según la
    emoción y abre la boca al hablar.
- **Placeholder SVG**: para personajes sin sprites (o un clon nuevo del repo).

### Generar los sprites

`characters/<id>/avatar.yaml` describe el avatar; las imágenes van en
`characters/<id>/art/`.

- **Modo static**: basta con `base: base` (lee `art/base.png`). La herramienta quita el
  fondo, recorta al personaje y reduce el tamaño. Las imágenes con transparencia se
  aplanan sobre blanco antes de quitar el fondo. Para arte muy alto (cuerpo entero),
  `max_aspect: 2.0` recorta por abajo.
- **Modo layered** (ver `characters/akari/avatar.yaml`): además `blink`, `mouth_open`,
  `expressions` y `regions`. Todas las imágenes deben tener el mismo tamaño y pose; solo
  cambia la cara. Genéralas con *inpainting* sobre la imagen base (máscara solo en la
  cara). La herramienta rechaza imágenes que cambien fuera de la cara.

```bash
make setup-avatar-tool        # una vez (instala rembg en tools/avatar/.venv)
make avatar                   # todos los personajes
make avatar CHARACTER=<id>    # solo uno
```

Los resultados van a `apps/desktop/src/renderer/src/avatar/sprite/assets/<id>/` y se
empaquetan con la app.

> Las imágenes fuente y los assets generados están en `.gitignore`: son arte personal y
> pueden incluir propiedad intelectual de terceros. No se suben al repositorio público.

## Tests, linters y build

```bash
make test     # pytest + vitest
make lint     # ruff + mypy --strict + eslint + tsc
make build    # build de producción de Electron (apps/desktop/out)
make check    # todo lo anterior
```

## Estado de implementación

**Fases 0 y 1 completadas**, con IA local real vía Ollama. **Fase 2 en curso:** avatar de
sprites y varios personajes listos; Live2D pendiente. **Fase 3 en curso:** voz de los
personajes lista; micrófono pendiente.

- [x] Electron + React + Vite + TypeScript estricto
- [x] FastAPI + WebSocket con protocolo tipado (Pydantic ↔ TypeScript) y fixtures compartidas
- [x] `AIProvider` + `MockAIProvider`; selección por `.env`
- [x] `OllamaProvider` (modelos locales): structured outputs, historial de conversación, precarga del modelo, reintento ante respuestas vacías, errores claros
- [ ] `OpenAIProvider` (stub por ahora)
- [x] Respuestas estructuradas validadas con valores seguros por defecto
- [x] `CharacterService`: system prompt generado desde `character.yaml`
- [x] Máquina de estados `idle → thinking → speaking → idle` / `error`, con el backend como fuente de verdad
- [x] Avatar placeholder SVG tras la interfaz `AvatarController` (expresiones, gestos, parpadeo, boca al hablar)
- [x] Avatar de sprites: capas de ojos/boca, parpadeo, boca al hablar, transiciones, gestos y respiración
- [x] Herramienta `tools/avatar/prepare_sprites.py`: modos static y layered, validación de alineación, quitado de fondo y exportación
- [x] Varios personajes (`characters/<id>/`), personalidad completa en `prompt.md` y selector en la app
- [ ] Live2D
- [x] Voz por personaje (Qwen3-TTS local, clonación de una voz diseñada), audio en streaming, lip sync por volumen y botón Voz ON/OFF
- [x] Indicadores: estado, conexión, emoción, proveedor local/remoto, Mic OFF, Camera OFF
- [x] Reconexión WebSocket con backoff, errores de IA mostrados en la UI
- [x] Logging estructurado con etiquetas (`[AI]`, `[WS]`, `[STATE]`…)

## Roadmap

| Fase | Contenido | Estado |
|---|---|---|
| 0 | Análisis y estructura | ✅ |
| 1 | Chat de texto + avatar placeholder + mock | ✅ |
| 2 | Avatar real: sprites ✅, Live2D (expresiones y motions mapeadas por configuración) | 🚧 en curso |
| 3 | Voz del personaje (TTS) y lip sync ✅; micrófono y VAD | 🚧 |
| 4 | Cámara, captura de frames, visión | |
| 5 | Memoria persistente: historial por personaje en SQLite ✅, memoria a largo plazo (datos + resumen) ✅; embeddings y recuperación semántica | 🚧 |
| 6 | EventBus, presencia, comportamiento proactivo con cooldowns | |
