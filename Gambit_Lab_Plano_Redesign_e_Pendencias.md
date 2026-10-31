# Gambit Lab — Redesign de experiência e pendências reais do MVP

## Objetivo
Manter os motores determinísticos de Xadrez e Go e a arquitetura Game-Driven Multi-Agent System, mas substituir o fluxo inicial excessivamente técnico por uma experiência **pergunta primeiro, investigação depois**. O layout é inspirado no padrão de uso de assistentes conversacionais, sem copiar marcas ou layouts pixel a pixel.

## Jornada proposta

1. **Entrada:** fundo espacial sutil, campo de texto central, opções compactas de Pesquisa/Debate/Auditoria, Xadrez/Go, política de fontes, FUSION e upload. Nenhum veredito ou selo de auditoria aparece antes da sessão real existir.
2. **Criação:** frontend solicita `POST /api/v1/sessions` com modo, jogo, pergunta, política e configurações; anexa documentos pelo endpoint próprio; reporta falha de rede, limites, consentimento e custos.
3. **Transição:** campo de entrada inicial colapsa; o workspace entra com cabeçalho de pergunta, tabuleiro 3D/2D, conversa com agentes, evidências, histórico e controles. Toda a transição é reversível e acessível.
4. **Execução:** backend confirma cada ação antes da animação persistente; websocket/SSE opcional para eventos e respostas em streaming. Evitar exibir `SUPPORTED`, `SOURCE_VERIFIED`, porcentagens ou SHA-256 antes de comprovados.
5. **Explicações:** clique em peça/pedra abre alegação, fonte, trecho, URL/ID, hash, método de avaliação e motivo da decisão. Eventos de jogo e status epistemológicos são entidades diferentes.
6. **Replay:** aplicar histórico de eventos do servidor ao motor determinístico. Efeitos 3D acompanham movimentos, não comandam regras.

## Diretrizes visuais

- Fundo preto profundo `#05070e`, estrelas pequenas animadas via Canvas com limite de FPS/CPU, planetas discretos por CSS, gradientes azuis/roxo escuro; opacidade reduzida no workspace.
- Texto branco-acinzentado com contraste WCAG AA; menta `#70f0d2` para ações e status não enganadores. Nunca usar apenas cor para comunicar status.
- Superfícies translúcidas sobre fundo quase sólido, sem reduzir legibilidade. `prefers-reduced-motion` e opção 2D acessível.
- Em desktop: navegação estreita e área central prioritária; painel de evidências colapsável. Em mobile: tabuleiro ajustado à largura, evidências em drawer, controles com área de toque adequada.
- Peças 3D reais na versão de produto usando React Three Fiber/Three.js (geometrias, interação e animação), com fallback 2D em HTML/SVG. Protótipo HTML entregue usa **perspectiva CSS**, não malhas WebGL nem motor de regras.

## Contratos de integração que devem ser preservados

- Estado da sessão no backend é a fonte da verdade: ID, modo, jogo, pergunta, status, versões, agentes, documentos e autorização de rede.
- A UI deve usar contratos Pydantic/TypeScript compartilhados; não manter lógica de xadrez/go no frontend além de animação e feedback.
- Somente após sucesso `2xx` o movimento vira permanente; `409` exige reidratação do estado, e `422`/`403` exibem motivo compreensível.
- Política `own_only` nunca faz pesquisa externa. Opção Web deve mostrar `Em desenvolvimento` e ficar desativada até a ferramenta auditável existir.
- `GEMINI_API_KEY` somente no `.env` do backend, jamais no JavaScript ou no bundle entregue ao usuário. Na publicação, `.env.example` sem segredos e README com configuração BYOK.
- Distinguir `integrity_status`, `source_status`, `evidence_assessment`. Ausência de artefatos/citações não permite `SUPPORTED`; hash comprova integridade relativa ao registro, não verdade.

## Pendências para concluir o MVP declarado

