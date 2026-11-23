import { AvatarView } from './avatar/AvatarView'
import { CharacterPicker } from './components/CharacterPicker'
import { ChatPanel } from './components/ChatPanel'
import { ForgetConversationButton } from './components/ForgetConversationButton'
import { StatusBar } from './components/StatusBar'
import { useCompanionSession } from './session/useCompanionSession'
import {
  selectCanClearConversation,
  selectCanSend,
  selectCanSwitchCharacter,
} from './state/appState'

export function App() {
  const {
    state,
    avatar,
    sendUserMessage,
    selectCharacter,
    clearConversation,
    selectModel,
    setVoice,
    voiceVolume,
    setVoiceVolume,
  } = useCompanionSession()
  const { session } = state
  const characterName = session?.characterName ?? '…'

  return (
    <div className="app">
      <StatusBar
        state={state}
        onSelectModel={selectModel}
        onToggleVoice={setVoice}
        voiceVolume={voiceVolume}
        onVoiceVolume={setVoiceVolume}
      />
      <main className="app__body">
        <section className="avatar-stage">
          <AvatarView controller={avatar} characterId={session?.characterId ?? null} />
          {session ? (
            <>
              <CharacterPicker
                characters={session.characters}
                currentId={session.characterId}
                disabled={!selectCanSwitchCharacter(state)}
                onSelect={selectCharacter}
              />
              <ForgetConversationButton
                key={session.characterId}
                characterName={session.characterName}
                disabled={!selectCanClearConversation(state)}
                onConfirm={clearConversation}
              />
            </>
          ) : (
            <h1 className="avatar-stage__name">{characterName}</h1>
          )}
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
