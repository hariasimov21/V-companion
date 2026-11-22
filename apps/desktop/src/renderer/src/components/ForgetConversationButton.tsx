import { useState } from 'react'

interface ForgetConversationButtonProps {
  characterName: string
  disabled: boolean
  onConfirm: () => void
}

/** Forgets the active character's conversation. Asks first: it cannot be undone. */
export function ForgetConversationButton({
  characterName,
  disabled,
  onConfirm,
}: ForgetConversationButtonProps) {
  const [confirming, setConfirming] = useState(false)

  if (!confirming || disabled) {
    return (
      <button
        type="button"
        className="forget-conversation"
        disabled={disabled}
        title={`Borra todo lo que has hablado con ${characterName} y lo que recuerda de ti`}
        onClick={() => setConfirming(true)}
      >
        Olvidar conversación
      </button>
    )
  }

  return (
    <div
      className="forget-conversation__confirm"
      role="alertdialog"
      aria-label="Confirmar olvido"
      onKeyDown={(event) => event.key === 'Escape' && setConfirming(false)}
    >
      <span>¿Olvidar todo lo hablado con {characterName}? No se puede deshacer.</span>
      <div className="forget-conversation__actions">
        <button
          type="button"
          className="forget-conversation__yes"
          onClick={() => {
            setConfirming(false)
            onConfirm()
          }}
        >
          Sí, olvidar
        </button>
        <button type="button" autoFocus onClick={() => setConfirming(false)}>
          Cancelar
        </button>
      </div>
    </div>
  )
}