| Prioridade | Pendência | Evidência de aceite |
|---|---|---|
| Bloqueante | Teste **real** da API Gemini | Com chave configurada localmente, executar consulta inédita; salvar custos/latência (sem segredos), trechos corretos e eventuais erros; não dizer que `skipped` comprova integração. |
| Bloqueante | Fluxo completo de documento → extração → citação → contestação → resultado | PDFs/TXT enviados em `own_only`; citar trecho exato e página/posição; hipótese sem apoio marcada `INSUFFICIENT`/`HYPOTHESIS`; casos contraditórios não inventados. |
| Bloqueante | Atestar 3×2 sem mocks no caminho crítico | Pesquisa, debate e auditoria com Xadrez e Go; movimentos legais e casos extremos, estados e fontes coerentes no navegador e API. |
| Bloqueante | Segurança reais dos uploads e cofre | Controle de autenticação/autorização compatível com implantação; tipo/tamanho/validade de arquivo; impedir acesso cruzado, SSRF em futuras buscas, prompt injection e vazamento de chave. |
| Bloqueante | Semântica do árbitro e conflitos | Rubrica com critérios e motivação; `INCONCLUSIVE` quando não há base; separar verificação literal de suporte factual; testes adversariais. |
| Importante | Replay e trilha auditável E2E | Navegador e API reconstroem a mesma posição/decisão a partir de eventos; alteração de evento é detectada; sem promessa de imutabilidade forte apenas por SHA-256. |
| Importante | Observabilidade e custos | Medir tokens, falhas, latência, retries, limites e orçamento por sessão; sem logging de chave ou conteúdo sigiloso. |
| Opcional para MVP | Exportação PDF binária | Se PDF direto for exigido no escopo, gerar e validar `.pdf`; HTML imprimível pode atender MVP documentado. |
| Pós-MVP | Web opt-in, FUSION cross-game, SaaS | Não rotular como entregue sem integração e testes reais. |
| Pós-MVP | Benchmark comparativo | Avaliar com mesmo orçamento e fontes versus LLM direto, incluindo citações, erro factual e cobertura. |

## Observações sobre as alegações do relatório

- `37 passed` é uma informação do agente, não validação independente nesta entrega.
- O teste Gemini `SKIPPED` significa que a integração **não foi testada ao vivo**.
- SHA-256 encadeado não é, isoladamente, prova de que um log não possa ser reescrito por alguém com acesso total ao armazenamento; para resistência à adulteração, considerar âncoras externas, assinaturas ou armazenamento WORM.
- Estudos Alpha/Beta e fontes descritas como “cenários reais” precisam ter proveniência checada. Um resumo ou arquivo de demonstração não é automaticamente um padrão publicado verificável.

## Critérios de aceite do redesign

- [ ] Página inicial apresenta a pergunta em destaque, sem os painéis técnicos.
- [ ] Usuário escolhe os três modos e ambos jogos no compositor inicial.
- [ ] Enviar com Enter cria sessão apenas quando o backend confirma; Shift+Enter quebra linha.
- [ ] Após iniciar, o compositor grande desaparece e o workspace é mostrado, com retorno para revisão.
- [ ] Xadrez e Go continuam interativos, com modos 3D/2D sem modificar as regras.
- [ ] Evidências e relatórios são ligados ao ID e à versão de sessão.
- [ ] Sem fontes verificadas, não exibir `SUPPORTED` ou `100% de citações válidas`.
- [ ] Mobile e navegação por teclado não ficam bloqueados; reduzir movimento funciona.
- [ ] Opções não implementadas, incluindo pesquisa web, são claramente sinalizadas.
- [ ] Manter testes de backend existentes e criar E2E de navegador para as duas fases da UX.

**Uso do protótipo:** abrir `Gambit_Lab_UI_Cosmica.html` no navegador; escolher opções; digitar uma pergunta; pressionar Enter ou enviar; alternar jogo, modos 2D/perspectiva, avançar/voltar movimentos e retornar à pergunta. É uma maquete funcional da **interface**, sem API, verificação científica, upload real ou regras completas.
