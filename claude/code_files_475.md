Excellent. The startup log is now clean, indicating that all managers called during the initial dashboard load have been successfully refactored.

I have reviewed my plan and the provided file list. There are two remaining manager files that still need to be updated to complete the architectural refactoring across the entire business logic layer: `SalesInvoiceManager` and `PurchaseInvoiceManager`.

I will now provide the complete, updated replacement files for this final set.

### **CodeNavigator Analysis and Execution Plan (Manager Refactoring - Final Set)**

**Goal:** Complete the architectural refactoring by updating the `SalesInvoiceManager` and `PurchaseInvoiceManager` to use the `app_core` dependency injection pattern. This will ensure every manager in the application follows the same clean, maintainable design.

**Plan for Each File:**
1.  **Modify `__init__` Signature:** Change the constructor to `def __init__(self, app_core: "ApplicationCore"):`.
2.  **Update Attribute Initialization:** Remove the verbose list of `__init__` parameters and service assignments. Initialize all required service instances from the `app_core` object.
3.  **Validate and Generate:** Perform a line-by-line comparison to ensure only the constructor is changed and that no business logic is altered. Generate the complete, updated file.

This process will be applied to the final two manager files.

***

### **Complete Updated Files (Set 3 of 3)**

Here are the final two refactored manager files.

#### **File 1: `app/business_logic/sales_invoice_manager.py` (Corrected)**

