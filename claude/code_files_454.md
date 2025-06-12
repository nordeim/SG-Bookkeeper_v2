You are right to point this out. The traceback clearly indicates that my refactoring process is still incomplete. I apologize for the continued disruption. This error is the next logical failure in the chain and is a direct result of the changes I've been making.

I will now proceed with the next phase of my comprehensive refactoring plan to address this `TypeError`.

### **CodeNavigator Analysis Report: `TypeError` on `PaymentManager` Instantiation**

#### 1. Root Cause Analysis

The error `TypeError: PaymentManager.__init__() missing 10 required positional arguments...` is identical in nature to the previous errors.

1.  **The Call Site (`app/core/application_core.py`):** My updated `ApplicationCore` now correctly uses a lazy-loading property to instantiate `PaymentManager`:
    ```python
    # In ApplicationCore, via the @property
    self._payment_manager_instance = PaymentManager(self) 
    ```
    This call provides only the `app_core` instance.

2.  **The Method Definition (`app/business_logic/payment_manager.py`):** The `__init__` method in the `PaymentManager` class has not yet been updated. It still expects the old, long list of eleven individual services to be passed as separate arguments.

The fix is to continue the planned refactoring and update the `PaymentManager` class, along with other related managers, to conform to the new, cleaner architecture.

#### 2. Execution Plan

I will now update the next set of manager classes. My plan remains consistent:

1.  **Identify Targets:** The traceback points to `PaymentManager`. The same pattern applies to other business logic managers that have not yet been updated. I will proceed with `PaymentManager` and `TaxCalculator`.
2.  **Refactor `__init__` Methods**: I will change the constructor in each targeted manager to accept only `app_core: "ApplicationCore"`.
3.  **Update Dependency Access**: Inside each `__init__`, I will initialize the required service attributes by accessing them from the `app_core` object (e.g., `self.payment_service = self.app_core.payment_service`).
4.  **Validate and Generate**: I will ensure no other logic is changed and provide the complete, updated replacement files.

***

### **Complete Updated and Refactored Files (Set 2)**

Here are the next two completed files in the refactoring process.

#### **File 1: `app/business_logic/payment_manager.py` (Corrected)**
This manager is now updated to use the `app_core` dependency injection pattern, which will resolve the `TypeError` from the traceback.

