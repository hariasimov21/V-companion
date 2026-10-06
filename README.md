# Virtual Companion 

Aplicación de escritorio con un personaje anime interactivo: mezcla de VTuber, asistente de
IA y personaje persistente. Diseñada de forma modular para crecer por fases: chat → avatar
Live2D → voz → cámara → memoria → comportamiento autónomo.

## Arquitectura

```
Electron / React  ──WebSocket (JSON tipado)──►  FastAPI
  avatar (AvatarController)                       ├── ConversationService
  chat + estado                                   ├── AIProvider (mock | openai | ollama)
                                                  ├── CharacterService (character.yaml)
                                                  └── CharacterStateStore (máquina de estados)
```

- **El backend es el cerebro**: orquesta IA, personalidad, estado y (en el futuro) memoria,
  visión y eventos. Es la única fuente de verdad del estado del personaje.
- **El frontend es el cuerpo**: muestra el avatar, el chat y el estado. Nunca llama a una IA.
- Detalles, diagramas y decisiones: [docs/architecture.md](docs/architecture.md).

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
│   │   │   ├── memory/       memoria de corto plazo
│   │   │   ├── models/       protocolo, emociones/gestos, estados
│   │   │   ├── container.py  composition root
│   │   │   └── main.py
│   │   └── tests/
│   └── desktop/              Electron + React + Vite + TypeScript
│       └── src/
│           ├── main/         proceso principal Electron
│           ├── preload/      puente mínimo (contextIsolation)
│           └── renderer/src/
│               ├── avatar/   AvatarController, AvatarDirector, placeholder SVG
│               ├── components/
│               ├── config/   AppConfig
│               ├── protocol/ tipos + validación del protocolo
│               ├── session/  hook que conecta todo
│               ├── speech/   SpeechOutput (texto hoy, TTS en Fase 3)
│               ├── state/    reducer de UI
│               └── websocket/ BackendClient con reconexión
├── character/character.yaml  personalidad (independiente del modelo)
├── shared/protocol-fixtures/ ejemplos de mensajes validados por ambos test suites
├── docs/architecture.md
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
| `OLLAMA_MODEL` | — | Requerido si `AI_PROVIDER=ollama` (p. ej. `gpt-oss:latest`) |
| `OLLAMA_THINK` | vacío | Razonamiento en modelos "thinking": `low`, `medium`, `high`, `true`, `false` |
| `OLLAMA_KEEP_ALIVE` | `30m` | Tiempo que el modelo queda en VRAM tras cada mensaje |
| `BACKEND_HOST` / `BACKEND_PORT` | `127.0.0.1` / `8000` | |
| `LOG_LEVEL` | `INFO` | `DEBUG` muestra transiciones de estado |
| `CHARACTER_FILE` | `character/character.yaml` | Relativo a la raíz del repo |
| `SHORT_TERM_MEMORY_SIZE` | `30` | Mensajes recientes enviados como contexto |
| `PRIVACY_MICROPHONE_ENABLED` | `false` | |
| `PRIVACY_CAMERA_ENABLED` | `false` | |
| `PRIVACY_REMOTE_VISION_ENABLED` | `false` | |
| `VITE_BACKEND_WS_URL` | `ws://127.0.0.1:8000/ws` | URL del backend para el frontend |

## Cómo ejecutar el backend

```bash
make backend        # o: cd apps/backend && .venv/bin/python -m app.main
make backend-dev    # con autoreload
```

Comprobación: `curl http://127.0.0.1:8000/health` → `{"status":"ok"}`.

## Cómo ejecutar el frontend

En otra terminal, con el backend corriendo:

```bash
make desktop        # o: cd apps/desktop && npm run dev
```

Se abre la ventana de Electron. Si el backend no está activo, la UI muestra **Offline** y
reintenta la conexión automáticamente con backoff exponencial.

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

Comparativa en una RTX 5080 (16 GB) con el prompt de Akari:

| Modelo | Latencia | Comentario |
|---|---|---|
| `gpt-oss:latest` (think `low`) | ~1 s | Recomendado: buena personalidad y elección de emociones. |
| `qwen2.5-coder:14b` | ~1 s | JSON correcto pero respuestas planas (modelo para código). |
| `glm-4.7-flash` | >5 min | 19 GB: no cabe en 16 GB de VRAM. |

Errores típicos que verás en la UI: Ollama apagado (`Cannot reach Ollama…`) o modelo no
descargado (`…Run: ollama pull <modelo>`).

### Probar el mock

El `MockAIProvider` responde `"Hola, estoy funcionando."` (happy + nod). Algunas palabras
clave permiten ver otras emociones: `triste`, `sorpresa`, `enoja`, `piensa`, `sueño`,
`vergüenza`, `chiste`, `pregunta`, `hola`. Escribe exactamente `/error` para simular un fallo
de la IA y ver el manejo de errores.

## Tests, linters y build

```bash
make test     # pytest + vitest
make lint     # ruff + mypy --strict + eslint + tsc
make build    # build de producción de Electron (apps/desktop/out)
make check    # todo lo anterior
```

## Estado de implementación

**Fase 0 y Fase 1 completadas**, con IA local real vía Ollama.

- [x] Electron + React + Vite + TypeScript estricto
- [x] FastAPI + WebSocket con protocolo tipado (Pydantic ↔ TypeScript) y fixtures compartidas
- [x] `AIProvider` + `MockAIProvider`; selección por `.env`
- [x] `OllamaProvider` (modelos locales): structured outputs, historial de conversación, precarga del modelo, reintento ante respuestas vacías, errores claros
- [ ] `OpenAIProvider` (stub por ahora)
- [x] Respuestas estructuradas validadas con valores seguros por defecto
- [x] `CharacterService`: system prompt generado desde `character.yaml`
- [x] Máquina de estados `idle → thinking → speaking → idle` / `error`, con el backend como fuente de verdad
- [x] Avatar placeholder SVG tras la interfaz `AvatarController` (expresiones, gestos, parpadeo, boca al hablar)
- [x] Indicadores: estado, conexión, emoción, proveedor local/remoto, Mic OFF, Camera OFF
- [x] Reconexión WebSocket con backoff, errores de IA mostrados en la UI
- [x] Logging estructurado con etiquetas (`[AI]`, `[WS]`, `[STATE]`…)

## Roadmap

| Fase | Contenido | Estado |
|---|---|---|
| 0 | Análisis y estructura | ✅ |
| 1 | Chat de texto + avatar placeholder + mock | ✅ |
| 2 | Live2D (expresiones y motions mapeadas por configuración) | ⏭️ siguiente |
| 3 | Micrófono, VAD, TTS, lip sync | |
| 4 | Cámara, captura de frames, visión | |
| 5 | Memoria persistente (SQLite/Postgres), embeddings, recuperación semántica | |
| 6 | EventBus, presencia, comportamiento proactivo con cooldowns | |
