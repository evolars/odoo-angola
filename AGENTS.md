# Tech Stack Standards

## Organization & Ownership (Mandatory Global Rule)
- **Empresa / GitHub Organization:** **`evolars`** (`https://github.com/evolars`).
- **Railway Workspace:** **`Evolars`**.
- Todos os repositórios, projetos, clientes e serviços devem ser criados e mantidos sob a **Evolars**.
- **Única Exceção:** Projeto pessoal **Orbit** (`orbitech1`). Nunca utilizar a conta pessoal `anliben` para clientes.

## Frontend
- **Framework:** Angular (v19+, Standalone Components, Signals, Zoneless)
- **Styling:** Tailwind CSS
- **Icons:** Phosphor Icons (https://phosphoricons.com)
- **Tooling:** Bun / pnpm + Angular CLI (`ng`)

## Backend
- **Language:** Go (Golang)
- **Architecture:** Idiomatic Go, clean architecture, standard library / Chi
- **Database & Storage:** PostgreSQL / SQLite

## Authentication
- **Framework:** Better Auth (https://www.better-auth.com)
- **Strategy:** Better Auth (Node/Bun auth service / edge) + Better Auth Client no Angular; Go valida sessões/tokens via banco compartilhado ou JWT/middleware.

## Engineering Standards
- Minimalist, high-performance, clean and idiomatic code.
- Zero comment spam, zero redundant UI text.
- 100% automated test coverage for critical paths.

## Institutional Sites Mandatory Baseline (SEO, Compliance & Discovery)
Todos os sites institucionais devem obrigatoriamente conter desde a concepção inicial:
- **SEO & Metadados Completos para Redes Sociais (WhatsApp, Facebook, Twitter, LinkedIn):**
  - **Open Graph Image dedicada em 1200x630px:** Banner de alta resolução (`og-image.jpg` ou `og-image.png`) com peso < 300KB (limite estrito do WhatsApp). Nunca usar logotipos pequenos como og:image principal (são ignorados pelas redes).
  - Tags completas de imagem: `og:image`, `og:image:secure_url`, `og:image:type`, `og:image:width="1200"`, `og:image:height="630"`, `og:image:alt`, e `<link rel="image_src">`.
  - A URL da imagem DEVE ser absoluta no domínio ativo (resolvível por crawlers externos) e/ou relativa.
  - Metatags de texto: `og:title`, `og:description`, `og:url`, `og:site_name`, `og:type="website"`, `og:locale`.
  - Twitter Cards em `summary_large_image`: `twitter:card`, `twitter:title`, `twitter:description`, `twitter:image`, `twitter:url`.
  - Canonical URL, robots (`index, follow, max-image-preview:large, max-snippet:-1, max-video-preview:-1`), theme-color e autor.
- **Dados Estruturados (Schema.org JSON-LD):**
  - Entidade `Organization` / `LocalBusiness` com razão social, NIF / identificador fiscal, sede/endereço, logomarca (`logo`), imagem (`image`) e redes sociais oficiais (`sameAs`).
- **Arquivos de Descoberta:**
  - `sitemap.xml` válido na raiz pública.
  - `robots.txt` apontando para o sitemap.
- **Web App Manifest:**
  - Manifesto (`site.webmanifest`) configurado com nome, ícones, tema escuro/claro e display standalone.
