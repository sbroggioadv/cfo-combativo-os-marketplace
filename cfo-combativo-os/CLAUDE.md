# CLAUDE.md — plugin-cfo-financeiro (interno do source)

> Regras internas do source `plugin-cfo-financeiro/`. Plugin alvo:
> `cfo-combativo-os`. Familia Adv-OS.
> **Estende** o ecossistema (`~/Dev/plugins-ia-combativa/CLAUDE.md` raiz da familia,
> `~/Dev/CLAUDE.md` workspace, `~/.claude/CLAUDE.md` universal) — NAO duplica.

---

## Identidade

- **Plugin name (slug):** `cfo-combativo-os`
- **Autoria (despersonalizada):** `IA Combativa` — PROIBIDO nome civil, numero de OAB, nome do escritorio-modelo, apelido do operador ou e-mail pessoal em qualquer arquivo do source (`audit/audit.py` bloqueia)
- **O que e:** um **CFO senior terceirizado** dentro do Claude Code, para **qualquer PF e PJ**. Le dados financeiros brutos, processa localmente, cruza com parametros oficiais de mercado, devolve diagnostico + municao decisoria + dashboards. Responde "quanto posso gastar este mes?", "meu caixa aguenta?", "essa taxa ta cara?", "crio uma meta de guardar X?".
- **O que NAO e:** SaaS, backend em nuvem, executor de transacoes, emissor de afirmacao juridica de ilegalidade.
- **Tom das skills/commands (para o operador):** CFO senior — direto, tecnico, decisorio, PT-BR. Sem prometer resultado. Sem afirmar ilegalidade.

---

## AS QUATRO TRAVAS INEGOCIAVEIS (gravadas na arquitetura)

Toda skill referencia. `auditoria-cfo` R3 bloqueia entrega que viole.

1. **Municao, nunca veredito.** Em taxas/indicadores/abusividade: aponta discrepancia e impacto, recomenda negociacao administrativa, remete a assessoria. **Jamais** afirma "taxa ilegal/abusiva" nem indica ajuizamento. Base: STJ Tema 27 / REsp 1.061.530/RS — superar a media **nao** e abusividade; gatilho pratico dos tribunais = **1,5x** da media. O plugin sinaliza; quem qualifica e o advogado. Verbos PROIBIDOS no modulo de credito: "ilegal", "abusiva", "cabe acao", "ajuize", "revisional".
2. **Gate de confirmacao humana no envio.** Nenhum e-mail a contabilidade/terceiro e disparado automaticamente. Monta o pacote, aguarda **confirmacao explicita**. `/cfo-full` monta mas **para antes do envio**. Espelha a regra DJEN do ecossistema: efeito externo nunca automatico.
3. **Dado sensivel tratado como sensivel.** Extrato/OFX/NF-e/dados pessoais = dados financeiros sob LGPD; parte e sigilo bancario (LC 105/2001). Tudo **local**; nada sai sem acao deliberada. Logs **nunca** registram conta/CPF/CNPJ completo/saldo em texto plano (mascarar).
4. **Nunca fabricar dado.** Taxas, indices, series, valores, fundamentos. Fonte oficial (API SGS BCB) indisponivel → **declara**, nao estima. Anti-halucinacao por design.

---

## ⭐ MODELO MULTI-ENTIDADE — o coracao da arquitetura (decisao fundadora)

O que diferencia o cfo-combativo de um app financeiro comum. O operador pode ser **PF, PJ ou ambos**, com **multiplas entidades simultaneas** (PF dele + PF do conjuge + N empresas), cada entidade com **N contas** (ate ~20). Modelado como **grafo de entidades e grupos**:

```
GRUPO (opcional)   →   ENTIDADE (pf|pj, doc mascarado, regime)   →   CONTA (banco+tipo)
```

