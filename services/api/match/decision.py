"""Explicit comparison rubric and citation-bound jury decision, independent of chess."""
import unicodedata


def historical_comparison(topic):
    text = ''.join(c for c in unicodedata.normalize('NFD', topic.lower()) if unicodedata.category(c) != 'Mn')
    return ('governo' in text and any(w in text for w in ('historia', 'historico', 'esquerda', 'direita', 'melhor')))


def comparison_plan(topic, mode):
    if mode == 'audit':
        labels = ['Implementação dos controles', 'Efetividade e exceções', 'Cobertura e rastreabilidade', 'Risco residual']
    elif historical_comparison(topic):
        labels = ['Economia e estabilidade', 'Renda, pobreza e desigualdade', 'Saúde, educação e serviços públicos',
                  'Instituições e direitos', 'Sustentabilidade fiscal', 'Contexto histórico e atribuição causal']
    else:
        labels = ['Resultados observados', 'Benefícios e abrangência', 'Custos e efeitos adversos', 'Robustez e contexto das evidências']
    return {
        'question': topic,
        'criteria': [{'id': f'C{i + 1}', 'label': label, 'weight': 1} for i, label in enumerate(labels)],
        'method': 'Um ponto por critério decidido; empate divide o ponto. Critério sem evidência comparável não pontua. Pesos iguais, definidos antes da pesquisa.',
        'scope_rule': ('Comparar períodos e indicadores equivalentes; explicitar quais governos e anos foram incluídos, '
                       'como esquerda/direita foram classificados e quais efeitos podem decorrer de herança, crises ou contexto externo.'
                       if historical_comparison(topic) else 'Explicitar população, período, critérios de aceitação e limites das fontes.'),
    }


def decide(plan, reviews, trace, execution_mode, mode):
    # A review can only use an exact quote already verified in a specific dossier.
    allowed = {(r['piece_id'], a.get('artifact_id'), a.get('quote_text'))
               for r in trace for a in r.get('evidence', []) if a.get('verified') and a.get('quote_text')}
    by_id = {}
    for review in reviews if isinstance(reviews, list) else []:
        if isinstance(review, dict) and isinstance(review.get('criterion_id'), str) and review.get('criterion_id') not in by_id:
            by_id[review.get('criterion_id')] = review
    rows, pro, contra, assessed = [], 0.0, 0.0, 0
    for criterion in plan['criteria']:
        raw = by_id.get(criterion['id'], {})
        citations = raw.get('citations', [])
        valid = isinstance(citations, list) and bool(citations) and all(
            isinstance(c, dict) and all(isinstance(c.get(k), str) for k in ('piece_id', 'artifact_id', 'quote_text'))
            and (c.get('piece_id'), c.get('artifact_id'), c.get('quote_text')) in allowed
            for c in citations)
        verdict = raw.get('verdict')
        reason = raw.get('reason')
        scope = raw.get('comparison_scope')
        if (execution_mode == 'DEMO_OFFLINE' or not valid or not isinstance(reason, str) or not reason.strip()
                or not isinstance(scope, str) or not scope.strip() or verdict not in ('PRO', 'CONTRA', 'BALANCED')):
            verdict, citations = 'NOT_ESTABLISHED', []
            reason = 'Não foi apresentada uma comparação fundamentada com citações verificadas para este critério.'
            scope = 'Comparação ainda não estabelecida.'
        else:
            assessed += 1
            pro += criterion['weight'] * (1 if verdict == 'PRO' else .5 if verdict == 'BALANCED' else 0)
            contra += criterion['weight'] * (1 if verdict == 'CONTRA' else .5 if verdict == 'BALANCED' else 0)
        rows.append({**criterion, 'verdict': verdict, 'reason': reason, 'comparison_scope': scope, 'citations': citations})
    if execution_mode == 'DEMO_OFFLINE':
        code, title = 'DEMONSTRATION', 'Demonstração concluída — sem julgamento histórico real'
    elif not assessed:
        code, title = 'NOT_DEMONSTRATED', ('Conformidade não demonstrada no escopo examinado' if mode == 'audit' else 'Superioridade da tese não demonstrada nesta investigação')
    elif pro > contra:
        code, title = 'PRO_BY_CRITERIA', 'Tese Pró vence a comparação dos critérios avaliados'
    elif contra > pro:
        code, title = 'CONTRA_BY_CRITERIA', 'Tese Contra vence a comparação dos critérios avaliados'
    else:
        code, title = 'BALANCED_BY_CRITERIA', 'Empate fundamentado nos critérios avaliados'
    missing = [r['label'] for r in rows if r['verdict'] == 'NOT_ESTABLISHED']
    answer = f"{title}. Foram julgados {assessed} de {len(rows)} critérios, com placar {pro:g} a {contra:g} (Pró × Contra)."
    if missing:
        answer += ' A decisão é limitada por lacunas em: ' + '; '.join(missing) + '.'
    answer += ' O placar representa o julgamento comparativo das evidências desta execução, não uma probabilidade nem uma verdade histórica universal.'
    return {'code': code, 'title': title, 'answer': answer, 'pro_points': pro, 'contra_points': contra,
            'assessed_criteria': assessed, 'total_criteria': len(rows), 'criteria': rows,
            'method': plan['method'], 'scope_rule': plan['scope_rule'],
            'reviewer': 'LLM com referências verificadas; interpretação sujeita a revisão humana'}