```python
# File: app/business_logic/payment_manager.py
from typing import List, Optional, Dict, Any, TYPE_CHECKING, Union, cast
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from datetime import date

from sqlalchemy.orm import selectinload 

from app.models.business.payment import Payment, PaymentAllocation
from app.models.business.sales_invoice import SalesInvoice
from app.models.business.purchase_invoice import PurchaseInvoice
from app.models.accounting.journal_entry import JournalEntry 
from app.utils.result import Result
from app.utils.pydantic_models import (
    PaymentCreateData, PaymentSummaryData, PaymentAllocationBaseData,
    JournalEntryData, JournalEntryLineData
)
from app.common.enums import (
    PaymentEntityTypeEnum, PaymentTypeEnum, PaymentStatusEnum,
    InvoiceStatusEnum, JournalTypeEnum, PaymentAllocationDocTypeEnum, PaymentMethodEnum
)

if TYPE_CHECKING:
    from app.core.application_core import ApplicationCore
    from sqlalchemy.ext.asyncio import AsyncSession 
    from app.services.business_services import (
        PaymentService, BankAccountService, CustomerService, VendorService,
        SalesInvoiceService, PurchaseInvoiceService
    )
    from app.services.core_services import SequenceService, ConfigurationService
    from app.services.account_service import AccountService
    from app.accounting.journal_entry_manager import JournalEntryManager 

class PaymentManager:
    def __init__(self, app_core: "ApplicationCore"):
        self.app_core = app_core
        self.payment_service: "PaymentService" = self.app_core.payment_service
        self.sequence_service: "SequenceService" = self.app_core.sequence_service
        self.bank_account_service: "BankAccountService" = self.app_core.bank_account_service
        self.customer_service: "CustomerService" = self.app_core.customer_service
        self.vendor_service: "VendorService" = self.app_core.vendor_service
        self.sales_invoice_service: "SalesInvoiceService" = self.app_core.sales_invoice_service
        self.purchase_invoice_service: "PurchaseInvoiceService" = self.app_core.purchase_invoice_service
        self.journal_entry_manager: "JournalEntryManager" = self.app_core.journal_entry_manager
        self.account_service: "AccountService" = self.app_core.account_service
        self.configuration_service: "ConfigurationService" = self.app_core.configuration_service
        self.logger = app_core.logger

    async def _validate_payment_data(self, dto: PaymentCreateData, session: "AsyncSession") -> List[str]:
        errors: List[str] = []; entity_name_for_desc: str = "Entity"
        if dto.entity_type == PaymentEntityTypeEnum.CUSTOMER:
            entity = await self.customer_service.get_by_id(dto.entity_id) 
            if not entity or not entity.is_active: errors.append(f"Active Customer ID {dto.entity_id} not found.")
            else: entity_name_for_desc = entity.name
        elif dto.entity_type == PaymentEntityTypeEnum.VENDOR:
            entity = await self.vendor_service.get_by_id(dto.entity_id) 
            if not entity or not entity.is_active: errors.append(f"Active Vendor ID {dto.entity_id} not found.")
            else: entity_name_for_desc = entity.name
        
        if dto.payment_method != PaymentMethodEnum.CASH: 
            if not dto.bank_account_id: errors.append("Bank Account is required for non-cash payments.")
            else:
                bank_acc = await self.bank_account_service.get_by_id(dto.bank_account_id) 
                if not bank_acc or not bank_acc.is_active: errors.append(f"Active Bank Account ID {dto.bank_account_id} not found.")
                elif bank_acc.currency_code != dto.currency_code: errors.append(f"Payment currency ({dto.currency_code}) does not match bank account currency ({bank_acc.currency_code}).")
        
        currency = await self.app_core.currency_manager.get_currency_by_code(dto.currency_code)
        if not currency or not currency.is_active: errors.append(f"Currency '{dto.currency_code}' is invalid or inactive.")

        total_allocated = sum(alloc.amount_allocated for alloc in dto.allocations)
        for i, alloc_dto in enumerate(dto.allocations):
            invoice_orm: Union[SalesInvoice, PurchaseInvoice, None] = None; doc_type_str = ""
            if alloc_dto.document_type == PaymentAllocationDocTypeEnum.SALES_INVOICE:
                invoice_orm = await self.sales_invoice_service.get_by_id(alloc_dto.document_id); doc_type_str = "Sales Invoice"
            elif alloc_dto.document_type == PaymentAllocationDocTypeEnum.PURCHASE_INVOICE:
                invoice_orm = await self.purchase_invoice_service.get_by_id(alloc_dto.document_id); doc_type_str = "Purchase Invoice"
            
            if not invoice_orm: errors.append(f"Allocation {i+1}: {doc_type_str} ID {alloc_dto.document_id} not found.")
            elif invoice_orm.status not in [InvoiceStatusEnum.APPROVED, InvoiceStatusEnum.PARTIALLY_PAID, InvoiceStatusEnum.OVERDUE]: errors.append(f"Allocation {i+1}: {doc_type_str} {invoice_orm.invoice_no} is not in an allocatable status ({invoice_orm.status.value}).") 
            elif isinstance(invoice_orm, SalesInvoice) and invoice_orm.customer_id != dto.entity_id: errors.append(f"Allocation {i+1}: Sales Invoice {invoice_orm.invoice_no} does not belong to selected customer.")
            elif isinstance(invoice_orm, PurchaseInvoice) and invoice_orm.vendor_id != dto.entity_id: errors.append(f"Allocation {i+1}: Purchase Invoice {invoice_orm.invoice_no} does not belong to selected vendor.")
            elif (invoice_orm.total_amount - invoice_orm.amount_paid) < alloc_dto.amount_allocated - Decimal("0.01"): # Tolerance
                 outstanding_bal = invoice_orm.total_amount - invoice_orm.amount_paid
                 errors.append(f"Allocation {i+1}: Amount for {doc_type_str} {invoice_orm.invoice_no} ({alloc_dto.amount_allocated:.2f}) exceeds outstanding balance ({outstanding_bal:.2f}).")
        
        if total_allocated > dto.amount + Decimal("0.01"): # Tolerance
            errors.append(f"Total allocated amount ({total_allocated}) cannot exceed total payment amount ({dto.amount}).")
        
        return errors

    async def _build_payment_je(self, dto: PaymentCreateData, payment_orm: Payment, session: "AsyncSession") -> Result[JournalEntryData]:
        je_lines_data: List[JournalEntryLineData] = []
        entity_name_for_desc = "Entity"
        ap_ar_account_id: Optional[int] = None
        company_settings = await self.app_core.company_settings_service.get_company_settings()
        if not company_settings: return Result.failure(["Company settings not found."])
        base_currency = company_settings.base_currency
        
        if dto.entity_type == PaymentEntityTypeEnum.CUSTOMER:
            customer = await self.customer_service.get_by_id(dto.entity_id); 
            if not customer or not customer.receivables_account_id: return Result.failure(["Customer or its A/R account not found."])
            entity_name_for_desc = customer.name; ap_ar_account_id = customer.receivables_account_id
        else: # Vendor
            vendor = await self.vendor_service.get_by_id(dto.entity_id)
            if not vendor or not vendor.payables_account_id: return Result.failure(["Vendor or its A/P account not found."])
            entity_name_for_desc = vendor.name; ap_ar_account_id = vendor.payables_account_id
        
        cash_or_bank_gl_id: Optional[int] = None
        if dto.payment_method == PaymentMethodEnum.CASH:
            cash_acc_code = await self.configuration_service.get_config_value("SysAcc_DefaultCash", "1112")
            cash_acc = await self.account_service.get_by_code(cash_acc_code) if cash_acc_code else None
            if not cash_acc or not cash_acc.is_active: return Result.failure(["Default Cash account is not configured or inactive."])
            cash_or_bank_gl_id = cash_acc.id
        else:
            if dto.bank_account_id is None: return Result.failure(["Bank Account ID is missing for non-cash payment."])
            bank_account = await self.bank_account_service.get_by_id(dto.bank_account_id)
            if not bank_account or not bank_account.gl_account_id: return Result.failure(["Bank account or its GL link not found."])
            cash_or_bank_gl_id = bank_account.gl_account_id
        
        total_payment_in_base = dto.amount * dto.exchange_rate
        total_ar_ap_cleared_base = Decimal(0)
        
        for alloc in payment_orm.allocations:
            invoice_orm: Union[SalesInvoice, PurchaseInvoice, None] = None
            if alloc.document_type == PaymentAllocationDocTypeEnum.SALES_INVOICE.value:
                invoice_orm = await session.get(SalesInvoice, alloc.document_id)
            elif alloc.document_type == PaymentAllocationDocTypeEnum.PURCHASE_INVOICE.value:
                invoice_orm = await session.get(PurchaseInvoice, alloc.document_id)
            if invoice_orm: total_ar_ap_cleared_base += alloc.amount * invoice_orm.exchange_rate
        
        if dto.currency_code != base_currency and total_ar_ap_cleared_base == 0 and len(payment_orm.allocations)>0:
            return Result.failure(["Cannot determine original base currency amount for allocated invoices."])
        elif total_ar_ap_cleared_base == 0:
            total_ar_ap_cleared_base = total_payment_in_base # For on-account payments

        wht_amount_base = Decimal(0)
        if dto.apply_withholding_tax and dto.withholding_tax_amount is not None:
            wht_amount_base = dto.withholding_tax_amount * dto.exchange_rate
            cash_paid_base = total_payment_in_base - wht_amount_base
        else:
            cash_paid_base = total_payment_in_base
        
        forex_gain_loss = total_ar_ap_cleared_base - total_payment_in_base
        
        desc_suffix = f"Pmt No: {payment_orm.payment_no} for {entity_name_for_desc}"
        if dto.payment_type == PaymentTypeEnum.CUSTOMER_PAYMENT:
            je_lines_data.append(JournalEntryLineData(account_id=cash_or_bank_gl_id, debit_amount=cash_paid_base, credit_amount=Decimal(0)))
            je_lines_data.append(JournalEntryLineData(account_id=ap_ar_account_id, debit_amount=Decimal(0), credit_amount=total_ar_ap_cleared_base))
            if forex_gain_loss > 0: # Loss for AR
                loss_acc_code = await self.configuration_service.get_config_value("SysAcc_ForexLoss", "8200")
                loss_acc = await self.account_service.get_by_code(loss_acc_code); 
                if not loss_acc: return Result.failure(["Forex Loss account not configured."])
                je_lines_data.append(JournalEntryLineData(account_id=loss_acc.id, debit_amount=forex_gain_loss, credit_amount=Decimal(0)))
            elif forex_gain_loss < 0: # Gain for AR
                gain_acc_code = await self.configuration_service.get_config_value("SysAcc_ForexGain", "7200")
                gain_acc = await self.account_service.get_by_code(gain_acc_code); 
                if not gain_acc: return Result.failure(["Forex Gain account not configured."])
                je_lines_data.append(JournalEntryLineData(account_id=gain_acc.id, debit_amount=Decimal(0), credit_amount=-forex_gain_loss))
        
        else: # Vendor Payment
            je_lines_data.append(JournalEntryLineData(account_id=ap_ar_account_id, debit_amount=total_ar_ap_cleared_base, credit_amount=Decimal(0)))
            je_lines_data.append(JournalEntryLineData(account_id=cash_or_bank_gl_id, debit_amount=Decimal(0), credit_amount=cash_paid_base))
            if wht_amount_base > 0:
                wht_acc_code = await self.configuration_service.get_config_value("SysAcc_WHTPayable", "2130")
                wht_acc = await self.account_service.get_by_code(wht_acc_code)
                if not wht_acc: return Result.failure(["WHT Payable account not configured."])
                je_lines_data.append(JournalEntryLineData(account_id=wht_acc.id, debit_amount=Decimal(0), credit_amount=wht_amount_base))
            
            if forex_gain_loss > 0: # Gain for AP
                gain_acc_code = await self.configuration_service.get_config_value("SysAcc_ForexGain", "7200")
                gain_acc = await self.account_service.get_by_code(gain_acc_code)
                if not gain_acc: return Result.failure(["Forex Gain account not configured."])
                je_lines_data.append(JournalEntryLineData(account_id=gain_acc.id, debit_amount=Decimal(0), credit_amount=forex_gain_loss))
            elif forex_gain_loss < 0: # Loss for AP
                loss_acc_code = await self.configuration_service.get_config_value("SysAcc_ForexLoss", "8200")
                loss_acc = await self.account_service.get_by_code(loss_acc_code)
                if not loss_acc: return Result.failure(["Forex Loss account not configured."])
                je_lines_data.append(JournalEntryLineData(account_id=loss_acc.id, debit_amount=-forex_gain_loss, credit_amount=Decimal(0)))

        for line in je_lines_data: line.description = desc_suffix
        
        return Result.success(JournalEntryData(
            journal_type=JournalTypeEnum.CASH_RECEIPT.value if dto.payment_type == PaymentTypeEnum.CUSTOMER_PAYMENT else JournalTypeEnum.CASH_DISBURSEMENT.value,
            entry_date=dto.payment_date, description=f"{dto.payment_type.value} - {entity_name_for_desc}",
            reference=dto.reference or payment_orm.payment_no, user_id=dto.user_id, lines=je_lines_data,
            source_type="Payment", source_id=payment_orm.id ))

    async def create_payment(self, dto: PaymentCreateData) -> Result[Payment]:
        async with self.app_core.db_manager.session() as session: 
            try:
                validation_errors = await self._validate_payment_data(dto, session=session)
                if validation_errors: return Result.failure(validation_errors)
                payment_no_str = await self.sequence_service.get_next_sequence("payment") 
                if not payment_no_str: return Result.failure(["Failed to generate payment number."])

                payment_orm = Payment(
                    payment_no=payment_no_str, payment_type=dto.payment_type.value, payment_method=dto.payment_method.value, payment_date=dto.payment_date,
                    entity_type=dto.entity_type.value, entity_id=dto.entity_id, bank_account_id=dto.bank_account_id, currency_code=dto.currency_code,
                    exchange_rate=dto.exchange_rate, amount=dto.amount, reference=dto.reference, description=dto.description, cheque_no=dto.cheque_no,
                    status=PaymentStatusEnum.APPROVED.value, created_by_user_id=dto.user_id, updated_by_user_id=dto.user_id )
                for alloc_dto in dto.allocations:
                    payment_orm.allocations.append(PaymentAllocation(document_type=alloc_dto.document_type.value, document_id=alloc_dto.document_id, amount=alloc_dto.amount_allocated, created_by_user_id=dto.user_id))
                session.add(payment_orm); await session.flush(); await session.refresh(payment_orm)

                je_data_result = await self._build_payment_je(dto, payment_orm, session=session)
                if not je_data_result.is_success: raise Exception(f"Failed to build JE: {', '.join(je_data_result.errors)}")
                
                je_dto = je_data_result.value; assert je_dto is not None
                create_je_result = await self.journal_entry_manager.create_journal_entry(je_dto, session=session)
                if not create_je_result.is_success or not create_je_result.value: raise Exception(f"Failed to create JE for payment: {', '.join(create_je_result.errors)}") 
                
                created_je: JournalEntry = create_je_result.value
                post_je_result = await self.journal_entry_manager.post_journal_entry(created_je.id, dto.user_id, session=session)
                if not post_je_result.is_success: raise Exception(f"JE (ID: {created_je.id}) created but failed to post: {', '.join(post_je_result.errors)}")

                payment_orm.journal_entry_id = created_je.id; session.add(payment_orm) 
                
                for alloc_orm in payment_orm.allocations:
                    if alloc_orm.document_type == PaymentAllocationDocTypeEnum.SALES_INVOICE.value:
                        inv = await session.get(SalesInvoice, alloc_orm.document_id)
                        if inv: inv.amount_paid = (inv.amount_paid or Decimal(0)) + alloc_orm.amount; inv.status = InvoiceStatusEnum.PAID.value if inv.amount_paid >= inv.total_amount else InvoiceStatusEnum.PARTIALLY_PAID.value; session.add(inv)
                    elif alloc_orm.document_type == PaymentAllocationDocTypeEnum.PURCHASE_INVOICE.value:
                        inv = await session.get(PurchaseInvoice, alloc_orm.document_id)
                        if inv: inv.amount_paid = (inv.amount_paid or Decimal(0)) + alloc_orm.amount; inv.status = InvoiceStatusEnum.PAID.value if inv.amount_paid >= inv.total_amount else InvoiceStatusEnum.PARTIALLY_PAID.value; session.add(inv)

                await session.flush(); await session.refresh(payment_orm, attribute_names=['allocations', 'journal_entry']) 
                self.logger.info(f"Payment '{payment_orm.payment_no}' created and posted successfully. JE ID: {created_je.id}"); return Result.success(payment_orm)
            except Exception as e:
                self.logger.error(f"Error in create_payment transaction: {e}", exc_info=True); return Result.failure([f"Failed to create payment: {str(e)}"])

    async def get_payment_for_dialog(self, payment_id: int) -> Optional[Payment]:
        try: return await self.payment_service.get_by_id(payment_id)
        except Exception as e: self.logger.error(f"Error fetching Payment ID {payment_id} for dialog: {e}", exc_info=True); return None

    async def get_payments_for_listing(self, entity_type: Optional[PaymentEntityTypeEnum] = None, entity_id: Optional[int] = None, status_list: Optional[List[PaymentStatusEnum]] = None, start_date: Optional[date] = None, end_date: Optional[date] = None, page: int = 1, page_size: int = 50) -> Result[List[PaymentSummaryData]]:
        try:
            summaries = await self.payment_service.get_all_summary(entity_type=entity_type, entity_id=entity_id, status_list=status_list, start_date=start_date, end_date=end_date, page=page, page_size=page_size)
            return Result.success(summaries)
        except Exception as e: self.logger.error(f"Error fetching payment listing: {e}", exc_info=True); return Result.failure([f"Failed to retrieve payment list: {str(e)}"])
```