- **Entidade:** unidade patrimonial — PF=CPF mascarado, PJ=CNPJ mascarado, tipo, nome/apelido, regime tributario (PJ), inicio no sistema.
- **Grupo:** agrupamento livre (grupo-empresas, grupo-familia); entidade pertence a 0 ou 1 grupo (v0.1.0); opcional.
- **Conta:** vinculo banco+conta dentro de uma entidade. Toda transacao → exatamente uma conta → exatamente uma entidade.

### Tres recortes de leitura (todo dashboard e analise suporta)
1. **Por entidade** — visao individual.
2. **Por grupo** — soma das entidades, **eliminando transferencias intragrupo** (nao contar 2x).
3. **Total consolidado** — operador inteiro, **fronteira PF↔PJ sempre explicita** (holding / planejamento patrimonial).

### Persistencia incremental — REGRA DURA (append-only)
- Setup define o grafo; **alteravel a qualquer tempo sem perder o consolidado** — so agrega.
- Append-only por competencia: cada mes ingerido vira registro historico no SQLite da entidade. Reprocessar um mes **substitui so aquele mes** (idempotencia por `(entidade, conta, competencia)`), nunca rebuild destrutivo.
- Adicionar entidade nova no mes 7 **nao invalida** os meses 1-6 das outras. O grafo evolui; o historico e monotonico. `state.py` faz backup antes de salvar.

### Onde o estado vive
- **`cfo-state.json`** (grafo + preferencias + tools) em `<cwd>/.cfo/` — NUNCA no plugin distribuido, NUNCA versionado (`.gitignore`).
- **`base.sqlite` por entidade** em `<cwd>/.cfo/entidades/{id}/base.sqlite` — historico consolidado.
- Maquina de estados: `scripts/state.py` (schema CFO, `STATE_DIR=".cfo"`); `scripts/resolve-state.py` (env `CFO_STATE`).

---

## Skill map (24 analiticas + 3 invariantes)

**Invariantes (sempre carregadas):** `cfo-master`, `auditoria-cfo`, `cfo-onboarding`.

### Camada E — Orquestracao/Auditoria
- `cfo-master` (orquestrador · `/cfo`)
- `auditoria-cfo` (R1-R4 — Integridade, Calculo, Calibragem, Completude)
- `cfo-onboarding` (monta/edita grafo multi-entidade · `/cfo-setup`)

### Camada A — Ingestao (4)
- `ingest-extrato-bancario` · `ingest-notas-fiscais` · `ingest-tabela-produtos` · `conciliacao-bancaria`

### Camada B — Analise (8)
- `fluxo-de-caixa` · `contas-a-pagar` · `contas-a-receber` · `indicadores-kpi` · `benchmark-precos` · `analise-credito-bancario`⚠️ · `indicadores-de-mercado` · `consolidacao-multi-entidade`

### Camada C — Triagem/Envio (2)
- `triagem-contabil` · `envio-contabilidade`🔒 (UNICA que toca conector externo, com gate)

### Camada D — Visualizacao (1)
- `dashboard-html`

### Camada F — Complementares (6)
- `carga-tributaria` (informativo, nao consultivo) · `provisoes` · `orcamento` · `deteccao-anomalias` · `capacidade-credito` · `relatorio-executivo`

---

## Commands (14)

`/cfo` (master) · `/cfo-setup` (onboarding grafo) · `/cfo-ingest` · `/cfo-conciliar` · `/cfo-caixa` · `/cfo-kpi` · `/cfo-precos` · `/cfo-credito`⚠️ · `/cfo-receber` · `/cfo-pagar` · `/cfo-contabil` · `/cfo-enviar`🔒 · `/cfo-dashboard` · `/cfo-consolidar` · `/cfo-full` (pipeline; PARA antes do envio).

> Cada command e **fino** — frontmatter `description` + corpo curto que aponta para `cfo-master` (que decide a skill). Aux/engines vivem em `scripts/lib/` e `config/`, nunca dentro de `skills/x/`.

