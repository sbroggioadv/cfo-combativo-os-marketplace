# cfo-combativo-os

> Um **CFO senior terceirizado** dentro do Claude Code, para **qualquer pessoa
> fisica e juridica**. Le seus dados financeiros brutos, processa **localmente**,
> cruza com parametros oficiais do mercado e devolve **diagnostico + municao
> decisoria + dashboards visuais** — substituindo consultoria financeira pontual
> e software de gestao caro.

---

## O que faz

- Responde as perguntas de gestor: **"quanto posso gastar este mes?"**, **"meu
  caixa aguenta junho?"**, **"essa taxa de emprestimo esta cara?"**, **"crio uma
  meta de guardar X ate dezembro?"**.
- **Ingere** extratos bancarios/cartao (OFX/QFX/CSV/XLSX), NF-e/NFS-e (XML) e
  tabela de produtos/precos — normalizando tudo para um **schema canonico de
  transacao** que permite cruzar extrato x nota x lancamento.
- **Concilia** automaticamente (casa transacao x nota x lancamento) e separa o
  que esta solto do que esta fechado.
- **Analisa:** fluxo de caixa com alerta de ruptura, KPIs de CFO (liquidez,
  endividamento, prazos/ciclo, rentabilidade, operacional), contas a pagar e a
  receber (aging), benchmark de precos, custo de credito vs **Banco Central**,
  indicadores de mercado (Selic/CDI/IPCA), provisoes (o que deveria estar
  reservado), orcamento x realizado e deteccao de anomalias.
- **Visualiza:** gera **dashboard HTML single-file** standalone (sem servidor),
  pronto para impressao/PDF.
- **Triagem contabil:** monta o pacote mensal para a contabilidade e — com
  **gate de confirmacao humana** — envia.

---

## ⭐ Multi-entidade desde o setup

A decisao que diferencia o cfo-combativo de um app financeiro comum: voce pode
ser **PF, PJ ou ambos**, com **multiplas entidades simultaneas** — a sua PF + a
PF do conjuge + 3 empresas, por exemplo — e cada entidade pode ter **N contas**
(voce pode ter 20 contas). O sistema modela isso como um **grafo de entidades e
grupos**:

```
GRUPO (opcional)        ENTIDADE                  CONTA
─────────────────       ──────────────            ──────────────
grupo-empresas    ──┬──  empresa-alfa (PJ)   ──┬─ itau-cc-001
                    └──  empresa-beta  (PJ)   └─ bb-cc-002
grupo-familia     ──┬──  joao         (PF)   ──┬─ nubank-001
                    └──  maria        (PF)   └─ c6-cc-002
```

Todo dashboard e analise suporta **tres recortes de leitura**:

1. **Por entidade** — visao individual (empresa-alfa isolada; joao isolado).
2. **Por grupo** — soma das entidades, **eliminando transferencias intragrupo**
   (nao conta a mesma movimentacao duas vezes).
3. **Total consolidado** — voce inteiro, com a **fronteira PF↔PJ sempre
   explicita** (relevante para holding e planejamento patrimonial).

O grafo e **append-only**: voce adiciona entidade, conta ou grupo a qualquer
tempo **sem perder o consolidado ja construido** — o sistema so agrega.
Reprocessar um mes substitui **so aquele mes**, nunca destroi o historico.

---

## As 4 travas — features de confianca

Toda entrega passa por uma auditoria interna (R1-R4) que so libera a saida apos
verificar estas quatro garantias:

1. **Municao, nunca veredito.** No modulo de credito, o plugin compara sua taxa
   com a media oficial do Banco Central e **sinaliza** a discrepancia,
   recomendando negociacao e, quando o caso, assessoria especializada. **Jamais
   afirma que uma taxa e "ilegal" ou "abusiva"** nem indica acao judicial —
   superar a media de mercado, por si so, nao caracteriza abusividade (STJ REsp
   1.061.530/RS). Quem qualifica juridicamente e o advogado.
