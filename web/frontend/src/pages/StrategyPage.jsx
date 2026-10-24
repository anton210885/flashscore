import { useEffect, useMemo, useState } from 'react'
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  Cell,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  Legend,
  ReferenceLine,
  LabelList,
} from 'recharts'
import { api } from '../api'
import SwisslosBadge from '../components/SwisslosBadge'
import { loadStrategyResults, saveStrategyResults } from '../strategyResultsStore'
import {
  listStrategyPresets,
  saveStrategyPreset,
  getStrategyPreset,
  deleteStrategyPreset,
  syncStrategyPresets,
} from '../strategyPresetsStore'
import { metricName, withMetricNames } from '../metricNames'
import MatchParamsPanel from '../components/MatchParamsPanel'
import StrategyHover, { fromHistory } from '../components/StrategyHover'
import {
  ANALYSE_HELP_TITLE,
  CORR_COLUMN_MAP,
  CORR_METRIC_MAP,
  METRIKEN_HELP_TITLE,
} from '../strategyHelp'
import {
  CorrelationHelpPanel,
  CorrRowExplainPanel,
  MetrikenHelpPanel,
} from '../components/StrategyHelpPanels'
import {
  num,
  oddsNum,
  pctCell,
  resolveEquity,
  resolveGlicko,
  resolveOutcomes,
} from '../strategyDisplay'

const MARKET_OPTS = [
  { key: 'market_home', label: 'Home' },
  { key: 'market_draw', label: 'Draw' },
  { key: 'market_away', label: 'Away' },
  { key: 'market_over', label: 'Over 2.5' },
  { key: 'market_under', label: 'Under 2.5' },
  { key: 'market_over_35', label: 'Over 3.5' },
  { key: 'market_under_35', label: 'Under 3.5' },
]

/** FT-Ergebnis-Filter (Look-ahead) — nur Backtest, nicht Upcoming */
const FT_OUTCOME_OPTS = [
  { key: 'ft_home_win', label: 'Home gewonnen' },
  { key: 'ft_draw', label: 'Unentschieden' },
  { key: 'ft_away_win', label: 'Away gewonnen' },
  { key: 'ft_over_25', label: 'Over 2.5' },
  { key: 'ft_under_25', label: 'Under 2.5' },
]

function Range({ label, minKey, maxKey, filters, setFilters, step = 'any' }) {
  return (
    <label className="strat-field">
      <span>{label}</span>
      <div className="strat-range">
        <input
          type="number"
          step={step}
          placeholder="min"
          value={filters[minKey] ?? ''}
          onChange={(e) => setFilters((f) => ({ ...f, [minKey]: e.target.value }))}
        />
        <span>–</span>
        <input
          type="number"
          step={step}
          placeholder="max"
          value={filters[maxKey] ?? ''}
          onChange={(e) => setFilters((f) => ({ ...f, [maxKey]: e.target.value }))}
        />
      </div>
    </label>
  )
}

function filled(v) {
  return v !== '' && v != null && v !== false
}

/** Kurze Chips für aktive Filter — Überblick ohne alle Panels offen zu lassen. */
function activeFilterChips(filters) {
  const chips = []
  const markets = MARKET_OPTS.filter((o) => filters[o.key]).map((o) => o.label)
  if (markets.length) chips.push(`Markt: ${markets.join(', ')}`)
  else chips.push('Markt: —')
  if (filters.gender_filter && filters.gender_filter !== 'all') {
    chips.push(filters.gender_filter === 'women' ? 'Frauen' : 'Männer')
  }
  chips.push(filters.odds_type === 'opening' ? 'Opening' : 'Closing')
  const ranges = [
    ['Home Q', 'odds_home_min', 'odds_home_max'],
    ['Away Q', 'odds_away_min', 'odds_away_max'],
    ['O2.5 Q', 'odds_over_min', 'odds_over_max'],
    ['U2.5 Q', 'odds_under_min', 'odds_under_max'],
    ['xROI', 'xroi_min', 'xroi_max'],
    ['ROI', 'roi_min', 'roi_max'],
  ]
  for (const [label, a, b] of ranges) {
    if (filled(filters[a]) || filled(filters[b])) {
      chips.push(`${label} ${filters[a] || '…'}–${filters[b] || '…'}`)
    }
  }
  const ft = FT_OUTCOME_OPTS.filter((o) => filters[o.key]).map((o) => o.label)
  if (ft.length) chips.push(`Ergebnis: ${ft.join(', ')}`)
  if (filters.use_xg_comparison) {
    const nExtra = Array.isArray(filters.xg_comparisons) ? filters.xg_comparisons.length : 0
    chips.push(nExtra > 0 ? `Vergleich (${1 + nExtra})` : 'Vergleich an')
  }
  if (filters.use_percentile) {
    chips.push(`Top ${filters.percentile_value || 10}% ${filters.percentile_metric || 'chance'}`)
  }
  if (filled(filters.league_filter)) chips.push(`Liga: ${filters.league_filter}`)
  if (filled(filters.country_filter)) chips.push(`Land: ${filters.country_filter}`)
  const advancedKeys = [
    'xg_glicko_home_min', 'xg_glicko_home_max', 'xg_glicko_away_min', 'xg_glicko_away_max',
    'xg_form2_home_min', 'xg_form2_home_max', 'xg_form2_away_min', 'xg_form2_away_max',
    'xg_match_home_min', 'xg_match_home_max', 'xg_match_away_min', 'xg_match_away_max',
    'glicko_home_min', 'glicko_home_max', 'glicko_away_min', 'glicko_away_max',
    'glicko_rd_home_min', 'glicko_rd_home_max', 'glicko_rd_away_min', 'glicko_rd_away_max',
    'glicko_vol_home_min', 'glicko_vol_home_max', 'glicko_vol_away_min', 'glicko_vol_away_max',
    'glicko_p_home_min', 'glicko_p_home_max', 'glicko_p_draw_min', 'glicko_p_draw_max',
    'glicko_p_away_min', 'glicko_p_away_max',
    'season_games_home_min', 'season_games_home_max', 'season_games_away_min', 'season_games_away_max',
  ]
  if (advancedKeys.some((k) => filled(filters[k]))) chips.push('Glicko/Saison-Filter')
  const matchXgKeys = ['xg_match_home_min', 'xg_match_home_max', 'xg_match_away_min', 'xg_match_away_max']
  if (matchXgKeys.some((k) => filled(filters[k]))) chips.push('Match-xG (Look-ahead)')
  return chips
}

const CMP_ATTRS = withMetricNames([
  { value: 'rating_home', label: 'homeRating' },
  { value: 'rating_away', label: 'awayRating' },
  { value: 'xg_home_glicko', label: 'xG Glicko Home' },
  { value: 'xg_away_glicko', label: 'xG Glicko Away' },
  { value: 'rd_home', label: 'homeRd' },
  { value: 'rd_away', label: 'awayRd' },
  { value: 'vol_home', label: 'homeVol' },
  { value: 'vol_away', label: 'awayVol' },
  { value: 'p_home', label: 'P(Home)' },
  { value: 'p_draw', label: 'P(Draw)' },
  { value: 'p_away', label: 'P(Away)' },
  { value: 'xg_form2_home', label: 'xG Form2 Home' },
  { value: 'xg_form2_away', label: 'xG Form2 Away' },
  { value: 'form2_avg_xg_home', label: 'Form2 Ø xG Home' },
  { value: 'form2_avg_xg_away', label: 'Form2 Ø xG Away' },
  { value: 'form2_avg_xga_home', label: 'Form2 Ø xGA Home' },
  { value: 'form2_avg_xga_away', label: 'Form2 Ø xGA Away' },
  { value: 'form2_avg_gf_home', label: 'Form2 Ø Tore Home' },
  { value: 'form2_avg_gf_away', label: 'Form2 Ø Tore Away' },
  { value: 'form2_avg_ga_home', label: 'Form2 Ø Gegentore Home' },
  { value: 'form2_avg_ga_away', label: 'Form2 Ø Gegentore Away' },
  { value: 'hometeam_home_xg', label: 'hometeam_home_xg' },
  { value: 'hometeam_home_xga', label: 'hometeam_home_xga' },
  { value: 'hometeam_home_gf', label: 'hometeam_home_gf' },
  { value: 'hometeam_home_ga', label: 'hometeam_home_ga' },
  { value: 'hometeam_away_xg', label: 'hometeam_away_xg' },
  { value: 'hometeam_away_xga', label: 'hometeam_away_xga' },
  { value: 'hometeam_away_gf', label: 'hometeam_away_gf' },
  { value: 'hometeam_away_ga', label: 'hometeam_away_ga' },
  { value: 'awayteam_home_xg', label: 'awayteam_home_xg' },
  { value: 'awayteam_home_xga', label: 'awayteam_home_xga' },
  { value: 'awayteam_home_gf', label: 'awayteam_home_gf' },
  { value: 'awayteam_home_ga', label: 'awayteam_home_ga' },
  { value: 'awayteam_away_xg', label: 'awayteam_away_xg' },
  { value: 'awayteam_away_xga', label: 'awayteam_away_xga' },
  { value: 'awayteam_away_gf', label: 'awayteam_away_gf' },
  { value: 'awayteam_away_ga', label: 'awayteam_away_ga' },
  { value: 'hometeam_pred_xg', label: 'hometeam_pred_xg' },
  { value: 'awayteam_pred_xg', label: 'awayteam_pred_xg' },
  { value: 'power_home', label: 'power_home' },
  { value: 'power_away', label: 'power_away' },
  { value: 'power_diff', label: 'power_diff' },
  { value: 'tempo_home', label: 'tempo_home' },
  { value: 'tempo_away', label: 'tempo_away' },
  { value: 'tempo_sum', label: 'tempo_sum' },
  { value: 'power_home_venue', label: 'power_home_venue' },
  { value: 'power_away_venue', label: 'power_away_venue' },
  { value: 'power_diff_venue', label: 'power_diff_venue' },
  { value: 'tempo_home_venue', label: 'tempo_home_venue' },
  { value: 'tempo_away_venue', label: 'tempo_away_venue' },
])

const PCT_METRICS = withMetricNames([
  { value: 'chance', label: 'Chance (Modell)' },
  { value: 'glicko_rating', label: 'Ø Glicko Rating' },
  { value: 'rating_diff', label: 'Rating Diff (H−A)' },
  { value: 'rating_sum', label: 'Rating Summe (H+A)' },
  { value: 'glicko_xg', label: 'xG Summe (Glicko)' },
  { value: 'xg_glicko_diff', label: 'xG Glicko Diff (H−A)' },
  { value: 'xg_glicko_ratio', label: 'xG Glicko-Verhältnis H/A' },
  { value: 'xg_glicko_home', label: 'xG Glicko Home' },
  { value: 'xg_glicko_away', label: 'xG Glicko Away' },
  { value: 'xg_form2_home', label: 'xG Form2 Home' },
  { value: 'xg_form2_away', label: 'xG Form2 Away' },
  { value: 'xg_form2_sum', label: 'xG Form2 Summe' },
  { value: 'xg_form2_diff', label: 'xG Form2 Diff (H−A)' },
  { value: 'xg_form2_ratio', label: 'xG Form2-Verhältnis H/A' },
  { value: 'form2_avg_xg_home', label: 'Form2 Ø xG Home' },
  { value: 'form2_avg_xg_away', label: 'Form2 Ø xG Away' },
  { value: 'form2_avg_xga_home', label: 'Form2 Ø xGA Home' },
  { value: 'form2_avg_xga_away', label: 'Form2 Ø xGA Away' },
  { value: 'form2_avg_gf_home', label: 'Form2 Ø Tore Home' },
  { value: 'form2_avg_gf_away', label: 'Form2 Ø Tore Away' },
  { value: 'form2_avg_ga_home', label: 'Form2 Ø Gegentore Home' },
  { value: 'form2_avg_ga_away', label: 'Form2 Ø Gegentore Away' },
  { value: 'hometeam_home_xg', label: 'hometeam_home_xg' },
  { value: 'hometeam_home_xga', label: 'hometeam_home_xga' },
  { value: 'hometeam_away_xg', label: 'hometeam_away_xg' },
  { value: 'awayteam_away_xg', label: 'awayteam_away_xg' },
  { value: 'awayteam_away_xga', label: 'awayteam_away_xga' },
  { value: 'hometeam_pred_xg', label: 'hometeam_pred_xg' },
  { value: 'awayteam_pred_xg', label: 'awayteam_pred_xg' },
  { value: 'odds', label: 'Quote' },
  { value: 'xroi_pct', label: 'xROI %' },
  { value: 'profit', label: 'Profit (Look-ahead!)' },
  { value: 'power_home', label: 'power_home' },
  { value: 'power_away', label: 'power_away' },
  { value: 'power_diff', label: 'power_diff' },
  { value: 'tempo_home', label: 'tempo_home' },
  { value: 'tempo_away', label: 'tempo_away' },
  { value: 'tempo_sum', label: 'tempo_sum' },
  { value: 'power_home_venue', label: 'power_home_venue' },
  { value: 'power_away_venue', label: 'power_away_venue' },
  { value: 'power_diff_venue', label: 'power_diff_venue' },
  { value: 'tempo_home_venue', label: 'tempo_home_venue' },
  { value: 'tempo_away_venue', label: 'tempo_away_venue' },
])