```python
# File: app/business_logic/sales_invoice_manager.py
from typing import List, Optional, Dict, Any, TYPE_CHECKING, Union, cast
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from datetime import date, datetime 

from sqlalchemy import text 
from sqlalchemy.orm import selectinload 

from app.models.business.sales_invoice import SalesInvoice, SalesInvoiceLine
from app.models.business.customer import Customer
from app.models.business.product import Product
from app.models.accounting.journal_entry import JournalEntry 
from app.models.business.inventory_movement import InventoryMovement 

from app.utils.result import Result
from app.utils.pydantic_models import (
    SalesInvoiceCreateData, SalesInvoiceUpdateData, SalesInvoiceLineBaseData,
    SalesInvoiceSummaryData, TaxCalculationResultData,
    JournalEntryData, JournalEntryLineData 
)
from app.common.enums import InvoiceStatusEnum, ProductTypeEnum, JournalTypeEnum, InventoryMovementTypeEnum 

if TYPE_CHECKING:
    from app.core.application_core import ApplicationCore
    from app.services.business_services import SalesInvoiceService, CustomerService, ProductService, InventoryMovementService
    from app.services.core_services import SequenceService, ConfigurationService
    from app.services.tax_service import TaxCodeService
    from app.services.account_service import AccountService
    from app.tax.tax_calculator import TaxCalculator
    from app.models.accounting.tax_code import TaxCode

class SalesInvoiceManager:
    def __init__(self, app_core: "ApplicationCore"): 
        self.app_core = app_core
        self.sales_invoice_service: "SalesInvoiceService" = self.app_core.sales_invoice_service
        self.customer_service: "CustomerService" = self.app_core.customer_service
        self.product_service: "ProductService" = self.app_core.product_service
        self.tax_code_service: "TaxCodeService" = self.app_core.tax_code_service
        self.tax_calculator: "TaxCalculator" = self.app_core.tax_calculator
        self.sequence_service: "SequenceService" = self.app_core.sequence_service
        self.account_service: "AccountService" = self.app_core.account_service
        self.configuration_service: "ConfigurationService" = self.app_core.configuration_service
        self.inventory_movement_service: "InventoryMovementService" = self.app_core.inventory_movement_service
        self.logger = self.app_core.logger

    async def _validate_and_prepare_invoice_data(
        self, 
        dto: Union[SalesInvoiceCreateData, SalesInvoiceUpdateData],
        is_update: bool = False 
    ) -> Result[Dict[str, Any]]:
        errors: List[str] = []
        customer = await self.customer_service.get_by_id(dto.customer_id)
        if not customer: errors.append(f"Customer with ID {dto.customer_id} not found.")
        elif not customer.is_active: errors.append(f"Customer '{customer.name}' (ID: {dto.customer_id}) is not active.")
        if not dto.currency_code or len(dto.currency_code) != 3: errors.append(f"Invalid currency code: '{dto.currency_code}'.")
        else:
           currency_obj = await self.app_core.currency_manager.get_currency_by_code(dto.currency_code)
           if not currency_obj or not currency_obj.is_active: errors.append(f"Currency '{dto.currency_code}' is invalid or not active.")
        calculated_lines_for_orm: List[Dict[str, Any]] = []; invoice_subtotal_calc = Decimal(0); invoice_total_tax_calc = Decimal(0)
        if not dto.lines: errors.append("Sales invoice must have at least one line item.")
        for i, line_dto in enumerate(dto.lines):
            line_errors_current_line: List[str] = []; product: Optional[Product] = None; line_description = line_dto.description
            unit_price = line_dto.unit_price; line_sales_account_id: Optional[int] = None; product_type_for_line: Optional[ProductTypeEnum] = None
            if line_dto.product_id:
                product = await self.product_service.get_by_id(line_dto.product_id)
                if not product: line_errors_current_line.append(f"Product ID {line_dto.product_id} not found on line {i+1}.")
                elif not product.is_active: line_errors_current_line.append(f"Product '{product.name}' is not active on line {i+1}.")
                if product: 
                    if not line_description: line_description = product.name
                    if (unit_price is None or unit_price == Decimal(0)) and product.sales_price is not None: unit_price = product.sales_price
                    line_sales_account_id = product.sales_account_id; product_type_for_line = ProductTypeEnum(product.product_type)
            if not line_description: line_errors_current_line.append(f"Description is required on line {i+1}.")
            if unit_price is None: line_errors_current_line.append(f"Unit price is required on line {i+1}."); unit_price = Decimal(0) 
            try:
                qty = Decimal(str(line_dto.quantity)); price = Decimal(str(unit_price)); discount_pct = Decimal(str(line_dto.discount_percent))
                if qty <= 0: line_errors_current_line.append(f"Quantity must be positive on line {i+1}.")
                if price < 0: line_errors_current_line.append(f"Unit price cannot be negative on line {i+1}.")
                if not (0 <= discount_pct <= 100): line_errors_current_line.append(f"Discount percent must be between 0 and 100 on line {i+1}.")
            except InvalidOperation: line_errors_current_line.append(f"Invalid numeric for qty/price/disc on line {i+1}."); errors.extend(line_errors_current_line); continue
            discount_amount = (qty * price * (discount_pct / Decimal(100))).quantize(Decimal("0.0001"), ROUND_HALF_UP)
            line_subtotal_before_tax = (qty * price) - discount_amount; line_tax_amount_calc = Decimal(0); line_tax_account_id: Optional[int] = None 
            if line_dto.tax_code:
                tax_calc_result: TaxCalculationResultData = await self.tax_calculator.calculate_line_tax(amount=line_subtotal_before_tax, tax_code_str=line_dto.tax_code, transaction_type="SalesInvoiceLine")
                line_tax_amount_calc = tax_calc_result.tax_amount; line_tax_account_id = tax_calc_result.tax_account_id 
                if tax_calc_result.tax_account_id is None and line_tax_amount_calc > Decimal(0): 
                    tc_check_orm = await self.tax_code_service.get_tax_code(line_dto.tax_code)
                    if not tc_check_orm or not tc_check_orm.is_active: line_errors_current_line.append(f"Tax code '{line_dto.tax_code}' used on line {i+1} is invalid or inactive.")
            invoice_subtotal_calc += line_subtotal_before_tax; invoice_total_tax_calc += line_tax_amount_calc
            if line_errors_current_line: errors.extend(line_errors_current_line)
            calculated_lines_for_orm.append({
                "product_id": line_dto.product_id, "description": line_description, "quantity": qty, "unit_price": price, "discount_percent": discount_pct,
                "discount_amount": discount_amount.quantize(Decimal("0.01"), ROUND_HALF_UP), "line_subtotal": line_subtotal_before_tax.quantize(Decimal("0.01"), ROUND_HALF_UP), 
                "tax_code": line_dto.tax_code, "tax_amount": line_tax_amount_calc, "line_total": (line_subtotal_before_tax + line_tax_amount_calc).quantize(Decimal("0.01"), ROUND_HALF_UP),
                "dimension1_id": line_dto.dimension1_id, "dimension2_id": line_dto.dimension2_id,
                "_line_sales_account_id": line_sales_account_id, "_line_tax_account_id": line_tax_account_id, "_product_type": product_type_for_line
            })
        if errors: return Result.failure(errors)
        invoice_grand_total = invoice_subtotal_calc + invoice_total_tax_calc
        return Result.success({
            "header_dto": dto, "customer_orm": customer, "calculated_lines_for_orm": calculated_lines_for_orm,
            "invoice_subtotal": invoice_subtotal_calc.quantize(Decimal("0.01"), ROUND_HALF_UP),
            "invoice_total_tax": invoice_total_tax_calc.quantize(Decimal("0.01"), ROUND_HALF_UP),
            "invoice_grand_total": invoice_grand_total.quantize(Decimal("0.01"), ROUND_HALF_UP),
        })

    async def create_draft_invoice(self, dto: SalesInvoiceCreateData) -> Result[SalesInvoice]:
        preparation_result = await self._validate_and_prepare_invoice_data(dto)
        if not preparation_result.is_success: return Result.failure(preparation_result.errors)
        prepared_data = preparation_result.value; assert prepared_data is not None 
        header_dto = cast(SalesInvoiceCreateData, prepared_data["header_dto"])
        try:
            invoice_no_val = await self.app_core.db_manager.execute_scalar("SELECT core.get_next_sequence_value($1);", "sales_invoice")
            if not invoice_no_val or not isinstance(invoice_no_val, str): return Result.failure(["Failed to generate invoice number."])
            invoice_no = invoice_no_val
            invoice_orm = SalesInvoice(
                invoice_no=invoice_no, customer_id=header_dto.customer_id, invoice_date=header_dto.invoice_date, due_date=header_dto.due_date,
                currency_code=header_dto.currency_code, exchange_rate=header_dto.exchange_rate, notes=header_dto.notes, 
                terms_and_conditions=header_dto.terms_and_conditions, subtotal=prepared_data["invoice_subtotal"], 
                tax_amount=prepared_data["invoice_total_tax"], total_amount=prepared_data["invoice_grand_total"], 
                amount_paid=Decimal(0), status=InvoiceStatusEnum.DRAFT.value,
                created_by_user_id=header_dto.user_id, updated_by_user_id=header_dto.user_id
            )
            for i, line_data_dict in enumerate(prepared_data["calculated_lines_for_orm"]):
                orm_line_data = {k.lstrip('_'): v for k,v in line_data_dict.items() if not k.startswith('_') and k != "_product_type"}
                invoice_orm.lines.append(SalesInvoiceLine(line_number=i + 1, **orm_line_data))
            saved_invoice = await self.sales_invoice_service.save(invoice_orm)
            return Result.success(saved_invoice)
        except Exception as e: self.logger.error(f"Error creating draft SI: {e}", exc_info=True); return Result.failure([f"Error creating SI: {str(e)}"])

    async def update_draft_invoice(self, invoice_id: int, dto: SalesInvoiceUpdateData) -> Result[SalesInvoice]:
        async with self.app_core.db_manager.session() as session: 
            existing_invoice = await session.get(SalesInvoice, invoice_id, options=[selectinload(SalesInvoice.lines)])
            if not existing_invoice: return Result.failure([f"SI ID {invoice_id} not found."])
            if existing_invoice.status != InvoiceStatusEnum.DRAFT.value: return Result.failure([f"Only draft invoices can be updated. Status: {existing_invoice.status}"])
            preparation_result = await self._validate_and_prepare_invoice_data(dto, is_update=True)
            if not preparation_result.is_success: return Result.failure(preparation_result.errors)
            prepared_data = preparation_result.value; assert prepared_data is not None 
            header_dto = cast(SalesInvoiceUpdateData, prepared_data["header_dto"])
            try:
                existing_invoice.customer_id = header_dto.customer_id; existing_invoice.invoice_date = header_dto.invoice_date
                existing_invoice.due_date = header_dto.due_date; existing_invoice.currency_code = header_dto.currency_code
                existing_invoice.exchange_rate = header_dto.exchange_rate; existing_invoice.notes = header_dto.notes
                existing_invoice.terms_and_conditions = header_dto.terms_and_conditions
                existing_invoice.subtotal = prepared_data["invoice_subtotal"]; existing_invoice.tax_amount = prepared_data["invoice_total_tax"]
                existing_invoice.total_amount = prepared_data["invoice_grand_total"]; existing_invoice.updated_by_user_id = header_dto.user_id
                for line_orm_to_delete in list(existing_invoice.lines): await session.delete(line_orm_to_delete)
                await session.flush() 
                new_lines_orm: List[SalesInvoiceLine] = []
                for i, line_data_dict in enumerate(prepared_data["calculated_lines_for_orm"]):
                    orm_line_data = {k.lstrip('_'): v for k,v in line_data_dict.items() if not k.startswith('_') and k != "_product_type"}
                    new_lines_orm.append(SalesInvoiceLine(line_number=i + 1, **orm_line_data))
                existing_invoice.lines = new_lines_orm 
                await session.flush(); await session.refresh(existing_invoice)
                if existing_invoice.lines: await session.refresh(existing_invoice, attribute_names=['lines'])
                return Result.success(existing_invoice)
            except Exception as e: self.logger.error(f"Error updating draft SI ID {invoice_id}: {e}", exc_info=True); return Result.failure([f"Error updating SI: {str(e)}"])

    async def get_invoice_for_dialog(self, invoice_id: int) -> Optional[SalesInvoice]:
        try: return await self.sales_invoice_service.get_by_id(invoice_id)
        except Exception as e: self.logger.error(f"Error fetching SI ID {invoice_id} for dialog: {e}", exc_info=True); return None


    async def post_invoice(self, invoice_id: int, user_id: int) -> Result[SalesInvoice]:
        async with self.app_core.db_manager.session() as session: # type: ignore
            try:
                invoice_to_post = await session.get(
                    SalesInvoice, invoice_id, 
                    options=[
                        selectinload(SalesInvoice.lines).selectinload(SalesInvoiceLine.product).selectinload(Product.sales_account),
                        selectinload(SalesInvoice.lines).selectinload(SalesInvoiceLine.product).selectinload(Product.inventory_account), 
                        selectinload(SalesInvoice.lines).selectinload(SalesInvoiceLine.product).selectinload(Product.purchase_account), 
                        selectinload(SalesInvoice.lines).selectinload(SalesInvoiceLine.tax_code_obj).selectinload(TaxCode.affects_account), 
                        selectinload(SalesInvoice.customer).selectinload(Customer.receivables_account)
                    ]
                )
                if not invoice_to_post: return Result.failure([f"SI ID {invoice_id} not found."])
                if invoice_to_post.status != InvoiceStatusEnum.DRAFT.value: return Result.failure([f"Only Draft invoices can be posted. Status: {invoice_to_post.status}."])
                if not invoice_to_post.customer or not invoice_to_post.customer.is_active: return Result.failure(["Customer is inactive or not found."])
                if not invoice_to_post.customer.receivables_account_id or not invoice_to_post.customer.receivables_account: return Result.failure([f"Customer '{invoice_to_post.customer.name}' AR account not configured or invalid."])
                ar_account = invoice_to_post.customer.receivables_account
                if not ar_account.is_active: return Result.failure([f"Configured AR account '{ar_account.code}' for customer is inactive."])

                default_sales_acc_code = await self.configuration_service.get_config_value("SysAcc_DefaultSalesRevenue", "4100")
                default_gst_output_acc_code = await self.configuration_service.get_config_value("SysAcc_DefaultGSTOutput", "SYS-GST-OUTPUT")
                default_cogs_acc_code = await self.configuration_service.get_config_value("SysAcc_DefaultCOGS", "5100") 

                fin_je_lines_data: List[JournalEntryLineData] = []
                fin_je_lines_data.append(JournalEntryLineData( account_id=ar_account.id, debit_amount=invoice_to_post.total_amount, credit_amount=Decimal(0), description=f"A/R for Inv {invoice_to_post.invoice_no}", currency_code=invoice_to_post.currency_code, exchange_rate=invoice_to_post.exchange_rate))
                for line in invoice_to_post.lines:
                    sales_gl_id = line.product.sales_account.id if line.product and line.product.sales_account and line.product.sales_account.is_active else (await self.account_service.get_by_code(default_sales_acc_code)).id # type: ignore
                    if not sales_gl_id: return Result.failure([f"Could not determine Sales Revenue account for line: {line.description}"])
                    fin_je_lines_data.append(JournalEntryLineData( account_id=sales_gl_id, debit_amount=Decimal(0), credit_amount=line.line_subtotal, description=f"Sale: {line.description[:100]} (Inv {invoice_to_post.invoice_no})", currency_code=invoice_to_post.currency_code, exchange_rate=invoice_to_post.exchange_rate))
                    if line.tax_amount and line.tax_amount != Decimal(0) and line.tax_code:
                        gst_gl_id_orm = line.tax_code_obj.affects_account if line.tax_code_obj and line.tax_code_obj.affects_account else None
                        gst_gl_id = gst_gl_id_orm.id if gst_gl_id_orm and gst_gl_id_orm.is_active else (await self.account_service.get_by_code(default_gst_output_acc_code)).id if default_gst_output_acc_code else None # type: ignore
                        if not gst_gl_id: return Result.failure([f"Could not determine GST Output account for tax on line: {line.description}"])
                        fin_je_lines_data.append(JournalEntryLineData( account_id=gst_gl_id, debit_amount=Decimal(0), credit_amount=line.tax_amount, description=f"GST Output ({line.tax_code}) for Inv {invoice_to_post.invoice_no}", currency_code=invoice_to_post.currency_code, exchange_rate=invoice_to_post.exchange_rate))
                
                fin_je_dto = JournalEntryData( journal_type=JournalTypeEnum.SALES.value, entry_date=invoice_to_post.invoice_date, description=f"Sales Invoice {invoice_to_post.invoice_no} to {invoice_to_post.customer.name}", source_type="SalesInvoice", source_id=invoice_to_post.id, user_id=user_id, lines=fin_je_lines_data)
                create_fin_je_result = await self.app_core.journal_entry_manager.create_journal_entry(fin_je_dto, session=session)
                if not create_fin_je_result.is_success or not create_fin_je_result.value: return Result.failure(["Failed to create financial JE for SI."] + create_fin_je_result.errors)
                created_fin_je: JournalEntry = create_fin_je_result.value
                post_fin_je_result = await self.app_core.journal_entry_manager.post_journal_entry(created_fin_je.id, user_id, session=session)
                if not post_fin_je_result.is_success: return Result.failure([f"Financial JE (ID: {created_fin_je.id}) created but failed to post."] + post_fin_je_result.errors)

                cogs_je_lines_data: List[JournalEntryLineData] = []
                for line in invoice_to_post.lines:
                    if line.product and ProductTypeEnum(line.product.product_type) == ProductTypeEnum.INVENTORY:
                        wac_query = text("SELECT average_cost FROM business.inventory_summary WHERE product_id = :pid")
                        wac_result = await session.execute(wac_query, {"pid": line.product_id})
                        current_wac = wac_result.scalar_one_or_none()
                        if current_wac is None: current_wac = line.product.purchase_price or Decimal(0) 
                        
                        cogs_amount_for_line = (line.quantity * current_wac).quantize(Decimal("0.01"), ROUND_HALF_UP)

                        inv_movement = InventoryMovement(
                            product_id=line.product_id, movement_date=invoice_to_post.invoice_date,
                            movement_type=InventoryMovementTypeEnum.SALE.value, quantity=-line.quantity, 
                            unit_cost=current_wac, total_cost=cogs_amount_for_line,
                            reference_type='SalesInvoiceLine', reference_id=line.id, created_by_user_id=user_id
                        )
                        await self.inventory_movement_service.save(inv_movement, session=session)

                        cogs_acc_orm = line.product.purchase_account if line.product.purchase_account and line.product.purchase_account.is_active else (await self.account_service.get_by_code(default_cogs_acc_code))
                        inv_asset_acc_orm = line.product.inventory_account if line.product.inventory_account and line.product.inventory_account.is_active else None # No easy system default for this specific product's asset account
                        if not cogs_acc_orm or not cogs_acc_orm.is_active or not inv_asset_acc_orm or not inv_asset_acc_orm.is_active: return Result.failure(["COGS or Inventory Asset account setup issue for product."])
                        
                        cogs_je_lines_data.append(JournalEntryLineData(account_id=cogs_acc_orm.id, debit_amount=cogs_amount_for_line, credit_amount=Decimal(0), description=f"COGS: {line.description[:50]}"))
                        cogs_je_lines_data.append(JournalEntryLineData(account_id=inv_asset_acc_orm.id, debit_amount=Decimal(0), credit_amount=cogs_amount_for_line, description=f"Inventory Sold: {line.description[:50]}"))

                if cogs_je_lines_data:
                    cogs_je_dto = JournalEntryData(journal_type=JournalTypeEnum.GENERAL.value, entry_date=invoice_to_post.invoice_date, description=f"COGS for SI {invoice_to_post.invoice_no}", source_type="SalesInvoiceCOGS", source_id=invoice_to_post.id, user_id=user_id, lines=cogs_je_lines_data)
                    create_cogs_je_result = await self.app_core.journal_entry_manager.create_journal_entry(cogs_je_dto, session=session)
                    if not create_cogs_je_result.is_success or not create_cogs_je_result.value: return Result.failure(["Failed to create COGS JE."] + create_cogs_je_result.errors)
                    post_cogs_je_result = await self.app_core.journal_entry_manager.post_journal_entry(create_cogs_je_result.value.id, user_id, session=session)
                    if not post_cogs_je_result.is_success: return Result.failure([f"COGS JE (ID: {create_cogs_je_result.value.id}) created but failed to post."] + post_cogs_je_result.errors)

                invoice_to_post.status = InvoiceStatusEnum.APPROVED.value 
                invoice_to_post.journal_entry_id = created_fin_je.id
                invoice_to_post.updated_by_user_id = user_id
                session.add(invoice_to_post); await session.flush(); await session.refresh(invoice_to_post)
                self.logger.info(f"SI {invoice_to_post.invoice_no} (ID: {invoice_id}) posted. Fin JE ID: {created_fin_je.id}")
                return Result.success(invoice_to_post)

            except Exception as e: self.logger.error(f"Error posting SI ID {invoice_id}: {e}", exc_info=True); return Result.failure([f"Unexpected error posting SI: {str(e)}"])

    async def get_invoices_for_listing(self, customer_id: Optional[int]=None, status_list:Optional[List[InvoiceStatusEnum]]=None, start_date:Optional[date]=None, end_date:Optional[date]=None, page:int=1, page_size:int=50) -> Result[List[SalesInvoiceSummaryData]]:
        try:
            summaries = await self.sales_invoice_service.get_all_summary(
                customer_id=customer_id, 
                status_list=status_list, 
                start_date=start_date, 
                end_date=end_date, 
                page=page, 
                page_size=page_size
            )
            return Result.success(summaries)
        except Exception as e: 
            self.logger.error(f"Error fetching SI listing: {e}", exc_info=True)
            return Result.failure([f"Failed to retrieve SI list: {str(e)}"])
```

