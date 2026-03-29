-- ============================================================
-- M-Okoa Agent — Production MariaDB Schema
-- Domain: Kenyan micro-entrepreneur financial co-pilot
-- Standard: Clean Code, DDD-aligned, OWASP-safe
-- ============================================================

SET FOREIGN_KEY_CHECKS = 0;
SET sql_mode = 'STRICT_TRANS_TABLES,NO_ZERO_DATE,NO_ZERO_IN_DATE,ERROR_FOR_DIVISION_BY_ZERO';

-- ------------------------------------------------------------
-- USERS
-- Represents a registered M-Okoa client (business owner)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id                  BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    public_id           CHAR(26) NOT NULL UNIQUE COMMENT 'ULID for public exposure',
    full_name           VARCHAR(120) NOT NULL,
    phone_number        VARCHAR(15) NOT NULL UNIQUE COMMENT 'E.164 format: +2547XXXXXXXX',
    email               VARCHAR(254) UNIQUE,
    password_hash       VARCHAR(255) NOT NULL,
    telegram_chat_id    BIGINT UNIQUE COMMENT 'Bound Telegram session',
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    is_verified         BOOLEAN NOT NULL DEFAULT FALSE,
    subscription_tier   ENUM('msingi', 'biashara', 'enterprise') NOT NULL DEFAULT 'msingi',
    created_at          DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    updated_at          DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
    INDEX idx_phone     (phone_number),
    INDEX idx_telegram  (telegram_chat_id)
    mpesa_identity_token VARCHAR(255) UNIQUE COMMENT 'Daraja 3.0 Security API token — no raw MSISDN stored',