---

## auditoria-cfo (R1-R4 — espelha a Suprema Corte dos plugins juridicos)

- **R1 — Integridade de dados:** arquivos lidos? buracos de periodo? conciliacao fechou? valor sem origem?
- **R2 — Correcao de calculo:** formulas de KPI conferidas; series BCB da modalidade certa e atualizadas; nenhuma taxa/indice fabricado.
- **R3 — Calibragem de conclusao:** nenhuma afirmacao de ilegalidade; municao rotulada; disclaimers presentes; gate de envio respeitado; LGPD/mascaramento ok.
- **R4 — Completude e apresentacao:** dashboard cobre os paineis pedidos; recortes (entidade/grupo/total) corretos; nada faltou para PF e PJ.
- Sem aprovacao das quatro → saida retida. Veredito visivel: `R1✓/R2✓/R3✓/R4✓ — APROVADO`.

---

## Config (dados oficiais — contrato anti-halucinacao)

- `config/series-bcb.json` — mapa de codigos SGS do Banco Central (modalidade → codigo). Endpoint publico sem chave: `https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados/ultimos/{N}?formato=json`.
- `config/indicadores.json` — formulas + faixas semaforicas de cada KPI.
- `config/compliance.json` — textos fixos de aviso LGPD/LC105, disclaimer do modulo de credito, texto do gate de envio.
- `config/categorias.json` — regras de auto-classificacao de transacao.
- `scripts/data/cache-bcb/` — cache de series (TTL); valores `null` se nunca buscado.

> **Regra:** o plugin **busca ao vivo** na API SGS no momento da analise (com cache TTL). NUNCA chumba a taxa no codigo/config. Indisponivel → declara (trava 4).

---

## hook-utils.py e RUNTIME-REQUIRED (premortem C1 — licao 2026-05-26)

Em v0.1.0 o `hooks/hooks.json` usa **echo puro** (sem dependencia Python) — escolha deliberada por **maxima robustez**: o hook NUNCA pode crashar o Cowork na instalacao.

REGRA DURA que vale mesmo assim (e para qualquer hook que venha a importar Python):
- **`scripts/hook-utils.py` e RUNTIME-REQUIRED** — se algum hook futuro o importar (via `importlib.spec_from_file_location` / `exec_module`), ele **NUNCA** pode ser removido no scrub do marketplace publico classificado como build-only. Foi o que crashou o `direito-medico` em 2026-05-26.
- Qualquer hook que importe Python deve **degradar a echo simples** se o import falhar — jamais propagar excecao pro Cowork.
- Pre-push: grep TRIPLO (path literal + `spec_from_file_location|exec_module` + nome do arquivo solto) confirma que nada runtime foi removido.

> Nota: o `hook-utils.py` atual ainda carrega `STATE_DIR="trabalhista"` (copiado do irmao) — adaptar para `.cfo` quando algum hook passar a importa-lo. Em v0.1.0 nao e importado, entao nao quebra.

---

## Degradacao graciosa dos parsers (premortem C2)

`ofxparse`/`nfelib`/`pandas` podem nao estar instalados na maquina do cliente. Todo parser **degrada**: tenta a lib → fallback stdlib (`xml.etree`, `csv`) → declara e instrui `pip install`. Import **dentro de funcao**, nunca no topo de modulo que o hook toque. NUNCA quebra a sessao do Cowork.

---

## Dashboard (camada de visualizacao)

`dashboard-html` gera **single-file HTML standalone** (sem servidor, sem localStorage, dados injetados na geracao). Identidade visual canonica: `--base:#101010; --surface:#1a1a1a; --lime:#CCFF00; --text:#f2f2f2; --green:#3ddc84; --amber:#ffc043; --red:#ff5252`. Chart.js via CDN (com nota de fallback offline). Engine em `scripts/lib/dashboard_generator.py`; referencia visual fiel em `templates/dashboard-reference.html`. Seletor de recorte multi-entidade obrigatorio.

