import { type FormEvent, useEffect, useRef, useState } from 'react'

import type { ChatEntry } from '../state/appState'

interface ChatPanelProps {
  characterName: string
  messages: ChatEntry[]
  canSend: boolean
  error: string | null
  onSend: (text: string) => boolean
}

export function ChatPanel({ characterName, messages, canSend, error, onSend }: ChatPanelProps) {
  const [draft, setDraft] = useState('')
  const listEnd = useRef<HTMLDivElement>(null)

  useEffect(() => {
    listEnd.current?.scrollIntoView?.({ behavior: 'smooth' })
  }, [messages.length])

  const submit = (event: FormEvent) => {
    event.preventDefault()
    if (canSend && onSend(draft)) setDraft('')
  }

  return (
    <section className="chat-panel">
      <div className="chat-panel__messages">
        {messages.length === 0 && <p className="chat-panel__empty">Escribe algo para empezar.</p>}
        {messages.map((message) => (
          <div key={message.id} className={`chat-message chat-message--${message.role}`}>
            <span className="chat-message__author">
              {message.role === 'user' ? 'Tú' : characterName}
              {message.role === 'assistant' && (
                <span className="chat-message__meta"> · {message.emotion}</span>
              )}
            </span>
            <p>{message.text}</p>
          </div>
        ))}
        <div ref={listEnd} />
      </div>
      {error && (
        <div className="chat-panel__error" role="alert">
          AI connection error: {error}
        </div>
      )}
      <form className="chat-panel__form" onSubmit={submit}>
        <input
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder={canSend ? 'Mensaje…' : 'Esperando…'}
          maxLength={4000}
          aria-label="Mensaje"
        />
        <button type="submit" disabled={!canSend || !draft.trim()}>
          Enviar
        </button>
      </form>
    </section>
  )
}
