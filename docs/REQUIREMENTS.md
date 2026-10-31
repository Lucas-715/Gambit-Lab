# Catálogo de Requisitos e Critérios de Aceite — Gambit Lab 2.0

## 1. Requisitos Funcionais (RF) — Destaque P0 / P1
- **RF-01 (P0)**: Criar sessão com modo (Pesquisa, Debate, Auditoria) e jogo (Xadrez, Go) independentes, status e versão.
- **RF-02 (P0)**: Editar tema, objetivo e orçamento até o início (`LOCKED`).
- **RF-03 (P0)**: Listar sessões e retomar o estado salvo com posição e fontes autorizadas.
- **RF-04 (P0)**: Enviar PDF, TXT e MD com tamanho e tipo limitados; cálculo de hash SHA-256.
- **RF-05 (P0)**: Extrair texto com localizador de página/bloco e hash.
- **RF-06 (P0)**: Selecionar `own_only` ou `web_opt_in` por sessão.
- **RF-07 (P0)**: Buscar trechos autorizados via índice local.
- **RF-08 (P0)**: Bloquear documentos privados entre lados pré-partida (retornar 403).
- **RF-09 (P0)**: Selecionar Xadrez 8×8 ou Go 9×9 em qualquer modalidade (Matriz 3×2).
- **RF-10 (P0)**: Validar movimentos especiais de Xadrez (roque, en passant, promoção, xeque, mate, empates).
- **RF-11 (P0)**: Validar liberdades, captura espacial, ko/superko, passes e pontuação em Go.
- **RF-12 (P0)**: Definir tese e permissões privadas para os dois lados no Debate.
- **RF-13 (P0)**: Registrar hash dos artefatos antes do início (manifesto de lock).
- **RF-14 (P0)**: Brancas iniciam Xadrez; pretas iniciam Go.
- **RF-15 (P0)**: Arbitrar captura proposta no Xadrez antes de aplicar (exige veredito `REFUTED`).
- **RF-16 (P0)**: Capturar grupos Go apenas pelo motor, mantendo histórico de claims.
- **RF-17 (P0)**: Marcar impasse de variante sem alterar resultado oficial FIDE.
- **RF-18 (P0)**: Selecionar presets investigativos por jogo (Gambitos no Xadrez, Lentes no Go).
- **RF-19 (P0)**: Iniciar busca assistida Gemini com contexto autorizado e quota de tokens.
- **RF-20 (P0)**: Executar Pesquisa FUSION com 2 a 3 ramos independentes em tabuleiros isolados.
- **RF-21 (P1)**: Permitir FUSION entre jogos sob quota explícita.
- **RF-22 (P0)**: Deduplicar fontes citadas por múltiplos agentes (mesma URL/hash = 1 fonte).
- **RF-23 (P0)**: Classificar divergências sem votação por maioria (`CONVERGENT`, `CONTRADICTORY`, `DIFFERENT_SCOPE`, `INSUFFICIENT`).
- **RF-24 (P0)**: Definir checklist de requisitos/controles e severidade na Auditoria.
- **RF-25 (P0)**: Relacionar peça/pedra e requisito por ID na Auditoria.
- **RF-26 (P0)**: Produzir matriz de cobertura e achados na Auditoria.
- **RF-27 (P0)**: Executar funções lógicas de pesquisador, crítico, árbitro e sintetizador com JSON tipado.
- **RF-28 (P0)**: Bloquear texto de fontes como instrução operacional (mitigação de prompt injection).
- **RF-29 (P0)**: Validar citação e impedir identificadores inexistentes (claims sem suporte permanecem hipótese).
- **RF-30 (P0)**: Registrar veredito com rubrica de 7 pontos e suporte a `INCONCLUSIVE`.
- **RF-31 (P0)**: Exibir tabuleiro interativo 3D com movimentos animados.
- **RF-32 (P0)**: Oferecer fallback 2D acessível e controle por teclado.
- **RF-33 (P0)**: Exibir timeline por movimento com fontes, trechos e custos.
- **RF-34 (P0)**: Oferecer replay passo a passo determinístico sem chamar LLM.
- **RF-35 (P0)**: Exportar relatório em PDF, HTML e JSON com rastreabilidade integral.
- **RF-36 (P0)**: Executar sem API em modo demo com dados simulados explicitamente rotulados.
- **RF-37 (P0)**: Utilizar Gemini via backend e variável de ambiente (`GEMINI_API_KEY`).
- **RF-38 (P0)**: Controlar limite de chamadas/tokens e interrupção segura por orçamento.
- **RF-39 (P0)**: Gerar IDs de correlação, logs de falhas e suporte a retry com idempotência.
- **RF-42 (P0)**: Persistir eventos canônicos e cadeia de hashes SHA-256.
- **RF-43 (P0)**: Versionar reavaliações sem sobrescrever decisões históricas.
- **RF-44 (P0)**: Mostrar painel de FUSION com ramos paralelos, divergências e síntese.
- **RF-45 (P0)**: Trocar jogo/modo na configuração antes do lock com aviso.
- **RF-46 (P0)**: Oferecer endpoint de saúde (`GET /health`) e documentação OpenAPI.

