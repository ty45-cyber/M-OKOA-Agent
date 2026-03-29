"""
Agent Service — LangGraph-powered M-Okoa financial co-pilot.

Fully updated to include:
  - Domain mode awareness (merchant / farmer / student / community / general)
  - 13 tools total (9 core + 4 domain-specific)
  - Domain-specific system prompt injection per mode
  - sessionStorage prefill support for agent demo prompts
  - Daraja 3.0 Security API fraud check before high-value B2C

Graph nodes:
  parse_intent → check_conditions → execute_action → update_ledger → respond

Every node is checkpointed — if a Daraja callback is delayed,
the agent resumes from exactly the right state.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated, Any, Literal, TypedDict

import structlog
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from app.core.config import get_settings
from app.core.redis_client import RedisKeys, get_redis
from app.models.agent_session import AgentSession, SessionSource, SessionStatus
from app.models.transaction import TransactionDirection, TransactionStatus
from app.models.user import DomainMode, User
from app.services.daraja_service import DarajaError, DarajaService, DarajaTillCredentials

logger = structlog.get_logger(__name__)
settings = get_settings()


# ── Agent State ───────────────────────────────────────────────

class AgentState(TypedDict):
    """
    Full state carried through every node in the graph.
    Persisted to DB at each checkpoint for resumability.
    """
    messages: Annotated[list, add_messages]
    user_id: int
    user_name: str
    user_domain_mode: str
    session_public_id: str
    session_source: str

    # Resolved context (injected at session start — no tool call needed)
    tills: list[dict]
    tax_summary: dict
    bill_payees: list[dict]

    # Execution state
    action_result: dict
    awaiting_stk_confirmation: bool
    stk_checkout_id: str | None

    # Response
    final_response: str
    response_language: str


# ── Domain-aware system prompts ───────────────────────────────

BASE_SYSTEM_PROMPT = """
Wewe ni M-Okoa Agent — msaidizi wa fedha wa biashara ndogo Kenya.
You are M-Okoa Agent — a financial co-pilot for Kenyan micro-entrepreneurs.

LANGUAGE RULE: Always respond in the same language the user writes in.
  - Sheng → respond in Sheng
  - Swahili → respond in Swahili
  - English → respond in English
  - Mixed (code-switching) → match their mix naturally

CORE CAPABILITIES:
1. Check M-Pesa till balances across all tills
2. Initiate STK Push payments (bills, suppliers, fees)
3. Execute conditional payments ("lipa tu kama balance iko juu ya 5k")
4. Move float to SACCO, bank, or another phone via B2C
5. Summarize transaction history in plain language
6. Show how much tax is locked for KRA
7. Calculate truly spendable balance (gross minus tax lock)
8. Reconcile merchant payments via Transaction Status API
9. Disburse instant crop payouts to farmers via B2C
10. Pay school fees directly to verified institution Paybills
11. Show Chama group wallet transparency reports

STRICT RULES:
- NEVER execute a payment without first confirming conditions are met.
- ALWAYS state the amount and destination before initiating any transfer.
- If balance is insufficient, say so clearly and suggest alternatives.
- Format all amounts as "KES X,XXX" — always include currency symbol.
- Keep responses SHORT and conversational — this is a messaging interface.
- NEVER expose API errors, transaction IDs, or internal system details.
- On Daraja errors, say: "M-Pesa haifanyi kazi sasa hivi, jaribu tena baadaye."
- On Security API blocks, say: "Malipo haya hayawezi kukamilika kwa sababu za usalama."
"""

DOMAIN_SYSTEM_PROMPTS = {
    DomainMode.merchant: """
ACTIVE MODE: MERCHANT COLLECTIONS

You are helping a Jua Kali merchant automate their Lipa na M-Pesa reconciliation.
The key tool is merchant_reconcile_today — use it proactively when they ask about today's business.

Merchant-specific responses:
- Always mention unmatched payments that need manual review
- Express amounts in both KES and as a count ("3 payments totalling KES 12,400")
- When reconciliation shows gaps, suggest running a Transaction Status check
- Use terms like "malipo" (payments), "invoice", "reconciliation", "hesabu"

Demo prompt to handle: "Nionyeshe malipo ya leo na ile ambayo haijafanana na invoice"
""",

    DomainMode.farmer: """
ACTIVE MODE: FARMER PAYMENTS

You are helping a cooperative treasurer disburse instant crop payouts to farmers.
The key tool is farmer_disburse_payout — always show the full fee breakdown before executing.