#### **File 2: `app/tax/tax_calculator.py` (Corrected)**
This manager is updated to use the `app_core` dependency injection pattern.

```python
# File: app/tax/tax_calculator.py
from decimal import Decimal
from typing import List, Optional, Any, TYPE_CHECKING

from app.utils.pydantic_models import TaxCalculationResultData, TransactionTaxData, TransactionLineTaxData
from app.models.accounting.tax_code import TaxCode as TaxCodeModel

if TYPE_CHECKING:
    from app.services.tax_service import TaxCodeService
    from app.core.application_core import ApplicationCore

class TaxCalculator:
    def __init__(self, app_core: "ApplicationCore"):
        self.app_core = app_core
        self.tax_code_service: "TaxCodeService" = self.app_core.tax_code_service
    
    async def calculate_transaction_taxes(self, transaction_data: TransactionTaxData) -> List[dict]:
        results = []
        for line in transaction_data.lines:
            tax_result: TaxCalculationResultData = await self.calculate_line_tax(
                line.amount,
                line.tax_code,
                transaction_data.transaction_type,
                line.account_id 
            )
            results.append({ 
                'line_index': line.index,
                'tax_amount': tax_result.tax_amount,
                'tax_account_id': tax_result.tax_account_id,
                'taxable_amount': tax_result.taxable_amount
            })
        return results
    
    async def calculate_line_tax(self, amount: Decimal, tax_code_str: Optional[str], 
                                 transaction_type: str, account_id: Optional[int] = None) -> TaxCalculationResultData:
        result = TaxCalculationResultData(
            tax_amount=Decimal(0),
            tax_account_id=None,
            taxable_amount=amount
        )
        
        if not tax_code_str or abs(amount) < Decimal("0.01"):
            return result
        
        tax_code_info: Optional[TaxCodeModel] = await self.tax_code_service.get_tax_code(tax_code_str)
        if not tax_code_info:
            return result 
        
        if tax_code_info.tax_type == 'GST':
            return await self._calculate_gst(amount, tax_code_info, transaction_type)
        elif tax_code_info.tax_type == 'Withholding Tax':
            return await self._calculate_withholding_tax(amount, tax_code_info, transaction_type)
        return result
    
    async def _calculate_gst(self, amount: Decimal, tax_code_info: TaxCodeModel, transaction_type: str) -> TaxCalculationResultData:
        tax_rate = Decimal(str(tax_code_info.rate))
        net_amount = amount 
        tax_amount = net_amount * tax_rate / Decimal(100)
        tax_amount = tax_amount.quantize(Decimal("0.01"))
        
        return TaxCalculationResultData(
            tax_amount=tax_amount,
            tax_account_id=tax_code_info.affects_account_id,
            taxable_amount=net_amount
        )
    
    async def _calculate_withholding_tax(self, amount: Decimal, tax_code_info: TaxCodeModel, transaction_type: str) -> TaxCalculationResultData:
        applicable_transaction_types = ['Purchase Payment', 'Expense Payment'] 
        if transaction_type not in applicable_transaction_types:
            return TaxCalculationResultData(
                tax_amount=Decimal(0), tax_account_id=None, taxable_amount=amount
            )
        
        tax_rate = Decimal(str(tax_code_info.rate))
        tax_amount = amount * tax_rate / Decimal(100)
        tax_amount = tax_amount.quantize(Decimal("0.01"))
        
        return TaxCalculationResultData(
            tax_amount=tax_amount,
            tax_account_id=tax_code_info.affects_account_id,
            taxable_amount=amount
        )
```