const EMPTY_CMP = {
  attr1: 'xg_form2_home',
  operation: '-',
  attr2: 'xg_form2_away',
  comparison_operator: '>=',
  comparison_value: '',
}

const MAX_XG_COMPARISONS = 4

const PCT_VALUES = ['1', '5', '10', '15', '20', '25', '30', '50']

const BUCKET_METRICS = withMetricNames([
  { value: 'home_quote', label: 'Home-Quote' },
  { value: 'away_quote', label: 'Away-Quote' },
  { value: 'over_25_quote', label: 'Over 2.5 Quote' },
  { value: 'odds', label: 'Quote (gewählter Markt)' },
  { value: 'rating_diff', label: 'Rating Diff (H−A)' },
  { value: 'rating_ratio', label: 'Rating-Verhältnis H/A' },
  { value: 'rating_sum', label: 'Rating Summe (H+A)' },
  { value: 'rating_home', label: 'Rating Home' },
  { value: 'rating_away', label: 'Rating Away' },
  { value: 'xg_glicko_diff', label: 'xG Glicko Diff (H−A)' },
  { value: 'xg_glicko_ratio', label: 'xG Glicko-Verhältnis H/A' },
  { value: 'xg_glicko_sum', label: 'xG Glicko Summe' },
  { value: 'xg_glicko_home', label: 'xG Glicko Home' },
  { value: 'xg_glicko_away', label: 'xG Glicko Away' },
  { value: 'xg_form2_diff', label: 'xG Form2 Diff (H−A)' },
  { value: 'xg_form2_ratio', label: 'xG Form2-Verhältnis H/A' },
  { value: 'xg_form2_sum', label: 'xG Form2 Summe' },
  { value: 'xg_form2_home', label: 'xG Form2 Home' },
  { value: 'xg_form2_away', label: 'xG Form2 Away' },
  { value: 'form2_avg_xg_home', label: 'Form2 Ø xG Home' },
  { value: 'form2_avg_xg_away', label: 'Form2 Ø xG Away' },
  { value: 'form2_avg_xga_home', label: 'Form2 Ø xGA Home' },
  { value: 'form2_avg_xga_away', label: 'Form2 Ø xGA Away' },
  { value: 'form2_avg_gf_home', label: 'Form2 Ø Tore Home' },
  { value: 'form2_avg_gf_away', label: 'Form2 Ø Tore Away' },
  { value: 'form2_avg_ga_home', label: 'Form2 Ø Gegentore Home' },
  { value: 'form2_avg_ga_away', label: 'Form2 Ø Gegentore Away' },
  { value: 'hometeam_home_xg', label: 'hometeam_home_xg' },
  { value: 'hometeam_home_xga', label: 'hometeam_home_xga' },
  { value: 'hometeam_home_gf', label: 'hometeam_home_gf' },
  { value: 'hometeam_home_ga', label: 'hometeam_home_ga' },
  { value: 'hometeam_away_xg', label: 'hometeam_away_xg' },
  { value: 'hometeam_away_xga', label: 'hometeam_away_xga' },
  { value: 'awayteam_home_xg', label: 'awayteam_home_xg' },
  { value: 'awayteam_home_xga', label: 'awayteam_home_xga' },
  { value: 'awayteam_away_xg', label: 'awayteam_away_xg' },
  { value: 'awayteam_away_xga', label: 'awayteam_away_xga' },
  { value: 'hometeam_pred_xg', label: 'hometeam_pred_xg' },
  { value: 'awayteam_pred_xg', label: 'awayteam_pred_xg' },
  { value: 'chance', label: 'Chance' },
  { value: 'xroi_pct', label: 'xROI %' },
  { value: 'power_home', label: 'power_home' },
  { value: 'power_away', label: 'power_away' },
  { value: 'power_diff', label: 'power_diff' },
  { value: 'tempo_home', label: 'tempo_home' },
  { value: 'tempo_away', label: 'tempo_away' },
  { value: 'tempo_sum', label: 'tempo_sum' },
  { value: 'power_home_venue', label: 'power_home_venue' },
  { value: 'power_away_venue', label: 'power_away_venue' },
  { value: 'power_diff_venue', label: 'power_diff_venue' },
  { value: 'tempo_home_venue', label: 'tempo_home_venue' },
  { value: 'tempo_away_venue', label: 'tempo_away_venue' },
])

const DEFAULTS = {
  market_over: true,
  odds_type: 'closing',
  odds_home_min: '',
  odds_home_max: '',
  odds_away_min: '',
  odds_away_max: '',
  odds_over_min: '',
  odds_over_max: '',
  odds_under_min: '',
  odds_under_max: '',
  xroi_min: '',
  xroi_max: '',
  roi_min: '',
  roi_max: '',
  gender_filter: 'men',
  league_filter: '',
  country_filter: '',
  date_from: '',
  date_to: '',
  ft_home_win: false,
  ft_draw: false,
  ft_away_win: false,
  ft_over_25: false,
  ft_under_25: false,
  use_xg_comparison: false,
  xg_attr1: 'rating_home',
  xg_operation: '-',
  xg_attr2: 'rating_away',
  xg_comparison_operator: '>=',
  xg_comparison_value: '',
  xg_comparisons: [],
  use_percentile: false,
  percentile_value: '10',
  percentile_metric: 'chance',
  xg_glicko_home_min: '',
  xg_glicko_home_max: '',
  xg_glicko_away_min: '',
  xg_glicko_away_max: '',
  xg_form2_home_min: '',
  xg_form2_home_max: '',
  xg_form2_away_min: '',
  xg_form2_away_max: '',
  xg_match_home_min: '',
  xg_match_home_max: '',
  xg_match_away_min: '',
  xg_match_away_max: '',
  season_games_home_min: '',
  season_games_home_max: '',
  season_games_away_min: '',
  season_games_away_max: '',
  glicko_home_min: '',
  glicko_home_max: '',
  glicko_away_min: '',
  glicko_away_max: '',
  glicko_rd_home_min: '',
  glicko_rd_home_max: '',
  glicko_rd_away_min: '',
  glicko_rd_away_max: '',
  glicko_vol_home_min: '',
  glicko_vol_home_max: '',
  glicko_vol_away_min: '',
  glicko_vol_away_max: '',
  glicko_p_home_min: '',
  glicko_p_home_max: '',
  glicko_p_draw_min: '',
  glicko_p_draw_max: '',
  glicko_p_away_min: '',
  glicko_p_away_max: '',
}

function CmpConditionRow({
  attr1,
  operation,
  attr2,
  comparisonOperator,
  comparisonValue,
  disabled,
  onChange,
}) {
  return (
    <div className="strat-cmp-row">
      <select
        value={attr1}
        onChange={(e) => onChange({ attr1: e.target.value })}
        disabled={disabled}
      >
        {CMP_ATTRS.map((a) => (
          <option key={a.value} value={a.value}>{a.label}</option>
        ))}
      </select>
      <select
        value={operation}
        onChange={(e) => onChange({ operation: e.target.value })}
        disabled={disabled}
        title="vs = direkt vergleichen; sonst Rechnung"
      >
        <option value="vs">vs</option>
        <option value="-">−</option>
        <option value="+">+</option>
        <option value="*">×</option>
        <option value="/">÷</option>
      </select>
      <select
        value={attr2}
        onChange={(e) => onChange({ attr2: e.target.value })}
        disabled={disabled}
      >
        {CMP_ATTRS.map((a) => (
          <option key={`b-${a.value}`} value={a.value}>{a.label}</option>
        ))}
      </select>
      <select
        value={comparisonOperator}
        onChange={(e) => onChange({ comparison_operator: e.target.value })}
        disabled={disabled}
      >
        <option value=">=">≥</option>
        <option value="<=">≤</option>
        <option value=">">&gt;</option>
        <option value="<">&lt;</option>
        <option value="=">=</option>
        <option value="!=">≠</option>
      </select>
      <input
        type="number"
        step="any"
        placeholder={operation === 'vs' ? '— (vs)' : 'Wert'}
        value={comparisonValue}
        onChange={(e) => onChange({ comparison_value: e.target.value })}
        disabled={disabled || operation === 'vs'}
      />
    </div>
  )
}