2. **Gate de confirmacao humana no envio.** Nenhum e-mail a contabilidade ou a
   terceiro e disparado automaticamente. O plugin monta o pacote e **aguarda
   sua confirmacao explicita**. Sem confirmacao, ele instrui o envio manual.
3. **Dado sensivel tratado como sensivel.** Extratos, OFX e NF-e sao dados
   financeiros sob LGPD (e parte e sigilo bancario, LC 105/2001). **Tudo e
   processado localmente na sua maquina** — nada sai sem acao deliberada sua. Os
   logs nunca registram numero de conta, CPF/CNPJ completo ou saldo em texto
   plano.
4. **Nunca fabricar dado.** Taxas, indices e series sao **buscados ao vivo** na
   fonte oficial (API do Banco Central). Se a fonte estiver indisponivel, o
   plugin **declara a indisponibilidade** — nunca estima um numero como se fosse
   fato.

---

## As skills (24 analiticas + orquestrador)

| Camada | Conteudo |
|--------|----------|
| **Orquestracao/Auditoria** | `cfo-master` (orquestrador) · `auditoria-cfo` (R1-R4) · `cfo-onboarding` (setup do grafo) |
| **Ingestao** (4) | extrato bancario · notas fiscais · tabela de produtos · conciliacao bancaria |
| **Analise** (8) | fluxo de caixa · contas a pagar · contas a receber · KPIs de CFO · benchmark de precos · credito vs Banco Central · indicadores de mercado · consolidacao multi-entidade |
| **Triagem/Envio** (2) | triagem contabil · envio a contabilidade (com gate) |
| **Visualizacao** (1) | dashboard HTML standalone |
| **Complementares** (6) | carga tributaria (informativa) · provisoes (PF+PJ) · orcamento x realizado · deteccao de anomalias · capacidade de credito · relatorio executivo narrado |

---

## Como instalar

O plugin e distribuido via marketplace GitHub publico. Para instalar no Cowork:

1. Abra **Settings → Plugins → aba Pessoal**.
2. Clique em **"+" Uploads locais**.
3. Cole a URL do repositorio do marketplace (informada no checkout).
4. Rode `/cfo-setup` para montar o seu grafo de entidades (PF, PJ ou ambos).

---

## Como usar

```
/cfo-setup
```
Monta o grafo: PF/PJ/ambos, entidades, contas de cada uma, grupos opcionais e
contabilidade.

```
/cfo quanto posso gastar esse mes na empresa alfa?
```
Caixa livre real apos provisoes e contas a pagar — nao o saldo da conta.

```
/cfo-credito  (anexa o contrato de emprestimo)
```
Compara sua taxa com a media do Banco Central e devolve municao comparativa,
sempre com o disclaimer de nao-afirmacao de ilegalidade.

```
/cfo-dashboard --total
```
Dashboard visual single-file com o seletor de recorte multi-entidade.

```
/cfo-full
```
Fechamento de ponta a ponta (ingere → concilia → analisa → audita → dashboard →
monta o pacote contabil) — **parando antes do envio**.

---

## Privacidade

A pasta `<seu-projeto>/.cfo/` onde vivem o grafo, o estado e o historico e
**gitignored** por padrao. O plugin emite aviso se o workspace estiver em pasta
sincronizada (iCloud / OneDrive / Dropbox / Drive). **Nenhum dado financeiro
seu sai do seu ambiente.**

---

## Disclaimer

Este plugin e uma **ferramenta de organizacao e diagnostico financeiro**. Ele
**gera dados, nao pareceres**: nao substitui contador, consultor financeiro ou
advogado, e nao emite afirmacao juridica de ilegalidade de taxas, contratos ou
tributos. As taxas e indices sao buscados em fontes oficiais; valores devem ser
validados na fonte antes de qualquer decisao formal. O modulo de credito produz
apenas **municao comparativa** para negociacao — a qualificacao juridica de
qualquer contrato cabe a um profissional habilitado.

---

**Licenca:** MIT · **Familia:** IA Combativa
