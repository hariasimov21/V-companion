import type { CharacterSummary } from '../protocol/types'

interface CharacterPickerProps {
  characters: CharacterSummary[]
  currentId: string
  disabled: boolean
  onSelect: (characterId: string) => void
}

/** Character name that doubles as a selector. Each character resumes its own conversation. */
export function CharacterPicker({ characters, currentId, disabled, onSelect }: CharacterPickerProps) {
  return (
    <select
      className="character-picker"
      aria-label="Character"
      title="Cambiar de personaje (cada uno retoma su conversación)"
      value={currentId}
      disabled={disabled || characters.length < 2}
      onChange={(event) => onSelect(event.target.value)}
    >
      {characters.map((character) => (
        <option key={character.id} value={character.id}>
          {character.name}
        </option>
      ))}
    </select>
  )
}
