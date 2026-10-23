import { useEffect, useState } from 'react'
import { api } from '../api'

export default function SettingsPage() {
  const [status, setStatus] = useState(null)
  const [apiKey, setApiKey] = useState('')
  const [model, setModel] = useState('gpt-4o-mini')
  const [msg, setMsg] = useState('')
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  const load = () => {
    setError('')
    api
      .settingsAi()
      .then((s) => {
        setStatus(s)
        if (s?.openai_model) setModel(s.openai_model)
      })
      .catch((e) => setError(String(e.message || e)))
  }

  useEffect(() => {
    load()
  }, [])

  const save = () => {
    setSaving(true)
    setMsg('')
    setError('')
    api
      .settingsAiSave({
        api_key: apiKey.trim() || undefined,
        model: model.trim() || undefined,
      })
      .then((s) => {
        setStatus(s)
        setApiKey('')
        setMsg('Gespeichert in .env (nur lokal, nicht in Git).')
      })
      .catch((e) => setError(String(e.message || e)))
      .finally(() => setSaving(false))
  }

  const clearKey = () => {
    if (!window.confirm('OpenAI-API-Key aus .env entfernen?')) return
    setSaving(true)
    setMsg('')
    setError('')
    api
      .settingsAiClear()
      .then((s) => {
        setStatus(s)
        setMsg('API-Key entfernt.')
      })
      .catch((e) => setError(String(e.message || e)))
      .finally(() => setSaving(false))
  }

  const downloadEnv = () => {
    api
      .settingsAiEnvExport()
      .then((blob) => {
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = '.env'
        a.click()
        URL.revokeObjectURL(url)
        setMsg('Vorlage heruntergeladen — Key in der Datei einfügen und als .env speichern.')
      })
      .catch((e) => setError(String(e.message || e)))
  }

  return (
    <div className="main settings-page">
      <div className="toolbar" style={{ justifyContent: 'space-between' }}>
        <div>
          <h1 className="page-title">Einstellungen</h1>
          <p className="page-sub">API-Keys lokal speichern — nur den Key einfügen</p>
        </div>
        <button type="button" className="nav-btn nav-btn--muted" onClick={load}>
          Aktualisieren
        </button>
      </div>

      {error ? <p className="error">{error}</p> : null}
      {msg ? <p className="muted">{msg}</p> : null}

      <section className="settings-card">
        <h2 className="settings-h">OpenAI (KI-Analyse)</h2>
        <p className="muted" style={{ marginTop: 0 }}>
          Key unter{' '}
          <a href="https://platform.openai.com/settings/organization/api-keys" target="_blank" rel="noreferrer">
            platform.openai.com → API keys
          </a>{' '}
          erzeugen. Wird in <code>.env</code> im Projektroot gespeichert (nicht committen).
        </p>

        <div className="settings-status">
          <span className={`pill ${status?.openai_configured ? 'pill-live' : 'pill-muted'}`}>
            {status?.openai_configured ? 'Key hinterlegt' : 'Kein Key'}
          </span>
          {status?.openai_key_masked ? (
            <code className="settings-masked">{status.openai_key_masked}</code>
          ) : null}
          <span className="muted">Modell: {status?.openai_model || model}</span>
        </div>

        <label className="strat-field">
          <span>OpenAI API-Key</span>
          <input
            type="password"
            autoComplete="off"
            placeholder={status?.openai_configured ? 'Neuen Key einfügen (ersetzt den alten)' : 'sk-… hier einfügen'}
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
          />
        </label>

        <label className="strat-field">
          <span>Modell</span>
          <input
            type="text"
            value={model}
            onChange={(e) => setModel(e.target.value)}
            placeholder="gpt-4o-mini"
          />
        </label>

        <div className="settings-actions">
          <button type="button" className="nav-btn" onClick={save} disabled={saving || (!apiKey.trim() && !model.trim())}>
            {saving ? 'Speichern…' : 'Speichern'}
          </button>
          <button type="button" className="nav-btn nav-btn--muted" onClick={downloadEnv}>
            .env Vorlage exportieren
          </button>
          <button
            type="button"
            className="nav-btn nav-btn--muted"
            onClick={clearKey}
            disabled={saving || !status?.openai_configured}
          >
            Key löschen
          </button>
        </div>

        <ol className="settings-steps muted">
          <li>
            Entweder Key oben einfügen → <strong>Speichern</strong>
          </li>
          <li>
            Oder <strong>.env Vorlage exportieren</strong> → Datei öffnen → nur <code>sk-...</code> ersetzen → als{' '}
            <code>.env</code> im Projektordner speichern → API neu starten
          </li>
        </ol>
      </section>
    </div>
  )
}
