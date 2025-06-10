# File: app/accounting/forex_manager.py
from typing import List, Optional, Dict, TYPE_CHECKING
from decimal import Decimal
from datetime import date, timedelta
from collections import defaultdict

from app.utils.result import Result
from app.utils.pydantic_models import JournalEntryData, JournalEntryLineData
from app.common.enums import JournalTypeEnum
from app.models.business.sales_invoice import SalesInvoice
from app.models.business.purchase_invoice import PurchaseInvoice
from app.models.business.bank_account import BankAccount
from app.models.accounting.journal_entry import JournalEntry

if TYPE_CHECKING:
    from app.core.application_core import ApplicationCore
    from app.services.business_services import SalesInvoiceService, PurchaseInvoiceService, BankAccountService
    from app.services.accounting_services import ExchangeRateService
    from app.services.journal_service import JournalService
    from app.accounting.journal_entry_manager import JournalEntryManager
    
class ForexManager:
    def __init__(self, app_core: "ApplicationCore"):
        self.app_core = app_core
        self.logger = app_core.logger
        self.sales_invoice_service: "SalesInvoiceService" = app_core.sales_invoice_service
        self.purchase_invoice_service: "PurchaseInvoiceService" = app_core.purchase_invoice_service
        self.bank_account_service: "BankAccountService" = app_core.bank_account_service
        self.exchange_rate_service: "ExchangeRateService" = app_core.exchange_rate_service
        self.journal_service: "JournalService" = app_core.journal_service
        self.journal_entry_manager: "JournalEntryManager" = app_core.journal_entry_manager

    async def create_unrealized_gain_loss_je(self, revaluation_date: date, user_id: int) -> Result[JournalEntry]:
        self.logger.info(f"Starting unrealized forex gain/loss calculation for {revaluation_date}.")
        
        settings = await self.app_core.company_settings_service.get_company_settings()
        if not settings: return Result.failure(["Company settings not found."])
        base_currency = settings.base_currency

        adjustments: Dict[int, Decimal] = defaultdict(Decimal)
        total_adjustment = Decimal(0)
        
        # 1. Process Accounts Receivable (Sales Invoices)
        open_sales_invoices = await self.sales_invoice_service.get_all_open_invoices()
        for inv in open_sales_invoices:
            if inv.currency_code == base_currency: continue
            
            outstanding_fc = inv.total_amount - inv.amount_paid
            if abs(outstanding_fc) < Decimal("0.01"): continue
            
            rate_reval = await self.exchange_rate_service.get_rate_for_date(inv.currency_code, base_currency, revaluation_date)
            if not rate_reval: return Result.failure([f"Missing exchange rate for {inv.currency_code} to {base_currency} on {revaluation_date}."])
            
            # This calculation is simplified. A more robust way would be to track payments and their rates.
            # For now, we assume the booked base balance is the original total minus payments converted at original rate.
            # This is an approximation.
            booked_base_balance = (inv.total_amount - inv.amount_paid) * inv.exchange_rate
            revalued_base_balance = outstanding_fc * rate_reval.exchange_rate_value
            adjustment = revalued_base_balance - booked_base_balance
            
            if inv.customer.receivables_account_id:
                adjustments[inv.customer.receivables_account_id] += adjustment
                total_adjustment += adjustment
        
        # 2. Process Accounts Payable (Purchase Invoices)
        open_purchase_invoices = await self.purchase_invoice_service.get_all_open_invoices()
        for inv in open_purchase_invoices:
            if inv.currency_code == base_currency: continue

            outstanding_fc = inv.total_amount - inv.amount_paid
            if abs(outstanding_fc) < Decimal("0.01"): continue

            rate_reval = await self.exchange_rate_service.get_rate_for_date(inv.currency_code, base_currency, revaluation_date)
            if not rate_reval: return Result.failure([f"Missing exchange rate for {inv.currency_code} to {base_currency} on {revaluation_date}."])

            booked_base_balance = (inv.total_amount - inv.amount_paid) * inv.exchange_rate
            revalued_base_balance = outstanding_fc * rate_reval.exchange_rate_value
            adjustment = revalued_base_balance - booked_base_balance
            
            if inv.vendor.payables_account_id:
                adjustments[inv.vendor.payables_account_id] -= adjustment # AP is a liability, sign is opposite of AR
                total_adjustment -= adjustment

        # 3. Process Foreign Currency Bank Accounts
        all_bank_accounts = await self.bank_account_service.get_all_active()
        for ba in all_bank_accounts:
            if ba.currency_code == base_currency: continue
            
            balance_fc = ba.current_balance
            current_base_balance = await self.journal_service.get_account_balance(ba.gl_account_id, revaluation_date)
            rate_reval = await self.exchange_rate_service.get_rate_for_date(ba.currency_code, base_currency, revaluation_date)
            if not rate_reval: return Result.failure([f"Missing exchange rate for {ba.currency_code} to {base_currency} on {revaluation_date}."])
            
            revalued_base_balance = balance_fc * rate_reval.exchange_rate_value
            adjustment = revalued_base_balance - current_base_balance
            adjustments[ba.gl_account_id] += adjustment
            total_adjustment += adjustment

        if abs(total_adjustment) < Decimal("0.01"):
            return Result.success(None) # No adjustment needed

        # 4. Create Journal Entry
        je_lines = []
        for account_id, amount in adjustments.items():
            if abs(amount) < Decimal("0.01"): continue
            debit = amount if amount > 0 else Decimal(0)
            credit = -amount if amount < 0 else Decimal(0)
            je_lines.append(JournalEntryLineData(account_id=account_id, debit_amount=debit, credit_amount=credit))

        if total_adjustment > 0: # Net Gain
            gain_acc_code = await self.app_core.configuration_service.get_config_value("SysAcc_UnrealizedForexGain", "7201")
            gain_acc = await self.app_core.account_service.get_by_code(gain_acc_code)
            if not gain_acc: return Result.failure([f"Unrealized Forex Gain account '{gain_acc_code}' not found."])
            je_lines.append(JournalEntryLineData(account_id=gain_acc.id, debit_amount=Decimal(0), credit_amount=total_adjustment))
        else: # Net Loss
            loss_acc_code = await self.app_core.configuration_service.get_config_value("SysAcc_UnrealizedForexLoss", "8201")
            loss_acc = await self.app_core.account_service.get_by_code(loss_acc_code)
            if not loss_acc: return Result.failure([f"Unrealized Forex Loss account '{loss_acc_code}' not found."])
            je_lines.append(JournalEntryLineData(account_id=loss_acc.id, debit_amount=-total_adjustment, credit_amount=Decimal(0)))

        je_data = JournalEntryData(
            journal_type=JournalTypeEnum.ADJUSTMENT.value,
            entry_date=revaluation_date,
            description=f"Unrealized Forex Gain/Loss as at {revaluation_date.strftime('%Y-%m-%d')}",
            user_id=user_id,
            lines=je_lines
        )
        
        create_result = await self.journal_entry_manager.create_journal_entry(je_data)
        if not create_result.is_success or not create_result.value:
            return create_result

        created_je = create_result.value
        post_result = await self.journal_entry_manager.post_journal_entry(created_je.id, user_id)
        if not post_result.is_success:
            self.logger.error(f"Failed to post unrealized forex JE {created_je.entry_no}: {post_result.errors}")
            return post_result

        # 5. Create and Post Reversing Entry
        reversal_date = revaluation_date + timedelta(days=1)
        reversal_result = await self.journal_entry_manager.create_reversing_entry(created_je.id, reversal_date, user_id)
        if not reversal_result.is_success or not reversal_result.value:
            self.logger.error(f"Failed to create reversing JE for unrealized forex JE {created_je.entry_no}: {reversal_result.errors}")
            return reversal_result
            
        reversal_je = reversal_result.value
        post_reversal_result = await self.journal_entry_manager.post_journal_entry(reversal_je.id, user_id)
        if not post_reversal_result.is_success:
            self.logger.error(f"Reversing JE {reversal_je.entry_no} created but failed to post: {post_reversal_result.errors}")
            return post_reversal_result

        self.logger.info(f"Successfully created and posted Unrealized Forex JE {created_je.entry_no} and its reversal {reversal_je.entry_no}.")
        return Result.success(created_je)
