# JetPay24 — Product Specification Document (PSD)

**Brand:** JetPay24 (`جت‌پی‌۲۴`)
**Document type:** Architecture & Product Specification
**Status:** Draft — active project under development
**Audience:** Engineering, product, operations, and stakeholders

---

## 1. Executive Summary

JetPay24 is an international payment services platform for students and individuals. It enables users to request and complete cross-border payments — university application fees, tuition, TOEFL/GRE registration, embassy/visa fees, and general international transfers — through a secure, Persian-first web experience with planned English support.

The platform evolves from the current single-service Django website into a multi-surface product:

- A **public marketing and content website** (`jetpay24.com`).
- A **customer self-service panel** (`panel.jetpay24.com`) with KYC, wallet, orders, and support.
- A future **operations/admin panel** (`admin.jetpay24.com`).
- A shared **REST API backend** (Django + Django REST Framework) consumed by web and future mobile apps.

This document defines the target architecture, data model, workflows, and a phased roadmap to reach that vision. It is a planning artifact; it intentionally contains no implementation code.

### Goals

- Provide a trustworthy, transparent, compliant international payment workflow.
- Centralize identity (KYC), funds (wallet), and fulfillment (orders) in one account.
- Offer self-service support augmented by an AI assistant with human escalation.
- Support bilingual (Persian/English) audiences.
- Establish an API-first foundation for web and mobile clients.

### Non-Goals (current phase)

- JetPay24 is not a licensed bank or exchange; it brokers/facilitates payments.
- No automated on-chain crypto custody in the initial phases (crypto pages are informational/pricing first).
- No production-grade trading engine; exchange/tether/crypto pages are rate display and conversion tools.

---

## 2. System Architecture

### 2.1 High-Level Topology

```text
                         ┌─────────────────────────────┐
                         │          End Users          │
                         │  Web (FA/EN) · Future Mobile │
                         └───────────────┬─────────────┘
                                         │ HTTPS
              ┌──────────────────────────┼───────────────────────────┐
              │                          │                           │
   jetpay24.com (Public)     panel.jetpay24.com (Customer)   admin.jetpay24.com (Ops)
   Next.js SSR/ISR           Next.js (authenticated SPA)     Next.js / Django Admin
              │                          │                           │
              └──────────────────────────┼───────────────────────────┘
                                         │ REST (JSON) + Auth tokens
                                ┌────────▼─────────┐
                                │   API Gateway    │  (DRF, versioned /api/v1)
                                └────────┬─────────┘
                                         │
              ┌──────────────┬───────────┼───────────┬───────────────┐
              │              │           │           │               │
        Auth/Identity     Orders      Wallet/Ledger  KYC          Content/Blog
              │              │           │           │               │
                                ┌────────▼─────────┐
                                │   PostgreSQL     │ (target; SQLite today)
                                └────────┬─────────┘
                                         │
        ┌────────────┬─────────────┬─────┴───────┬──────────────┬─────────────┐
   Object Storage  Redis Cache  Async Workers   Email/SMS    Rate Providers  AI Provider
   (documents)    + sessions    (Celery/RQ)     gateways     (FX/USDT/crypto) (assistant)
```

### 2.2 Logical Layers

| Layer | Responsibility | Technology (target) |
|---|---|---|
| Presentation | Public site, customer panel, admin panel | Next.js, Bootstrap/Tailwind, RTL support |
| API | Versioned REST endpoints, auth, validation, serialization | Django REST Framework |
| Domain services | Orders, wallet/ledger, KYC, support, content, rates | Django apps (modular) |
| Persistence | Relational data, transactions, audit | PostgreSQL (SQLite for dev today) |
| Async/Jobs | Notifications, rate sync, video/KYC processing, webhooks | Celery + Redis broker |
| Storage | KYC documents, attachments, media | Private object storage (S3-compatible) |
| Integrations | Email, SMS/OTP, FX/crypto rate feeds, AI assistant | External providers |

