import { PlaceholderAvatar } from './avatar/placeholder/PlaceholderAvatar'
import { ChatPanel } from './components/ChatPanel'
import { StatusBar } from './components/StatusBar'
import { useCompanionSession } from './session/useCompanionSession'
import { selectCanSend } from './state/appState'

export function App() {
  const { state, avatar, sendUserMessage } = useCompanionSession()
  const characterName = state.session?.characterName ?? '…'

  return (
    <div className="app">
      <StatusBar state={state} />
      <main className="app__body">
        <section className="avatar-stage">
          <PlaceholderAvatar controller={avatar} />
          <h1 className="avatar-stage__name">{characterName}</h1>
        </section>
        <ChatPanel
          characterName={characterName}
          messages={state.messages}
          canSend={selectCanSend(state)}
          error={state.lastError}
          onSend={sendUserMessage}
        />
      </main>
    </div>
  )
}
