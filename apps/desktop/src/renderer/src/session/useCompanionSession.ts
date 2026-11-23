import { useCallback, useEffect, useReducer, useRef, useState } from 'react'

import { AvatarDirector } from '../avatar/AvatarDirector'
import { ObservableAvatarController } from '../avatar/ObservableAvatarController'
import { appConfig } from '../config/appConfig'
import type { AssistantMessageEvent, ServerEvent } from '../protocol/types'
import { AudioSpeechPlayer } from '../speech/AudioSpeechPlayer'
import { clampVolume, loadVoiceVolume, saveVoiceVolume } from '../speech/voiceVolume'
import { TextOnlySpeechOutput } from '../speech/SpeechOutput'
import { type AppState, appReducer, initialAppState } from '../state/appState'
import { BackendClient } from '../websocket/BackendClient'

interface CompanionSession {
  state: AppState
  avatar: ObservableAvatarController
  sendUserMessage: (text: string) => boolean
  selectCharacter: (characterId: string) => boolean
  clearConversation: () => boolean
  selectModel: (model: string) => boolean
  setVoice: (enabled: boolean) => boolean
  /** 0 .. 1.5, remembered on this device. */
  voiceVolume: number
  setVoiceVolume: (volume: number) => void
}

/**
 * Wires the backend connection, UI state, avatar and speech output together.
 * React components only see state and a send function.
 */
export function useCompanionSession(): CompanionSession {
  const [state, dispatch] = useReducer(appReducer, initialAppState)
  const [avatar] = useState(() => new ObservableAvatarController())
  const [client] = useState(
    () => new BackendClient(appConfig.backendWsUrl, appConfig.reconnect),
  )
  const speechAbort = useRef<AbortController | null>(null)
  const [voiceVolume, setVolumeState] = useState(loadVoiceVolume)
  // Real lip sync: the mouth follows the loudness of the character's voice.
  const [voice] = useState(() => {
    const player = new AudioSpeechPlayer((level) => avatar.setMouthOpen(level))
    player.setVolume(loadVoiceVolume())
    return player
  })

  useEffect(() => {
    const director = new AvatarDirector(avatar)
    const speech = new TextOnlySpeechOutput(appConfig.speech)

    const stopSpeech = () => {
      speechAbort.current?.abort()
      speechAbort.current = null
    }

    /** Voiced replies play their streamed audio; the rest wait a reading-time estimate. */
    const speak = (message: AssistantMessageEvent) => {
      stopSpeech()
      const abort = new AbortController()
      speechAbort.current = abort
      const done = message.voice
        ? voice.play(message.utterance_id, abort.signal)
        : speech.speak(message.text, abort.signal)
      done
        .then(() => client.send({ type: 'speech_finished' }))
        .catch(() => undefined) // Aborted: a newer turn or a disconnect took over.
    }

    const handleEvent = (event: ServerEvent) => {
      dispatch({ type: 'server_event', event })
      if (event.type === 'state_changed' || event.type === 'session_ready') {
        director.onPhaseChanged(event.state)
      } else if (event.type === 'character_changed' || event.type === 'conversation_cleared') {
        stopSpeech() // A line from the previous conversation must not keep "playing".
        director.reset()
      } else if (event.type === 'assistant_message') {
        director.onAssistantMessage(event)
        speak(event)
      } else if (event.type === 'speech_audio') {
        voice.push(event.utterance_id, event.sample_rate, event.pcm)
      } else if (event.type === 'speech_end') {
        voice.end(event.utterance_id)
      }
    }

    const offEvent = client.onEvent(handleEvent)
    const offStatus = client.onStatus((status) => {
      dispatch({ type: 'connection_changed', status })
      if (status === 'disconnected') {
        stopSpeech()
        director.onPhaseChanged('idle')
      }
    })
    client.connect()

    return () => {
      offEvent()
      offStatus()
      stopSpeech()
      voice.dispose()
      client.disconnect()
    }
  }, [avatar, client, voice])

  const sendUserMessage = useCallback(
    (text: string) => {
      const trimmed = text.trim()
      if (!trimmed) return false
      speechAbort.current?.abort() // The user interrupting cancels the current speech.
      const sent = client.send({ type: 'user_message', text: trimmed })
      if (sent) dispatch({ type: 'user_message_sent', text: trimmed })
      return sent
    },
    [client],
  )

  const selectCharacter = useCallback(
    (characterId: string) => client.send({ type: 'select_character', character_id: characterId }),
    [client],
  )

  const clearConversation = useCallback(
    () => client.send({ type: 'clear_conversation' }),
    [client],
  )

  const selectModel = useCallback(
    (model: string) => client.send({ type: 'select_model', model }),
    [client],
  )

  const setVoice = useCallback(
    (enabled: boolean) => client.send({ type: 'set_voice', enabled }),
    [client],
  )

  const setVoiceVolume = useCallback(
    (volume: number) => {
      const clamped = clampVolume(volume)
      voice.setVolume(clamped)
      saveVoiceVolume(clamped)
      setVolumeState(clamped)
    },
    [voice],
  )

  return {
    state,
    avatar,
    sendUserMessage,
    selectCharacter,
    clearConversation,
    selectModel,
    setVoice,
    voiceVolume,
    setVoiceVolume,
  }
}