### 2.3 Domain Modules (Django apps)

- `accounts` — users, authentication, sessions, profile.
- `kyc` — verification records, documents, review workflow.
- `orders` — service categories, orders, status workflow (exists today, to be extended).
- `wallet` — balances, transactions, ledger, adjustments.
- `payments` — payment intents/receipts tied to orders and wallet.
- `support` — tickets, live chat, AI escalation.
- `content` — blog, articles, FAQ, static pages.
- `rates` — exchange rates, USDT (tether), crypto prices, converter.
- `notifications` — multi-channel notifications and preferences.
- `pages` — public marketing pages (exists today).
- `api` — DRF routing, versioning, shared serializers/permissions.

### 2.4 Architectural Principles

- **API-first:** every customer capability is exposed via versioned REST for web + mobile reuse.
- **Separation of surfaces:** public, customer, and admin are distinct deployables sharing one API.
- **Ledger integrity:** wallet uses append-only double-entry transactions; balances are derived/reconciled.
- **Security by default:** least privilege, encrypted secrets, private storage for KYC, audit logging.
- **Idempotency:** financial and webhook endpoints are idempotent (idempotency keys).
- **Observability:** structured logging, metrics, and audit trails on sensitive actions.

---

## 3. User Roles

| Role | Surface | Description | Key permissions |
|---|---|---|---|
| Guest | Public | Unauthenticated visitor | Browse content, rates, FAQ, contact, AI assistant (limited) |
| Customer | Panel | Registered, email-verified user | Manage profile, KYC, orders, wallet, tickets, settings |
| Verified Customer | Panel | KYC-approved customer | Place higher-value orders, withdraw, full feature access |
| Support Agent | Admin | Handles tickets and live chat | View user context, respond, escalate, internal notes |
| KYC Reviewer | Admin | Reviews identity submissions | Approve/reject KYC, request re-submission |
| Finance/Operations | Admin | Processes orders & wallet | Update order status, manual wallet adjustments, reconcile |
| Content Manager | Admin | Manages content | Blog, articles, FAQ, static pages, rates content |
| Administrator | Admin | Full platform control | All capabilities, role management, configuration |
| Super Admin | Admin | System owner | Role assignment, security config, audit access |

Role model: RBAC with role-permission mapping; users may hold multiple staff roles. Customer vs. staff are separated to keep public account flows isolated from operations.

---

## 4. Page Structure

### 4.1 Public Website (`jetpay24.com`)

| Page | Path | Purpose |
|---|---|---|
| Home | `/` | Brand intro, services overview, CTAs |
| Services index | `/services` | All service categories |
| Service detail | `/services/{slug}` | Per-service explanation + CTA to order |
| Blog index | `/blog` | Latest posts, categories |
| Blog post | `/blog/{slug}` | Article content, SEO |
| Educational articles | `/learn` and `/learn/{slug}` | Guides for students/families |
| FAQ | `/faq` | Categorized questions |
| Contact | `/contact` | Contact form + channels |
| Exchange rates | `/rates` | Fiat exchange rates |
| Tether (USDT) rates | `/rates/tether` | USDT buy/sell rates |
| Crypto prices | `/rates/crypto` | Cryptocurrency price list |
| Currency converter | `/converter` | Interactive conversion tool |
| About / Legal | `/about`, `/terms`, `/privacy` | Company & legal pages |
| Auth entry | `/login`, `/register` | Redirect into panel flows |

Global elements: AI assistant widget (all pages), language switcher (FA/EN), header nav, footer.

### 4.2 Customer Panel (`panel.jetpay24.com`)