#### **File 3: `app/reporting/dashboard_manager.py` (Corrected)**
This manager is updated to use the `app_core` dependency injection pattern.

```python
# File: app/reporting/dashboard_manager.py
from typing import Optional, TYPE_CHECKING, List, Dict
from datetime import date
from decimal import Decimal

from app.utils.pydantic_models import DashboardKPIData
from app.models.accounting.fiscal_year import FiscalYear 
from app.models.accounting.account import Account

if TYPE_CHECKING:
    from app.core.application_core import ApplicationCore

CURRENT_ASSET_SUBTYPES = ["Cash and Cash Equivalents", "Accounts Receivable", "Inventory", "Prepaid Expenses", "Other Current Assets", "Current Asset"]
CURRENT_LIABILITY_SUBTYPES = ["Accounts Payable", "Accrued Liabilities", "Short-Term Loans", "Current Portion of Long-Term Debt", "GST Payable", "Other Current Liabilities", "Current Liability"]
NON_CURRENT_LIABILITY_SUBTYPES = ["Long-term Liability", "Long-Term Loans"]

class DashboardManager:
    def __init__(self, app_core: "ApplicationCore"):
        self.app_core = app_core
        self.logger = app_core.logger

    async def get_dashboard_kpis(self, as_of_date: Optional[date] = None) -> Optional[DashboardKPIData]:
        try:
            effective_date = as_of_date if as_of_date is not None else date.today()
            self.logger.info(f"Fetching dashboard KPIs as of {effective_date}...")
            
            company_settings = await self.app_core.company_settings_service.get_company_settings()
            if not company_settings: self.logger.error("Company settings not found."); return None
            base_currency = company_settings.base_currency

            all_fiscal_years_orm: List[FiscalYear] = await self.app_core.fiscal_year_service.get_all()
            current_fy: Optional[FiscalYear] = next((fy for fy in sorted(all_fiscal_years_orm, key=lambda fy: fy.start_date, reverse=True) if fy.start_date <= effective_date <= fy.end_date and not fy.is_closed), None)
            if not current_fy: current_fy = next((fy for fy in sorted(all_fiscal_years_orm, key=lambda fy: fy.start_date, reverse=True) if not fy.is_closed), None)
            if not current_fy and all_fiscal_years_orm: current_fy = max(all_fiscal_years_orm, key=lambda fy: fy.start_date)

            total_revenue_ytd, total_expenses_ytd, net_profit_ytd = Decimal(0), Decimal(0), Decimal(0)
            kpi_period_description = f"As of {effective_date.strftime('%d %b %Y')} (No active FY)"
            if current_fy and effective_date >= current_fy.start_date:
                effective_end_date_for_ytd = min(effective_date, current_fy.end_date)
                kpi_period_description = f"YTD as of {effective_end_date_for_ytd.strftime('%d %b %Y')} (FY: {current_fy.year_name})"
                pl_data = await self.app_core.financial_statement_generator.generate_profit_loss(current_fy.start_date, effective_end_date_for_ytd)
                if pl_data:
                    total_revenue_ytd, total_expenses_ytd, net_profit_ytd = pl_data.get('revenue', {}).get('total', Decimal(0)), pl_data.get('expenses', {}).get('total', Decimal(0)), pl_data.get('net_profit', Decimal(0))
            elif current_fy:
                 kpi_period_description = f"As of {effective_date.strftime('%d %b %Y')} (FY: {current_fy.year_name} not started)"

            current_cash_balance = await self._get_total_cash_balance(base_currency, effective_date)
            total_outstanding_ar = await self.app_core.customer_service.get_total_outstanding_balance(); total_outstanding_ap = await self.app_core.vendor_service.get_total_outstanding_balance()
            total_ar_overdue = await self.app_core.customer_service.get_total_overdue_balance(); total_ap_overdue = await self.app_core.vendor_service.get_total_overdue_balance() 
            ar_aging_summary = await self.app_core.customer_service.get_ar_aging_summary(effective_date); ap_aging_summary = await self.app_core.vendor_service.get_ap_aging_summary(effective_date)

            total_current_assets, total_current_liabilities, total_non_current_liabilities, total_inventory, total_equity = (Decimal(0) for _ in range(5))
            all_active_accounts: List[Account] = await self.app_core.account_service.get_all_active()

            for acc in all_active_accounts:
                balance = await self.app_core.journal_service.get_account_balance(acc.id, effective_date)
                if acc.account_type == "Asset":
                    if acc.sub_type in CURRENT_ASSET_SUBTYPES: total_current_assets += balance
                    if acc.sub_type == "Inventory": total_inventory += balance
                elif acc.account_type == "Liability":
                    if acc.sub_type in CURRENT_LIABILITY_SUBTYPES: total_current_liabilities -= balance # Liabilities have negative balance
                    elif acc.sub_type in NON_CURRENT_LIABILITY_SUBTYPES: total_non_current_liabilities -= balance # Liabilities have negative balance
                elif acc.account_type == "Equity": total_equity -= balance # Equity has negative balance

            total_liabilities = total_current_liabilities + total_non_current_liabilities
            
            quick_ratio: Optional[Decimal] = None
            if total_current_liabilities > 0: quick_ratio = ((total_current_assets - total_inventory) / total_current_liabilities).quantize(Decimal("0.01"))
            elif (total_current_assets - total_inventory) > 0: quick_ratio = Decimal('inf')

            debt_to_equity_ratio: Optional[Decimal] = None
            if total_equity > 0: debt_to_equity_ratio = (total_liabilities / total_equity).quantize(Decimal("0.01"))
            elif total_liabilities > 0: debt_to_equity_ratio = Decimal('inf')

            current_ratio: Optional[Decimal] = None
            if total_current_liabilities > 0: current_ratio = (total_current_assets / total_current_liabilities).quantize(Decimal("0.01"))
            elif total_current_assets > 0: current_ratio = Decimal('inf')

            return DashboardKPIData(
                kpi_period_description=kpi_period_description, base_currency=base_currency,
                total_revenue_ytd=total_revenue_ytd, total_expenses_ytd=total_expenses_ytd, net_profit_ytd=net_profit_ytd,
                current_cash_balance=current_cash_balance, total_outstanding_ar=total_outstanding_ar, total_outstanding_ap=total_outstanding_ap,
                total_ar_overdue=total_ar_overdue, total_ap_overdue=total_ap_overdue,
                ar_aging_current=ar_aging_summary.get("Current", Decimal(0)), ar_aging_1_30=ar_aging_summary.get("1-30 Days", Decimal(0)),
                ar_aging_31_60=ar_aging_summary.get("31-60 Days", Decimal(0)), ar_aging_61_90=ar_aging_summary.get("61-90 Days", Decimal(0)),
                ar_aging_91_plus=ar_aging_summary.get("91+ Days", Decimal(0)),
                ap_aging_current=ap_aging_summary.get("Current", Decimal(0)), ap_aging_1_30=ap_aging_summary.get("1-30 Days", Decimal(0)),
                ap_aging_31_60=ap_aging_summary.get("31-60 Days", Decimal(0)), ap_aging_61_90=ap_aging_summary.get("61-90 Days", Decimal(0)),
                ap_aging_91_plus=ap_aging_summary.get("91+ Days", Decimal(0)),
                total_current_assets=total_current_assets.quantize(Decimal("0.01")), total_current_liabilities=total_current_liabilities.quantize(Decimal("0.01")),
                total_inventory=total_inventory.quantize(Decimal("0.01")), total_liabilities=total_liabilities.quantize(Decimal("0.01")), total_equity=total_equity.quantize(Decimal("0.01")),
                current_ratio=current_ratio, quick_ratio=quick_ratio, debt_to_equity_ratio=debt_to_equity_ratio
            )
        except Exception as e:
            self.logger.error(f"Error fetching dashboard KPIs: {e}", exc_info=True)
            return None

    async def _get_total_cash_balance(self, base_currency: str, as_of_date: date) -> Decimal:
        active_bank_accounts_summary = await self.app_core.bank_account_service.get_all_summary(active_only=True, currency_code=base_currency, page_size=-1)
        total_cash = sum(ba.current_balance for ba in active_bank_accounts_summary if ba.currency_code == base_currency and ba.current_balance is not None)
        cash_on_hand_code = await self.app_core.configuration_service.get_config_value("SysAcc_DefaultCash")
        if cash_on_hand_code:
            cash_on_hand_acc = await self.app_core.account_service.get_by_code(cash_on_hand_code)
            if cash_on_hand_acc and cash_on_hand_acc.is_active:
                linked_bank_acc_check = await self.app_core.bank_account_service.get_by_gl_account_id(cash_on_hand_acc.id)
                if not linked_bank_acc_check:
                    total_cash += await self.app_core.journal_service.get_account_balance(cash_on_hand_acc.id, as_of_date)
        return total_cash.quantize(Decimal("0.01"))
```

This completes the refactoring for another set of managers. Please confirm, and I will proceed with the final batch.

