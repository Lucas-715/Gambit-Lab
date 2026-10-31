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

Para executar os 27 testes unitários e de integração (cobrindo as 6 combinações obrigatórias AC-01 a AC-06, FUSION AC-07, integridade de hash SHA-256 e replay AC-18):

```bash
# Definindo PYTHONPATH para a raiz do repositório:
$env:PYTHONPATH="."  # PowerShell
pytest tests/ -v
```

---

## 6. Integridade Tripartida e Regras Fundamentais

1. **Placar do Jogo** (`game_result`): Decidido pelo motor determinístico (`python-chess` ou `GoEngine9x9`). O LLM não pode sobrepor rejeições.
2. **Cofres Privados**: No debate, cada lado vê somente seus próprios documentos até o início da partida (`LOCKED`), comprovados por manifesto de hashes SHA-256. O árbitro só recebe acesso aos trechos submetidos a julgamento.
3. **Replay Determinístico**: Reconstitui o histórico de lances e vereditos aplicando os eventos canônicos diretamente sobre os motores formais, **sem chamar o LLM**.
4. **Política de Fontes**: `own_only` garante zero chamadas de busca externa. `web_opt_in` exige consentimento explícito.

---

## 7. Licença
Projeto acadêmico e de engenharia de software distribuído sob a licença MIT.