#### **File 4: `app/business_logic/purchase_invoice_manager.py` (Corrected)**

```python
# File: app/business_logic/purchase_invoice_manager.py
from typing import List, Optional, Dict, Any, TYPE_CHECKING, Union, cast
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from datetime import date

from sqlalchemy.orm import selectinload 
from sqlalchemy import text

from app.models.business.purchase_invoice import PurchaseInvoice, PurchaseInvoiceLine
from app.models.business.inventory_movement import InventoryMovement 

from app.utils.result import Result
from app.utils.pydantic_models import (
    PurchaseInvoiceCreateData, PurchaseInvoiceUpdateData, PurchaseInvoiceSummaryData,
    PurchaseInvoiceLineBaseData, TaxCalculationResultData,
    JournalEntryData, JournalEntryLineData 
)
from app.common.enums import InvoiceStatusEnum, ProductTypeEnum, JournalTypeEnum, InventoryMovementTypeEnum 

if TYPE_CHECKING:
    from app.core.application_core import ApplicationCore
    from app.services.business_services import PurchaseInvoiceService, VendorService, ProductService, InventoryMovementService
    from app.services.core_services import SequenceService, ConfigurationService
    from app.services.tax_service import TaxCodeService
    from app.services.account_service import AccountService
    from app.tax.tax_calculator import TaxCalculator
    from app.models.business.vendor import Vendor
    from app.models.business.product import Product
    from app.models.accounting.tax_code import TaxCode
    from app.models.accounting.journal_entry import JournalEntry


class PurchaseInvoiceManager:
    def __init__(self, app_core: "ApplicationCore"): 
        self.app_core = app_core
        self.purchase_invoice_service: "PurchaseInvoiceService" = self.app_core.purchase_invoice_service
        self.vendor_service: "VendorService" = self.app_core.vendor_service
        self.product_service: "ProductService" = self.app_core.product_service
        self.tax_code_service: "TaxCodeService" = self.app_core.tax_code_service
        self.tax_calculator: "TaxCalculator" = self.app_core.tax_calculator
        self.sequence_service: "SequenceService" = self.app_core.sequence_service
        self.account_service: "AccountService" = self.app_core.account_service
        self.configuration_service: "ConfigurationService" = self.app_core.configuration_service
        self.inventory_movement_service: "InventoryMovementService" = self.app_core.inventory_movement_service
        self.logger = self.app_core.logger
        
    async def _validate_and_prepare_pi_data(
        self, 
        dto: Union[PurchaseInvoiceCreateData, PurchaseInvoiceUpdateData],
        is_update: bool = False
    ) -> Result[Dict[str, Any]]:
        errors: List[str] = []
        
        vendor = await self.vendor_service.get_by_id(dto.vendor_id)
        if not vendor:
            errors.append(f"Vendor with ID {dto.vendor_id} not found.")
        elif not vendor.is_active:
            errors.append(f"Vendor '{vendor.name}' (ID: {dto.vendor_id}) is not active.")

        if not dto.currency_code or len(dto.currency_code) != 3:
            errors.append(f"Invalid currency code: '{dto.currency_code}'.")
        else:
           currency_obj = await self.app_core.currency_manager.get_currency_by_code(dto.currency_code)
           if not currency_obj or not currency_obj.is_active:
               errors.append(f"Currency '{dto.currency_code}' is invalid or not active.")

        if dto.vendor_invoice_no and not is_update: 
            existing_pi = await self.purchase_invoice_service.get_by_vendor_and_vendor_invoice_no(dto.vendor_id, dto.vendor_invoice_no)
            if existing_pi:
                errors.append(f"Duplicate vendor invoice number '{dto.vendor_invoice_no}' already exists for this vendor.")
        elif dto.vendor_invoice_no and is_update and isinstance(dto, PurchaseInvoiceUpdateData): 
            existing_pi_for_update = await self.purchase_invoice_service.get_by_id(dto.id) 
            if existing_pi_for_update and existing_pi_for_update.vendor_invoice_no != dto.vendor_invoice_no:
                colliding_pi = await self.purchase_invoice_service.get_by_vendor_and_vendor_invoice_no(dto.vendor_id, dto.vendor_invoice_no)
                if colliding_pi and colliding_pi.id != dto.id:
                    errors.append(f"Duplicate vendor invoice number '{dto.vendor_invoice_no}' already exists for this vendor on another record.")

        calculated_lines_for_orm: List[Dict[str, Any]] = []
        invoice_subtotal_calc = Decimal(0)
        invoice_total_tax_calc = Decimal(0)

        if not dto.lines: errors.append("Purchase invoice must have at least one line item.")
        
        for i, line_dto in enumerate(dto.lines):
            line_errors_current_line: List[str] = []
            product: Optional["Product"] = None 
            line_description = line_dto.description
            unit_price = line_dto.unit_price
            line_purchase_account_id: Optional[int] = None 
            line_tax_account_id: Optional[int] = None
            product_type_for_line: Optional[ProductTypeEnum] = None


            if line_dto.product_id:
                product = await self.product_service.get_by_id(line_dto.product_id)
                if not product: line_errors_current_line.append(f"Product ID {line_dto.product_id} not found on line {i+1}.")
                elif not product.is_active: line_errors_current_line.append(f"Product '{product.name}' is not active on line {i+1}.")
                if product: 
                    if not line_description: line_description = product.name
                    if (unit_price is None or unit_price == Decimal(0)) and product.purchase_price is not None: unit_price = product.purchase_price
                    line_purchase_account_id = product.purchase_account_id
                    product_type_for_line = ProductTypeEnum(product.product_type) 
            
            if not line_description: line_errors_current_line.append(f"Description is required on line {i+1}.")
            if unit_price is None: line_errors_current_line.append(f"Unit price is required on line {i+1}."); unit_price = Decimal(0) 

            try:
                qty = Decimal(str(line_dto.quantity)); price = Decimal(str(unit_price)); discount_pct = Decimal(str(line_dto.discount_percent))
                if qty <= 0: line_errors_current_line.append(f"Quantity must be positive on line {i+1}.")
                if not (0 <= discount_pct <= 100): line_errors_current_line.append(f"Discount percent must be between 0 and 100 on line {i+1}.")
            except InvalidOperation: line_errors_current_line.append(f"Invalid numeric value for quantity, price, or discount on line {i+1}."); errors.extend(line_errors_current_line); continue

            discount_amount = (qty * price * (discount_pct / Decimal(100))).quantize(Decimal("0.0001"), ROUND_HALF_UP)
            line_subtotal_before_tax = (qty * price) - discount_amount
            
            line_tax_amount_calc = Decimal(0)
            if line_dto.tax_code:
                tax_calc_result: TaxCalculationResultData = await self.tax_calculator.calculate_line_tax(amount=line_subtotal_before_tax, tax_code_str=line_dto.tax_code, transaction_type="PurchaseInvoiceLine")
                line_tax_amount_calc = tax_calc_result.tax_amount; line_tax_account_id = tax_calc_result.tax_account_id
                if tax_calc_result.tax_account_id is None and line_tax_amount_calc > Decimal(0):
                    tc_check_orm: Optional["TaxCode"] = await self.tax_code_service.get_tax_code(line_dto.tax_code)
                    if not tc_check_orm or not tc_check_orm.is_active: line_errors_current_line.append(f"Tax code '{line_dto.tax_code}' used on line {i+1} is invalid or inactive.")
            
            invoice_subtotal_calc += line_subtotal_before_tax; invoice_total_tax_calc += line_tax_amount_calc
            if line_errors_current_line: errors.extend(line_errors_current_line)
            
            calculated_lines_for_orm.append({
                "product_id": line_dto.product_id, "description": line_description, "quantity": qty, "unit_price": price, "discount_percent": discount_pct,
                "discount_amount": discount_amount.quantize(Decimal("0.01"), ROUND_HALF_UP), "line_subtotal": line_subtotal_before_tax.quantize(Decimal("0.01"), ROUND_HALF_UP), 
                "tax_code": line_dto.tax_code, "tax_amount": line_tax_amount_calc.quantize(Decimal("0.01"), ROUND_HALF_UP), 
                "line_total": (line_subtotal_before_tax + line_tax_amount_calc).quantize(Decimal("0.01"), ROUND_HALF_UP),
                "dimension1_id": line_dto.dimension1_id, "dimension2_id": line_dto.dimension2_id,
                "_line_purchase_account_id": line_purchase_account_id, "_line_tax_account_id": line_tax_account_id, "_product_type": product_type_for_line
            })

        if errors: return Result.failure(errors)
        invoice_grand_total = invoice_subtotal_calc + invoice_total_tax_calc
        return Result.success({
            "header_dto": dto, "vendor_orm": vendor, "calculated_lines_for_orm": calculated_lines_for_orm,
            "invoice_subtotal": invoice_subtotal_calc.quantize(Decimal("0.01"), ROUND_HALF_UP),
            "invoice_total_tax": invoice_total_tax_calc.quantize(Decimal("0.01"), ROUND_HALF_UP),
            "invoice_grand_total": invoice_grand_total.quantize(Decimal("0.01"), ROUND_HALF_UP),
        })

    async def create_draft_purchase_invoice(self, dto: PurchaseInvoiceCreateData) -> Result[PurchaseInvoice]:
        preparation_result = await self._validate_and_prepare_pi_data(dto)
        if not preparation_result.is_success: return Result.failure(preparation_result.errors)
        prepared_data = preparation_result.value; assert prepared_data is not None 
        header_dto = cast(PurchaseInvoiceCreateData, prepared_data["header_dto"])
        try:
            our_internal_ref_no = await self.app_core.db_manager.execute_scalar("SELECT core.get_next_sequence_value($1);", "purchase_invoice")
            if not our_internal_ref_no or not isinstance(our_internal_ref_no, str): return Result.failure(["Failed to generate internal invoice number."])
            invoice_orm = PurchaseInvoice(
                invoice_no=our_internal_ref_no, vendor_invoice_no=header_dto.vendor_invoice_no, vendor_id=header_dto.vendor_id,
                invoice_date=header_dto.invoice_date, due_date=header_dto.due_date, currency_code=header_dto.currency_code, 
                exchange_rate=header_dto.exchange_rate, notes=header_dto.notes, subtotal=prepared_data["invoice_subtotal"], 
                tax_amount=prepared_data["invoice_total_tax"], total_amount=prepared_data["invoice_grand_total"], 
                amount_paid=Decimal(0), status=InvoiceStatusEnum.DRAFT.value, 
                created_by_user_id=header_dto.user_id, updated_by_user_id=header_dto.user_id
            )
            for i, line_data_dict in enumerate(prepared_data["calculated_lines_for_orm"]):
                orm_line_data = {k.lstrip('_'): v for k,v in line_data_dict.items() if not k.startswith('_') and k != "_product_type"}
                invoice_orm.lines.append(PurchaseInvoiceLine(line_number=i + 1, **orm_line_data))
            saved_invoice = await self.purchase_invoice_service.save(invoice_orm)
            self.logger.info(f"Draft PI '{saved_invoice.invoice_no}' created for vendor ID {saved_invoice.vendor_id}.")
            return Result.success(saved_invoice)
        except Exception as e: self.logger.error(f"Error creating draft PI: {e}", exc_info=True); return Result.failure([f"Error creating PI: {str(e)}"])

    async def update_draft_purchase_invoice(self, invoice_id: int, dto: PurchaseInvoiceUpdateData) -> Result[PurchaseInvoice]:
        async with self.app_core.db_manager.session() as session: 
            existing_invoice = await session.get(PurchaseInvoice, invoice_id, options=[selectinload(PurchaseInvoice.lines)])
            if not existing_invoice: return Result.failure([f"PI ID {invoice_id} not found."])
            if existing_invoice.status != InvoiceStatusEnum.DRAFT.value: return Result.failure([f"Only draft PIs can be updated. Status: {existing_invoice.status}"])
            preparation_result = await self._validate_and_prepare_pi_data(dto, is_update=True)
            if not preparation_result.is_success: return Result.failure(preparation_result.errors)
            prepared_data = preparation_result.value; assert prepared_data is not None 
            header_dto = cast(PurchaseInvoiceUpdateData, prepared_data["header_dto"])
            try:
                existing_invoice.vendor_id = header_dto.vendor_id; existing_invoice.vendor_invoice_no = header_dto.vendor_invoice_no
                existing_invoice.invoice_date = header_dto.invoice_date; existing_invoice.due_date = header_dto.due_date
                existing_invoice.currency_code = header_dto.currency_code; existing_invoice.exchange_rate = header_dto.exchange_rate
                existing_invoice.notes = header_dto.notes; existing_invoice.subtotal = prepared_data["invoice_subtotal"]
                existing_invoice.tax_amount = prepared_data["invoice_total_tax"]; existing_invoice.total_amount = prepared_data["invoice_grand_total"]
                existing_invoice.updated_by_user_id = header_dto.user_id
                for line_orm_to_delete in list(existing_invoice.lines): await session.delete(line_orm_to_delete)
                await session.flush() 
                new_lines_orm: List[PurchaseInvoiceLine] = []
                for i, line_data_dict in enumerate(prepared_data["calculated_lines_for_orm"]):
                    orm_line_data = {k.lstrip('_'): v for k,v in line_data_dict.items() if not k.startswith('_') and k != "_product_type"}
                    new_lines_orm.append(PurchaseInvoiceLine(line_number=i + 1, **orm_line_data))
                existing_invoice.lines = new_lines_orm 
                await session.flush(); await session.refresh(existing_invoice, attribute_names=['lines'])
                self.logger.info(f"Draft PI '{existing_invoice.invoice_no}' (ID: {invoice_id}) updated.")
                return Result.success(existing_invoice)
            except Exception as e: self.logger.error(f"Error updating draft PI ID {invoice_id}: {e}", exc_info=True); return Result.failure([f"Error updating PI: {str(e)}"])

    async def post_purchase_invoice(self, invoice_id: int, user_id: int) -> Result[PurchaseInvoice]:
        async with self.app_core.db_manager.session() as session: # type: ignore
            try:
                invoice_to_post = await session.get(
                    PurchaseInvoice, invoice_id, 
                    options=[
                        selectinload(PurchaseInvoice.lines).selectinload(PurchaseInvoiceLine.product).selectinload(Product.purchase_account),
                        selectinload(PurchaseInvoice.lines).selectinload(PurchaseInvoiceLine.product).selectinload(Product.inventory_account),
                        selectinload(PurchaseInvoice.lines).selectinload(PurchaseInvoiceLine.tax_code_obj).selectinload(TaxCode.affects_account), 
                        selectinload(PurchaseInvoice.vendor).selectinload(Vendor.payables_account)
                    ]
                )
                if not invoice_to_post:
                    return Result.failure([f"Purchase Invoice ID {invoice_id} not found."])
                if invoice_to_post.status != InvoiceStatusEnum.DRAFT.value:
                    return Result.failure([f"Only Draft invoices can be posted. Current status: {invoice_to_post.status}."])

                if not invoice_to_post.vendor or not invoice_to_post.vendor.is_active:
                    return Result.failure(["Vendor is inactive or not found."])
                
                ap_account_id_from_vendor = invoice_to_post.vendor.payables_account_id
                ap_account_code_fallback = await self.configuration_service.get_config_value("SysAcc_DefaultAP", "2110")
                ap_account_final_id: Optional[int] = None

                if ap_account_id_from_vendor:
                    ap_acc_orm = await self.account_service.get_by_id(ap_account_id_from_vendor) 
                    if ap_acc_orm and ap_acc_orm.is_active: ap_account_final_id = ap_acc_orm.id
                    else: self.logger.warning(f"Vendor AP account ID {ap_account_id_from_vendor} is invalid/inactive for PI {invoice_to_post.invoice_no}. Falling back.")
                
                if not ap_account_final_id and ap_account_code_fallback:
                    fallback_ap_acc_orm = await self.account_service.get_by_code(ap_account_code_fallback)
                    if fallback_ap_acc_orm and fallback_ap_acc_orm.is_active: ap_account_final_id = fallback_ap_acc_orm.id
                
                if not ap_account_final_id:
                    return Result.failure([f"Could not determine a valid Accounts Payable account for PI {invoice_to_post.invoice_no}."])

                default_purchase_expense_code = await self.configuration_service.get_config_value("SysAcc_DefaultPurchaseExpense", "5100")
                default_inventory_asset_code = await self.configuration_service.get_config_value("SysAcc_DefaultInventoryAsset", "1130") 
                default_gst_input_acc_code = await self.configuration_service.get_config_value("SysAcc_DefaultGSTInput", "SYS-GST-INPUT")
                
                je_lines_data: List[JournalEntryLineData] = []
                
                je_lines_data.append(JournalEntryLineData(
                    account_id=ap_account_final_id, debit_amount=Decimal(0), credit_amount=invoice_to_post.total_amount,
                    description=f"A/P for P.Inv {invoice_to_post.invoice_no} from {invoice_to_post.vendor.name}",
                    currency_code=invoice_to_post.currency_code, exchange_rate=invoice_to_post.exchange_rate ))

                for line in invoice_to_post.lines:
                    debit_account_id_for_line: Optional[int] = None
                    product_type_for_line: Optional[ProductTypeEnum] = None
                    if line.product: product_type_for_line = ProductTypeEnum(line.product.product_type)
                    
                    if product_type_for_line == ProductTypeEnum.INVENTORY and line.product and line.product.inventory_account:
                        if line.product.inventory_account.is_active: debit_account_id_for_line = line.product.inventory_account.id
                        else: self.logger.warning(f"Product '{line.product.name}' inventory account '{line.product.inventory_account.code}' is inactive for PI {invoice_to_post.invoice_no}.")
                    elif line.product and line.product.purchase_account: 
                         if line.product.purchase_account.is_active: debit_account_id_for_line = line.product.purchase_account.id
                         else: self.logger.warning(f"Product '{line.product.name}' purchase account '{line.product.purchase_account.code}' is inactive for PI {invoice_to_post.invoice_no}.")
                    
                    if not debit_account_id_for_line: 
                        fallback_code = default_inventory_asset_code if product_type_for_line == ProductTypeEnum.INVENTORY else default_purchase_expense_code
                        fallback_acc = await self.account_service.get_by_code(fallback_code)
                        if not fallback_acc or not fallback_acc.is_active: return Result.failure([f"Default debit account '{fallback_code}' for line '{line.description}' is invalid/inactive."])
                        debit_account_id_for_line = fallback_acc.id
                    
                    if not debit_account_id_for_line: return Result.failure([f"Could not determine Debit GL account for line: {line.description}"])

                    je_lines_data.append(JournalEntryLineData(
                        account_id=debit_account_id_for_line, debit_amount=line.line_subtotal, credit_amount=Decimal(0), 
                        description=f"Purchase: {line.description[:100]} (P.Inv {invoice_to_post.invoice_no})",
                        currency_code=invoice_to_post.currency_code, exchange_rate=invoice_to_post.exchange_rate ))

                    if line.tax_amount and line.tax_amount != Decimal(0) and line.tax_code:
                        gst_gl_id_for_line: Optional[int] = None
                        line_tax_code_obj_orm = line.tax_code_obj 
                        if line_tax_code_obj_orm and line_tax_code_obj_orm.affects_account:
                            if line_tax_code_obj_orm.affects_account.is_active: gst_gl_id_for_line = line_tax_code_obj_orm.affects_account.id
                            else: self.logger.warning(f"Tax code '{line.tax_code}' affects account '{line_tax_code_obj_orm.affects_account.code}' is inactive. Falling back.")
                        
                        if not gst_gl_id_for_line and default_gst_input_acc_code: 
                            def_gst_input_acc = await self.account_service.get_by_code(default_gst_input_acc_code)
                            if not def_gst_input_acc or not def_gst_input_acc.is_active: return Result.failure([f"Default GST Input account '{default_gst_input_acc_code}' is invalid or inactive."])
                            gst_gl_id_for_line = def_gst_input_acc.id

                        if not gst_gl_id_for_line: return Result.failure([f"Could not determine GST Input account for tax on line: {line.description}"])
                        
                        je_lines_data.append(JournalEntryLineData(
                            account_id=gst_gl_id_for_line, debit_amount=line.tax_amount, credit_amount=Decimal(0),
                            description=f"GST Input ({line.tax_code}) for P.Inv {invoice_to_post.invoice_no}",
                            currency_code=invoice_to_post.currency_code, exchange_rate=invoice_to_post.exchange_rate ))
                
                je_dto = JournalEntryData(
                    journal_type=JournalTypeEnum.PURCHASE.value, entry_date=invoice_to_post.invoice_date,
                    description=f"Purchase Invoice {invoice_to_post.invoice_no} from {invoice_to_post.vendor.name}",
                    source_type="PurchaseInvoice", source_id=invoice_to_post.id, user_id=user_id, lines=je_lines_data
                )

                create_je_result = await self.app_core.journal_entry_manager.create_journal_entry(je_dto, session=session)
                if not create_je_result.is_success or not create_je_result.value: return Result.failure(["Failed to create JE for PI."] + create_je_result.errors)
                
                created_je: "JournalEntry" = create_je_result.value
                post_je_result = await self.app_core.journal_entry_manager.post_journal_entry(created_je.id, user_id, session=session)
                if not post_je_result.is_success: return Result.failure([f"JE (ID: {created_je.id}) created but failed to post."] + post_je_result.errors)

                for line in invoice_to_post.lines:
                    if line.product and ProductTypeEnum(line.product.product_type) == ProductTypeEnum.INVENTORY:
                        inv_movement = InventoryMovement(
                            product_id=line.product_id, movement_date=invoice_to_post.invoice_date,
                            movement_type=InventoryMovementTypeEnum.PURCHASE.value,
                            quantity=line.quantity, unit_cost=(line.line_subtotal / line.quantity if line.quantity else Decimal(0)),
                            total_cost=line.line_subtotal, reference_type='PurchaseInvoiceLine', reference_id=line.id,
                            created_by_user_id=user_id
                        )
                        await self.inventory_movement_service.save(inv_movement, session=session)
                
                invoice_to_post.status = InvoiceStatusEnum.APPROVED.value 
                invoice_to_post.journal_entry_id = created_je.id
                invoice_to_post.updated_by_user_id = user_id
                
                session.add(invoice_to_post) 
                await session.flush(); await session.refresh(invoice_to_post)
                self.logger.info(f"PI {invoice_to_post.invoice_no} (ID: {invoice_id}) posted. JE ID: {created_je.id}")
                return Result.success(invoice_to_post)

            except Exception as e: self.logger.error(f"Error posting PI ID {invoice_id}: {e}", exc_info=True); return Result.failure([f"Unexpected error posting PI: {str(e)}"])

    async def get_invoice_for_dialog(self, invoice_id: int) -> Optional[PurchaseInvoice]:
        try: return await self.purchase_invoice_service.get_by_id(invoice_id)
        except Exception as e: self.logger.error(f"Error fetching PI ID {invoice_id} for dialog: {e}", exc_info=True); return None

    async def get_invoices_for_listing(self, vendor_id: Optional[int]=None, status_list:Optional[List[InvoiceStatusEnum]]=None, start_date:Optional[date]=None, end_date:Optional[date]=None, page:int=1, page_size:int=50) -> Result[List[PurchaseInvoiceSummaryData]]:
        try:
            summaries = await self.purchase_invoice_service.get_all_summary(
                vendor_id=vendor_id, 
                status_list=status_list, 
                start_date=start_date, 
                end_date=end_date, 
                page=page, 
                page_size=page_size
            )
            return Result.success(summaries)
        except Exception as e: 
            self.logger.error(f"Error fetching PI listing: {e}", exc_info=True)
            return Result.failure([f"Failed to retrieve PI list: {str(e)}"])
```