export default function StrategyPage() {
  const [filters, setFilters] = useState({ ...DEFAULTS })
  const [data, setData] = useState(null)
  const [upcoming, setUpcoming] = useState(null)
  const [rankReport, setRankReport] = useState(null)
  const [rankLoading, setRankLoading] = useState(false)
  const [corrSortBy, setCorrSortBy] = useState('roi') // roi | profit
  const [selectedCorrRow, setSelectedCorrRow] = useState(null)
  const [optReport, setOptReport] = useState(null)
  const [optLoading, setOptLoading] = useState(false)
  const [bucketReport, setBucketReport] = useState(null)
  const [bucketLoading, setBucketLoading] = useState(false)
  const [bucketMetric, setBucketMetric] = useState('rating_diff')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [tab, setTab] = useState('analyse') // analyse | metrics | corr | past | upcoming
  const [presets, setPresets] = useState(() => listStrategyPresets())
  const [presetName, setPresetName] = useState('')
  const [selectedPresetId, setSelectedPresetId] = useState('')
  const [presetMsg, setPresetMsg] = useState('')
  const [filtersOpen, setFiltersOpen] = useState(true)
  const [presetUpcomingMap, setPresetUpcomingMap] = useState({})
  const [presetUpcomingLoading, setPresetUpcomingLoading] = useState(false)
  const [presetUpcomingOpen, setPresetUpcomingOpen] = useState(false)
  const [presetUpcomingGames, setPresetUpcomingGames] = useState([])
  const [pastDetail, setPastDetail] = useState(null)

  useEffect(() => {
    const prev = loadStrategyResults()
    if (prev?.data?.ok) {
      setData(prev.data)
      setFiltersOpen(false) // Ergebnisse zuerst, Filter nur bei Bedarf
    }
    if (prev?.upcoming?.ok) setUpcoming(prev.upcoming)
    if (prev?.rankReport?.ok) setRankReport(prev.rankReport)
    if (prev?.filters && typeof prev.filters === 'object') {
      setFilters((f) => ({ ...DEFAULTS, ...prev.filters }))
    }
    const onPresets = () => setPresets(listStrategyPresets())
    window.addEventListener('strategy-presets', onPresets)
    syncStrategyPresets().catch(() => {})
    return () => window.removeEventListener('strategy-presets', onPresets)
  }, [])

  const resetFilters = () => {
    setFilters({ ...DEFAULTS })
    setPresetMsg('Filter zurückgesetzt (Defaults).')
    setFiltersOpen(true)
  }

  const savePreset = () => {
    try {
      const name =
        String(presetName || '').trim() ||
        presets.find((p) => p.id === selectedPresetId)?.name ||
        ''
      const entry = saveStrategyPreset(name, filters)
      setPresets(listStrategyPresets())
      setSelectedPresetId(entry.id)
      setPresetName(entry.name)
      setPresetMsg(`Gespeichert: ${entry.name}`)
      setError('')
    } catch (e) {
      setError(String(e.message || e))
      setPresetMsg('')
    }
  }

  const removePreset = () => {
    const id = selectedPresetId
    if (!id) return
    const entry = getStrategyPreset(id)
    if (!window.confirm(`Strategie „${entry?.name || id}“ löschen?`)) return
    deleteStrategyPreset(id)
    setPresets(listStrategyPresets())
    setSelectedPresetId('')
    setPresetMsg('Strategie gelöscht.')
  }

  const run = (overrideFilters = null, opts = {}) => {
    const f = overrideFilters ? { ...DEFAULTS, ...overrideFilters } : filters
    const preferUpcoming = !!opts.preferUpcoming
    setLoading(true)
    setError('')
    setTab(preferUpcoming ? 'upcoming' : 'analyse')
    setRankReport(null)
    api
      .strategyAnalyze(f, 500)
      .then((res) => {
        const up = res?.upcoming
        const finish = (upcomingRes) => {
          const upcomingFinal = upcomingRes || up || null
          setData(res)
          setUpcoming(upcomingFinal)
          setFiltersOpen(false)
          saveStrategyResults({ data: res, upcoming: upcomingFinal, filters: f, rankReport: null })
          if (preferUpcoming) {
            if (upcomingFinal?.skipped) {
              setTab('analyse')
              setPresetMsg(
                upcomingFinal.message ||
                  'Strategie geladen — Upcoming wegen Ergebnis-/ROI-Filter ausgeblendet.',
              )
            } else if (upcomingFinal?.ok && (upcomingFinal.n || 0) > 0) {
              setTab('upcoming')
              setPresetMsg(
                `Geladen · ${upcomingFinal.n} bevorstehende Spiele`,
              )
            } else {
              setTab('analyse')
              setPresetMsg('Geladen · keine bevorstehenden Treffer (Analyse zeigt Backtest).')
            }
          }
        }
        // FT-Ergebnis-Filter → kein Upcoming (Backend setzt skipped)
        if (up || up?.skipped) {
          finish(up)
          return null
        }
        return api.strategyUpcoming(f, 300).then(finish)
      })
      .catch((e) => {
        const msg = String(e.message || e)
        if (/not found/i.test(msg)) {
          setError(
            'API „Not Found“ — Backend neu starten (uvicorn), damit /api/strategy aktiv ist.',
          )
        } else {
          setError(msg)
        }
      })
      .finally(() => setLoading(false))
  }

  const loadPreset = () => {
    const id = selectedPresetId
    if (!id) {
      setError('Bitte gespeicherte Strategie wählen.')
      return
    }
    const entry = getStrategyPreset(id)
    if (!entry?.filters) {
      setError('Strategie nicht gefunden.')
      return
    }
    const next = { ...DEFAULTS, ...entry.filters }
    setFilters(next)
    setPresetName(entry.name)
    setRankReport(null)
    setPresetMsg(`Lade „${entry.name}“ inkl. bevorstehender Spiele…`)
    setError('')
    run(next, { preferUpcoming: true })
  }

  /** Alle gespeicherten Strategien auf bevorstehende Spiele prüfen (Überblick). */
  const scanPresetsUpcoming = () => {
    const list = listStrategyPresets()
    if (!list.length) {
      setError('Keine gespeicherten Strategien.')
      return
    }
    setPresetUpcomingLoading(true)
    setPresetUpcomingOpen(true)
    setError('')
    setPresetMsg(`Prüfe Upcoming für ${list.length} Strategien…`)
    api
      .strategyPresetsUpcoming(
        list.map((p) => ({ id: p.id, name: p.name, filters: { ...DEFAULTS, ...p.filters } })),
      )
      .then((res) => {
        const rows = (res?.strategies || []).map((s) => ({
          id: s.id,
          name: s.name,
          n: s.skipped ? 0 : Number(s.n_upcoming) || 0,
          skipped: !!s.skipped,
          message: s.message || null,
          ok: !!s.ok,
          error: s.error || null,
          losingStreak: s.losing_streak,
          winningStreak: s.winning_streak,
          history: s,
        }))
        const map = {}
        for (const r of rows) map[r.id] = r
        setPresetUpcomingMap(map)
        setPresetUpcomingGames(res?.matches || [])
        const withHits = rows.filter((r) => r.n > 0).length
        setPresetMsg(
          withHits > 0
            ? `${withHits} von ${rows.length} Strategien haben bevorstehende Spiele.`
            : `Keine bevorstehenden Treffer in ${rows.length} Strategien.`,
        )
      })
      .catch((e) => setError(String(e.message || e)))
      .finally(() => setPresetUpcomingLoading(false))
  }

  const openPresetFromUpcomingScan = (presetId) => {
    setSelectedPresetId(presetId)
    const entry = getStrategyPreset(presetId)
    if (!entry?.filters) return
    setPresetName(entry.name)
    const next = { ...DEFAULTS, ...entry.filters }
    setFilters(next)
    setPresetMsg(`Lade „${entry.name}“…`)
    run(next, { preferUpcoming: true })
  }

  const presetUpcomingRows = presets
    .map((p) => presetUpcomingMap[p.id] || null)
    .filter(Boolean)
    .sort((a, b) => (b.n || 0) - (a.n || 0) || String(a.name).localeCompare(String(b.name)))
  const presetUpcomingHits = presetUpcomingRows.filter((r) => r.n > 0).length

  const rankedCorrRows = useMemo(() => {
    const rows = [...(rankReport?.ranked || [])]
    if (corrSortBy === 'profit') {
      rows.sort(
        (a, b) =>
          (Number(b.profit_delta) || 0) - (Number(a.profit_delta) || 0) ||
          (Number(b.roi_delta) || 0) - (Number(a.roi_delta) || 0) ||
          (Number(b.n) || 0) - (Number(a.n) || 0),
      )
    } else {
      rows.sort(
        (a, b) =>
          (Number(b.roi_delta) || 0) - (Number(a.roi_delta) || 0) ||
          (Number(b.profit_delta) || 0) - (Number(a.profit_delta) || 0) ||
          (Number(b.n) || 0) - (Number(a.n) || 0),
      )
    }
    return rows
  }, [rankReport, corrSortBy])

  const runCorrelation = () => {
    setRankLoading(true)
    setError('')
    setSelectedCorrRow(null)
    setTab('corr')
    api
      .strategyMetricRank(filters, 40, corrSortBy)
      .then((res) => {
        setRankReport(res)
        saveStrategyResults({ data, upcoming, filters, rankReport: res })
      })
      .catch((e) => setError(String(e.message || e)))
      .finally(() => setRankLoading(false))
  }

  const runOptimize = () => {
    setOptLoading(true)
    setError('')
    setTab('corr')
    api
      .strategyOptimizeParams(filters, { minN: 25, maxParams: 2, topK: 15 })
      .then((res) => {
        if (!res?.ok) {
          setError(res?.error || 'Optimierung fehlgeschlagen.')
          setOptReport(null)
          return
        }
        setOptReport(res)
      })
      .catch((e) => setError(String(e.message || e)))
      .finally(() => setOptLoading(false))
  }

  const applyOptimizedFilters = (row) => {
    const patch = row?.suggested_filters
    if (!patch || !Object.keys(patch).length) {
      setError('Keine übernehmbaren Filter für diese Parameter (z. B. rating_diff nur über Attribut-Filter).')
      return
    }
    const next = { ...filters, ...patch }
    setFilters(next)
    setPresetMsg('Optimierte Filter übernommen — analysiere…')
    run(next)
  }

  const runBucketChart = (metricOverride = null) => {
    const metric = metricOverride || bucketMetric
    if (metricOverride) setBucketMetric(metricOverride)
    setBucketLoading(true)
    setError('')
    setTab('corr')
    api
      .strategyMetricBuckets(filters, { metric, bins: 16 })
      .then((res) => {
        if (!res?.ok) {
          setError(res?.error || 'Bucket-Grafik fehlgeschlagen.')
          setBucketReport(null)
          return
        }
        setBucketReport(res)
      })
      .catch((e) => setError(String(e.message || e)))
      .finally(() => setBucketLoading(false))
  }

  const bucketChartData = (bucketReport?.bins || []).map((b) => ({
    ...b,
    n: Number(b.n) || 0,
    label: b.label || `${num(b.bin_from, 2)}–${num(b.bin_to, 2)}`,
    isBest:
      bucketReport?.best_bin &&
      Math.abs(Number(b.bin_from) - Number(bucketReport.best_bin.bin_from)) < 1e-9 &&
      Math.abs(Number(b.bin_to) - Number(bucketReport.best_bin.bin_to)) < 1e-9,
  }))

  const bucketTooltip = ({ active, payload, label }) => {
    if (!active || !payload?.length) return null
    const row = payload[0]?.payload || {}
    return (
      <div className="strat-bucket-tooltip">
        <div className="strat-bucket-tooltip-title">Bereich {label}</div>
        <div>Spiele (n): <strong>{num(row.n, 0)}</strong></div>
        <div>Profit: <strong>{num(row.total_profit)}</strong></div>
        <div>ROI: <strong>{num(row.roi_pct, 1)}%</strong></div>
        <div>WR: <strong>{num(row.win_rate, 1)}%</strong></div>
      </div>
    )
  }

  const m = data?.metrics || {}
  const oc = resolveOutcomes(m, data?.results)
  const glicko = resolveGlicko(m, data?.results)
  const equity = resolveEquity(m, data?.results)
  const equitySeries = equity.series || []
  const pctInfo = data?.percentile || m.percentile || {}

  const filterChips = activeFilterChips(filters)

  return (
    <div className="main strategy-page">
      <div className="toolbar" style={{ justifyContent: 'space-between' }}>
        <div>
          <h1 className="page-title">Strategie</h1>
          <p className="page-sub">Preset laden oder Filter setzen → Analysieren → Ergebnisse</p>
        </div>
        <div className="toolbar-actions">
          <button
            type="button"
            className="nav-btn nav-btn--muted"
            onClick={() => setFiltersOpen((v) => !v)}
          >
            {filtersOpen ? 'Filter einklappen' : 'Filter bearbeiten'}
          </button>
          <button type="button" className="nav-btn nav-btn--muted" onClick={resetFilters}>
            Reset
          </button>
          <button type="button" className="nav-btn" onClick={() => run()} disabled={loading}>
            {loading ? 'Analysiert…' : 'Analysieren'}
          </button>
        </div>
      </div>

      <section className="strat-preset-bar">
        <label className="strat-field strat-preset-select">
          <span>1 · Strategie wählen</span>
          <select
            value={selectedPresetId}
            onChange={(e) => {
              setSelectedPresetId(e.target.value)
              const p = presets.find((x) => x.id === e.target.value)
              if (p) setPresetName(p.name)
            }}
          >
            <option value="">— neu / manuell —</option>
            {presets.map((p) => {
              const u = presetUpcomingMap[p.id]
              const suffix =
                u == null
                  ? ''
                  : u.skipped
                    ? ' · —'
                    : u.n > 0
                      ? ` · ${u.n} upcoming`
                      : ' · 0'
              return (
                <option key={p.id} value={p.id}>
                  {p.name}
                  {suffix}
                </option>
              )
            })}
          </select>
        </label>
        <button type="button" className="nav-btn" onClick={loadPreset} disabled={!selectedPresetId || loading}>
          2 · Laden
        </button>
        <label className="strat-field strat-preset-name">
          <span>Name speichern</span>
          <input
            value={presetName}
            onChange={(e) => setPresetName(e.target.value)}
            placeholder="z.B. Over 2.5 Men CLV+"
          />
        </label>
        <button type="button" className="nav-btn nav-btn--muted" onClick={savePreset}>
          Speichern
        </button>
        <button
          type="button"
          className="nav-btn nav-btn--muted"
          onClick={removePreset}
          disabled={!selectedPresetId}
        >
          Löschen
        </button>
        <button
          type="button"
          className="nav-btn"
          onClick={scanPresetsUpcoming}
          disabled={presetUpcomingLoading || !presets.length || loading}
          title="Alle gespeicherten Strategien auf bevorstehende Spiele prüfen"
        >
          {presetUpcomingLoading
            ? 'Prüfe…'
            : presetUpcomingHits > 0
              ? `Upcoming-Überblick (${presetUpcomingHits})`
              : 'Upcoming-Überblick'}
        </button>
        {presetMsg ? <span className="muted strat-preset-msg">{presetMsg}</span> : null}
      </section>

      {presetUpcomingOpen ? (
        <section className="strat-preset-upcoming">
          <div className="strat-preset-upcoming-head">
            <strong>Bevorstehende Spiele je Strategie</strong>
            <button
              type="button"
              className="strat-corr-explain-close"
              onClick={() => setPresetUpcomingOpen(false)}
              aria-label="Schließen"
            >
              ×
            </button>
          </div>
          <p className="muted" style={{ margin: '0 0 0.5rem' }}>
            Zeigt, welche gespeicherten Strategien aktuell Treffer haben. Klick auf eine Zeile → laden +
            Bevorstehende.
          </p>
          {!presetUpcomingRows.length && !presetUpcomingLoading ? (
            <p className="muted">Noch nicht geprüft — Button „Upcoming-Überblick“ tippen.</p>
          ) : (
            <div className="table-wrap strat-preset-upcoming-table">
              <table>
                <thead>
                  <tr>
                    <th>Strategie</th>
                    <th className="num">Upcoming</th>
                    <th className="num" title="Wetten im Backtest (Vergangenheit)">Vergangene</th>
                    <th className="num">Profit</th>
                    <th className="num">ROI %</th>
                    <th className="num" title="Längste Niederlagenserie">Max −</th>
                    <th className="num" title="Längste Siegesserie">Max +</th>
                    <th className="num" title="Typische Niederlagenserie (Median, Anzahl Serien)">Median −</th>
                    <th className="num" title="Typische Siegesserie (Median, Anzahl Serien)">Median +</th>
                    <th className="num" title="Aktuelle Serie: − verloren / + gewonnen in Folge">Aktuell</th>
                    <th>Status</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {presetUpcomingRows.map((r) => (
                    <tr
                      key={r.id}
                      className={r.n > 0 ? 'strat-preset-upcoming-hit' : ''}
                      style={{ cursor: 'pointer' }}
                      onClick={() => openPresetFromUpcomingScan(r.id)}
                    >
                      <td>
                        <StrategyHover name={r.name} backtest={fromHistory(r.history)} />
                      </td>
                      <td className="num">
                        {r.skipped ? '—' : <strong>{r.n}</strong>}
                      </td>
                      <td className="num">{num(r.history?.n_bets, 0)}</td>
                      <td className={`num ${r.history?.profit > 0 ? 'pos' : r.history?.profit < 0 ? 'neg' : ''}`}>
                        {num(r.history?.profit)}
                      </td>
                      <td className={`num ${r.history?.roi_pct > 0 ? 'pos' : r.history?.roi_pct < 0 ? 'neg' : ''}`}>
                        {num(r.history?.roi_pct, 1)}
                      </td>
                      <td className="num neg">{num(r.history?.max_losing_streak, 0)}</td>
                      <td className="num pos">{num(r.history?.max_winning_streak, 0)}</td>
                      <td className="num">
                        {num(r.history?.median_losing_streak, 1)}
                        <span className="muted"> ({r.history?.n_losing_streaks ?? 0})</span>
                      </td>
                      <td className="num">
                        {num(r.history?.median_winning_streak, 1)}
                        <span className="muted"> ({r.history?.n_winning_streaks ?? 0})</span>
                      </td>
                      <td className={`num ${r.losingStreak > 0 ? 'neg' : 'pos'}`}>
                        {r.losingStreak > 0 ? `−${r.losingStreak}` : r.winningStreak > 0 ? `+${r.winningStreak}` : '0'}
                      </td>
                      <td className="muted">
                        {r.error
                          ? r.error
                          : r.skipped
                            ? r.message || 'Look-ahead-Filter → kein Upcoming'
                            : r.n > 0
                              ? 'Treffer'
                              : 'keine'}
                      </td>
                      <td>
                        <button
                          type="button"
                          className="nav-btn nav-btn--muted"
                          style={{ padding: '0.2rem 0.45rem', fontSize: '0.75rem' }}
                          onClick={(e) => {
                            e.stopPropagation()
                            openPresetFromUpcomingScan(r.id)
                          }}
                        >
                          Öffnen
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {presetUpcomingGames.length ? (
            <>
              <div className="strat-preset-upcoming-head" style={{ marginTop: '0.9rem' }}>
                <strong>Alle bevorstehenden Spiele ({presetUpcomingGames.length})</strong>
              </div>
              <p className="muted" style={{ margin: '0 0 0.5rem' }}>
                Nach Anstoß sortiert. Serie = aktuelle Serie der Strategie in der Vergangenheit:
                <strong> −</strong> verlorene Wetten in Folge, <strong>+</strong> gewonnene in Folge
                (Unentschieden zählt bei Home/Away als verloren).
              </p>
              <div className="table-wrap strat-preset-upcoming-table">
                <table>
                  <thead>
                    <tr>
                      <th>Datum</th>
                      <th>Land</th>
                      <th>Liga</th>
                      <th>Heim</th>
                      <th>Gast</th>
                      <th>Markt</th>
                      <th className="num">Quote</th>
                      <th>Strategie</th>
                      <th className="num" title="Verlorene Wetten in Folge (aktuell)">Serie −</th>
                      <th className="num" title="Gewonnene Wetten in Folge (aktuell)">Serie +</th>
                    </tr>
                  </thead>
                  <tbody>
                    {presetUpcomingGames.map((g, i) => (
                      <tr
                        key={`pug-${g.game_id}-${g.market}-${g.strategy_id}-${i}`}
                        style={{ cursor: 'pointer' }}
                        onClick={() => openPresetFromUpcomingScan(g.strategy_id)}
                        title="Klick → Strategie laden"
                      >
                        <td>{String(g.date || '').slice(0, 16).replace('T', ' ')}</td>
                        <td>{g.country || '—'}</td>
                        <td>
                          {g.league || '—'}
                          {g.swisslos ? <SwisslosBadge /> : null}
                        </td>
                        <td>{g.home}</td>
                        <td>{g.away}</td>
                        <td>{g.market}</td>
                        <td className="num">{oddsNum(g.odds)}</td>
                        <td>
                          <StrategyHover name={g.strategy} backtest={fromHistory(presetUpcomingMap[g.strategy_id]?.history)} />
                        </td>
                        <td className={`num ${g.losing_streak > 0 ? 'neg' : ''}`}>{num(g.losing_streak, 0)}</td>
                        <td className={`num ${g.winning_streak > 0 ? 'pos' : ''}`}>{num(g.winning_streak, 0)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          ) : null}
        </section>
      ) : null}

      <button
        type="button"
        className="strat-chip-row"
        aria-label="Aktive Filter — klicken zum Bearbeiten"
        onClick={() => setFiltersOpen(true)}
        title="Filter bearbeiten"
      >
        {filterChips.map((c) => (
          <span key={c} className="pill pill-muted">
            {c}
          </span>
        ))}
        {!filtersOpen ? <span className="pill">Filter bearbeiten</span> : null}
      </button>

      {data?.ok ? (
        <div className="strat-result-strip">
          <span>
            <strong>{num(m.n, 0)}</strong> Wetten
          </span>
          <span className={Number(m.roi_pct) < 0 ? 'neg' : ''}>
            ROI <strong>{num(m.roi_pct, 1)}%</strong>
          </span>
          <span className={Number(m.total_profit) < 0 ? 'neg' : ''}>
            Profit <strong>{num(m.total_profit)}</strong>
          </span>
          <span>
            WR <strong>{num(m.win_rate, 1)}%</strong>
          </span>
          {upcoming?.ok && !upcoming?.skipped ? (
            <span className="pill pill-live">{upcoming.n ?? 0} Upcoming</span>
          ) : null}
          <button type="button" className="nav-btn nav-btn--muted" onClick={() => setTab('analyse')}>
            Zur Analyse
          </button>
          {upcoming?.ok && !upcoming?.skipped && (upcoming.n || 0) > 0 ? (
            <button type="button" className="nav-btn" onClick={() => setTab('upcoming')}>
              Bevorstehende
            </button>
          ) : null}
        </div>
      ) : null}

      {error ? <div className="error-banner">{error}</div> : null}

      <div className={`strat-panels${filtersOpen ? '' : ' strat-panels--collapsed'}`}>
        <section className="strat-card strat-card--main">
          <h3>Hauptkriterien</h3>
          <div className="strat-checks">
            {MARKET_OPTS.map((o) => (
              <label key={o.key}>
                <input
                  type="checkbox"
                  checked={!!filters[o.key]}
                  onChange={(e) => setFilters((f) => ({ ...f, [o.key]: e.target.checked }))}
                />
                {o.label}
              </label>
            ))}
          </div>
          <div className="strat-main-grid">
            <Range label="Home Quote" minKey="odds_home_min" maxKey="odds_home_max" filters={filters} setFilters={setFilters} step="0.01" />
            <Range label="Away Quote" minKey="odds_away_min" maxKey="odds_away_max" filters={filters} setFilters={setFilters} step="0.01" />
            <Range label="Over 2.5 Quote" minKey="odds_over_min" maxKey="odds_over_max" filters={filters} setFilters={setFilters} step="0.01" />
            <Range label="Under 2.5 Quote" minKey="odds_under_min" maxKey="odds_under_max" filters={filters} setFilters={setFilters} step="0.01" />
            <Range label="xROI %" minKey="xroi_min" maxKey="xroi_max" filters={filters} setFilters={setFilters} step="0.1" />
            <Range label="ROI % (Wette)" minKey="roi_min" maxKey="roi_max" filters={filters} setFilters={setFilters} step="0.1" />
            <label className="strat-field">
              <span>Geschlecht</span>
              <select
                value={filters.gender_filter}
                onChange={(e) => setFilters((f) => ({ ...f, gender_filter: e.target.value }))}
              >
                <option value="men">Männer</option>
                <option value="women">Frauen</option>
                <option value="all">Beide</option>
              </select>
            </label>
            <label className="strat-field">
              <span>Quoten-Typ</span>
              <select
                value={filters.odds_type}
                onChange={(e) => setFilters((f) => ({ ...f, odds_type: e.target.value }))}
              >
                <option value="closing">Closing</option>
                <option value="opening">Opening</option>
              </select>
            </label>
          </div>
          <h4 className="strat-subhead">Nur Spiele mit Ergebnis …</h4>
          <div className="strat-checks">
            {FT_OUTCOME_OPTS.map((o) => (
              <label key={o.key}>
                <input
                  type="checkbox"
                  checked={!!filters[o.key]}
                  onChange={(e) => setFilters((f) => ({ ...f, [o.key]: e.target.checked }))}
                />
                {o.label}
              </label>
            ))}
          </div>
          <p className="muted">
            xROI = (Open−Close)/Close×100 · ROI % pro Wette = Profit×100 (Look-ahead).
            Ergebnis-Filter: z.B. nur Home-Siege · 1X2 und O/U getrennt (OR / AND).
          </p>
        </section>

        <details className="strat-advanced">
          <summary>Erweiterte Filter (Vergleich, Percentile, Glicko, Liga) …</summary>
          <div className="strat-advanced-grid">

        <section className="strat-card strat-card--main">
          <h3>Vergleich / Differenz</h3>
          <label className="strat-checks" style={{ marginBottom: '0.65rem' }}>
            <input
              type="checkbox"
              checked={!!filters.use_xg_comparison}
              onChange={(e) => setFilters((f) => ({
                ...f,
                use_xg_comparison: e.target.checked,
                ...(e.target.checked ? {} : { xg_comparisons: [] }),
              }))}
            />
            Aktiv (Backtest + Upcoming) — mehrere Bedingungen = UND
          </label>
          <CmpConditionRow
            attr1={filters.xg_attr1}
            operation={filters.xg_operation}
            attr2={filters.xg_attr2}
            comparisonOperator={filters.xg_comparison_operator}
            comparisonValue={filters.xg_comparison_value}
            disabled={!filters.use_xg_comparison}
            onChange={(patch) => setFilters((f) => ({
              ...f,
              ...(patch.attr1 !== undefined ? { xg_attr1: patch.attr1 } : {}),
              ...(patch.operation !== undefined ? { xg_operation: patch.operation } : {}),
              ...(patch.attr2 !== undefined ? { xg_attr2: patch.attr2 } : {}),
              ...(patch.comparison_operator !== undefined
                ? { xg_comparison_operator: patch.comparison_operator }
                : {}),
              ...(patch.comparison_value !== undefined
                ? { xg_comparison_value: patch.comparison_value }
                : {}),
            }))}
          />
          {(filters.xg_comparisons || []).map((c, idx) => (
            <div key={`cmp-extra-${idx}`} className="strat-cmp-extra">
              <div className="strat-cmp-extra-head">
                <span className="muted">UND Bedingung {idx + 2}</span>
                <button
                  type="button"
                  className="nav-btn nav-btn--muted"
                  disabled={!filters.use_xg_comparison}
                  onClick={() => setFilters((f) => ({
                    ...f,
                    xg_comparisons: (f.xg_comparisons || []).filter((_, i) => i !== idx),
                  }))}
                >
                  Entfernen
                </button>
              </div>
              <CmpConditionRow
                attr1={c.attr1}
                operation={c.operation}
                attr2={c.attr2}
                comparisonOperator={c.comparison_operator}
                comparisonValue={c.comparison_value}
                disabled={!filters.use_xg_comparison}
                onChange={(patch) => setFilters((f) => {
                  const list = [...(f.xg_comparisons || [])]
                  list[idx] = { ...list[idx], ...patch }
                  return { ...f, xg_comparisons: list }
                })}
              />
            </div>
          ))}
          <div style={{ marginTop: '0.5rem' }}>
            <button
              type="button"
              className="nav-btn nav-btn--muted"
              disabled={
                !filters.use_xg_comparison ||
                (filters.xg_comparisons || []).length >= MAX_XG_COMPARISONS - 1
              }
              onClick={() => setFilters((f) => ({
                ...f,
                use_xg_comparison: true,
                xg_comparisons: [...(f.xg_comparisons || []), { ...EMPTY_CMP }],
              }))}
            >
              + Bedingung anfügen
            </button>
          </div>
          <p className="muted">
            z.B. Form2 Home − Away ≥ 0,3 · oder hometeam_pred_xg vs awayteam_pred_xg &gt;
          </p>
        </section>

        <section className="strat-card strat-card--main">
          <h3>Percentile (Top X%)</h3>
          <label className="strat-checks" style={{ marginBottom: '0.65rem' }}>
            <input
              type="checkbox"
              checked={!!filters.use_percentile}
              onChange={(e) => setFilters((f) => ({ ...f, use_percentile: e.target.checked }))}
            />
            Aktiv — nur beste X% nach Metrik (Vergangenheit + Upcoming)
          </label>
          <div className="strat-main-grid">
            <label className="strat-field">
              <span>Top %</span>
              <select
                value={filters.percentile_value}
                onChange={(e) => setFilters((f) => ({ ...f, percentile_value: e.target.value }))}
                disabled={!filters.use_percentile}
              >
                {PCT_VALUES.map((v) => (
                  <option key={v} value={v}>{v}%</option>
                ))}
              </select>
            </label>
            <label className="strat-field">
              <span>Metrik</span>
              <select
                value={filters.percentile_metric}
                onChange={(e) => setFilters((f) => ({ ...f, percentile_metric: e.target.value }))}
                disabled={!filters.use_percentile}
              >
                {PCT_METRICS.map((a) => (
                  <option key={a.value} value={a.value}>{a.label}</option>
                ))}
              </select>
            </label>
          </div>
          <p className="muted">
            z.B. Top 10% Chance · Profit = Look-ahead (nur Analyse, nicht live)
          </p>
        </section>

        <section className="strat-card">
          <h3>Glicko xG (Vorhersage)</h3>
          <p className="muted" style={{ marginTop: 0 }}>
            Pre-match Modellwert — für Backtest und Upcoming nutzbar.
          </p>
          <Range label="Home xG Glicko" minKey="xg_glicko_home_min" maxKey="xg_glicko_home_max" filters={filters} setFilters={setFilters} step="0.01" />
          <Range label="Away xG Glicko" minKey="xg_glicko_away_min" maxKey="xg_glicko_away_max" filters={filters} setFilters={setFilters} step="0.01" />
          <Range label="Home xG Form2" minKey="xg_form2_home_min" maxKey="xg_form2_home_max" filters={filters} setFilters={setFilters} step="0.01" />
          <Range label="Away xG Form2" minKey="xg_form2_away_min" maxKey="xg_form2_away_max" filters={filters} setFilters={setFilters} step="0.01" />
        </section>

        <section className="strat-card">
          <h3>Match xG (erzielt)</h3>
          <p className="muted" style={{ marginTop: 0 }}>
            Tatsächliche xG in diesem Spiel (calculated). Look-ahead — nur Analyse, Upcoming wird ausgeblendet.
          </p>
          <Range label="Home xG Match" minKey="xg_match_home_min" maxKey="xg_match_home_max" filters={filters} setFilters={setFilters} step="0.01" />
          <Range label="Away xG Match" minKey="xg_match_away_min" maxKey="xg_match_away_max" filters={filters} setFilters={setFilters} step="0.01" />
        </section>

        <section className="strat-card">
          <h3>Glicko Rating</h3>
          <Range label="homeRating" minKey="glicko_home_min" maxKey="glicko_home_max" filters={filters} setFilters={setFilters} step="1" />
          <Range label="awayRating" minKey="glicko_away_min" maxKey="glicko_away_max" filters={filters} setFilters={setFilters} step="1" />
          <Range label="homeRd" minKey="glicko_rd_home_min" maxKey="glicko_rd_home_max" filters={filters} setFilters={setFilters} step="0.1" />
          <Range label="awayRd" minKey="glicko_rd_away_min" maxKey="glicko_rd_away_max" filters={filters} setFilters={setFilters} step="0.1" />
          <Range label="homeVolatility" minKey="glicko_vol_home_min" maxKey="glicko_vol_home_max" filters={filters} setFilters={setFilters} step="0.001" />
          <Range label="awayVolatility" minKey="glicko_vol_away_min" maxKey="glicko_vol_away_max" filters={filters} setFilters={setFilters} step="0.001" />
        </section>

        <section className="strat-card">
          <h3>Glicko Wahrscheinlichkeiten</h3>
          <Range label="P(Home) %" minKey="glicko_p_home_min" maxKey="glicko_p_home_max" filters={filters} setFilters={setFilters} step="1" />
          <Range label="P(Draw) %" minKey="glicko_p_draw_min" maxKey="glicko_p_draw_max" filters={filters} setFilters={setFilters} step="1" />
          <Range label="P(Away) %" minKey="glicko_p_away_min" maxKey="glicko_p_away_max" filters={filters} setFilters={setFilters} step="1" />
        </section>

        <section className="strat-card">
          <h3>Saison / Ort</h3>
          <Range label="Home Spiel-Nr." minKey="season_games_home_min" maxKey="season_games_home_max" filters={filters} setFilters={setFilters} step="1" />
          <Range label="Away Spiel-Nr." minKey="season_games_away_min" maxKey="season_games_away_max" filters={filters} setFilters={setFilters} step="1" />
          <label className="strat-field">
            <span>Liga</span>
            <input
              value={filters.league_filter}
              onChange={(e) => setFilters((f) => ({ ...f, league_filter: e.target.value }))}
              placeholder="z.B. Championship"
            />
          </label>
          <label className="strat-field">
            <span>Land</span>
            <input
              value={filters.country_filter}
              onChange={(e) => setFilters((f) => ({ ...f, country_filter: e.target.value }))}
            />
          </label>
        </section>
          </div>
        </details>
      </div>

      <section className="stat-section">
        <div className="stat-section-head">
          <div className="metric-tabs">
            <button type="button" className={tab === 'analyse' ? 'active' : ''} onClick={() => setTab('analyse')}>
              Analyse
            </button>
            <button type="button" className={tab === 'metrics' ? 'active' : ''} onClick={() => setTab('metrics')}>
              Metriken
            </button>
            <button type="button" className={tab === 'corr' ? 'active' : ''} onClick={() => setTab('corr')}>
              Korrelation
            </button>
            <button type="button" className={tab === 'past' ? 'active' : ''} onClick={() => setTab('past')}>
              Vergangene Spiele{data?.ok ? ` (${data.n})` : ''}
            </button>
            <button type="button" className={tab === 'upcoming' ? 'active' : ''} onClick={() => setTab('upcoming')}>
              Bevorstehende
              {upcoming?.skipped ? ' (—)' : upcoming?.ok ? ` (${upcoming.n})` : ''}
            </button>
          </div>
        </div>

        {!data?.ok && tab !== 'upcoming' && tab !== 'corr' && tab !== 'metrics' ? (
          <p className="muted">Filter setzen → „Analysieren“ — füllt Analyse (ROI/Ausgänge), Metriken (Glicko) und Tabellen.</p>
        ) : null}

        {tab === 'corr' ? (
          <>
            <CorrelationHelpPanel />
            <div className="stat-section-head" style={{ marginBottom: '0.75rem', gap: '0.5rem', flexWrap: 'wrap' }}>
              <p className="muted" style={{ margin: 0, flex: '1 1 240px' }}>
                Ranking: welche Metric-Schwellen ROI/Profit vs. Baseline am stärksten verbessern.
                Oder: max. 2 Parameter inkl. optimaler Quote nach höchstem Profit suchen.
              </p>
              <label className="muted" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}>
                Sortierung
                <select
                  value={corrSortBy}
                  onChange={(e) => setCorrSortBy(e.target.value)}
                  disabled={rankLoading}
                >
                  <option value="roi">Δ ROI</option>
                  <option value="profit">Δ Profit</option>
                </select>
              </label>
              <button type="button" className="nav-btn" onClick={runCorrelation} disabled={rankLoading || loading || optLoading}>
                {rankLoading ? 'Berechnet…' : 'Korrelation berechnen'}
              </button>
              <button type="button" className="nav-btn" onClick={runOptimize} disabled={optLoading || loading || rankLoading}>
                {optLoading ? 'Suche…' : 'Optimal (max. 2 Parameter)'}
              </button>
            </div>

            {optReport?.ok ? (
              <section className="strat-opt-panel">
                <h3 className="strat-outcome-title">Optimale Parameter (max. Profit)</h3>
                <p className="muted" style={{ marginBottom: '0.65rem' }}>
                  Baseline: n={num(optReport.baseline?.n, 0)} · Profit {num(optReport.baseline?.total_profit)} · ROI{' '}
                  {num(optReport.baseline?.roi_pct, 1)}% · min_n={optReport.min_n} · geprüft={num(optReport.n_evaluated, 0)}
                </p>
                {optReport.best ? (
                  <div className="strat-opt-best">
                    <div className="strat-opt-best-head">
                      <strong>Beste Kombination</strong>
                      <span className="pill pill-live">
                        Profit {num(optReport.best.total_profit)} · ROI {num(optReport.best.roi_pct, 1)}% · n=
                        {num(optReport.best.n, 0)}
                      </span>
                    </div>
                    <ul className="strat-opt-params">
                      {(optReport.best.params || []).map((p, i) => (
                        <li key={`${p.metric}-${i}`}>
                          <code title={p.metric}>{metricName(p.metric)}</code> — {p.condition}
                          <span className="muted"> ({p.rule})</span>
                        </li>
                      ))}
                    </ul>
                    {optReport.best.odds_band ? (
                      <p style={{ margin: '0.35rem 0' }}>
                        Optimale Quote ({optReport.best.odds_band.metric}):{' '}
                        <strong>
                          {optReport.best.odds_band.min != null ? num(optReport.best.odds_band.min, 2) : '—'}
                          {' – '}
                          {optReport.best.odds_band.max != null ? num(optReport.best.odds_band.max, 2) : '—'}
                        </strong>
                        {optReport.best.avg_odds != null ? (
                          <span className="muted"> · Ø Quote {num(optReport.best.avg_odds, 2)}</span>
                        ) : null}
                      </p>
                    ) : null}
                    <div className="settings-actions" style={{ marginTop: '0.55rem' }}>
                      <button
                        type="button"
                        className="nav-btn"
                        onClick={() => applyOptimizedFilters(optReport.best)}
                        disabled={loading || !Object.keys(optReport.best.suggested_filters || {}).length}
                      >
                        Filter übernehmen &amp; Analysieren
                      </button>
                    </div>
                    {!Object.keys(optReport.best.suggested_filters || {}).length ? (
                      <p className="muted" style={{ marginTop: '0.35rem' }}>
                        Diese Parameter haben keinen Direktfilter — Werte manuell / über Attribut setzen.
                      </p>
                    ) : null}
                  </div>
                ) : (
                  <p className="muted">Keine gültige Kombination (zu wenig Daten oder Filter zu eng).</p>
                )}

                {optReport.best_odds_only &&
                (optReport.best_odds_only.conditions || []).join('|') !==
                  (optReport.best?.conditions || []).join('|') ? (
                  <p className="muted" style={{ marginTop: '0.65rem' }}>
                    Beste nur-Quote:{' '}
                    <code>{(optReport.best_odds_only.conditions || []).join(' · ')}</code>
                    {' · '}Profit {num(optReport.best_odds_only.total_profit)} · n=
                    {num(optReport.best_odds_only.n, 0)}
                    <button
                      type="button"
                      className="nav-btn nav-btn--muted"
                      style={{ marginLeft: '0.5rem' }}
                      onClick={() => applyOptimizedFilters(optReport.best_odds_only)}
                      disabled={loading || !Object.keys(optReport.best_odds_only.suggested_filters || {}).length}
                    >
                      Quote übernehmen
                    </button>
                  </p>
                ) : null}

                {(optReport.top || []).length > 1 ? (
                  <div className="table-wrap strat-corr-table" style={{ marginTop: '0.75rem' }}>
                    <table>
                      <thead>
                        <tr>
                          <th className="num">#</th>
                          <th>Parameter</th>
                          <th className="num">n</th>
                          <th className="num">Profit</th>
                          <th className="num">ROI%</th>
                          <th className="num">Δ Profit</th>
                          <th></th>
                        </tr>
                      </thead>
                      <tbody>
                        {(optReport.top || []).slice(0, 12).map((row, i) => (
                          <tr key={`opt-${i}`}>
                            <td className="num">{i + 1}</td>
                            <td>
                              {(row.conditions || []).join(' · ')}
                              <div className="muted" style={{ fontSize: '0.78rem' }}>
                                {row.n_params} Parameter
                                {row.odds_band
                                  ? ` · Quote ${num(row.odds_band.min, 2)}–${num(row.odds_band.max, 2)}`
                                  : ''}
                              </div>
                            </td>
                            <td className="num">{num(row.n, 0)}</td>
                            <td className={`num ${Number(row.total_profit) < 0 ? 'neg' : ''}`}>
                              {num(row.total_profit)}
                            </td>
                            <td className={`num ${Number(row.roi_pct) < 0 ? 'neg' : ''}`}>
                              {num(row.roi_pct, 1)}
                            </td>
                            <td className={`num ${Number(row.profit_delta) < 0 ? 'neg' : ''}`}>
                              {num(row.profit_delta)}
                            </td>
                            <td>
                              <button
                                type="button"
                                className="nav-btn nav-btn--muted"
                                style={{ padding: '0.2rem 0.45rem', fontSize: '0.75rem' }}
                                onClick={() => applyOptimizedFilters(row)}
                                disabled={!Object.keys(row.suggested_filters || {}).length}
                              >
                                Übernehmen
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : null}
              </section>
            ) : null}
            {!rankReport?.ok ? (
              <p className="muted">Filter setzen → „Korrelation berechnen“.</p>
            ) : (
              <>
                <p className="muted" style={{ marginBottom: '0.65rem' }}>
                  Baseline: n={num(rankReport.baseline?.n ?? rankReport.n, 0)}
                  {' · '}Profit {num(rankReport.baseline?.total_profit)}
                  {' · '}ROI {num(rankReport.baseline?.roi_pct, 1)}%
                  {' · '}WR {num(rankReport.baseline?.win_rate, 1)}%
                  {' · '}min_n={rankReport.min_n ?? 40}
                  {' · '}Sortierung:{' '}
                  {corrSortBy === 'profit' ? 'Δ Profit' : 'Δ ROI'}
                </p>
                {rankedCorrRows.length === 0 ? (
                  <p className="muted">Keine gültigen Schwellen (zu wenig Daten oder Filter zu eng).</p>
                ) : (
                  <>
                    <p className="muted" style={{ marginBottom: '0.5rem' }}>
                      Zeile anklicken → Erklärung in Alltagssprache + Parameter-Grafik.
                    </p>
                    <CorrRowExplainPanel
                      row={selectedCorrRow}
                      onClose={selectedCorrRow ? () => setSelectedCorrRow(null) : undefined}
                    />
                    <div className="table-wrap strat-corr-table">
                      <table>
                        <thead>
                          <tr>
                            <th className="num" title={CORR_COLUMN_MAP['#']}>#</th>
                            <th title={CORR_COLUMN_MAP.Metric}>Metric</th>
                            <th title={CORR_COLUMN_MAP.Regel}>Regel</th>
                            <th title={CORR_COLUMN_MAP.Bedingung}>Bedingung</th>
                            <th className="num" title={CORR_COLUMN_MAP.n}>n</th>
                            <th className="num" title={CORR_COLUMN_MAP['WR%']}>WR%</th>
                            <th className="num" title={CORR_COLUMN_MAP.Profit}>Profit</th>
                            <th className="num" title={CORR_COLUMN_MAP['ROI%']}>ROI%</th>
                            <th
                              className={`num ${corrSortBy === 'roi' ? 'corr-sort-active' : ''}`}
                              title={CORR_COLUMN_MAP['Δ ROI']}
                            >
                              Δ ROI
                            </th>
                            <th
                              className={`num ${corrSortBy === 'profit' ? 'corr-sort-active' : ''}`}
                              title={CORR_COLUMN_MAP['Δ Profit']}
                            >
                              Δ Profit
                            </th>
                            <th className="num" title={CORR_COLUMN_MAP['Anteil%']}>Anteil%</th>
                          </tr>
                        </thead>
                        <tbody>
                          {rankedCorrRows.slice(0, 50).map((row, i) => {
                            const selected =
                              selectedCorrRow &&
                              selectedCorrRow.metric === row.metric &&
                              selectedCorrRow.rule === row.rule &&
                              selectedCorrRow.condition === row.condition
                            return (
                              <tr
                                key={`${row.metric}-${row.rule}-${i}`}
                                className={[
                                  Number(row.roi_delta) >= 0 ? 'strat-corr-pos' : 'strat-corr-neg',
                                  selected ? 'strat-corr-selected' : '',
                                ]
                                  .filter(Boolean)
                                  .join(' ')}
                                style={{ cursor: 'pointer' }}
                                title={CORR_METRIC_MAP[row.metric] || 'Klicken → Erklärung + Grafik'}
                                onClick={() => {
                                  setSelectedCorrRow(row)
                                  runBucketChart(row.metric)
                                }}
                              >
                                <td className="num">{i + 1}</td>
                                <td title={row.metric}>{metricName(row.metric)}</td>
                                <td>{row.rule}</td>
                                <td>{row.condition}</td>
                                <td className="num">{num(row.n, 0)}</td>
                                <td className="num">{num(row.win_rate, 1)}</td>
                                <td className={`num ${Number(row.total_profit) < 0 ? 'neg' : ''}`}>
                                  {num(row.total_profit)}
                                </td>
                                <td className={`num ${Number(row.roi_pct) < 0 ? 'neg' : ''}`}>
                                  {num(row.roi_pct, 1)}
                                </td>
                                <td className={`num ${Number(row.roi_delta) < 0 ? 'neg' : ''}`}>
                                  {num(row.roi_delta, 1)}
                                </td>
                                <td className={`num ${Number(row.profit_delta) < 0 ? 'neg' : ''}`}>
                                  {num(row.profit_delta)}
                                </td>
                                <td className="num">{num(row.coverage_pct, 0)}</td>
                              </tr>
                            )
                          })}
                        </tbody>
                      </table>
                    </div>
                  </>
                )}
              </>
            )}

            <section className="strat-bucket-panel">
              <h3 className="strat-outcome-title">Parameter-Grafik (optimaler Bereich)</h3>
              <p className="muted" style={{ marginBottom: '0.65rem' }}>
                Zeigt Profit, ROI und Anzahl Spiele (n) je Werte-Bereich. Markierter Balken = bestes ROI-Bin.
                Mindestens ~5 Werte nötig; bei kleinen Stichproben vorsichtig interpretieren.
              </p>
              <div className="strat-bucket-controls">
                <label className="strat-field">
                  <span>Metrik</span>
                  <select value={bucketMetric} onChange={(e) => setBucketMetric(e.target.value)}>
                    {BUCKET_METRICS.map((m) => (
                      <option key={m.value} value={m.value}>
                        {m.label}
                      </option>
                    ))}
                  </select>
                </label>
                <button
                  type="button"
                  className="nav-btn"
                  onClick={() => runBucketChart()}
                  disabled={bucketLoading || loading}
                >
                  {bucketLoading ? 'Zeichne…' : 'Grafik berechnen'}
                </button>
              </div>
              {bucketReport?.ok ? (
                <>
                  <p className="muted" style={{ margin: '0.5rem 0 0.75rem' }}>
                    {bucketReport.metric_label || bucketReport.metric}
                    {' · '}n={num(bucketReport.n, 0)}
                    {' · '}Range {num(bucketReport.vmin, 3)}–{num(bucketReport.vmax, 3)}
                    {' · '}Step {num(bucketReport.step, 3)}
                    {bucketReport.best_bin ? (
                      <>
                        {' · '}Bestes ROI:{' '}
                        <strong>
                          {bucketReport.best_bin.label} → {num(bucketReport.best_bin.roi_pct, 1)}% (n=
                          {num(bucketReport.best_bin.n, 0)})
                        </strong>
                      </>
                    ) : null}
                  </p>
                  {bucketChartData.length === 0 ? (
                    <p className="muted">Keine Bins.</p>
                  ) : (
                    <div className="strat-bucket-charts">
                      <div className="strat-equity-chart">
                        <h4 className="strat-bucket-chart-title">Profit je Bereich</h4>
                        <ResponsiveContainer width="100%" height={260}>
                          <BarChart data={bucketChartData} margin={{ top: 22, right: 12, left: 0, bottom: 40 }}>
                            <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" />
                            <XAxis dataKey="label" stroke="var(--muted)" fontSize={10} angle={-35} textAnchor="end" height={50} interval={0} />
                            <YAxis stroke="var(--muted)" fontSize={11} />
                            <Tooltip content={bucketTooltip} />
                            <Legend />
                            <ReferenceLine y={0} stroke="var(--muted)" strokeDasharray="4 4" />
                            <Bar dataKey="total_profit" name="Profit" radius={[3, 3, 0, 0]}>
                              {bucketChartData.map((b, i) => (
                                <Cell
                                  key={`p-${i}`}
                                  fill={b.isBest ? '#22c55e' : Number(b.total_profit) >= 0 ? '#3d9cfd' : '#ef4444'}
                                />
                              ))}
                              <LabelList
                                dataKey="n"
                                position="top"
                                formatter={(v) => (Number(v) > 0 ? `n=${v}` : '')}
                                style={{ fill: 'var(--muted)', fontSize: 10 }}
                              />
                            </Bar>
                          </BarChart>
                        </ResponsiveContainer>
                      </div>
                      <div className="strat-equity-chart">
                        <h4 className="strat-bucket-chart-title">ROI % je Bereich</h4>
                        <ResponsiveContainer width="100%" height={260}>
                          <BarChart data={bucketChartData} margin={{ top: 22, right: 12, left: 0, bottom: 40 }}>
                            <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" />
                            <XAxis dataKey="label" stroke="var(--muted)" fontSize={10} angle={-35} textAnchor="end" height={50} interval={0} />
                            <YAxis stroke="var(--muted)" fontSize={11} tickFormatter={(v) => `${v}%`} />
                            <Tooltip content={bucketTooltip} />
                            <Legend />
                            <ReferenceLine y={0} stroke="var(--muted)" strokeDasharray="4 4" />
                            <Bar dataKey="roi_pct" name="ROI %" radius={[3, 3, 0, 0]}>
                              {bucketChartData.map((b, i) => (
                                <Cell
                                  key={`r-${i}`}
                                  fill={b.isBest ? '#22c55e' : Number(b.roi_pct) >= 0 ? '#e8a838' : '#ef4444'}
                                />
                              ))}
                              <LabelList
                                dataKey="n"
                                position="top"
                                formatter={(v) => (Number(v) > 0 ? `n=${v}` : '')}
                                style={{ fill: 'var(--muted)', fontSize: 10 }}
                              />
                            </Bar>
                          </BarChart>
                        </ResponsiveContainer>
                      </div>
                      <div className="strat-equity-chart strat-bucket-chart--n">
                        <h4 className="strat-bucket-chart-title">Anzahl Spiele (n) je Bereich</h4>
                        <ResponsiveContainer width="100%" height={220}>
                          <BarChart data={bucketChartData} margin={{ top: 22, right: 12, left: 0, bottom: 40 }}>
                            <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" />
                            <XAxis dataKey="label" stroke="var(--muted)" fontSize={10} angle={-35} textAnchor="end" height={50} interval={0} />
                            <YAxis stroke="var(--muted)" fontSize={11} allowDecimals={false} />
                            <Tooltip content={bucketTooltip} />
                            <Legend />
                            <Bar dataKey="n" name="Spiele (n)" radius={[3, 3, 0, 0]}>
                              {bucketChartData.map((b, i) => (
                                <Cell
                                  key={`n-${i}`}
                                  fill={b.isBest ? '#22c55e' : '#94a3b8'}
                                />
                              ))}
                              <LabelList
                                dataKey="n"
                                position="top"
                                formatter={(v) => (Number(v) > 0 ? v : '')}
                                style={{ fill: 'var(--text)', fontSize: 11 }}
                              />
                            </Bar>
                          </BarChart>
                        </ResponsiveContainer>
                      </div>
                    </div>
                  )}
                </>
              ) : (
                <p className="muted">Metrik wählen → „Grafik berechnen“ (oder Zeile im Ranking anklicken).</p>
              )}
            </section>
          </>
        ) : null}

        {tab === 'analyse' && data?.ok ? (
          <>
            {pctInfo.enabled ? (
              <p className="muted" style={{ marginBottom: '0.65rem' }}>
                Percentile Top {pctInfo.percentile}% · {pctInfo.metric}
                {pctInfo.threshold != null ? ` · Schwelle ≥ ${num(pctInfo.threshold, 3)}` : ''}
                {' · '}
                {pctInfo.n_before} → {pctInfo.n_after} Wetten
              </p>
            ) : null}

            <div className="stat-grid">
              <div className="stat-card" title={ANALYSE_HELP_TITLE.roi}>
                <div className="stat-card-title">ROI</div>
                <div className="stat-card-value">{num(m.roi_pct)}%</div>
                <div className="stat-card-sub">{num(m.n, 0)} Wetten</div>
              </div>
              <div className="stat-card" title={ANALYSE_HELP_TITLE.xroi}>
                <div className="stat-card-title">xROI</div>
                <div className="stat-card-value">
                  {m.avg_xroi_pct != null ? `${num(m.avg_xroi_pct, 1)}%` : '—'}
                </div>
                <div className="stat-card-sub">n={m.xroi_n ?? 0}</div>
              </div>
              <div className="stat-card" title={ANALYSE_HELP_TITLE.winrate}>
                <div className="stat-card-title">Winrate</div>
                <div className="stat-card-value">{num(m.win_rate)}%</div>
              </div>
              <div className="stat-card" title={ANALYSE_HELP_TITLE.profit}>
                <div className="stat-card-title">Profit</div>
                <div className="stat-card-value">{num(m.total_profit)}</div>
              </div>
              <div className="stat-card" title={ANALYSE_HELP_TITLE.roi_close}>
                <div className="stat-card-title">ROI Closing</div>
                <div className="stat-card-value">{num(equity.roi_close_pct, 1)}%</div>
              </div>
              <div className="stat-card" title={ANALYSE_HELP_TITLE.roi_open}>
                <div className="stat-card-title">ROI Opening</div>
                <div className="stat-card-value">{num(equity.roi_open_pct, 1)}%</div>
              </div>
              <div
                className="stat-card"
                title="Ø Match-xG Home / Away — tatsächlich erzielte xG in diesen Spielen (1× pro Match)"
              >
                <div className="stat-card-title">Ø xG Match H / A</div>
                <div className="stat-card-value">
                  {num(glicko.avg_xg_match_h)} / {num(glicko.avg_xg_match_a)}
                </div>
                <div className="stat-card-sub">
                  Summe {num(glicko.avg_xg_match_sum)} · n={glicko.n_xg_match ?? 0}
                </div>
              </div>
              <div
                className="stat-card"
                title="Ø Tore Home / Away — Endstand in diesen Spielen (1× pro Match)"
              >
                <div className="stat-card-title">Ø Goals H / A</div>
                <div className="stat-card-value">
                  {num(glicko.avg_goals_h)} / {num(glicko.avg_goals_a)}
                </div>
                <div className="stat-card-sub">
                  Summe {num(glicko.avg_goals_sum)} · n={glicko.n_goals ?? 0}
                </div>
              </div>
              <div
                className="stat-card"
                title="Ø Glicko-xG Home / Away — Vorhersage pre-match (nicht die Match-xG)"
              >
                <div className="stat-card-title">Ø xG Glicko H / A</div>
                <div className="stat-card-value">
                  {num(glicko.avg_xg_h)} / {num(glicko.avg_xg_a)}
                </div>
                <div className="stat-card-sub">n={glicko.n_xg ?? 0}</div>
              </div>
            </div>

            <h3 className="strat-outcome-title">
              Spielausgänge · n={num(oc.games_n, 0)} Spiele (Endstand, 1× pro Match — keine Wette)
            </h3>
            <div className="stat-grid strat-outcome-grid">
              <div className="stat-card">
                <div className="stat-card-title">Home gewonnen</div>
                <div className="stat-card-value">{num(oc.home_pct, 1)}%</div>
                <div className="stat-card-sub">{oc.home_n ?? 0} Spiele</div>
              </div>
              <div className="stat-card">
                <div className="stat-card-title">Unentschieden</div>
                <div className="stat-card-value">{num(oc.draw_pct, 1)}%</div>
                <div className="stat-card-sub">{oc.draw_n ?? 0} Spiele</div>
              </div>
              <div className="stat-card">
                <div className="stat-card-title">Away gewonnen</div>
                <div className="stat-card-value">{num(oc.away_pct, 1)}%</div>
                <div className="stat-card-sub">{oc.away_n ?? 0} Spiele</div>
              </div>
              <div className="stat-card">
                <div className="stat-card-title">Over 2.5</div>
                <div className="stat-card-value">{num(oc.over25_pct, 1)}%</div>
                <div className="stat-card-sub">{oc.over25_n ?? 0} Spiele</div>
              </div>
              <div className="stat-card">
                <div className="stat-card-title">Under 2.5</div>
                <div className="stat-card-value">{num(oc.under25_pct, 1)}%</div>
                <div className="stat-card-sub">{oc.under25_n ?? 0} Spiele</div>
              </div>
            </div>

            <details className="strat-alt-markets">
              <summary>
                Pro Markt · Prozent, Profit, ROI, xROI (dieselben Strategie-Spiele)
              </summary>
              <p className="muted" style={{ margin: '0.35rem 0 0.5rem' }}>
                <strong>Spielausgänge</strong> oben = Endstand der Matches (1× pro Spiel), keine Wette.
                <br />
                <strong>Tabelle</strong> = hypothetische Wette auf diesen Markt auf denselben Spielen.
                N kann kleiner sein, wenn für den Markt keine Quote da ist. Gewählter Markt ≈ Analyse-WR.
              </p>
              {(data.alt_markets || []).length === 0 ? (
                <p className="muted">Keine Marktdaten — erneut Analysieren.</p>
              ) : (
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Markt</th>
                        <th className="num">N</th>
                        <th className="num">Prozent</th>
                        <th className="num">Profit</th>
                        <th className="num">ROI</th>
                        <th className="num">xROI</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(data.alt_markets || []).map((row) => {
                        const thin = Number(row.n) > 0 && Number(row.n) < 100
                        return (
                        <tr
                          key={row.market}
                          className={[
                            row.selected ? 'strat-alt-selected' : '',
                            thin ? 'strat-alt-thin' : '',
                          ]
                            .filter(Boolean)
                            .join(' ') || undefined}
                        >
                          <td>
                            {row.market}
                            {row.selected ? <span className="pill pill-muted strat-alt-pill">gewählt</span> : null}
                            {thin ? <span className="pill pill-muted strat-alt-pill">wenig Daten</span> : null}
                          </td>
                          <td className="num">{num(row.n, 0)}</td>
                          <td className="num">{num(row.percent ?? row.win_rate, 1)}%</td>
                          <td className={`num ${Number(row.total_profit) < 0 ? 'neg' : ''}`}>
                            {num(row.total_profit)}
                          </td>
                          <td className={`num ${Number(row.roi_pct) < 0 ? 'neg' : ''}`}>
                            {num(row.roi_pct, 1)}%
                          </td>
                          <td className={`num ${row.avg_xroi_pct != null && Number(row.avg_xroi_pct) < 0 ? 'neg' : ''}`}>
                            {row.avg_xroi_pct != null ? `${num(row.avg_xroi_pct, 1)}%` : '—'}
                          </td>
                        </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </details>

            {equitySeries.length > 0 ? (
              <div className="strat-equity">
                <div className="stat-section-head">
                  <h3 className="strat-outcome-title" style={{ margin: 0 }}>
                    Profit über Zeit (Units)
                  </h3>
                  <span className="pill pill-muted">
                    Close {num(equity.total_profit_close)} u · ROI {num(equity.roi_close_pct, 1)}%
                  </span>
                  <span className="pill pill-muted">
                    Open {num(equity.total_profit_open)} u · ROI {num(equity.roi_open_pct, 1)}%
                  </span>
                </div>
                <div className="strat-equity-chart">
                  <ResponsiveContainer width="100%" height={280}>
                    <LineChart data={equitySeries} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
                      <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" />
                      <XAxis dataKey="date" stroke="var(--muted)" fontSize={11} minTickGap={40} />
                      <YAxis stroke="var(--muted)" fontSize={11} tickFormatter={(v) => Number(v).toFixed(0)} />
                      <Tooltip
                        contentStyle={{
                          background: 'var(--bg-elevated)',
                          border: '1px solid var(--border)',
                          borderRadius: 8,
                        }}
                        formatter={(v, name) => [`${num(v, 2)} u`, name]}
                      />
                      <Legend />
                      <ReferenceLine y={0} stroke="var(--muted)" strokeDasharray="4 4" />
                      <Line type="monotone" dataKey="equity_close" name="Profit Closing" stroke="#3d9cfd" strokeWidth={2} dot={false} isAnimationActive={false} />
                      <Line type="monotone" dataKey="equity_open" name="Profit Opening" stroke="#e8a838" strokeWidth={2} dot={false} isAnimationActive={false} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </div>
            ) : null}
          </>
        ) : null}

        {tab === 'metrics' ? (
          <>
            <MetrikenHelpPanel />
            {!data?.ok ? (
              <p className="muted">Filter setzen → „Analysieren“, dann erscheinen die Glicko-Aggregate.</p>
            ) : (
              <>
            <h3 className="strat-outcome-title">
              Glicko-Metriken · n={num(glicko.games_n, 0)} Spiele
            </h3>
            <div className="stat-grid strat-outcome-grid">
              <div className="stat-card" title={METRIKEN_HELP_TITLE.avg_rating_h}>
                <div className="stat-card-title">Ø Rating H</div>
                <div className="stat-card-value">{num(glicko.avg_rating_h, 0)}</div>
              </div>
              <div className="stat-card" title={METRIKEN_HELP_TITLE.avg_rating_a}>
                <div className="stat-card-title">Ø Rating A</div>
                <div className="stat-card-value">{num(glicko.avg_rating_a, 0)}</div>
              </div>
              <div className="stat-card" title={METRIKEN_HELP_TITLE.avg_rating_diff}>
                <div className="stat-card-title">Ø Rating Diff</div>
                <div className="stat-card-value">{num(glicko.avg_rating_diff, 0)}</div>
                <div className="stat-card-sub">Home − Away</div>
              </div>
              <div className="stat-card" title={METRIKEN_HELP_TITLE.avg_rd}>
                <div className="stat-card-title">Ø RD H / A</div>
                <div className="stat-card-value">
                  {num(glicko.avg_rd_h, 1)} / {num(glicko.avg_rd_a, 1)}
                </div>
              </div>
              <div className="stat-card" title={METRIKEN_HELP_TITLE.avg_vol}>
                <div className="stat-card-title">Ø Vol H / A</div>
                <div className="stat-card-value">
                  {num(glicko.avg_vol_h, 3)} / {num(glicko.avg_vol_a, 3)}
                </div>
              </div>
              <div className="stat-card" title={METRIKEN_HELP_TITLE.avg_xg}>
                <div className="stat-card-title">Ø xG Glicko H / A</div>
                <div className="stat-card-value">
                  {num(glicko.avg_xg_h)} / {num(glicko.avg_xg_a)}
                </div>
                <div className="stat-card-sub">Vorhersage</div>
              </div>
              <div
                className="stat-card"
                title="Ø Match-xG Home / Away — tatsächlich erzielte xG (Look-ahead)"
              >
                <div className="stat-card-title">Ø xG Match H / A</div>
                <div className="stat-card-value">
                  {num(glicko.avg_xg_match_h)} / {num(glicko.avg_xg_match_a)}
                </div>
                <div className="stat-card-sub">Summe {num(glicko.avg_xg_match_sum)}</div>
              </div>
              <div className="stat-card" title="Ø Tore Home / Away aus dem Endstand">
                <div className="stat-card-title">Ø Goals H / A</div>
                <div className="stat-card-value">
                  {num(glicko.avg_goals_h)} / {num(glicko.avg_goals_a)}
                </div>
                <div className="stat-card-sub">Summe {num(glicko.avg_goals_sum)}</div>
              </div>
              <div className="stat-card" title={METRIKEN_HELP_TITLE.avg_p_home}>
                <div className="stat-card-title">Ø P(Home)</div>
                <div className="stat-card-value">{pctCell(glicko.avg_p_home)}</div>
              </div>
              <div className="stat-card" title={METRIKEN_HELP_TITLE.avg_p_draw}>
                <div className="stat-card-title">Ø P(Draw)</div>
                <div className="stat-card-value">{pctCell(glicko.avg_p_draw)}</div>
              </div>
              <div className="stat-card" title={METRIKEN_HELP_TITLE.avg_p_away}>
                <div className="stat-card-title">Ø P(Away)</div>
                <div className="stat-card-value">{pctCell(glicko.avg_p_away)}</div>
              </div>
            </div>
              </>
            )}
          </>
        ) : null}

        {tab === 'past' && data?.ok ? (
          <>
            {data.truncated ? (
              <p className="muted">Tabelle auf {data.results.length} Zeilen begrenzt (gesamt {data.n}).</p>
            ) : null}
            <p className="muted">Zeile anklicken → alle Parameter des Spiels.</p>
            <MatchParamsPanel row={pastDetail} onClose={() => setPastDetail(null)} />
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Datum</th>
                    <th>Home</th>
                    <th>Away</th>
                    <th>Land</th>
                    <th>Liga</th>
                    <th className="num">Rating H</th>
                    <th className="num">Rating A</th>
                    <th className="num">xG Gl H</th>
                    <th className="num">xG Gl A</th>
                    <th className="num" title="xG Saison Home (früher Form2)">xG Sa H</th>
                    <th className="num" title="xG Saison Away (früher Form2)">xG Sa A</th>
                    <th className="num">xG Ma H</th>
                    <th className="num">xG Ma A</th>
                    <th>Markt</th>
                    <th className="num">Open</th>
                    <th className="num">Close</th>
                    <th className="num">xROI %</th>
                    <th className="num">Quote</th>
                    <th className="num">Profit</th>
                    <th className="num">Erg.</th>
                  </tr>
                </thead>
                <tbody>
                  {(data.results || []).map((r, i) => (
                    <tr
                      key={`${r.game_id}-${r.market}-${i}`}
                      style={{ cursor: 'pointer' }}
                      className={pastDetail === r ? 'row-selected' : ''}
                      onClick={() => setPastDetail(pastDetail === r ? null : r)}
                    >
                      <td>{String(r.date || '').slice(0, 10)}</td>
                      <td>{r.home}</td>
                      <td>{r.away}</td>
                      <td>{r.country || '—'}</td>
                      <td>{r.league || '—'}</td>
                      <td className="num">{num(r.rating_h, 0)}</td>
                      <td className="num">{num(r.rating_a, 0)}</td>
                      <td className="num">{num(r.xg_glicko_h)}</td>
                      <td className="num">{num(r.xg_glicko_a)}</td>
                      <td className="num">{num(r.xg_form2_h)}</td>
                      <td className="num">{num(r.xg_form2_a)}</td>
                      <td className="num">{num(r.xg_h ?? r.xg_match_h)}</td>
                      <td className="num">{num(r.xg_a ?? r.xg_match_a)}</td>
                      <td>{r.market}</td>
                      <td className="num">{oddsNum(r.odds_opening)}</td>
                      <td className="num">{oddsNum(r.odds_closing)}</td>
                      <td className={`num ${r.xroi_pct >= 0 ? 'pos' : 'neg'}`}>
                        {r.xroi_pct == null ? '—' : `${num(r.xroi_pct, 1)}%`}
                      </td>
                      <td className="num">{oddsNum(r.odds)}</td>
                      <td className={`num ${r.profit >= 0 ? 'pos' : 'neg'}`}>{num(r.profit)}</td>
                      <td className="num">
                        {r.home_score}–{r.away_score}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        ) : null}

        {tab === 'upcoming' ? (
          upcoming?.skipped ? (
            <p className="muted">
              {upcoming.message ||
                'Bevorstehende Spiele ausgeblendet: Ergebnis-Filter (Home/Draw/Away/O-U) braucht den Endstand.'}
            </p>
          ) : !upcoming?.ok ? (
            <p className="muted">Noch keine Daten — „Analysieren“ tippen.</p>
          ) : upcoming.n === 0 ? (
            <p className="muted">Keine Upcoming-Spiele mit diesen Filtern.</p>
          ) : (
            <>
              <div className="stat-section-head" style={{ marginBottom: '0.75rem' }}>
                <span className="pill pill-live">{upcoming.n} Treffer</span>
                <span className="pill pill-muted">
                  Ø xROI{' '}
                  {upcoming.avg_xroi_pct != null ? `${num(upcoming.avg_xroi_pct, 1)}%` : '—'}
                  {' · '}n={upcoming.xroi_n ?? 0}
                </span>
              </div>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Datum</th>
                      <th>Home</th>
                      <th>Away</th>
                      <th>Land</th>
                      <th>Liga</th>
                      <th className="num">Rating H</th>
                      <th className="num">Rating A</th>
                      <th className="num">xG Gl H</th>
                      <th className="num">xG Gl A</th>
                      <th>Markt</th>
                      <th className="num">Open</th>
                      <th className="num">Close</th>
                      <th className="num">xROI %</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(upcoming.matches || []).map((r, i) => (
                      <tr key={`u-${r.game_id}-${r.market}-${i}`}>
                        <td>{String(r.date || '').slice(0, 16).replace('T', ' ')}</td>
                        <td>{r.home}</td>
                        <td>{r.away}</td>
                        <td>{r.country || '—'}</td>
                        <td>
                          {r.league || '—'}
                          {r.swisslos ? <SwisslosBadge /> : null}
                        </td>
                        <td className="num">{num(r.rating_h, 0)}</td>
                        <td className="num">{num(r.rating_a, 0)}</td>
                        <td className="num">{num(r.xg_glicko_h)}</td>
                        <td className="num">{num(r.xg_glicko_a)}</td>
                        <td>{r.market}</td>
                        <td className="num">{oddsNum(r.odds_opening)}</td>
                        <td className="num">{oddsNum(r.odds_closing)}</td>
                        <td className={`num ${r.xroi_pct >= 0 ? 'pos' : 'neg'}`}>
                          {r.xroi_pct == null ? '—' : `${num(r.xroi_pct, 1)}%`}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )
        ) : null}
      </section>
    </div>
  )
}
