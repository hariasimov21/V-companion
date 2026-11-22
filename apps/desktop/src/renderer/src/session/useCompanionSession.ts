import { useCallback, useEffect, useReducer, useRef, useState } from 'react'

import { AvatarDirector } from '../avatar/AvatarDirector'
import { ObservableAvatarController } from '../avatar/ObservableAvatarController'
import { appConfig } from '../config/appConfig'
import type { ServerEvent } from '../protocol/types'
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

  useEffect(() => {
    const director = new AvatarDirector(avatar)
    const speech = new TextOnlySpeechOutput(appConfig.speech)

    const stopSpeech = () => {
      speechAbort.current?.abort()
      speechAbort.current = null
    }

    const speak = (text: string) => {
      stopSpeech()
      const abort = new AbortController()
      speechAbort.current = abort
      speech
        .speak(text, abort.signal)
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
        speak(event.text)
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
      client.disconnect()
    }
  }, [avatar, client])

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

  return { state, avatar, sendUserMessage, selectCharacter, clearConversation, selectModel }
}
