import {
  type AppState,
  type DisplayStatus,
  selectCanSwitchModel,
  selectDisplayStatus,
} from '../state/appState'
import { MAX_VOICE_VOLUME } from '../speech/voiceVolume'
import { ModelPicker } from './ModelPicker'

const STATUS_LABELS: Record<DisplayStatus, string> = {
  idle: 'Idle',
  listening: 'Listening',
  thinking: 'Thinking',
  speaking: 'Speaking',
  error: 'Error',
  offline: 'Offline',
  loading: 'Cargando modelo…',
}

function Indicator({ label, active, title }: { label: string; active: boolean; title: string }) {
  return (
    <span className={`indicator ${active ? 'indicator--on' : 'indicator--off'}`} title={title}>
      {label} {active ? 'ON' : 'OFF'}
    </span>
  )
}

interface StatusBarProps {
  state: AppState
  onSelectModel?: (model: string) => void
  onToggleVoice?: (enabled: boolean) => void
  voiceVolume?: number
  onVoiceVolume?: (volume: number) => void
}

function VoiceVolume({ volume, onChange }: { volume: number; onChange: (volume: number) => void }) {
  const percent = Math.round(volume * 100)
  return (
    <label className="voice-volume" title={`Volumen de la voz: ${percent} %`}>
      <span aria-hidden="true">🔊</span>
      <input
        type="range"
        min={0}
        max={MAX_VOICE_VOLUME}
        step={0.05}
        value={volume}
        aria-label="Volumen de la voz"
        aria-valuetext={`${percent} %`}
        onChange={(event) => onChange(Number(event.target.value))}
      />
      <span className="voice-volume__value">{percent}%</span>
    </label>
  )
}

function VoiceToggle({
  available,
  enabled,
  onToggle,
}: {
  available: boolean
  enabled: boolean
  onToggle: (enabled: boolean) => void
}) {
  const on = available && enabled
  const title = !available
    ? 'Voz no disponible: inicia el servicio de voz (make tts) o crea la voz del personaje (make voice)'
    : enabled
      ? 'El personaje habla en voz alta. Clic para silenciarlo'
      : 'Voz desactivada. Clic para que el personaje hable'
  return (
    <button
      type="button"
      className={`voice-toggle ${on ? 'voice-toggle--on' : ''}`}
      title={title}
      aria-pressed={on}
      disabled={!available}
      onClick={() => onToggle(!enabled)}
    >
      {available ? `Voz ${enabled ? 'ON' : 'OFF'}` : 'Voz —'}
    </button>
  )
}

export function StatusBar({
  state,
  onSelectModel = () => undefined,
  onToggleVoice = () => undefined,
  voiceVolume = 1,
  onVoiceVolume = () => undefined,
}: StatusBarProps) {
  const status = selectDisplayStatus(state)
  const { session } = state

  return (
    <header className="status-bar">
      <div className="status-bar__group">
        <span className={`status-badge status-badge--${status}`} data-testid="status">
          {STATUS_LABELS[status]}
        </span>
        <span className="status-bar__item">
          Backend: <strong>{state.connection}</strong>
        </span>
        <span className="status-bar__item">
          Emotion: <strong>{state.emotion}</strong>
        </span>
      </div>
      <div className="status-bar__group">
        {session && session.aiModels.length > 0 && session.aiModel && (
          <ModelPicker
            models={session.aiModels}
            currentModel={session.aiModel}
            disabled={!selectCanSwitchModel(state)}
            onSelect={onSelectModel}
          />
        )}
        {session && (
          <span
            className={`indicator ${session.aiIsRemote ? 'indicator--remote' : 'indicator--off'}`}
            title={session.aiIsRemote ? 'Messages are sent to a remote AI API' : 'AI runs locally'}
          >
            AI: {session.aiProvider} {session.aiIsRemote ? '(remote)' : '(local)'}
          </span>
        )}
        {session && (
          <VoiceToggle
            available={session.voiceAvailable}
            enabled={session.voiceEnabled}
            onToggle={onToggleVoice}
          />
        )}
        {session?.voiceAvailable && session.voiceEnabled && (
          <VoiceVolume volume={voiceVolume} onChange={onVoiceVolume} />
        )}
        <Indicator label="Mic" active={false} title="Microphone capture (not available yet)" />
        <Indicator label="Camera" active={false} title="Camera capture (not available yet)" />
      </div>
    </header>
  )
}
