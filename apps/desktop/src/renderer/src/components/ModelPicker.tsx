interface ModelPickerProps {
  models: string[]
  currentModel: string
  disabled: boolean
  onSelect: (model: string) => void
}

/** AI model for every character. Only installed local models; switching reloads it. */
export function ModelPicker({ models, currentModel, disabled, onSelect }: ModelPickerProps) {
  // The saved model may have been deleted from Ollama: still show what is in use.
  const options = models.includes(currentModel) ? models : [currentModel, ...models]
  return (
    <select
      className="model-picker"
      aria-label="Modelo"
      title="Modelo de IA (para todos los personajes). Al cambiar tarda unos segundos en cargar."
      value={currentModel}
      disabled={disabled || options.length < 2}
      onChange={(event) => onSelect(event.target.value)}
    >
      {options.map((model) => (
        <option key={model} value={model}>
          {model}
        </option>
      ))}
    </select>
  )
}