| Page | Path | Purpose |
|---|---|---|
| Dashboard | `/dashboard` | Summary: wallet, orders, KYC status, alerts |
| Profile | `/profile` | Personal info management |
| KYC | `/kyc` | Submit/track verification steps |
| Bank cards | `/cards` | Manage verified bank cards |
| Orders | `/orders`, `/orders/{id}` | List and detail with status timeline |
| New order | `/orders/new` | Service selection + submission |
| Wallet | `/wallet` | Balance, deposit, withdraw |
| Transactions | `/wallet/transactions` | Ledger history |
| Notifications | `/notifications` | In-app notifications |
| Support tickets | `/support`, `/support/{id}` | Ticket list and thread |
| Live chat | `/support/chat` | Real-time chat |
| Settings | `/settings` | Security, language, preferences |

### 4.3 Admin Panel (`admin.jetpay24.com`)

| Section | Purpose |
|---|---|
| Users | Search, view, suspend, manage roles |
| Orders | Queue, status transitions, assignment |
| Wallet | Adjustments, reconciliation, audits |
| KYC review | Approval workflow, document inspection |
| Support | Ticket queue, live chat, escalations |
| Content | Blog, articles, FAQ, pages |
| Rates | Manage FX/USDT/crypto sources and overrides |
| Notifications | Broadcasts, templates, channels |
| Settings | Roles, configuration, audit log |

---

## 5. Navigation Structure

### 5.1 Public Header

```text
Logo | خدمات (Services) | نرخ‌ها (Rates ▾: Exchange · Tether · Crypto · Converter) |
وبلاگ (Blog) | آموزش (Learn) | سوالات متداول (FAQ) | تماس (Contact) |
[FA/EN] | ورود/ثبت‌نام (Login/Register)
```

### 5.2 Public Footer

```text
About · Terms · Privacy · Contact
Services quick links
Rates quick links
Social links · Support email
```

### 5.3 Customer Panel Sidebar

```text
Dashboard · Orders · Wallet · KYC · Bank Cards ·
Notifications · Support (Tickets / Live Chat) · Profile · Settings · Logout
```

### 5.4 Admin Panel Sidebar

```text
Overview · Users · Orders · Wallet · KYC Review ·
Support · Content (Blog/Articles/FAQ/Pages) · Rates · Notifications · Settings
```

---

## 6. Database Model Design

Target engine: PostgreSQL. Notation below is conceptual (entities and key fields), not DDL.

### 6.1 Identity & Profile

**User**
- id, email (unique), phone (unique, nullable), password_hash
- is_email_verified, is_phone_verified, is_active, is_staff
- role(s) via UserRole, created_at, last_login_at

**Profile**
- user_id (1:1), first_name, last_name, national_id (nullable), birth_date
- preferred_language (fa/en), avatar, address fields

**Role / Permission / UserRole**
- Role: id, name, description
- Permission: id, codename, description
- UserRole: user_id, role_id (M:N)

### 6.2 KYC

**KYCProfile**
- user_id (1:1), status (NOT_STARTED, PENDING, APPROVED, REJECTED, RESUBMIT)
- level/tier, reviewed_by, reviewed_at, rejection_reason

**KYCDocument**
- id, kyc_id, type (NATIONAL_ID, SELFIE, VIDEO, DECLARATION, BANK_CARD)
- file_ref (private storage), status, uploaded_at, notes

**BankCard**
- id, user_id, card_number_masked, iban (nullable), holder_name
- status (PENDING, VERIFIED, REJECTED), verified_at

### 6.3 Orders

**ServiceCategory**
- id, slug, name_fa, name_en, description, is_active, sort_order

**Order**
- id, tracking_code (unique), user_id (nullable for legacy guest), service_category_id
- amount, currency, description, status (workflow §10)
- assigned_to (staff, nullable), created_at, updated_at

**OrderDocument**
- id, order_id, file_ref, type, uploaded_at

**OrderStatusHistory**
- id, order_id, from_status, to_status, changed_by, note, created_at

### 6.4 Wallet & Ledger

**Wallet**
- id, user_id (1:1), currency, balance_cached, status

