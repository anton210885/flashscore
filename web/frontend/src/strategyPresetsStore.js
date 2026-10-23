/** Gespeicherte Strategie-Filter: Server (data/strategy_presets.json), localStorage nur als Cache.
 *
 * localStorage gilt pro Adresse (:5173 vs. :8000) — deshalb liegt der Stand auf dem Server.
 */
import { api } from './api'

const KEY = 'flashscore_strategy_presets'
// Gesetzt, sobald die Presets dieses Browsers/dieser Adresse einmal zum Server übernommen wurden
const MIGRATED_KEY = 'flashscore_strategy_presets_on_server'

function readAll() {
  try {
    const raw = localStorage.getItem(KEY)
    if (!raw) return []
    const list = JSON.parse(raw)
    return Array.isArray(list) ? list : []
  } catch {
    return []
  }
}

function writeCache(list) {
  localStorage.setItem(KEY, JSON.stringify(list))
  window.dispatchEvent(new CustomEvent('strategy-presets', { detail: list }))
  return list
}

function writeAll(list) {
  writeCache(list)
  api.strategyPresetsSave(list).catch(() => {})
  return list
}

/** Stand vom Server holen; beim ersten Mal lokale Presets dieser Adresse dazunehmen. */
export async function syncStrategyPresets() {
  const server = (await api.strategyPresets()).presets || []
  let list = server
  if (!localStorage.getItem(MIGRATED_KEY)) {
    const names = new Set(server.map((p) => String(p.name || '').toLowerCase()))
    const local = readAll().filter((p) => !names.has(String(p.name || '').toLowerCase()))
    if (local.length) {
      list = (await api.strategyPresetsSave([...server, ...local])).presets || list
    }
    localStorage.setItem(MIGRATED_KEY, '1')
  }
  return writeCache(list)
}

export function listStrategyPresets() {
  return readAll().sort((a, b) => (b.updatedAt || 0) - (a.updatedAt || 0))
}

export function saveStrategyPreset(name, filters) {
  const title = String(name || '').trim()
  if (!title) throw new Error('Name für die Strategie fehlt.')
  if (!filters || typeof filters !== 'object') throw new Error('Keine Filter zum Speichern.')

  const now = Date.now()
  const list = readAll()
  const idx = list.findIndex((p) => p.name.toLowerCase() === title.toLowerCase())
  const entry = {
    id: idx >= 0 ? list[idx].id : `sp_${now.toString(36)}_${Math.random().toString(36).slice(2, 7)}`,
    name: title,
    filters: { ...filters },
    createdAt: idx >= 0 ? list[idx].createdAt || now : now,
    updatedAt: now,
  }
  if (idx >= 0) list[idx] = entry
  else list.push(entry)
  writeAll(list)
  return entry
}

export function getStrategyPreset(id) {
  return readAll().find((p) => p.id === id) || null
}

export function deleteStrategyPreset(id) {
  const next = readAll().filter((p) => p.id !== id)
  writeAll(next)
  return next
}
