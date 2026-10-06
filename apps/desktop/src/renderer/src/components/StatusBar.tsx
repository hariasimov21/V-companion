import { type AppState, type DisplayStatus, selectDisplayStatus } from '../state/appState'

const STATUS_LABELS: Record<DisplayStatus, string> = {
  idle: 'Idle',
  listening: 'Listening',
  thinking: 'Thinking',
  speaking: 'Speaking',
  error: 'Error',
  offline: 'Offline',
}

function Indicator({ label, active, title }: { label: string; active: boolean; title: string }) {
  return (
    <span className={`indicator ${active ? 'indicator--on' : 'indicator--off'}`} title={title}>
      {label} {active ? 'ON' : 'OFF'}
    </span>
  )
}

export function StatusBar({ state }: { state: AppState }) {
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
