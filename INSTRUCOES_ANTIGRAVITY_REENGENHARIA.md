# Instrução de execução — Antigravity / Gambit Lab R1

**Contexto**: revisar o projeto local `C:\Users\Lucky\Documents\Gambit_Lab` mantendo arquitetura Game-Driven Multi-Agent System, seis aplicações Pesquisa/Debate/Auditoria × Xadrez/Go, WebGL, regras, FUSION, Gemini, eventos e replay. O usuário identificou opção Web desativada, limite visual de 3/3 lances e deseja um novo visual escuro **Nocturne**.

**Leia primeiro:** `AUDITORIA_E_PLANO_REENGENHARIA_GAMBIT_LAB.md` (anexo deste pacote), comparando com `docs/`, testes e código real do repositório. `Gambit_Lab_Nocturne_Conceito_UI.html` é **referência de hierarquia, navegação e tokens CSS**, não substituto do frontend nem do motor 3D já existente.

## Ordem obrigatória de trabalho

1. **Congelar estado atual**: rodar `git status`, verificar branch, criar nova branch `refactor/nocturne-audit`; registrar baseline de testes e build; não sobrescrever sem backup, não publicar.
2. **Auditar sem modificar**: mapear módulos, modelos de dados, endpoints, provedores e flags `web_opt_in/own_only`, modo demo/live, contadores de lances, `Next/Advance/Replay`, agentes, fontes e arbitragem. Para cada achado, registrar arquivo:linha e a reprodução.
3. **Reproduzir bugs**: usar navegador real e observar API/Network/console; demonstrar o que acontece quando Web é selecionada e quando chega ao terceiro lance; verificar se três movimentos são somente um roteiro predefinido e se o botão de avançar invoca a API de geração. **Não afirmar causa antes de localizar o código.**
4. **Corrigir núcleo operacional antes da estética**: separar `CONTINUE_INVESTIGATION` de `REPLAY_NEXT`; distinguir etapas de pesquisa, plies do jogo e eventos; restaurar progressão não artificial quando for legal/permitida; persistir versão do estado, orçamento e transições, respeitando testes FIDE e Go.
5. **Pesquisa Web**: implementar capacidade opt-in auditável se couber no escopo P0 e houver provedor efetivo; opções OWN_ONLY/WEB_ONLY/HYBRID; persistência de URL/data/trecho; SSRF, redirecionamentos, rate-limit, consentimento. Se não houver integração real, deixar desabilitado e documentar como P1 — não liberar placebo.
6. **Gemini & evidências**: testes LIVE separados com chave no `.env` backend, nunca na UI; sem fonte, nunca SUPPORTED; separar cadeia SHA-256 de verificação literal e de sustentação; UI deve indicar DEMO versus LIVE e uso real versus não medido.
7. **Redesign Nocturne**: home preta, compositor único, configs compactas; depois transição para Workspace com tabuleiro 3D WebGL existente, modo 2D, painel lateral com tabs Conversa/Fontes/Auditoria/Histórico, histórico e comandos separados. Remover azul-marinho brilhante, excesso de menta, planetas fortes no Workspace; usar tokens do documento. **Não substituir as peças WebGL reais por Unicode ou CSS do protótipo.**
8. **Testes completos**: unitários + integração + E2E desktop/mobile; 6 matrizes de modo/jogo; Xadrez 10+ lances, Go até passes/superko; replay completo; simulação de provedor fora do ar, 429/503 e limites; teste de `own_only` sem busca pública; validação independente de citações; confidencialidade de cofres.
9. **Auditoria final**: arquivos e linhas alterados; outputs de testes; screenshots reais do navegador e logs de API; tabela PASS/FAIL/SKIPPED; métricas de custo/latência somente se medidos. Revisar segurança e README. Fazer commit local quando aprovado; **não executar push sem solicitação explícita**.

## Critério de encerramento sem ambiguidades

- O botão de continuar pode produzir um 4º, 5º, 6º... evento **quando condições do motor, orçamento e dados permitem**; se o fluxo termina deve exibir um motivo verídico e auditável.
- Replay chega ao último evento existente e não gera eventos novos.
- O seletor Web está disponível **somente** se a pesquisa real funcionar e citar fontes verificáveis; caso contrário mostra “Em desenvolvimento” e motivo.
- O sistema não exibe “Gemini executado” se usou demo; não exibe “SUPPORTED” sem alegação sustentada por citação avaliada; não inventa uso de tokens, custos ou 100% de validação.
- As seis combinações de modo × jogo passam nos testes; peças e lances WebGL refletem unicamente estado confirmado no backend.
- Não remover código do motor ou os testes existentes para “passar” a suite. Não refazer o backend inteiro por conveniência se o problema for só de flags e de UI.

## Relatório que espero receber

| Achado | Caminho/linha | Causa raiz comprovada | Correção | Teste/trace | Resultado |
|---|---|---|---|---|---|
| Web desativada | ... | ... | ... | ... | PASS/FAIL/SKIP |
| Três lances | ... | ... | ... | ... | PASS/FAIL/SKIP |
| Modo Demo/Live | ... | ... | ... | ... | PASS/FAIL/SKIP |
| Evidências/fonte | ... | ... | ... | ... | PASS/FAIL/SKIP |
| UI Nocturne | ... | ... | ... | ... | PASS/FAIL/SKIP |

**Importante:** não usar a minha API pessoal ou tokens compartilhados anteriormente; o usuário configura sua própria `GEMINI_API_KEY` no `.env` local. Preserve artefatos e pesquisas originais. Nunca substitua resultado real por mocks sem rotular claramente.
