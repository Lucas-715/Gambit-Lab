# Gambit Lab 2.0 — Especificação Técnica Integral

Framework Multiagente Baseado em Xadrez e Go para Pesquisa, Debate e Auditoria

Versão: 2.0 (Outubro de 2026)  
Status: Especificação de Engenharia e Roteiro de Implementação  
Princípio Fundamental: **O LLM propõe, as regras do jogo restringem, as evidências sustentam e o sistema registra.**

---

## 1. Visão Geral e Princípios Arquiteturais

Gambit Lab é um framework de raciocínio multiagente guiado por jogos (*Game-Driven Multi-Agent System*), e não simplesmente um jogo com inteligência artificial.

### 1.1 As Duas Dimensões Independentes (Matriz 3×2)

| Modalidade \ Jogo | Xadrez (8×8) | Go / Weiqi (9×9) |
| :--- | :--- | :--- |
| **Pesquisa** | Gambitos e diferentes linhas de investigação orientam busca central, contraponto e risco de hipótese. | Cobertura de regiões, expansão por influência e aprofundamento territorial de fontes. |
| **Debate** | Confronto de evidências com capturas condicionadas; brancas iniciam; árbitro factual avalia refutações. | Disputa territorial com contestação de teses; pretas iniciam; captura é espacial e avaliação factual é separada. |
| **Auditoria** | Peças representam controles, testes e riscos; confrontos capturam falhas de justificativa técnica. | Regiões representam domínios de conformidade, interseções representam verificações e lacunas. |

### 1.2 Princípio de Integridade Tripartida

O sistema distingue explicitamente três dimensões:
1. **Placar do Jogo** (`game_result`): Determinado exclusivamente pelos motores formais (python-chess / Go 9x9).
2. **Qualidade das Fontes** (`evidence_assessment`): Proveniência, hash SHA-256 de conteúdo, localizadores de trechos e integridade de citação.
3. **Validade Factual** (`verdict`): Veredito epistemológico emitido com suporte a `INCONCLUSIVE`, `NOT_COMPARABLE`, `REFUTED` ou `SUPPORTED`.

Uma partida pode terminar com vitória de um lado no jogo e, simultaneamente, declarar o tema investigado como **inconclusivo**.

---

## 2. A Nova Funcionalidade: FUSION Research

A **Pesquisa FUSION** permite investigar uma pergunta complexa a partir de 1 a 3 estratégias investigativas simultâneas:
- **No Xadrez**: Gambito da Dama (equilíbrio/metodologia), Gambito do Rei (exploração de hipóteses), Gambito Evans (descobertas/contraexemplos).
- **No Go**: Lente de Influência (cobertura ampla), Lente de Território (aprofundamento em fontes primárias), Lente de Invasão (testes adversariais), Lente de Conexão (interseção entre domínios).

### Pipeline Determinístico de Fusão:
1. **Planejar**: Decomposição da questão em tópicos, escopo e fontes permitidas.
2. **Alocar Orçamento**: Quota estrita de chamadas e tokens por ramo.
3. **Executar Ramos**: Cada ramo atua em um tabuleiro isolado com seu próprio estado de jogo. Ramos **não misturam lances** nem trocam conclusões prematuramente.
4. **Normalizar**: Extração de claims atômicas, localizadores e hashes de citação.
5. **Conciliar**: Deduplicação de fontes (mesma URL/hash = 1 fonte independente, evitando contagem de votos espúria) e classificação de relações (`CONVERGENT`, `CONTRADICTORY`, `DIFFERENT_SCOPE`, `INSUFFICIENT`).
6. **Red Team**: Agente crítico busca refutações e aponta vieses e limites.
7. **Sintetizar**: Emissão de relatório único auditável com conclusões fundamentadas, divergências e lacunas.

---

## 3. Regras de Jogo e Exceções de Domínio

### 3.1 Xadrez (8×8)
- Motor formal determinístico (`python-chess`).
- Peças, coordenadas algébricas, roque, *en passant*, promoção, xeque, xeque-mate, afogamento, regra de 50 lances e repetição de posição.
- **Variante Epistêmica**:
  - Movimentos não capturantes são validados pelo motor e executados normalmente.
  - Tentativas de captura exigem submissão de alegação adversária e trecho probatório. A captura só é persistida no motor se o árbitro emitir o veredito `REFUTED`.
  - Se condições epistêmicas impedirem ações admissíveis, registra-se `IMPASSE_DA_VARIANTE` sem alterar as regras oficiais da FIDE.

### 3.2 Go / Weiqi (9×9)
- Tabuleiro 9×9 no MVP, pretas iniciam.
- Ocupação de interseção, cálculo de liberdades e formação de cadeias/grupos.
- Captura espacial automática por cerco quando um grupo atinge 0 liberdades.
- Proibição absoluta de suicídio e regra de superko posicional.
- Dois passes consecutivos encerram a partida, com contagem por pontuação de área e komi pré-fixado (padrão: 6.5).
- **Separação Epistêmica**: A remoção de uma pedra por cerco espacial **não apaga** a alegação vinculada nem equivale a falsificação factual.

---

## 4. Rastreabilidade, Criptografia e Armazenamento de Eventos

- **Event Store Append-Only**: Cada ação gera um evento imutável com encadeamento de hash:
  $$\text{event\_hash} = \text{SHA256}(\text{canonical\_json}(\text{event\_payload}) + \text{previous\_event\_hash})$$
- **Replay Determinístico**: Qualquer sessão pode ser reconstituída passo a passo a partir da lista de eventos, sem necessidade de invocar o LLM novamente.
- **Cofres Privados e Manifesto Pré-Partida**: Documentos de cada lado são registrados por hash SHA-256 e congelados antes do primeiro lance (`LOCKED`). O árbitro acessa estritamente os trechos submetidos para disputa.
- **Política de Fontes**:
  - `own_only`: Restrito aos documentos carregados; nenhuma requisição externa de rede é efetuada.
  - `web_opt_in`: Pesquisa externa expressamente autorizada pelo usuário, com captura e URL registrada.

---

## 5. Máquina de Estados da Sessão

```
[DRAFT] -> [PREPARING] -> [LOCKED] -> [RUNNING] -> [PAUSED]
                                           |--------> [FINISHED]
                                           \--------> [FAILED_CONTROLLED]
```

### Estados de Claim:
- `HYPOTHESIS`: Proposta sem evidência conclusiva.
- `SUPPORTED`: Comprovada por trecho e localizador válido.
- `REFUTED`: Refutada formalmente por contra-evidência aceita pelo árbitro.
- `CONTESTED`: Sob disputa ativa.
- `INCONCLUSIVE`: Fontes insuficientes ou dados inconclusivos.
- `NOT_COMPARABLE`: Divergência de métrica, escopo ou metodologia.

---

## 6. Governança do Provedor de IA e Modo Demo

- **Gemini API**: Provedor sugerido via adaptador server-side com suporte a BYOK (*Bring Your Own Key*). A chave de API nunca é exposta no frontend.
- **Modo Demo Offline**: Execução integral sem chave e sem rede, utilizando cenários simulados pré-validados e explicitamente rotulados (`[DEMO / SIMULAÇÃO]`).
- **Defesa Contra Prompt Injection**: Documentos ingeridos são processados estritamente como dados não confiáveis, isolados das instruções operacionais dos agentes.
