/** Anzeige-Namen der Metriken. Interne Schlüssel (z. B. xg_form2_home) bleiben unverändert,
 * damit gespeicherte Strategien weiter funktionieren. Gleiches Schema im Backend:
 * services/strategy_service.py → METRIC_DISPLAY_NAMES.
 *
 * Home/Away = Heimteam bzw. Gast dieses Spiels; Klammer = Datenbasis.
 */
export const METRIC_NAMES = {
  // Glicko-Rating
  rating_home: 'Rating Home',
  rating_away: 'Rating Away',
  rating_avg: 'Rating Ø (Home + Away) ÷ 2',
  rating_sum: 'Rating Home + Away',
  rating_diff: 'Rating Home − Away',
  glicko_diff: 'Rating Home − Away',
  rating_ratio: 'Rating Home ÷ Away',
  glicko_rating: 'Rating Ø (Home + Away) ÷ 2',
  // xG Glicko (Vorhersage sstats)
  xg_glicko_home: 'xG Glicko Home',
  xg_glicko_away: 'xG Glicko Away',
  xg_home_glicko: 'xG Glicko Home',
  xg_away_glicko: 'xG Glicko Away',
  xg_glicko_sum: 'xG Glicko Home + Away',
  glicko_xg: 'xG Glicko Home + Away',
  xg_glicko_diff: 'xG Glicko Home − Away',
  xg_glicko_ratio: 'xG Glicko Home ÷ Away',
  // xG Saison (eigene Vorhersage: Ø xG + Gegner Ø xGA, alle Saisonspiele) — früher „Form2“
  xg_form2_home: 'xG Saison Home',
  xg_form2_away: 'xG Saison Away',
  xg_form2_sum: 'xG Saison Home + Away',
  xg_form2_diff: 'xG Saison Home − Away',
  xg_form2_ratio: 'xG Saison Home ÷ Away',
  // xG Venue (wie Saison, aber Home nur Heimspiele, Away nur Auswärtsspiele)
  hometeam_pred_xg: 'xG Venue Home',
  awayteam_pred_xg: 'xG Venue Away',
  // Saison-Durchschnitte (alle Spiele)
  form2_avg_xg_home: 'Ø xG Home (Saison)',
  form2_avg_xg_away: 'Ø xG Away (Saison)',
  form2_avg_xga_home: 'Ø xGA Home (Saison)',
  form2_avg_xga_away: 'Ø xGA Away (Saison)',
  form2_avg_gf_home: 'Ø Tore Home (Saison)',
  form2_avg_gf_away: 'Ø Tore Away (Saison)',
  form2_avg_ga_home: 'Ø Gegentore Home (Saison)',
  form2_avg_ga_away: 'Ø Gegentore Away (Saison)',
  // Durchschnitte nach Spielort
  hometeam_home_xg: 'Ø xG Home (Heimspiele)',
  hometeam_home_xga: 'Ø xGA Home (Heimspiele)',
  hometeam_home_gf: 'Ø Tore Home (Heimspiele)',
  hometeam_home_ga: 'Ø Gegentore Home (Heimspiele)',
  hometeam_away_xg: 'Ø xG Home (Auswärtsspiele)',
  hometeam_away_xga: 'Ø xGA Home (Auswärtsspiele)',
  hometeam_away_gf: 'Ø Tore Home (Auswärtsspiele)',
  hometeam_away_ga: 'Ø Gegentore Home (Auswärtsspiele)',
  awayteam_home_xg: 'Ø xG Away (Heimspiele)',
  awayteam_home_xga: 'Ø xGA Away (Heimspiele)',
  awayteam_home_gf: 'Ø Tore Away (Heimspiele)',
  awayteam_home_ga: 'Ø Gegentore Away (Heimspiele)',
  awayteam_away_xg: 'Ø xG Away (Auswärtsspiele)',
  awayteam_away_xga: 'Ø xGA Away (Auswärtsspiele)',
  awayteam_away_gf: 'Ø Tore Away (Auswärtsspiele)',
  awayteam_away_ga: 'Ø Gegentore Away (Auswärtsspiele)',
  // tatsächlich erzieltes xG (nach dem Spiel)
  xg_match_home: 'xG Match Home',
  xg_match_away: 'xG Match Away',
  xg_match_sum: 'xG Match Home + Away',
  xg_match_diff: 'xG Match Home − Away',
  xg_match_ratio: 'xG Match Home ÷ Away',
  // Glicko-Details
  rd_home: 'Rating-Unsicherheit (RD) Home',
  rd_away: 'Rating-Unsicherheit (RD) Away',
  vol_home: 'Rating-Volatilität Home',
  vol_away: 'Rating-Volatilität Away',
}

export function metricName(key, fallback) {
  return METRIC_NAMES[key] || fallback || key
}

/** Listen-Einträge { value, label } mit den Anzeige-Namen versehen. */
export function withMetricNames(list) {
  return list.map((a) => ({ ...a, label: metricName(a.value, a.label) }))
}
