# 📬 Evolars E-mail & Resend Hub (`evolars_email`)

> **Módulo Odoo Genérico e Reutilizável para Integração Completa com Resend** (Inbound Webhook, Outbound Transacional, Caixas Postais, Aliases e Portal do Cliente).

---

## 🌟 Recursos Principais

1. **Envio Transacional via Resend API:**
   - Disparo rápido com suporte a HTML rico, múltiplos anexos e rastreamento de IDs externos (`resend_email_id`).
   - Wizard integrado para composição e resposta rápida de mensagens.

2. **Ingestão Inbound com Validação Direta de Domínio (ADR-015):**
   - Webhook em `/api/webhooks/resend` e `/evolars_email/webhook`.
   - Comparação direta de domínio com o `resend.domain` configurado no sistema.
   - Idempotência rigorosa garantida por chave única em `resend_email_id`.

3. **Provisionamento Automático de E-mails para Contatos:**
   - Ao cadastrar novos contatos (professores, pais, alunos), gera automaticamente o e-mail institucional no formato `nome.sobrenome@dominio` e cria a caixa postal correspondente.

4. **Gerenciamento Administrativo Completo:**
   - Gestão de Caixas Compartilhadas (equipes/departamentos).
   - Aliases de redirecionamento (ex: `atendimento@dominio` ➔ `secretaria@dominio`).
   - Lixeira, Favoritos, e Auditoria de Payloads.

5. **Portal do Aluno e da Família (`/my/emails`):**
   - Acesso seguro e isolado para leitura, resposta e envio de e-mails diretamente da conta do portal.

---

## ⚙️ Configuração

Adicione as variáveis de ambiente ou configure no menu **E-mails & Resend ➔ Configurações Resend**:
- `RESEND_API_KEY`: Chave de API do Resend.
- `EMAIL_DOMAIN`: Domínio do sistema (ex: `c-edl.com` ou `evolars.com.br`).
- `EMAIL_FROM`: Remetente padrão para disparos.

---

## 📄 Licença
LGPL-3 · Desenvolvido por [Evolars Ltda](https://evolars.com.br).