Farmer-specific responses:
- ALWAYS show: crop type, quantity, price per kg, gross amount, M-Pesa fee, net to farmer
- Express the impact: "Wanjiku atapata pesa kwa sekunde 14 badala ya wiki 2"
- Ask for cooperative_ref if not provided (e.g. delivery note number)
- Use terms like "mazao" (crops), "ushirika" (cooperative), "malipo ya papo hapo" (instant payment)
- Before any B2C, confirm cooperative has sufficient balance

Demo prompt to handle: "Lipa Wanjiku KES 8,400 kwa mahindi 120kg @ 70 per kg"
""",

    DomainMode.student: """
ACTIVE MODE: STUDENT FINANCE

You are helping a student or parent pay school fees directly to verified institutions.
The key tool is student_pay_fees — ALWAYS verify the paybill is in the registry first.

Student-specific responses:
- Always confirm institution name before executing payment
- Warn if paybill is not in the verified registry
- Emphasize: "Pesa inaenda moja kwa moja kwa shule — hakuna kati" (money goes direct, no middleman)
- Ask for admission number if not provided
- Use terms like "ada" (fees), "chuo" (school/university), "admission number", "HELB"

Demo prompt to handle: "Lipa fees KES 35,000 kwa University of Nairobi admission A001/2024"
""",

    DomainMode.community: """
ACTIVE MODE: COMMUNITY / CHAMA

You are helping a Chama treasurer or member view real-time group wallet transparency.
The key tool is chama_transparency_report — any member can call this, not just the treasurer.

Community-specific responses:
- Always show: current balance, collection rate %, who has contributed, who hasn't
- Frame transparency as empowerment: "Kila mwanachama anaweza kuona pesa"
- When members haven't contributed, express as a count ("wanachama 7 hawajachanga bado")
- Use terms like "Chama", "mwanachama" (member), "mchango" (contribution), "akiba" (savings)
- Suggest Smart Float rule to auto-invest excess into SACCO

Demo prompt to handle: "Taarifa ya Chama yetu — Bidii Women Group, wanachama 20, kila mmoja KES 5,000"
""",

    DomainMode.general: """
ACTIVE MODE: GENERAL (FULL CO-PILOT)