INDEX idx_identity_token (mpesa_identity_token)
domain_mode ENUM('merchant','farmer','student','community','general')
            NOT NULL DEFAULT 'general'
            COMMENT 'Money in Motion challenge area persona',
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ------------------------------------------------------------
-- TILLS
-- An M-Pesa Till or Paybill number owned by a user
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tills (
    id                  BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    public_id           CHAR(26) NOT NULL UNIQUE,
    user_id             BIGINT UNSIGNED NOT NULL,
    display_name        VARCHAR(80) NOT NULL COMMENT 'e.g. Mama Mboga Till',
    till_number         VARCHAR(20) NOT NULL COMMENT 'M-Pesa Till or Paybill number',
    till_type           ENUM('till', 'paybill', 'personal') NOT NULL,
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    -- Daraja credentials (encrypted at application layer before insert)
    daraja_consumer_key     TEXT COMMENT 'AES-256 encrypted',
    daraja_consumer_secret  TEXT COMMENT 'AES-256 encrypted',
    daraja_shortcode        VARCHAR(20),
    daraja_passkey          TEXT COMMENT 'AES-256 encrypted',
    -- Smart Float config
    float_threshold_kes     DECIMAL(12,2) DEFAULT NULL COMMENT 'Auto-transfer triggers above this',
    float_target_account    VARCHAR(50) DEFAULT NULL COMMENT 'Bank acc or phone for auto-transfer',
    -- Cached balance (updated on each Daraja balance query)
    last_known_balance_kes  DECIMAL(12,2) DEFAULT NULL,
    balance_updated_at      DATETIME(3) DEFAULT NULL,
    created_at              DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    updated_at              DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
    CONSTRAINT fk_tills_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT,
    UNIQUE KEY uq_till_per_user (user_id, till_number),
    INDEX idx_till_number (till_number)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ------------------------------------------------------------
-- TRANSACTIONS
-- Every money movement tracked here — inbound, outbound, internal
-- Source of truth for the ledger
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS transactions (
    id                      BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    public_id               CHAR(26) NOT NULL UNIQUE,
    user_id                 BIGINT UNSIGNED NOT NULL,
    till_id                 BIGINT UNSIGNED NOT NULL,
    -- M-Pesa reference (nullable until Daraja confirms)
    mpesa_receipt_number    VARCHAR(30) UNIQUE COMMENT 'M-Pesa transaction receipt e.g. RBA67XXXXX',
    mpesa_transaction_id    VARCHAR(50) UNIQUE COMMENT 'Daraja internal transaction ID',
    transaction_type        ENUM(
                                'c2b_receive',      -- Customer pays till
                                'b2c_send',         -- Business pays customer
                                'stk_push',         -- Initiated STK push
                                'bill_payment',     -- KPLC, Water, etc.
                                'float_transfer',   -- Smart-float auto-move
                                'tax_lock',         -- Auto-locked for KRA
                                'sms_import'        -- Parsed from forwarded SMS
                            ) NOT NULL,
    direction               ENUM('credit', 'debit') NOT NULL,
    amount_kes              DECIMAL(12,2) NOT NULL,
    fee_kes                 DECIMAL(8,2) NOT NULL DEFAULT 0.00,
    net_amount_kes          DECIMAL(12,2) GENERATED ALWAYS AS (amount_kes - fee_kes) STORED,
    counterparty_name       VARCHAR(120) COMMENT 'Payer or recipient name',
    counterparty_phone      VARCHAR(15) COMMENT 'E.164 format',
    description             VARCHAR(255),
    -- Status lifecycle
    status                  ENUM('pending', 'completed', 'failed', 'reversed') NOT NULL DEFAULT 'pending',
    failure_reason          VARCHAR(255),
    -- Tax association
    tax_lock_id             BIGINT UNSIGNED DEFAULT NULL COMMENT 'Link to tax_locks if applicable',
    -- Source metadata
    source                  ENUM('daraja_callback', 'sms_parser', 'agent_action', 'manual') NOT NULL,
    raw_payload             JSON COMMENT 'Original Daraja payload stored for audit',
    -- Idempotency
    idempotency_key         VARCHAR(100) UNIQUE COMMENT 'Prevents double-processing of callbacks',
    transaction_date        DATETIME(3) NOT NULL COMMENT 'Actual M-Pesa transaction time',
    created_at              DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    CONSTRAINT fk_txn_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT,
    CONSTRAINT fk_txn_till FOREIGN KEY (till_id) REFERENCES tills(id) ON DELETE RESTRICT,
    INDEX idx_txn_user_date     (user_id, transaction_date DESC),
    INDEX idx_txn_till          (till_id),
    INDEX idx_txn_receipt       (mpesa_receipt_number),
    INDEX idx_txn_status        (status),
    INDEX idx_idempotency       (idempotency_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ------------------------------------------------------------
-- TAX LOCKS
-- Virtual sub-wallet — funds set aside for KRA compliance
-- DST = 1.5% on digital services, VAT = 16%
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tax_locks (
    id                  BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    public_id           CHAR(26) NOT NULL UNIQUE,
    user_id             BIGINT UNSIGNED NOT NULL,
    till_id             BIGINT UNSIGNED NOT NULL,
    tax_type            ENUM('dst', 'vat', 'income_tax', 'presumptive') NOT NULL,
    taxable_amount_kes  DECIMAL(12,2) NOT NULL,
    tax_rate            DECIMAL(5,4) NOT NULL COMMENT 'e.g. 0.0150 for 1.5% DST',
    locked_amount_kes   DECIMAL(12,2) NOT NULL,
    period_month        CHAR(7) NOT NULL COMMENT 'YYYY-MM, e.g. 2025-03',
    status              ENUM('locked', 'filed', 'released') NOT NULL DEFAULT 'locked',
    filed_at            DATETIME(3) DEFAULT NULL,
    created_at          DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    CONSTRAINT fk_taxlock_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT,
    CONSTRAINT fk_taxlock_till FOREIGN KEY (till_id) REFERENCES tills(id) ON DELETE RESTRICT,
    INDEX idx_taxlock_user_period (user_id, period_month)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ------------------------------------------------------------
-- SMS INBOX
-- Forwarded M-Pesa SMS messages awaiting parsing
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sms_inbox (
    id                  BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    public_id           CHAR(26) NOT NULL UNIQUE,
    user_id             BIGINT UNSIGNED NOT NULL,
    raw_sms_text        TEXT NOT NULL,
    sender_number       VARCHAR(20) COMMENT 'Phone that forwarded the SMS',
    -- Parsing outcome
    parse_status        ENUM('pending', 'parsed', 'ambiguous', 'failed') NOT NULL DEFAULT 'pending',
    parsed_transaction_id BIGINT UNSIGNED DEFAULT NULL,
    parse_error         VARCHAR(255),
    received_at         DATETIME(3) NOT NULL,
    parsed_at           DATETIME(3) DEFAULT NULL,
    created_at          DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    CONSTRAINT fk_sms_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT,
    INDEX idx_sms_user_status (user_id, parse_status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ------------------------------------------------------------
-- AGENT SESSIONS
-- LangGraph agent execution traces — resumable checkpoints
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS agent_sessions (
    id                  BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    public_id           CHAR(26) NOT NULL UNIQUE,
    user_id             BIGINT UNSIGNED NOT NULL,
    session_source      ENUM('telegram', 'web', 'api') NOT NULL,
    -- LangGraph state (serialized JSON)
    graph_state         JSON NOT NULL,
    current_node        VARCHAR(60) NOT NULL,
    status              ENUM('active', 'awaiting_callback', 'completed', 'failed') NOT NULL DEFAULT 'active',
    -- Correlation for async Daraja callbacks
    stk_correlation_id  VARCHAR(100) UNIQUE COMMENT 'CheckoutRequestID from STK push',
    user_input          TEXT,
    final_response      TEXT,
    error_detail        TEXT,
    started_at          DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    completed_at        DATETIME(3) DEFAULT NULL,
    CONSTRAINT fk_session_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT,
    INDEX idx_session_user      (user_id),
    INDEX idx_stk_correlation   (stk_correlation_id),
    INDEX idx_session_status    (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ------------------------------------------------------------
-- SMART FLOAT RULES
-- User-defined automation: "if balance > X, move Y to Z"
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS smart_float_rules (
    id                  BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    public_id           CHAR(26) NOT NULL UNIQUE,
    user_id             BIGINT UNSIGNED NOT NULL,
    till_id             BIGINT UNSIGNED NOT NULL,
    rule_name           VARCHAR(80) NOT NULL,
    trigger_threshold_kes DECIMAL(12,2) NOT NULL COMMENT 'Execute rule when balance exceeds this',
    transfer_amount_kes   DECIMAL(12,2) COMMENT 'NULL = transfer excess above threshold',
    destination_type    ENUM('bank_account', 'mpesa_phone', 'chama_paybill') NOT NULL,
    destination_ref     VARCHAR(50) NOT NULL COMMENT 'Bank acc, phone, or paybill number',
    destination_name    VARCHAR(80) COMMENT 'Display name for destination',
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    last_triggered_at   DATETIME(3) DEFAULT NULL,
    trigger_count       INT UNSIGNED NOT NULL DEFAULT 0,
    created_at          DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    CONSTRAINT fk_rule_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_rule_till FOREIGN KEY (till_id) REFERENCES tills(id) ON DELETE CASCADE,
    INDEX idx_rule_till (till_id, is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ------------------------------------------------------------
-- AUDIT LOG
-- Immutable record of every sensitive action — OWASP A09
-- Never updated, never deleted
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS audit_log (
    id              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id         BIGINT UNSIGNED DEFAULT NULL,
    actor_type      ENUM('user', 'agent', 'system', 'daraja_callback') NOT NULL,
    action          VARCHAR(100) NOT NULL COMMENT 'e.g. stk_push_initiated, balance_queried',
    entity_type     VARCHAR(50) COMMENT 'e.g. till, transaction, user',
    entity_id       BIGINT UNSIGNED,
    ip_address      VARCHAR(45) COMMENT 'IPv4 or IPv6',
    user_agent      VARCHAR(255),
    payload_summary JSON COMMENT 'Sanitized — no secrets, no card data',
    created_at      DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    INDEX idx_audit_user    (user_id),
    INDEX idx_audit_action  (action),
    INDEX idx_audit_date    (created_at DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ------------------------------------------------------------
-- BILL PAYEES
-- Pre-configured payee list per user (KPLC, Nairobi Water, etc.)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bill_payees (
    id              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    public_id       CHAR(26) NOT NULL UNIQUE,
    user_id         BIGINT UNSIGNED NOT NULL,
    payee_name      VARCHAR(80) NOT NULL COMMENT 'e.g. KPLC Prepaid',
    paybill_number  VARCHAR(20) NOT NULL,
    account_number  VARCHAR(50) NOT NULL COMMENT 'Meter number, account ref, etc.',
    category        ENUM('utility', 'rent', 'loan', 'supplier', 'other') NOT NULL DEFAULT 'other',
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    CONSTRAINT fk_payee_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE KEY uq_payee_per_user (user_id, paybill_number, account_number)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

SET FOREIGN_KEY_CHECKS = 1;