**WalletTransaction (append-only)**
- id, wallet_id, type (DEPOSIT, WITHDRAWAL, ORDER_DEBIT, ORDER_REFUND, ADJUSTMENT)
- direction (CREDIT/DEBIT), amount, balance_after, reference (order/payment id)
- created_by (system/admin), idempotency_key, created_at

**WithdrawalRequest**
- id, wallet_id, amount, destination_card_id, status, reviewed_by, created_at

**Payment**
- id, order_id (nullable), wallet_txn_id (nullable), provider, external_ref
- amount, status, idempotency_key, created_at

### 6.5 Support

**Ticket**
- id, user_id, subject, category, status (OPEN, PENDING, ANSWERED, CLOSED), priority
- assigned_to, created_at, updated_at

**TicketMessage**
- id, ticket_id, sender (user/agent/ai), body, attachments, created_at, is_internal

**ChatSession / ChatMessage**
- session: id, user_id, agent_id, status, started_at, ended_at
- message: id, session_id, sender, body, created_at

### 6.6 Content

**BlogPost / Article**
- id, slug, title, excerpt, body, cover_ref, status (DRAFT/PUBLISHED)
- author_id, published_at, locale, seo_title, seo_description

**Category / Tag** — taxonomy, M:N with posts/articles.

**FAQItem**
- id, category, question, answer, locale, sort_order, is_active

**StaticPage**
- id, slug, title, body, locale, updated_at

### 6.7 Rates

**RateSource** — id, name, type (FX/USDT/CRYPTO), endpoint, is_active.

**Rate**
- id, source_id, symbol/pair, buy, sell, mid, fetched_at, manual_override (bool)

### 6.8 Notifications

**Notification**
- id, user_id, type, title, body, channel (IN_APP/EMAIL/SMS/PUSH)
- is_read, created_at, metadata

**NotificationPreference**
- user_id, channel, category, enabled

### 6.9 Cross-Cutting

**AuditLog** — id, actor_id, action, target_type, target_id, metadata, ip, created_at.
**OTPCode** — id, user_id/phone, code_hash, purpose, expires_at, consumed_at.

### 6.10 Key Relationships

- User 1:1 Profile, Wallet, KYCProfile.
- User 1:N Orders, Tickets, BankCards, Notifications.
- Order 1:N OrderDocument, OrderStatusHistory.
- Wallet 1:N WalletTransaction.
- BlogPost N:M Category/Tag.

---

## 7. API Design

Style: REST, JSON, versioned under `/api/v1/`. Auth via bearer tokens (JWT access + refresh). All list endpoints paginated; financial endpoints require idempotency keys.

### 7.1 Conventions

| Aspect | Standard |
|---|---|
| Base path | `/api/v1/` |
| Auth | `Authorization: Bearer <access_token>` |
| Errors | `{ "error": { "code", "message", "details" } }` |
| Pagination | `?page=&page_size=` with `count/next/previous` |
| Localization | `Accept-Language: fa|en` |
| Idempotency | `Idempotency-Key` header on POST for money ops |

### 7.2 Endpoint Groups (representative)

**Auth**
- `POST /auth/register`
- `POST /auth/login` (email/password)
- `POST /auth/otp/request`, `POST /auth/otp/verify`
- `POST /auth/email/verify`, `POST /auth/email/resend`
- `POST /auth/password/reset/request`, `POST /auth/password/reset/confirm`
- `POST /auth/token/refresh`, `POST /auth/logout`

**Profile & Account**
- `GET/PATCH /me`
- `GET/PATCH /me/settings`
- `GET /me/notifications`, `POST /me/notifications/{id}/read`

**KYC**
- `GET /kyc` (status)
- `POST /kyc/documents` (upload)
- `POST /kyc/submit`
- `GET /kyc/bank-cards`, `POST /kyc/bank-cards`

