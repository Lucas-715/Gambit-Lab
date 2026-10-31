# Instrução de implementação — Gambit Lab Nocturne v2.3

Use o arquivo `GAMBIT_LAB_V23_AUDITORIA_REENGENHARIA.md` como especificação de correção da release `Gambit_Lab_v2.2_Nocturne_Research_Match.zip`.

## Objetivo de produto
Transformar o workspace em **Xadrez/Go primeiro, lance e evidência depois**. Não reconstruir o sistema do zero; preservar WebGL 3D, motores determinísticos, Event Store, replay, Gemini e fontes existentes.

## Ordem OBRIGATÓRIA
1. Crie uma branch com commit de preservação antes de editar; não use reset --hard e não divulgue `.env`.
2. Reproduza os achados C01–C12 do relatório com testes que falhem antes das correções.
3. Corrija primeiro a fundamentação factual: trecho localizado não significa suporte; captura física não equivale a refutação; dedupe evidências e remova multiplicação da verdade por peça.
4. Corrija a regra do Xadrez padrão. O motor FIDE deve determinar lances válidos, xeque-mate e empate. A resignação automática por 800cp não deve estar habilitada por padrão. Nunca invente vitória ao esgotar o orçamento. Se mantiver variantes, identifique-as claramente e teste-as isoladamente.
5. Introduza payload de **lance auditável** com SAN, UCI, origem, destino, agente, peça, tese, contra-tese, artefatos, trecho, avaliação semântica e snapshot; o painel lateral consome esse payload ao selecionar lances no replay.
6. Adicione rótulos externos `a–h`, `1–8` ao Xadrez 3D/2D; `A B C D E F G H J`, `1–9` ao Go 3D/2D. Preserve orientação e coordenadas no giro do tabuleiro.
7. Redesenhe workspace: tabuleiro grande + um único painel “**Lance selecionado**”, controles de replay; resultado resumido após a partida, dossiês/estatísticas/telemetria sob demanda; não exibir 32 cards simultaneamente.
8. Remova os badges permanentes de Gemini/Web da navbar e coloque informações detalhadas em menu “Diagnóstico”. Toast **somente quando o estado mudar**, sem esconder erro persistente. Faça sidebar retrátil no desktop e drawer no mobile com teclado/aria.
9. Execute todos os testes do repositório e os cenários UX01…SCI01 do relatório; evidencie inspeção real no navegador em 3D/2D, Xadrez/Go e mobile; valide API Gemini separadamente e com custo controlado.
10. Só depois faça commit. Relate arquivos alterados, testes aprovados/falhos/ignorados, capturas, exemplos de PGN/SGF e riscos remanescentes. Não publique no GitHub sem minha autorização.

## Critério final
Não declarar concluído se ainda houver `SUPPORTED` baseado somente em localização de trecho, peça `REFUTED` por captura física, resultado forçado por resignação silenciosa, ou coordenadas ausentes no tabuleiro. Evite poluição visual e destaque o **movimento + razões + rastreabilidade**.
