# Resultados e rastreabilidade

A página inicial e o formulário de pergunta foram preservados. As alterações abrangem a execução da investigação, os resultados no workspace e os relatórios.

## Encerramento

- Os sete estágios geram uma conclusão mesmo quando o orçamento de lances termina antes do jogo. O tabuleiro pode permanecer sem vencedor; a investigação entrega seu balanço documental.
- Falha do provedor, limite de uso ou resposta inválida na síntese acionam um resumo determinístico dos registros disponíveis.
- Falhas operacionais na pesquisa preservam um resultado parcial exportável, identificam a etapa pendente e permitem uma nova tentativa. Não são tratadas como execução completa.
- Resultado inconclusivo é acompanhado de lacunas e próximos passos. O sistema não fabrica um vencedor factual para satisfazer o encerramento.
- A busca do jogador de xadrez tem orçamento determinístico de posições por candidato. Todos os lances candidatos continuam legais; a busca limitada pode reduzir a força tática, sem alterar a verificação factual.

## Evidências e auditoria

Encontrar uma citação não comprova a tese. Somente alegações com estado `SUPPORTED` e referências verificadas entram na pontuação de sustentação; fontes e alegações repetidas são deduplicadas por lado. As proporções não são probabilidades calibradas.

O fluxo atual de preparação normalmente produz `SOURCE_VERIFIED`, e não uma avaliação semântica conclusiva. Assim, pode haver fontes verificadas e resultado factual inconclusivo. Uma avaliação normativa completa ainda depende de critérios explícitos e validação de pertinência e suficiência.

Na auditoria, o lance não escolhe mais uma norma fixa nem transforma captura em não conformidade. Os achados apontam a alegação examinada, o trecho disponível, o critério pendente e a recomendação. Gravidade não avaliada aparece como tal.

## Conferência e exportação

O resultado mostra alegação, estado, fonte, trecho, hash e lances associados. Os botões de lance abrem a inspeção existente. O relatório Markdown, HTML ou JSON inclui conclusão, limitações, próximos passos e eventos para conferência. A cadeia é verificada novamente na exportação.

A conclusão completa integra um evento encadeado. A gravação copia os dados para impedir que a retomada altere silenciosamente um resultado já registrado. Hashes detectam alterações no conteúdo; não certificam a veracidade da análise nem substituem armazenamento confiável.

## Limites da revisão

Os testes automatizados usam demonstração e provedores simulados. Não validam qualidade factual do Gemini real ou cobertura de pesquisa pública. O Event Store atual guarda eventos em memória; exporte os resultados antes de reiniciar o servidor. Persistência durável e autenticação de usuários continuam sendo trabalhos separados.