**Orders**
- `GET /services`
- `GET /orders`, `POST /orders`
- `GET /orders/{id}`
- `GET /orders/{id}/history`
- `GET /tracking/{code}` (public, limited fields)

**Wallet**
- `GET /wallet`
- `GET /wallet/transactions`
- `POST /wallet/deposit`
- `POST /wallet/withdraw`

**Support**
- `GET /tickets`, `POST /tickets`
- `GET /tickets/{id}`, `POST /tickets/{id}/messages`
- `POST /chat/sessions`, `GET /chat/sessions/{id}`
- `POST /assistant/message`, `POST /assistant/escalate`

**Content & Rates (public)**
- `GET /blog`, `GET /blog/{slug}`
- `GET /articles`, `GET /articles/{slug}`
- `GET /faq`
- `GET /rates/exchange`, `GET /rates/tether`, `GET /rates/crypto`
- `GET /converter?from=&to=&amount=`

**Admin (staff-scoped, role-gated)**
- `GET/PATCH /admin/users`
- `PATCH /admin/orders/{id}/status`
- `POST /admin/wallet/{id}/adjust`
- `PATCH /admin/kyc/{id}/review`
- `CRUD /admin/content/*`, `CRUD /admin/rates/*`
- `POST /admin/notifications/broadcast`

---

## 8. Authentication Flow

### 8.1 Methods

- Email + password (primary).
- Mobile OTP (passwordless / secondary factor).
- Email verification required before full account activation.
- Password reset via email link or SMS OTP.

### 8.2 Registration → Activation

```text
Register (email, password) ──► Create user (inactive/unverified)
        │
        └─► Send email verification link/code
                │
                ▼
        User verifies email ──► Account activated ──► Login enabled
```

### 8.3 Login (Email/Password)

```text
Submit credentials ─► Validate ─► Email verified?
   │ no  ─► Block + prompt to verify
   │ yes ─► Issue access + refresh tokens ─► Session established
```

### 8.4 Login (Mobile OTP)

```text
Enter phone ─► Send OTP (rate-limited, hashed, TTL) ─►
Enter OTP ─► Verify + consume ─► Issue tokens
```

### 8.5 Password Reset

```text
Request (email or phone) ─► Send reset token (email link) or SMS OTP ─►
Confirm new password ─► Invalidate old sessions
```

### 8.6 Security Controls

- Password hashing (Django PBKDF2/Argon2), token expiry + rotation.
- OTP: short TTL, attempt limits, hashed storage, per-phone/IP rate limits.
- Brute-force protection and lockout/backoff.
- Audit logging of auth events; device/session listing in settings.

---

## 9. KYC Workflow

### 9.1 Steps

1. National ID document upload.
2. Bank card verification.
3. Signed declaration upload.
4. Selfie verification.
5. Video verification.
6. Admin review and approval.

### 9.2 State Machine

```text
NOT_STARTED ─► PENDING (user submitted)
PENDING ─► APPROVED        (reviewer approves)
PENDING ─► REJECTED        (hard fail)
PENDING ─► RESUBMIT        (fixable issues) ─► PENDING (re-upload)
```

### 9.3 Flow

```text
Customer uploads documents (private storage)
        │
        ▼
KYC marked PENDING ─► appears in admin KYC queue
        │
        ▼
Reviewer inspects each document
        │
  ┌─────┼───────────────┐
  ▼     ▼               ▼
APPROVE RESUBMIT      REJECT
  │     │ (reason)      │ (reason)
  ▼     ▼               ▼
Unlock  Notify user   Notify user
features re-upload     blocked
```

### 9.4 Controls & Compliance

- Documents stored in private, access-controlled storage; never public URLs.
- Access to KYC documents restricted to KYC Reviewer/Admin and audit-logged.
- PII minimization; retention policy; encryption at rest.
- Tiered limits: order/withdrawal ceilings depend on KYC level.

---

## 10. Order Workflow

### 10.1 Status Model

