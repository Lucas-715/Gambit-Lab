# Gambit Lab 2.0 — Framework Multiagente Orientado por Jogos

> **Princípio Central**: *O LLM propõe, as regras do jogo restringem, as evidências sustentam e o sistema registra.*

O **Gambit Lab 2.0** é um framework de raciocínio multiagente guiado por jogos (*Game-Driven Multi-Agent System*), e não simplesmente um jogo com inteligência artificial. A plataforma estrutura investigações em sequências procedurais rigorosas de:
$$\text{Pergunta} \longrightarrow \text{Hipótese} \longrightarrow \text{Busca} \longrightarrow \text{Citação} \longrightarrow \text{Contestação} \longrightarrow \text{Arbitragem} \longrightarrow \text{Registro Imutável}$$

---

## 1. A Matriz 3×2 de Aplicações

Modalidade e Jogo são duas dimensões completamente ortogonais e independentes (**ADR-001**):

| Modalidade \ Jogo | Xadrez (8×8) | Go / Weiqi (9×9) |
| :--- | :--- | :--- |
| **Pesquisa** | Gambitos e diferentes linhas de investigação orientam busca central, contraponto e risco de hipótese. | Cobertura temática, expansão por influência e aprofundamento territorial de fontes primárias. |
| **Debate** | Confronto de evidências com capturas condicionadas; brancas iniciam; árbitro factual avalia refutações. | Disputa territorial com contestação de teses; pretas iniciam; captura é espacial e avaliação factual é separada. |
| **Auditoria** | Peças representam controles, testes e riscos; confrontos capturam falhas de justificativa técnica. | Regiões representam requisitos, achados e lacunas de conformidade. |

---

## 2. Pesquisa FUSION (Investigação Multiestratégica)

A **Pesquisa FUSION** permite investigar uma pergunta complexa a partir de 1 a 3 estratégias investigativas simultâneas:
- **No Xadrez**: Gambito da Dama (equilíbrio), Gambito do Rei (exploração de hipóteses), Gambito Evans (descobertas rápidas).
- **No Go**: Lente de Influência (cobertura ampla), Lente de Território (fontes primárias), Lente de Invasão (contestação adversarial), Lente de Conexão (interseção de domínios).

### Pipeline Determinístico de Fusão:
1. **Isolamento de Ramos**: Cada estratégia atua em seu próprio tabuleiro com seu próprio motor determinístico independente.
2. **Normalização de Claims**: Alegações atômicas são extraídas com offsets, quotes e hashes de documentos.
3. **Deduplicação de Fontes**: Múltiplos agentes citando o mesmo documento/URL contam como **1 única fonte independente** (evitando contagem de votos espúria).
4. **Reconciliação e Matriz de Divergências**: Identifica achados `CONVERGENT`, `CONTRADICTORY`, `DIFFERENT_SCOPE` e `INSUFFICIENT`.
5. **Síntese Unificada**: Emissão de relatório único auditável com níveis de evidência e limitações explícitas.

---

## 3. Estrutura do Repositório

```text
Gambit_Lab/
├── apps/
│   └── web/                   # Interface 3D (WebGL) + 2D Acessível, painéis e controles
├── services/
│   ├── api/                   # Backend FastAPI, modelos Pydantic, rotas REST
│   │   ├── agents/            # Adaptador Gemini (BYOK) e Modo Demo Offline rotulado
│   │   ├── engines/           # Orquestração de motores de jogo
│   │   ├── fusion/            # Pipeline determinístico de fusão
│   │   ├── models/            # Schemas tipados de dados
│   │   ├── routes/            # Endpoints de Sessão, Ações, Artefatos, Replay, Relatórios
│   │   └── storage/           # Event Store com hash SHA-256 e Cofres Privados
│   └── worker/                # Jobs em segundo plano
├── packages/
│   ├── contracts/             # Interfaces TypeScript e Schemas JSON
│   └── game_rules/            # Motores determinísticos (python-chess e Go 9x9)
├── docs/                      # Especificação Integral, ADRs e Catálogo de Requisitos
├── tests/
│   ├── unit/                  # Testes dos motores Xadrez, Go, EventStore e FUSION
│   └── integration/           # Testes dos endpoints FastAPI e das 6 combinações
├── docker-compose.yml         # Orquestração de containers para deploy local
├── .env.example               # Configurações de ambiente e variáveis
└── README.md
```

---

## 4. Como Executar Localmente

### Pré-requisitos
- Python 3.12+
- Node.js (opcional para desenvolvimento web separado)

### Passo 1: Ativação do Ambiente Virtual
```bash
# No Windows (PowerShell):
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# No Linux / macOS:
python3 -m venv .venv
source .venv/bin/activate
```

### Passo 2: Instalação das Dependências
```bash
pip install -r requirements.txt
```