---

## 2. Requisitos Não Funcionais (RNF) — Destaque P0
- **RNF-01 (Legalidade)**: Nenhuma ação ilegal persistida por motores determinísticos.
- **RNF-02 (Integridade)**: Eventos versionados e replay 100% consistente.
- **RNF-03 (Isolamento)**: Nenhum vazamento entre cofres privados dos lados.
- **RNF-04 (Segredos)**: Chave Gemini exclusivamente no backend; zero exposição no cliente.
- **RNF-05 (Robustez)**: Falha do LLM não deixa jogada parcialmente aplicada (transações atômicas).
- **RNF-06 (Disponibilidade)**: Modo de demonstração offline sem Gemini, sem rede e sem chave.
- **RNF-07 (Acessibilidade)**: Operação 2D acessível por teclado, contraste alto e foco visível.
- **RNF-08 (Animação)**: Movimento suave com suporte a `prefers-reduced-motion`.
- **RNF-09 (Performance UI)**: Meta de 30 FPS na interface 3D em hardware padrão.
- **RNF-10 (Responsividade)**: Suporte a desktop (1280px) e telas menores sem quebra funcional.
- **RNF-13 (Rastreabilidade)**: Toda conclusão aponta para trecho válido ou é rotulada como hipótese.
- **RNF-14 (Custo)**: Budget por sessão e por ramo com interrupção rígida (*hard stop*).
- **RNF-17 (Concorrência)**: Controle otimista via `expected_version` retornando HTTP 409 em conflitos.

---

## 3. Regras de Negócio Críticas (RN-01 a RN-40)
- **RN-01**: Modo e jogo são independentes: todas as 6 combinações sempre ativas.
- **RN-02**: Sessão inicia como `DRAFT` e só aceita turnos após `LOCKED`.
- **RN-03**: Brancas iniciam Xadrez e Pretas iniciam Go.
- **RN-04**: O Game Engine decide a legalidade; o LLM não pode sobrepor rejeições.
- **RN-05**: Jogada proposta não altera o estado do tabuleiro até confirmação transacional.
- **RN-06**: No Xadrez com captura condicionada, a captura exige veredito `REFUTED` da alegação alvo.
- **RN-07**: No Xadrez, lances não capturantes seguem regras normais sem exigir refutação.
- **RN-09**: No Go, capturas ocorrem puramente por ausência de liberdades conforme o motor.
- **RN-10**: No Go, a captura espacial de uma pedra não apaga sua alegação do histórico.
- **RN-17**: `own_only` proíbe ferramentas de busca externa e chamadas web.
- **RN-20**: Alegações sem citação válida permanecem `HYPOTHESIS`.
- **RN-21**: Julgamento `INCONCLUSIVE` é um desfecho legítimo e não gera vitória automática.
- **RN-24**: FUSION executa 1 a 3 estratégias, cada qual com seu estado de tabuleiro isolado.
- **RN-25**: FUSION consolida fontes e alegações; **nunca** mistura movimentos de tabuleiros diferentes.
- **RN-28**: Duplicação de fontes é colapsada por hash SHA-256 e URL canônica.
- **RN-32**: Replay não invoca o LLM: executa os eventos canônicos sobre o motor fixado.

---

## 4. Critérios de Aceite Ponta a Ponta (AC-01 a AC-24)
- **AC-01**: Pesquisa em Xadrez gera lance legal e claim vinculado.
- **AC-02**: Pesquisa em Go gera pedras legais e mapa de cobertura separado de território.
- **AC-03**: Debate em Xadrez com abertura privada; tentativa de captura sem refutação é rejeitada.
- **AC-04**: Debate em Go com pretas iniciando e captura espacial automática preservando histórico de claims.
- **AC-05**: Auditoria em Xadrez inspeciona controles e gera achados com severidade.
- **AC-06**: Auditoria em Go mapeia requisitos em interseções; lacunas sem fonte permanecem não testadas.
- **AC-07**: FUSION com múltiplos gambitos isola tabuleiros e agrega fontes sem somar repetidas.
- **AC-09**: Claim com `citation_id` inexistente é rejeitada ou marcada sem suporte.
- **AC-10**: Nenhuma requisição de rede é disparada na política `own_only`.
- **AC-13**: Lance ilegal em Xadrez ou violação de ko em Go não altera versão nem estado.
- **AC-16**: Modo offline demo inicia sem chave, sem rede e com identificação sintética clara.
- **AC-18**: Replay recarrega e reproduz exatamente o mesmo estado a partir dos eventos.

