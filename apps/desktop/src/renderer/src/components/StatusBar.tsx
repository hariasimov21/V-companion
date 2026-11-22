import {
  type AppState,
  type DisplayStatus,
  selectCanSwitchModel,
  selectDisplayStatus,
} from '../state/appState'
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
}

export function StatusBar({ state, onSelectModel = () => undefined }: StatusBarProps) {
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
        <Indicator label="Mic" active={false} title="Microphone capture (not available yet)" />
        <Indicator label="Camera" active={false} title="Camera capture (not available yet)" />
      </div>
    </header>
  )
}
