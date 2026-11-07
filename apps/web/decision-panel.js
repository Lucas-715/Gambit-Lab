function renderDecisionPanel(conclusion) {
  const panel = document.getElementById('decisionPanel');
  if (!panel) return;
  const decision = conclusion && conclusion.decision;
  if (!decision || !decision.criteria) { panel.hidden = true; return; }
  panel.hidden = false;
  const esc = escapeHtml;
  const labels = {PRO:'Favorece a tese Pró',CONTRA:'Favorece a tese Contra',BALANCED:'Equilíbrio fundamentado',NOT_ESTABLISHED:'Comparação não demonstrada'};
  const total = Math.max(1, Number(decision.total_criteria) || 1);
  const assessed = Math.max(0, Math.min(total, Number(decision.assessed_criteria) || 0));
  const missing = decision.criteria.filter(r => r.verdict === 'NOT_ESTABLISHED').map(r => r.label);
  const shortSummary = `Foram julgados ${assessed} de ${total} critérios (${decision.pro_points} Pró × ${decision.contra_points} Contra).` +
    (missing.length ? ` Lacunas em: ${missing.join(', ')}.` : '');
  const illustration = `<svg class="decision-illustration" viewBox="0 0 180 150" aria-hidden="true" fill="none"><path d="M40 60v38h100V60M90 98v25" stroke="#84759f" stroke-width="2"/><rect x="13" y="12" width="56" height="62" rx="9" fill="#272033" stroke="#ac8eff"/><rect x="111" y="12" width="56" height="62" rx="9" fill="#17262c" stroke="#75b8c4"/><path d="M25 29h30M25 40h23M25 51h27M123 29h30M123 40h23M123 51h27" stroke="#c9bfdd" stroke-width="2"/><circle cx="90" cy="125" r="18" fill="#3c2e59" stroke="#ac8eff"/><path d="m82 125 5 5 10-11" stroke="#ded2fa" stroke-width="2.5"/></svg>`;
  panel.innerHTML = `<div class="decision-hero"><div><div class="decision-kicker">Julgamento comparativo · resultado da investigação</div><h3>${esc(decision.title)}</h3><p class="decision-summary-line">${esc(shortSummary)}</p></div>${illustration}</div>
    <div class="decision-score-row">
      <div class="decision-score"><span>${esc(decision.pro_points)} <small>Pró</small></span><span aria-hidden="true">×</span><span>${esc(decision.contra_points)} <small>Contra</small></span></div>
      <span class="decision-bar-meta">${assessed}/${total} critérios fundamentados</span>
    </div>
    <div class="decision-bar" role="img" aria-label="${assessed} de ${total} critérios avaliados"><i style="width:${100*assessed/total}%"></i></div>
    <div class="decision-grid">${decision.criteria.map(row => `<details class="decision-criterion"><summary>${esc(row.id)} · ${esc(row.label)}<span class="decision-tag">${esc(labels[row.verdict] || row.verdict)}</span></summary><p>${esc(row.reason)}</p><p><b>Recorte comparado:</b> ${esc(row.comparison_scope)}</p>${(row.citations || []).map(c => `<blockquote>${esc(c.quote_text)}<br><small>Fonte: ${esc(c.artifact_id)} · Peça: ${esc(c.piece_id)}</small></blockquote>`).join('')}</details>`).join('')}</div>
    <div class="decision-actions">
      <button class="btn sm accent" data-decision-export="markdown">⬇ Exportar decisão (.md)</button>
      <button class="btn sm secondary" data-decision-export="json">Exportar JSON</button>
      <details class="decision-method-fold"><summary>Nota metodológica ▾</summary><p class="decision-foot">${esc(decision.method)}<br>${esc(decision.scope_rule)}<br>${esc(decision.reviewer)}</p></details>
    </div>`;
  panel.querySelectorAll('[data-decision-export]').forEach(b => b.addEventListener('click', () => exportReport(b.dataset.decisionExport)));
}