```text
Submitted ─► Under Review ─► Waiting For Payment ─► Processing ─► Completed
     │             │                  │                  │
     └─────────────┴──────────────────┴──────────────────┴─► Rejected
```

| Status | Meaning | Typical actor |
|---|---|---|
| Submitted | Order created by customer | Customer |
| Under Review | Operations validating details/docs | Operations |
| Waiting For Payment | Awaiting funds (wallet/transfer) | Customer |
| Processing | Payment received, executing service | Operations |
| Completed | Service fulfilled, receipt issued | Operations |
| Rejected | Declined at any review/payment stage | Operations |

### 10.2 Flow

```text
Customer selects service ─► submits order (+docs) ─► tracking_code generated
        │
        ▼
Operations review ──► request changes / proceed
        │
        ▼
Waiting For Payment ──► wallet debit or external payment confirmation
        │
        ▼
Processing ──► fulfillment ──► Completed (receipt + notification)
        │
        └─► Rejected (reason + optional refund to wallet)
```

### 10.3 Rules

- Every transition recorded in `OrderStatusHistory` with actor and note.
- Payment may be wallet-funded (debit) or external; refunds credited to wallet.
- Status changes trigger notifications (§13).
- Public tracking exposes only status, service type, and dates (no PII/documents).

---

## 11. Wallet Workflow

### 11.1 Capabilities

- View balance and transaction history.
- Deposit funds.
- Request withdrawals to verified bank cards.
- Admin manual adjustments (credits/debits) with reason + audit.

### 11.2 Ledger Model

- Append-only `WalletTransaction` entries; each records `balance_after`.
- Balance is derived from the ledger; `balance_cached` is a reconciled convenience field.
- All money mutations are idempotent and transactional.

### 11.3 Deposit

```text
Customer initiates deposit ─► payment provider/manual confirmation ─►
CREDIT transaction recorded ─► balance updated ─► notification
```

### 11.4 Withdrawal

```text
Customer requests withdrawal (verified card, sufficient balance, KYC ok)
        │
        ▼
WithdrawalRequest = PENDING ─► admin review
        │
   ┌────┴─────┐
   ▼          ▼
 APPROVE     REJECT
   │          │
 DEBIT txn   no change
 + payout    + notify reason
```

### 11.5 Order Settlement

```text
Order "Waiting For Payment" + wallet funded ─► ORDER_DEBIT ─► order Processing
Order Rejected after debit ─► ORDER_REFUND (CREDIT) ─► customer notified
```

### 11.6 Controls

- Withdrawals require KYC approval and a verified bank card.
- Manual adjustments restricted to Finance/Admin, always with reason + audit log.
- Negative balances prevented by pre-transaction checks within DB transactions.

---

## 12. Support Workflow

### 12.1 Channels

- **AI assistant widget** — first-line, available publicly and in-panel.
- **Tickets** — asynchronous, threaded, attachments.
- **Live chat** — real-time with support agents.

### 12.2 AI Assistant → Human Escalation

```text
User asks AI assistant
        │
   Can AI resolve? ── yes ─► Provide answer (FAQ/articles/account context*)
        │ no / user requests human
        ▼
Create ticket OR open live chat session (carry conversation context)
        │
        ▼
Agent handles ─► resolve ─► close ─► satisfaction prompt
```
*Account-specific answers require authentication; the assistant never exposes another user’s data.

### 12.3 Ticket Lifecycle

```text
OPEN ─► PENDING (awaiting user) ─► ANSWERED ─► CLOSED
            ▲                          │
            └──────── reopen ──────────┘
```

### 12.4 Controls

- Internal notes flagged and hidden from customers.
- PII redaction in AI prompts/logs; rate limiting and abuse protection.
- Clear disclaimer: assistant provides guidance, not legal/financial guarantees.

---

## 13. Notification System

### 13.1 Channels