I have provided the remaining files that need to be modified for your review and validation. Please proceed according to your plan. Thank you

---
https://drive.google.com/file/d/11X3f2mKRWl56NubmyAKo5dwck7p2JaLs/view?usp=sharing, https://drive.google.com/file/d/11XlZNQ-Qn9Lw3G-YPcWZrO-g5ZbwfscI/view?usp=sharing, https://drive.google.com/file/d/127qgzFTDe-WAnzFzOzBn2efixfG9w9YE/view?usp=sharing, https://drive.google.com/file/d/12KXr1nctXs-02etv6A72vihqrtK3dDK9/view?usp=sharing, https://drive.google.com/file/d/131RjCRl_kHc0XtnhCzDmf5bjgJX5iEww/view?usp=sharing, https://drive.google.com/file/d/13B_HcJmxgi3QGYHnj64s275QZN20pg3g/view?usp=sharing, https://drive.google.com/file/d/18FJ9jhk3oxKCC_sNWs_1C-EZZXe_j-TT/view?usp=sharing, https://drive.google.com/file/d/19n5zeGWlBAwCRFAXfbe4kY5xBK-uV-d7/view?usp=sharing, https://drive.google.com/file/d/1KHIzrVj6ijdFoVTVLa-lfyyVzwf5IYwp/view?usp=sharing, https://drive.google.com/file/d/1M5ybbmzIqj7IUo99Yle7xl_pkczow6Ci/view?usp=sharing, https://drive.google.com/file/d/1OSDUBHWuHA7wKnttqPtYbAEpqdXDi1_8/view?usp=sharing, https://drive.google.com/file/d/1P4rxLCG8-5cJ2_vt2qKJqO2wxN26ro9T/view?usp=sharing, https://aistudio.google.com/app/prompts?state=%7B%22ids%22:%5B%221Rh0wsFMlVjsOSccPUo5JJmfB6gof_tS2%22%5D,%22action%22:%22open%22,%22userId%22:%22103961307342447084491%22,%22resourceKeys%22:%7B%7D%7D&usp=sharing, https://drive.google.com/file/d/1T1kVeTCKFOIzPckOmAarcwHC8x0yau1i/view?usp=sharing, https://drive.google.com/file/d/1YZs4VLSKR9N-eVniftVGHgh9RJHLpFtu/view?usp=sharing, https://drive.google.com/file/d/1dAgihzWoQ03fPAECRX4qUzJiiJppPgwz/view?usp=sharing, https://drive.google.com/file/d/1gM89F4jZMNsWNTd9bxJxPfRxY0Y2Vfof/view?usp=sharing, https://drive.google.com/file/d/1hAf_3y-ecY6gAU67N0KzgqGZz1XrDjed/view?usp=sharing, https://drive.google.com/file/d/1iLEa4z_1QZHLh5VEurZg7rUHZneQzsY8/view?usp=sharing, https://drive.google.com/file/d/1jigzShY696C9WmGqx1js_OPVEWWBnXeg/view?usp=sharing, https://drive.google.com/file/d/1k1bI3w9HToGc_f_7QXKyvy6c1nDPxRzc/view?usp=sharing, https://drive.google.com/file/d/1mO8_5fwtxIboAdjNo31vNNnNYbzI8-gq/view?usp=sharing, https://drive.google.com/file/d/1pswWDECjQfPpG_vPcb2bGTynwme8P6nA/view?usp=sharing, https://drive.google.com/file/d/1tbuyHau6G4TdCZ0v6u22_ePISFTSNU7r/view?usp=sharing, https://drive.google.com/file/d/1uC_hd3fJooXn4tQQsLJPU3mxW07hDGym/view?usp=sharing, https://drive.google.com/file/d/1yVM3DBOfyPfYckF4q1C8S0ce_9pMnUvz/view?usp=sharing

