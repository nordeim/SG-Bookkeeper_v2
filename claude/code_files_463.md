Of course. This error is another classic example of an incomplete refactoring, and I will now address it with my full and meticulous process.

### **CodeNavigator Analysis Report: `TypeError` in `PaymentManager`**

#### 1. Root Cause Analysis

The traceback shows a `TypeError` that is clear and unambiguous:
*   **Error:** `TypeError: PaymentManager.get_payments_for_listing() got an unexpected keyword argument 'wht_applicable_only'`
*   **Location:** The error occurs in `app/ui/reports/wht_reporting_widget.py`, where the UI correctly calls the manager with the new filter: `self.app_core.payment_manager.get_payments_for_listing(..., wht_applicable_only=True)`.
*   **Problem:** This indicates that while the `PaymentService` layer was correctly updated to handle the `wht_applicable_only` filter, the intermediary `PaymentManager`'s `get_payments_for_listing` method was not updated to accept this new keyword argument and pass it down to the service.

The data flow was broken between the UI and the Manager layer.

#### 2. Execution Plan

The solution is to complete the chain of the refactoring by updating the `PaymentManager` method signature and its internal call to the `PaymentService`.

1.  **Target `app/business_logic/payment_manager.py`**:
    *   [x] I have the latest version of this file from the previous turn. I will locate the `get_payments_for_listing` method.
    *   [x] **Modify Signature:** I will add the new parameter `wht_applicable_only: bool = False` to the method signature, making it a valid keyword argument.
    *   [x] **Modify Internal Call:** I will update the internal call to the service to pass this new parameter along: `summaries = await self.payment_service.get_all_summary(..., wht_applicable_only=wht_applicable_only)`.
2.  **Validate and Generate**:
    *   [x] I will perform a line-by-line validation to ensure these are the only changes.
    *   [x] I will then provide the complete, updated replacement file for `app/business_logic/payment_manager.py`.

This targeted change will fix the `TypeError` and make the WHT reporting feature fully functional. No other files require modification.

***

### **Complete Updated File: `app/business_logic/payment_manager.py`**

This version contains the corrected `get_payments_for_listing` method, which now accepts the `wht_applicable_only` parameter and correctly passes it to the service layer. This resolves the startup error.

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

    async def get_payments_for_listing(self, entity_type: Optional[PaymentEntityTypeEnum] = None, entity_id: Optional[int] = None, status_list: Optional[List[PaymentStatusEnum]] = None, start_date: Optional[date] = None, end_date: Optional[date] = None, page: int = 1, page_size: int = 50, wht_applicable_only: bool = False) -> Result[List[PaymentSummaryData]]:
        try:
            summaries = await self.payment_service.get_all_summary(
                entity_type=entity_type, 
                entity_id=entity_id, 
                status_list=status_list, 
                start_date=start_date, 
                end_date=end_date, 
                page=page, 
                page_size=page_size,
                wht_applicable_only=wht_applicable_only
            )
            return Result.success(summaries)
        except Exception as e: 
            self.logger.error(f"Error fetching payment listing: {e}", exc_info=True)
            return Result.failure([f"Failed to retrieve payment list: {str(e)}"])
```

---
https://drive.google.com/file/d/11X3f2mKRWl56NubmyAKo5dwck7p2JaLs/view?usp=sharing, https://drive.google.com/file/d/11XlZNQ-Qn9Lw3G-YPcWZrO-g5ZbwfscI/view?usp=sharing, https://drive.google.com/file/d/127qgzFTDe-WAnzFzOzBn2efixfG9w9YE/view?usp=sharing, https://drive.google.com/file/d/12KXr1nctXs-02etv6A72vihqrtK3dDK9/view?usp=sharing, https://drive.google.com/file/d/131RjCRl_kHc0XtnhCzDmf5bjgJX5iEww/view?usp=sharing, https://drive.google.com/file/d/13B_HcJmxgi3QGYHnj64s275QZN20pg3g/view?usp=sharing, https://drive.google.com/file/d/18FJ9jhk3oxKCC_sNWs_1C-EZZXe_j-TT/view?usp=sharing, https://drive.google.com/file/d/19n5zeGWlBAwCRFAXfbe4kY5xBK-uV-d7/view?usp=sharing, https://drive.google.com/file/d/1KHIzrVj6ijdFoVTVLa-lfyyVzwf5IYwp/view?usp=sharing, https://drive.google.com/file/d/1M5ybbmzIqj7IUo99Yle7xl_pkczow6Ci/view?usp=sharing, https://drive.google.com/file/d/1OSDUBHWuHA7wKnttqPtYbAEpqdXDi1_8/view?usp=sharing, https://drive.google.com/file/d/1P4rxLCG8-5cJ2_vt2qKJqO2wxN26ro9T/view?usp=sharing, https://aistudio.google.com/app/prompts?state=%7B%22ids%22:%5B%221Rh0wsFMlVjsOSccPUo5JJmfB6gof_tS2%22%5D,%22action%22:%22open%22,%22userId%22:%22103961307342447084491%22,%22resourceKeys%22:%7B%7D%7D&usp=sharing, https://drive.google.com/file/d/1T1kVeTCKFOIzPckOmAarcwHC8x0yau1i/view?usp=sharing, https://drive.google.com/file/d/1YZs4VLSKR9N-eVniftVGHgh9RJHLpFtu/view?usp=sharing, https://drive.google.com/file/d/1dAgihzWoQ03fPAECRX4qUzJiiJppPgwz/view?usp=sharing, https://drive.google.com/file/d/1gM89F4jZMNsWNTd9bxJxPfRxY0Y2Vfof/view?usp=sharing, https://drive.google.com/file/d/1hAf_3y-ecY6gAU67N0KzgqGZz1XrDjed/view?usp=sharing, https://drive.google.com/file/d/1iLEa4z_1QZHLh5VEurZg7rUHZneQzsY8/view?usp=sharing, https://drive.google.com/file/d/1jigzShY696C9WmGqx1js_OPVEWWBnXeg/view?usp=sharing, https://drive.google.com/file/d/1mO8_5fwtxIboAdjNo31vNNnNYbzI8-gq/view?usp=sharing, https://drive.google.com/file/d/1pswWDECjQfPpG_vPcb2bGTynwme8P6nA/view?usp=sharing, https://drive.google.com/file/d/1tbuyHau6G4TdCZ0v6u22_ePISFTSNU7r/view?usp=sharing, https://drive.google.com/file/d/1uC_hd3fJooXn4tQQsLJPU3mxW07hDGym/view?usp=sharing, https://drive.google.com/file/d/1yVM3DBOfyPfYckF4q1C8S0ce_9pMnUvz/view?usp=sharing