---

## Cross-link com plugins-irmaos (SUGESTAO, NAO EXECUCAO)

Cada output do orquestrador termina com bloco fixo de sugestoes (texto):

```markdown
## 💡 Proximos passos opcionais

| Proximo passo | Comando | Plugin necessario |
|---|---|---|
| Notificacao extrajudicial de inadimplente | /execucao cobranca | execucao-adv-os |
| Calcular debito atualizado para cobranca | /calculos | calculosjudiciais-adv-os |
| Planejamento tributario formal / regime | /tributario | tributario-societario-adv-os |
| Auditoria suprema R1-R4 de peca juridica | /ia-combativa suprema-corte-r1-r4 | ia-combativa-adv-os |

> Se o plugin nao estiver instalado, copie o diagnostico acima e use manualmente.
```

NAO importar, NAO ler, NAO invocar plugin-irmao. So sinalizar. Tributario e extrajudicial fazem **handoff** ao ecossistema (compartimentacao de escopo): este plugin **informa/organiza**, planejamento tributario formal = `tributario-societario-adv-os`.

---

## Padroes de codigo

1. Skill folder = **so SKILL.md** (aux em `templates/`, `config/`, `scripts/lib/`, `scripts/data/`).
2. SKILL.md ≤ 11 KB. Description combined (description + when_to_use) ≤ 1024 chars.
3. plugin.json minimal (4 campos: name/version/description/author).
4. Saida estruturada (markdown com blocos/tabelas/yaml de contexto/memoria auditavel).
5. Disclaimer legal + aviso de fonte em cada output final; disclaimer fixo de credito em toda saida do modulo sensivel.
6. Stock-first: parsers e SQLite locais; API SGS BCB ao vivo so para taxas/indices oficiais.

---

## Anti-despersonalizacao

`audit/forbidden-terms.json` bloqueia: nome civil do criador, OAB pessoal, e-mail pessoal, nome do escritorio-modelo, casos reais. Rodar `python3 audit/audit.py` antes de cada commit. Autoria sempre `IA Combativa`.

---

## Pre-mortem (10 cenarios mitigados em design — ver `.planning/premortem.md`)

C1 crash do Cowork por hook → echo puro em v0.1.0 + hook-utils runtime-required.
C2 parser quebra por lib ausente → degradacao graciosa.
C3 numero fabricado no dashboard → cache BCB `null` + indisponibilidade declarada + R2 rejeita numero sem origem.
C4 vazamento LGPD → `.cfo/` no gitignore + mascaramento + aviso 1a vez + dados de teste sinteticos.
C5 envio automatico → gate humano, `envio-contabilidade` unica skill com conector.
C6 afirmacao de ilegalidade no credito → trava 1 + disclaimer fixo + verbos proibidos + R3 bloqueia.
C7 multi-entidade vira sopa → flag `is_transferencia_intragrupo` + fronteira PF↔PJ explicita.
C8 reprocessar mes destroi historico → append-only por competencia + backup.
C9 SKILL.md > 11 KB / arquivo extra na skill → aux fora de `skills/`, compactador mede, `validate` PASS.
C10 divergencia arquitetonica entre agentes → `.planning/` (schema §3 + state §6 + config §7) escrito ANTES do fan-out, leitura obrigatoria.

---

## Comunicacao

- **Idioma:** Portugues (Brasil)
- **Tom dos docs internos:** tecnico, direto, sem mencoes pessoais
- **Tom das skills/commands (para o operador):** CFO senior — direto, tecnico, decisorio; respeita preferencias do `cfo-state.json` em runtime
- **Reportes:** ✅ concluido / 🔴 erro / 🏁 sprint finalizada

---

**Ultima atualizacao:** 2026-05-29 — scaffold de commands + hooks + context + docs-raiz (FASE 4 do PLAYBOOK).