### Passo 3: Configurar Variáveis de Ambiente
Copie o arquivo de exemplo:
```bash
cp .env.example .env
```
> **Nota de Segurança**: Para executar no **Modo Demo Offline** (com fixtures sintéticas rotuladas), nenhuma chave de API é necessária. Para conectar o Google Gemini real, adicione sua chave `GEMINI_API_KEY` no `.env`. A chave nunca é exposta no frontend.

### Passo 4: Iniciar o Servidor
```bash
python -m uvicorn services.api.main:app --host 0.0.0.0 --port 8000 --reload
```

Acesse a aplicação no navegador em:
- **Interface Visual Completa (3D / 2D)**: `http://localhost:8000/`
- **Documentação Interativa Swagger / OpenAPI**: `http://localhost:8000/docs`
- **Health Check**: `http://localhost:8000/health`

---

## 5. Executando a Bateria de Testes Automatizados

Para executar os 40 testes unitários e de integração (cobrindo as 6 combinações obrigatórias AC-01 a AC-06, lances especiais FIDE AC-21, FUSION AC-07, integridade de hash SHA-256 encadeado, isolamento de cofres privados e fluxo cósmico):

```bash
# Definindo PYTHONPATH para a raiz do repositório:
$env:PYTHONPATH="."  # PowerShell
pytest tests/ -v
```

---

## 6. Gambit Lab Cosmic — Experiência em Duas Fases ("Pergunta Primeiro, Investigação Depois")

A interface de usuário adota o paradigma cósmico:
1. **Fase 1 (Home Screen / Compositor Central)**:
   - Fundo espacial imersivo com estrelas em Canvas de baixo consumo de CPU e planetas flutuantes.
   - Caixa de texto central inspirada em assistentes conversacionais modernos, com seletores compactos de Modo (Pesquisa, Debate, Auditoria), Jogo (Xadrez, Go) e Política de Fontes (`own_only` ou `web_opt_in` sinalizado como em desenvolvimento).
   - Sugestões de cenários pré-configurados (Segurança em IA Autônoma NIST, Debate Demográfico 2030, Auditoria ISO 27001 / OWASP) e upload de arquivos diretamente para o cofre.
   - Nenhum veredito factual ou selo de auditoria falso é exibido antes da sessão real existir no backend.

2. **Fase 2 (Workspace de Investigação)**:
   - Transição suave acionada assim que o backend confirma `POST /api/v1/sessions` com status `2xx`.
   - Cabeçalho com a pergunta real em destaque, botão `✎ Refinar pergunta` (retorno reversível à caixa de busca) e `＋ Nova investigação`.
   - **Arena do Tabuleiro**: Renderizador WebGL 3D nativo com shaders personalizados e peças esculpidas inspiradas nas silhuetas de alta fidelidade (Rei com Cruz Luminosa em cyan, Dama com coroa de pétalas, Cavalo modelado, Torre com ameias e peões em degraus; realces de lance em âmbar para origem e cyan para destino) ou alternância para **2D Acessível (WCAG AA)**.
   - **Auditoria em Três Camadas (Problema 1 Solucionado)**:
     - Camada 1: `integrity_status` (`INTEGRITY_VERIFIED` com hash SHA-256 encadeado).
     - Camada 2: `source_status` (`SOURCE_VERIFIED` com verificação de citação exata nos bytes do documento ou `NO_SOURCES_ATTACHED`).
     - Camada 3: `evidence_assessment` (`SUPPORTED`, `REFUTED`, `INSUFFICIENT` ou `HYPOTHESIS`). Sem documentos anexados, o sistema jamais emite `SUPPORTED`.
   - **Rubrica do Árbitro Epistêmico**: Avaliação em 7 pontos (Identidade, Comparabilidade, Proveniência, Citação, etc.) para debates e auditorias.
   - **Replay Determinístico do Event Store**: Navegação lance a lance pelo histórico de eventos criptograficamente encadeados sem refazer chamadas ao LLM.
   - **Pesquisa FUSION**: Síntese unificada, deduplicação de fontes por hash e matriz de divergências entre múltiplos ramos investigativos independentes.

---

## 7. Integridade Tripartida e Regras Fundamentais

1. **Placar do Jogo** (`game_result`): Decidido pelo motor determinístico (`python-chess` ou `GoEngine9x9`). O LLM não pode sobrepor rejeições.
2. **Cofres Privados**: No debate, cada lado vê somente seus próprios documentos até o início da partida (`LOCKED`), comprovados por manifesto de hashes SHA-256. Acesso cruzado pré-início é bloqueado com `HTTP 403`.
3. **Replay Determinístico**: Reconstitui o histórico de lances e vereditos aplicando os eventos canônicos diretamente sobre os motores formais, **sem chamar o LLM**.
4. **Política de Fontes**: `own_only` garante zero chamadas de busca externa. `web_opt_in` é sinalizado como planejado / em desenvolvimento.
5. **Segurança de Chaves (BYOK)**: `GEMINI_API_KEY` reside exclusivamente no `.env` do backend, nunca exposta ao JavaScript do navegador nem versionada no repositório.

---

## 8. Licença
Projeto acadêmico e de engenharia de software distribuído sob a licença MIT.