- In-app (panel) — always on.
- Email — transactional + selected updates.
- SMS — OTP and critical alerts.
- Push — future mobile apps.

### 13.2 Event Triggers (examples)

| Event | Channels |
|---|---|
| Email verification, OTP | Email/SMS |
| KYC status change | In-app, Email |
| Order status change | In-app, Email, (SMS for key states) |
| Wallet deposit/withdrawal/adjustment | In-app, Email |
| Ticket reply / chat | In-app, Email |
| Marketing/announcements | In-app, Email (opt-in) |

### 13.3 Design

- Template-based, locale-aware (FA/EN) messages.
- User-managed `NotificationPreference` per channel/category (except mandatory security messages).
- Async delivery via workers; delivery status tracked; retries with backoff.

---

## 14. Multilingual Strategy

- **Languages:** Persian (default, RTL) and English (LTR).
- **Content model:** locale field on content entities (blog, articles, FAQ, static pages); UI strings via i18n catalogs.
- **API:** `Accept-Language` negotiation; localized fields returned per request.
- **Routing (web):** locale-aware routes (e.g., `/` FA default, `/en/...` English) with SEO `hreflang`.
- **Direction:** automatic RTL/LTR switching; brand shown as `جت‌پی‌۲۴` (FA) and `JetPay24` (EN).
- **Fallback:** missing translations fall back to default locale with clear indicators in admin.
- **Formatting:** locale-aware dates, numbers, and currency display.

---

## 15. Future Mobile App Strategy

- **Approach:** API-first backend already powers web; mobile reuses `/api/v1`.
- **Platforms:** Android first, then iOS (native or cross-platform such as Flutter/React Native — TBD).
- **Auth:** same JWT model; secure token storage on device; biometric unlock option.
- **Feature parity:** dashboard, orders, wallet, KYC (camera capture for selfie/video/documents), notifications (push), support chat.
- **Push:** FCM/APNs integration via `notifications` module + device registry.
- **Offline/UX:** cache read-only content (rates, articles); graceful degradation.
- **Security:** certificate pinning, jailbreak/root detection, per-device session revocation.
- **Release:** versioned API with backward compatibility; feature flags for staged rollout.

---

## 16. Development Roadmap

### Phase 0 — Foundation Hardening (current → next)
- Production settings, environment-based secrets, `requirements.txt`.
- Migrate dev DB to PostgreSQL; storage for media/documents.
- Baseline tests, CI, logging. (Order tracking already implemented.)

### Phase 1 — Accounts & Authentication
- User accounts, email verification, password reset.
- Mobile OTP login; session/device management; audit logging.

### Phase 2 — Customer Panel Core
- Dashboard, profile, settings, notifications (in-app).
- Orders migrated into authenticated panel with status history UI.

### Phase 3 — KYC
- Document uploads (private storage), bank card verification.
- Selfie/video capture, declaration, admin review workflow + tiers.

### Phase 4 — Wallet & Payments
- Wallet, ledger, deposits, withdrawals, order settlement & refunds.
- Admin manual adjustments with audit; reconciliation tooling.

### Phase 5 — Support
- Tickets, live chat, AI assistant with human escalation.

### Phase 6 — Content & Rates
- Blog, educational articles, FAQ, static pages (bilingual).
- Exchange/tether/crypto rate pages + currency converter with rate sync.

### Phase 7 — Admin Panel
- Dedicated `admin.jetpay24.com`: users, orders, wallet, KYC, content, rates, notifications, roles.

### Phase 8 — Internationalization
- Full FA/EN coverage across UI and content; SEO `hreflang`, localized formatting.

### Phase 9 — Mobile Apps
- Android then iOS on the shared API; push notifications; device security.

### Cross-Cutting (continuous)
- Security reviews, rate limiting, observability, performance, compliance, backups/DR.

---

*This document is a living specification and will evolve as JetPay24 develops. It defines target architecture and intent; it is not an implementation artifact and contains no code.*