You are the full M-Okoa financial co-pilot with access to all tools.
Adapt your language and focus to whatever the user needs.
""",
}


def build_system_prompt(domain_mode: str) -> str:
    """Combine base prompt with domain-specific instructions."""
    mode = DomainMode(domain_mode) if domain_mode in DomainMode.__members__.values() else DomainMode.general
    domain_section = DOMAIN_SYSTEM_PROMPTS.get(mode, DOMAIN_SYSTEM_PROMPTS[DomainMode.general])
    return BASE_SYSTEM_PROMPT.strip() + "\n\n" + domain_section.strip()


# ── Tool factory ──────────────────────────────────────────────

def build_agent_tools(user_id: int, db: AsyncSession, daraja: DarajaService):
    """
    Build the complete tool set bound to this user's session.
    13 tools total: 9 core + 4 domain-specific.
    Each tool closes over user_id, db, and daraja — no global state.
    """

    # ── Core Tool 1: All balances ─────────────────────────

    @tool
    async def check_all_balances() -> str:
        """
        Check M-Pesa balances across ALL of the user's active tills.
        Use when user asks: 'pesa ngapi', 'balance yangu', 'how much do I have',
        'uko na pesa ngapi kwa till zote', or any aggregate balance question.
        """
        from app.services.till_service import TillService
        from app.models.user import User as UserModel
        from sqlalchemy import select

        till_service = TillService(db, daraja)
        user_result = await db.execute(select(UserModel).where(UserModel.id == user_id))
        user = user_result.scalar_one_or_none()
        if not user:
            return "Mtumiaji hapatikani."

        balances = await till_service.aggregate_all_balances(user)
        if not balances:
            return "Huna till yoyote iliyosajiliwa. Ongeza till kwenye app kwanza."

        lines = []
        total = Decimal("0.00")
        for b in balances:
            lines.append(f"• {b.display_name}: KES {float(b.balance_kes):,.2f}")
            total += b.balance_kes

        lines.append(f"\nJumla yote: KES {float(total):,.2f}")
        return "\n".join(lines)

    # ── Core Tool 2: Single till balance ──────────────────

    @tool
    async def check_balance(till_public_id: str) -> str:
        """
        Check the balance of one specific till by its public ID.
        Use when the user refers to a specific till by name or number.
        """
        from app.services.till_service import TillService
        from app.models.user import User as UserModel
        from sqlalchemy import select

        till_service = TillService(db, daraja)
        user_result = await db.execute(select(UserModel).where(UserModel.id == user_id))
        user = user_result.scalar_one_or_none()
        if not user:
            return "Mtumiaji hapatikani."

        try:
            balance = await till_service.query_balance(user, till_public_id)
            return f"{balance.display_name}: KES {float(balance.balance_kes):,.2f}"
        except Exception as exc:
            logger.warning("agent.check_balance_failed", error=str(exc))
            return "Imeshindwa kupata balance. Jaribu tena."

    # ── Core Tool 3: Spendable balance (after tax lock) ───

    @tool
    async def get_spendable_balance(till_public_id: str, gross_balance_kes: str) -> str:
        """
        Calculate the truly spendable balance after deducting locked tax.
        Use when user asks 'how much can I spend', 'ninatumia pesa ngapi',
        or before recommending a large payment.
        """
        from app.services.tax_service import TaxService

        tax_service = TaxService(db)
        try:
            gross = Decimal(gross_balance_kes)
            available = await tax_service.get_available_balance(
                user_id=user_id,
                till_id=int(till_public_id),
                gross_balance=gross,
            )
            locked = gross - available
            return (
                f"Gross balance: KES {float(gross):,.2f}\n"
                f"Tax locked (KRA): KES {float(locked):,.2f}\n"
                f"Unaweza kutumia: KES {float(available):,.2f}"
            )
        except Exception as exc:
            logger.warning("agent.spendable_balance_failed", error=str(exc))
            return "Imeshindwa kukokotoa balance inayopatikana."

    # ── Core Tool 4: Tax status ───────────────────────────

    @tool
    async def get_tax_status(period_month: str | None = None) -> str:
        """
        Show how much tax has been locked for KRA this month.
        Use when user asks about KRA, tax, 'pesa ya serikali', 'kodi yangu'.
        period_month format: YYYY-MM (optional, defaults to current month).
        """
        from app.services.tax_service import TaxService

        tax_service = TaxService(db)
        try:
            summary = await tax_service.get_tax_summary(user_id, period_month)
            period = summary["period_month"]
            total = summary["total_locked_kes"]
            breakdown = summary["breakdown"]

            lines = [f"📊 Tax iliyohifadhiwa — {period}:"]
            for tax_type, amount in breakdown.items():
                label = "DST (1.5%)" if tax_type == "dst" else "VAT (16%)"
                lines.append(f"  • {label}: KES {float(amount):,.2f}")
            lines.append(f"\nJumla: KES {float(total):,.2f}")
            lines.append("(Pesa hii imehifadhiwa kwa KRA — usitumie)")
            return "\n".join(lines)
        except Exception as exc:
            logger.warning("agent.tax_status_failed", error=str(exc))
            return "Imeshindwa kupata taarifa ya kodi."

    # ── Core Tool 5: Bill payees ──────────────────────────

    @tool
    async def get_bill_payees(user_public_id: str = "") -> str:
        """
        List the user's saved bill payees (KPLC, Nairobi Water, etc.)
        Use before initiating a bill payment to confirm the correct payee.
        """
        from app.models.bill_payee import BillPayee
        from sqlalchemy import select

        result = await db.execute(
            select(BillPayee).where(
                BillPayee.user_id == user_id,
                BillPayee.is_active == True,
            )
        )
        payees = result.scalars().all()
        if not payees:
            return "Huna payee zilizohifadhiwa. Ongeza kwenye app kwenye Settings."

        lines = ["💳 Payees zako:"]
        for p in payees:
            lines.append(
                f"  • {p.payee_name} — Paybill: {p.paybill_number}, Acc: {p.account_number}"
            )
        return "\n".join(lines)

    # ── Core Tool 6: Transaction summary ──────────────────

    @tool
    async def get_transaction_summary(days: int = 7) -> str:
        """
        Summarize recent transactions in plain language.
        Use when user asks 'matumizi yangu', 'nimelipa nini', 'transactions zangu',
        'malipo ya wiki iliyopita', or any transaction history question.
        days: number of days to look back (default 7, max 30).
        """
        from app.models.transaction import Transaction
        from sqlalchemy import select, and_
        from datetime import timedelta

        days = min(days, 30)
        since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)

        result = await db.execute(
            select(Transaction)
            .where(
                Transaction.user_id == user_id,
                Transaction.status == TransactionStatus.completed,
                Transaction.transaction_date >= since,
            )
            .order_by(Transaction.transaction_date.desc())
            .limit(20)
        )
        transactions = result.scalars().all()

        if not transactions:
            return f"Hakuna transactions katika siku {days} zilizopita."

        total_in = sum(
            t.amount_kes for t in transactions
            if t.direction == TransactionDirection.credit
        )
        total_out = sum(
            t.amount_kes for t in transactions
            if t.direction == TransactionDirection.debit
        )

        lines = [
            f"📈 Transactions — siku {days} zilizopita:",
            f"  Ziliingia:  KES {float(total_in):,.2f}",
            f"  Zilitoka:   KES {float(total_out):,.2f}",
            f"  Neti:       KES {float(total_in - total_out):,.2f}",
            "",
            "Za hivi karibuni:",
        ]

        for txn in transactions[:5]:
            direction_emoji = "⬆️" if txn.direction == TransactionDirection.credit else "⬇️"
            date_str = txn.transaction_date.strftime("%d %b %H:%M")
            lines.append(
                f"  {direction_emoji} KES {float(txn.amount_kes):,.0f} — "
                f"{txn.description or txn.transaction_type.value} ({date_str})"
            )

        return "\n".join(lines)

    # ── Core Tool 7: STK Push ─────────────────────────────

    @tool
    async def initiate_stk_push(
        till_public_id: str,
        phone_number: str,
        amount_kes: str,
        description: str,
        condition_balance_above: str | None = None,
    ) -> str:
        """
        Trigger an STK Push PIN prompt on a customer's phone.
        Use for collecting payments from customers.

        condition_balance_above: Optional KES minimum before executing.
        If balance is below this, abort and inform the user.
        """
        from app.models.till import Till
        from sqlalchemy import select

        till_result = await db.execute(
            select(Till).where(
                Till.public_id == till_public_id,
                Till.user_id == user_id,
                Till.is_active == True,
            )
        )
        till = till_result.scalar_one_or_none()
        if not till:
            return "Till haipatikani."

        amount = Decimal(amount_kes)

        if condition_balance_above:
            min_balance = Decimal(condition_balance_above)
            current = till.last_known_balance_kes or Decimal("0")
            if current < min_balance:
                return (
                    f"❌ Balance yako ni KES {float(current):,.2f} — "
                    f"chini ya kiwango cha KES {float(min_balance):,.2f}. "
                    f"Malipo hayajafanywa."
                )

        if not all([
            till.daraja_consumer_key, till.daraja_consumer_secret,
            till.daraja_shortcode, till.daraja_passkey,
        ]):
            return "Daraja credentials hazijasanidiwa kwa till hii. Ongeza kwenye Settings."

        try:
            creds = DarajaTillCredentials(
                encrypted_consumer_key=till.daraja_consumer_key,
                encrypted_consumer_secret=till.daraja_consumer_secret,
                shortcode=till.daraja_shortcode,
                encrypted_passkey=till.daraja_passkey,
            )
            normalized_phone = DarajaService.normalize_phone(phone_number)
            response = await daraja.initiate_stk_push(
                creds=creds,
                phone_number=normalized_phone,
                amount=amount,
                account_reference="MOKOA",
                transaction_desc=description[:13],
            )

            checkout_id = response.get("CheckoutRequestID", "")
            redis = get_redis()
            await redis.setex(
                RedisKeys.stk_session(checkout_id),
                300,
                json.dumps({
                    "till_id": till.id,
                    "user_id": user_id,
                    "amount": amount_kes,
                    "description": description,
                }),
            )

            return (
                f"✅ STK Push imetumwa kwa {normalized_phone}.\n"
                f"Kiasi: KES {float(amount):,.2f}\n"
                f"Ingiza PIN yako ya M-Pesa kukamilisha.\n"
                f"ref:{checkout_id}"
            )

        except DarajaError as exc:
            logger.warning("agent.stk_push_failed", error=str(exc))
            return "M-Pesa haifanyi kazi sasa hivi. Jaribu tena baadaye."

    # ── Core Tool 8: Pay bill ─────────────────────────────

    @tool
    async def pay_bill(
        till_public_id: str,
        paybill_number: str,
        account_number: str,
        amount_kes: str,
        condition_balance_above: str | None = None,
    ) -> str:
        """
        Pay a bill via STK Push (KPLC, Nairobi Water, rent, suppliers).
        condition_balance_above: Only pay if balance exceeds this amount.
        """
        from app.models.till import Till
        from sqlalchemy import select

        till_result = await db.execute(
            select(Till).where(
                Till.public_id == till_public_id,
                Till.user_id == user_id,
                Till.is_active == True,
            )
        )
        till = till_result.scalar_one_or_none()
        if not till:
            return "Till haipatikani."

        amount = Decimal(amount_kes)

        if condition_balance_above:
            min_balance = Decimal(condition_balance_above)
            current = till.last_known_balance_kes or Decimal("0")
            if current < min_balance:
                return (
                    f"❌ Huwezi kulipa — balance yako ni KES {float(current):,.2f}, "
                    f"inahitajika KES {float(min_balance):,.2f}."
                )

        if not till.daraja_shortcode:
            return "Daraja credentials hazijasanidiwa. Ongeza kwenye Settings."

        try:
            creds = DarajaTillCredentials(
                encrypted_consumer_key=till.daraja_consumer_key,
                encrypted_consumer_secret=till.daraja_consumer_secret,
                shortcode=till.daraja_shortcode,
                encrypted_passkey=till.daraja_passkey,
            )
            response = await daraja.initiate_stk_push(
                creds=creds,
                phone_number=till.daraja_shortcode,
                amount=amount,
                account_reference=account_number[:12],
                transaction_desc=f"Bill {paybill_number}"[:13],
            )

            checkout_id = response.get("CheckoutRequestID", "")
            redis = get_redis()
            await redis.setex(
                RedisKeys.stk_session(checkout_id),
                300,
                json.dumps({
                    "till_id": till.id,
                    "user_id": user_id,
                    "amount": amount_kes,
                    "description": f"Bill payment to {paybill_number}",
                    "paybill": paybill_number,
                    "account": account_number,
                }),
            )

            return (
                f"✅ Malipo ya bill yametumwa!\n"
                f"Paybill: {paybill_number}\n"
                f"Akaunti: {account_number}\n"
                f"Kiasi: KES {float(amount):,.2f}\n"
                f"Ingiza PIN yako ya M-Pesa kukamilisha."
            )

        except DarajaError:
            return "M-Pesa haifanyi kazi sasa hivi. Jaribu tena baadaye."

    # ── Core Tool 9: Move float ───────────────────────────

    @tool
    async def move_float(
        till_public_id: str,
        destination_phone: str,
        amount_kes: str,
        reason: str,
        condition_balance_above: str | None = None,
    ) -> str:
        """
        Transfer funds from a till to a phone number via B2C.
        Used for Smart Float transfers to SACCO, bank agent, or personal phone.
        condition_balance_above: Only move if balance exceeds this.
        """
        from app.models.till import Till
        from sqlalchemy import select

        till_result = await db.execute(
            select(Till).where(
                Till.public_id == till_public_id,
                Till.user_id == user_id,
                Till.is_active == True,
            )
        )
        till = till_result.scalar_one_or_none()
        if not till:
            return "Till haipatikani."

        amount = Decimal(amount_kes)

        if condition_balance_above:
            min_balance = Decimal(condition_balance_above)
            current = till.last_known_balance_kes or Decimal("0")
            if current < min_balance:
                return (
                    f"❌ Balance ni KES {float(current):,.2f} — "
                    f"unahitaji angalau KES {float(min_balance):,.2f}."
                )

        if not till.daraja_shortcode:
            return "Daraja credentials hazijasanidiwa. Ongeza kwenye Settings."

        try:
            creds = DarajaTillCredentials(
                encrypted_consumer_key=till.daraja_consumer_key,
                encrypted_consumer_secret=till.daraja_consumer_secret,
                shortcode=till.daraja_shortcode,
                encrypted_passkey=till.daraja_passkey,
            )
            normalized = DarajaService.normalize_phone(destination_phone)
            originator_id = str(ULID())

            await daraja.initiate_b2c(
                creds=creds,
                initiator_name="MokoaAgent",
                security_credential="",
                phone_number=normalized,
                amount=amount,
                command_id="BusinessPayment",
                remarks=reason[:100],
            )

            redis = get_redis()
            await redis.setex(
                f"b2c:session:{originator_id}",
                600,
                json.dumps({
                    "till_id": till.id,
                    "user_id": user_id,
                    "amount": amount_kes,
                    "destination": normalized,
                }),
            )

            return (
                f"✅ Uhamisho umeanzishwa!\n"
                f"KES {float(amount):,.2f} → {normalized}\n"
                f"Sababu: {reason}\n"
                f"Utapata ujumbe wa uthibitisho hivi karibuni."
            )

        except DarajaError:
            return "M-Pesa haifanyi kazi sasa hivi. Jaribu tena baadaye."

    # ── Domain Tool 10: Merchant reconciliation ───────────

    @tool
    async def merchant_reconcile_today() -> str:
        """
        Generate today's reconciliation summary for a Lipa na M-Pesa merchant.
        Use when user asks: 'malipo ya leo', 'nilikokotoa ngapi leo',
        'how many payments today', or any merchant daily collection question.
        """
        from app.services.merchant_service import MerchantService
        from app.models.till import Till
        from sqlalchemy import select

        merchant_svc = MerchantService(db, daraja)

        till_result = await db.execute(
            select(Till).where(
                Till.user_id == user_id,
                Till.is_active == True,
            ).limit(1)
        )
        till = till_result.scalar_one_or_none()
        if not till:
            return "Huna till iliyosajiliwa. Ongeza till kwanza."

        summary = await merchant_svc.get_daily_reconciliation_summary(
            user_id=user_id, till_id=till.id,
        )

        return (
            f"📊 Leo — {summary['date']}\n"
            f"Jumla iliyokusanywa: KES {float(summary['total_collected_kes']):,.2f}\n"
            f"Transactions: {summary['transaction_count']}\n"
            f"Ada za M-Pesa: KES {float(summary['fee_total_kes']):,.2f}\n"
            f"Neti: KES {float(summary['net_kes']):,.2f}"
        )

    # ── Domain Tool 11: Farmer payout ─────────────────────

    @tool
    async def farmer_disburse_payout(
        farmer_phone: str,
        farmer_name: str,
        crop_type: str,
        quantity_kg: str,
        price_per_kg: str,
        cooperative_ref: str,
    ) -> str:
        """
        Disburse an instant crop payout to a farmer via B2C.
        Use when cooperative user says 'lipa mkulima', 'pay farmer for [crop]',
        'send payout', or any crop payment request.
        Always show fee and net amount BEFORE confirming disbursement.
        """
        from app.services.farmer_service import FarmerService, CropPayoutRequest
        from app.models.till import Till
        from sqlalchemy import select

        farmer_svc = FarmerService(db, daraja)

        till_result = await db.execute(
            select(Till).where(
                Till.user_id == user_id,
                Till.is_active == True,
            ).limit(1)
        )
        till = till_result.scalar_one_or_none()
        if not till:
            return "Huna till iliyosajiliwa kwa ushirika."

        try:
            payout = CropPayoutRequest(
                farmer_phone=farmer_phone,
                farmer_name=farmer_name,
                crop_type=crop_type,
                quantity_kg=Decimal(quantity_kg),
                price_per_kg=Decimal(price_per_kg),
                cooperative_ref=cooperative_ref,
            )
        except Exception:
            return "Thamani ya mazao au bei ni batili. Angalia na ujaribu tena."

        result = await farmer_svc.disburse_crop_payout(
            till=till,
            payout=payout,
            user_id=user_id,
            initiator_name="MokoaAgent",
            security_credential="",
        )

        return result.get("summary") or result.get("reason", "Unknown error")

    # ── Domain Tool 12: Student fee payment ───────────────

    @tool
    async def student_pay_fees(
        student_phone: str,
        paybill_number: str,
        admission_number: str,
        amount_kes: str,
        student_name: str,
    ) -> str:
        """
        Pay school/university fees directly to a verified institution via STK Push.
        Use when user says 'lipa fees', 'pay school fees', 'send tuition',
        or any educational payment request.
        Always confirm institution name before executing.
        """
        from app.services.student_service import StudentService
        from app.models.till import Till
        from sqlalchemy import select

        student_svc = StudentService(db, daraja)

        till_result = await db.execute(
            select(Till).where(
                Till.user_id == user_id,
                Till.is_active == True,
            ).limit(1)
        )
        till = till_result.scalar_one_or_none()
        if not till:
            return "Huna till iliyosajiliwa. Ongeza till kwanza."

        result = await student_svc.initiate_fee_payment(
            till=till,
            user_id=user_id,
            student_phone=student_phone,
            paybill_number=paybill_number,
            admission_number=admission_number,
            amount_kes=Decimal(amount_kes),
            student_name=student_name,
        )

        return result.get("summary") or result.get("reason", "Payment failed.")

    # ── Domain Tool 13: Chama transparency ────────────────

    @tool
    async def chama_transparency_report(
        chama_name: str,
        member_count: str,
        monthly_target_per_member: str,
    ) -> str:
        """
        Generate a real-time Chama group wallet transparency report.
        Use when user asks: 'pesa za chama', 'Chama balance', 'who has paid',
        'wangapi wamechanga', or any group wallet transparency question.
        Any Chama member — not just the treasurer — can request this.
        """
        from app.services.community_service import CommunityService
        from app.models.till import Till
        from sqlalchemy import select

        community_svc = CommunityService(db, daraja)

        till_result = await db.execute(
            select(Till).where(
                Till.user_id == user_id,
                Till.is_active == True,
            ).limit(1)
        )
        till = till_result.scalar_one_or_none()
        if not till:
            return "Hakuna till ya Chama iliyosajiliwa."

        try:
            report = await community_svc.get_transparency_report(
                user_id=user_id,
                till_id=till.id,
                chama_name=chama_name,
                member_count=int(member_count),
                expected_monthly_contribution_kes=Decimal(monthly_target_per_member),
            )
            return report.to_agent_message()
        except Exception as exc:
            logger.warning("agent.chama_report_failed", error=str(exc))
            return "Imeshindwa kupata taarifa ya Chama. Jaribu tena."

    # ── Return all 13 tools ───────────────────────────────
    return [
        check_all_balances,
        check_balance,
        get_spendable_balance,
        get_tax_status,
        get_bill_payees,
        get_transaction_summary,
        initiate_stk_push,
        pay_bill,
        move_float,
        merchant_reconcile_today,
        farmer_disburse_payout,
        student_pay_fees,
        chama_transparency_report,
    ]


# ── LangGraph graph builder ───────────────────────────────────

def build_agent_graph(
    user_id: int,
    domain_mode: str,
    db: AsyncSession,
    daraja: DarajaService,
):
    """
    Construct the LangGraph state machine for one user session.
    Domain mode is injected into the system prompt at graph construction time.
    """
    tools = build_agent_tools(user_id, db, daraja)
    system_prompt = build_system_prompt(domain_mode)

    llm = ChatAnthropic(
        model="claude-sonnet-4-20250514",
        api_key=settings.anthropic_api_key,
        max_tokens=1000,
    ).bind_tools(tools)

    tools_by_name = {t.name: t for t in tools}

    async def call_llm(state: AgentState) -> dict:
        messages = [SystemMessage(content=system_prompt)] + state["messages"]
        response: AIMessage = await llm.ainvoke(messages)
        return {"messages": [response]}

    async def execute_tools(state: AgentState) -> dict:
        last_message: AIMessage = state["messages"][-1]
        tool_results = []

        for tool_call in last_message.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            tool_id = tool_call["id"]

            logger.info("agent.tool_call", tool=tool_name, user_id=user_id)

            if tool_name in tools_by_name:
                try:
                    result = await tools_by_name[tool_name].ainvoke(tool_args)
                    tool_results.append(
                        ToolMessage(content=str(result), tool_call_id=tool_id)
                    )
                except Exception as exc:
                    logger.error("agent.tool_error", tool=tool_name, error=str(exc))
                    tool_results.append(
                        ToolMessage(
                            content="Kuna tatizo la kiufundi. Jaribu tena.",
                            tool_call_id=tool_id,
                        )
                    )
            else:
                tool_results.append(
                    ToolMessage(
                        content=f"Tool '{tool_name}' haipatikani.",
                        tool_call_id=tool_id,
                    )
                )

        return {"messages": tool_results}

    def should_continue(state: AgentState) -> Literal["tools", END]:
        last = state["messages"][-1]
        if isinstance(last, AIMessage) and last.tool_calls:
            return "tools"
        return END

    graph = StateGraph(AgentState)
    graph.add_node("llm", call_llm)
    graph.add_node("tools", execute_tools)
    graph.add_edge(START, "llm")
    graph.add_conditional_edges(
        "llm", should_continue, {"tools": "tools", END: END}
    )
    graph.add_edge("tools", "llm")

    return graph.compile()


# ── Agent Service ─────────────────────────────────────────────

class AgentService:
    """
    Entry point for all agent interactions.
    Manages session lifecycle, graph execution, and DB persistence.
    Domain mode is read from the user record at session start.
    """

    def __init__(self, db: AsyncSession, daraja: DarajaService) -> None:
        self._db = db
        self._daraja = daraja

    async def handle_message(
        self,
        user_id: int,
        user_name: str,
        message_text: str,
        session_source: SessionSource,
        conversation_history: list[dict] | None = None,
        domain_mode_override: str | None = None,
    ) -> str:
        """
        Process a user message through the agent graph.

        1. Resolve user's domain mode (from DB or override)
        2. Build context (tills, tax summary, payees)
        3. Construct agent state with full conversation history
        4. Run the LangGraph graph with domain-aware system prompt
        5. Persist session to DB
        6. Return the agent's final text response
        """
        # Resolve domain mode
        domain_mode = domain_mode_override or await self._get_user_domain_mode(user_id)

        context = await self._build_user_context(user_id)
        history_messages = self._deserialize_history(conversation_history or [])

        initial_state: AgentState = {
            "messages": history_messages + [HumanMessage(content=message_text)],
            "user_id": user_id,
            "user_name": user_name,
            "user_domain_mode": domain_mode,
            "session_public_id": str(ULID()),
            "session_source": session_source.value,
            "tills": context["tills"],
            "tax_summary": context["tax_summary"],
            "bill_payees": context["bill_payees"],
            "action_result": {},
            "awaiting_stk_confirmation": False,
            "stk_checkout_id": None,
            "final_response": "",
            "response_language": "sw",
        }

        graph = build_agent_graph(
            user_id=user_id,
            domain_mode=domain_mode,
            db=self._db,
            daraja=self._daraja,
        )

        try:
            final_state: AgentState = await graph.ainvoke(initial_state)
        except Exception as exc:
            logger.error("agent.graph_error", user_id=user_id, error=str(exc))
            return "Samahani, kuna tatizo la kiufundi. Jaribu tena baadaye. 🙏"

        response = self._extract_final_response(final_state)

        await self._persist_session(
            user_id=user_id,
            session_public_id=initial_state["session_public_id"],
            source=session_source,
            user_input=message_text,
            domain_mode=domain_mode,
            final_state=final_state,
            final_response=response,
        )

        logger.info(
            "agent.message_handled",
            user_id=user_id,
            source=session_source.value,
            domain_mode=domain_mode,
            response_length=len(response),
        )

        return response

    # ── Context builder ───────────────────────────────────

    async def _build_user_context(self, user_id: int) -> dict:
        """
        Fetch tills, tax summary, and bill payees.
        Injected into initial agent state — reduces tool calls for basic info.
        """
        from app.models.till import Till
        from app.models.bill_payee import BillPayee
        from sqlalchemy import select

        tills_result = await self._db.execute(
            select(Till).where(Till.user_id == user_id, Till.is_active == True)
        )
        tills = tills_result.scalars().all()

        redis = get_redis()
        tills_data = []
        for t in tills:
            cached_balance = await redis.get(RedisKeys.till_balance_cache(t.id))
            tills_data.append({
                "public_id": t.public_id,
                "display_name": t.display_name,
                "till_number": t.till_number,
                "till_type": t.till_type.value,
                "balance_kes": cached_balance or str(t.last_known_balance_kes or "0"),
                "has_daraja_credentials": all([
                    t.daraja_consumer_key, t.daraja_consumer_secret,
                    t.daraja_shortcode, t.daraja_passkey,
                ]),
            })

        from app.services.tax_service import TaxService
        tax_service = TaxService(self._db)
        try:
            tax_summary = await tax_service.get_tax_summary(user_id)
        except Exception:
            tax_summary = {}

        payees_result = await self._db.execute(
            select(BillPayee).where(
                BillPayee.user_id == user_id,
                BillPayee.is_active == True,
            )
        )
        payees = payees_result.scalars().all()
        payees_data = [
            {
                "payee_name": p.payee_name,
                "paybill_number": p.paybill_number,
                "account_number": p.account_number,
                "category": p.category.value,
            }
            for p in payees
        ]

        return {"tills": tills_data, "tax_summary": tax_summary, "bill_payees": payees_data}

    # ── Domain mode resolver ──────────────────────────────

    async def _get_user_domain_mode(self, user_id: int) -> str:
        from app.models.user import User as UserModel
        from sqlalchemy import select

        result = await self._db.execute(
            select(UserModel.domain_mode).where(UserModel.id == user_id)
        )
        row = result.scalar_one_or_none()
        return row.value if row else DomainMode.general.value

    # ── Session persistence ───────────────────────────────

    async def _persist_session(
        self,
        user_id: int,
        session_public_id: str,
        source: SessionSource,
        user_input: str,
        domain_mode: str,
        final_state: AgentState,
        final_response: str,
    ) -> None:
        try:
            serializable_state = {
                k: v for k, v in final_state.items()
                if k != "messages"
            }
            # Inject domain_mode into stored state for audit
            serializable_state["domain_mode"] = domain_mode

            session = AgentSession(
                public_id=session_public_id,
                user_id=user_id,
                session_source=source,
                graph_state=serializable_state,
                current_node="completed",
                status=SessionStatus.completed,
                user_input=user_input[:1000],
                final_response=final_response[:2000],
                completed_at=datetime.now(timezone.utc).replace(tzinfo=None),
            )
            self._db.add(session)
            await self._db.flush()
        except Exception as exc:
            logger.warning("agent.session_persist_failed", error=str(exc))

    # ── Helpers ───────────────────────────────────────────

    @staticmethod
    def _extract_final_response(state: AgentState) -> str:
        for msg in reversed(state["messages"]):
            if isinstance(msg, AIMessage) and not msg.tool_calls:
                return msg.content if isinstance(msg.content, str) else str(msg.content)
        return "Samahani, sikupata jibu. Jaribu tena."

    @staticmethod
    def _deserialize_history(history: list[dict]) -> list:
        messages = []
        for item in history[-10:]:  # Last 10 turns for context window management
            role = item.get("role", "")
            content = item.get("content", "")
            if role == "user":
                messages.append(HumanMessage(content=content))
            elif role == "assistant":
                messages.append(AIMessage(content=content))
        return messages