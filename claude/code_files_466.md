<think>
The user is asking me to fix a new, more severe bug: a `sqlalchemy.exc.InvalidRequestError` that leads to a `Segmentation fault`. This is a critical error.

**My Task:**
1.  **Analyze the new problem:** Understand the traceback and the `InvalidRequestError`.
2.  **Formulate a fix:** Determine the correct way to construct the SQLAlchemy query to resolve the "auto-correlation" issue.
3.  **Generate a complete replacement file:** Create the full `app/services/business_services.py` file with the fix applied, using the provided `app-services--business_services(previous version).py` as the base.

**Phase 1: Deep Analysis of the Problem**

*   **User Input:** I have two main pieces of information:
    1.  The **previous version of the file**, which is the one I generated in the last step. This is now the "base" or "original" file for this new task.
    2.  The **new traceback and analysis** provided in `proposed_change_request.md`. The user has already done a great job analyzing the issue, which I must validate and use.

*   **Traceback Analysis:**
    *   The error is `sqlalchemy.exc.InvalidRequestError: Select statement ... returned no FROM clauses due to auto-correlation; specify correlate(<tables>) to control correlation manually.`
    *   This happens inside `PaymentService.get_all_summary`.
    *   The user's analysis in `proposed_change_request.md` is spot-on. The problem lies in how the `SELECT` statement is constructed. When using correlated subqueries (like `select(Customer.name).where(Customer.id == Payment.entity_id)`) inside a `CASE` statement *within* the main `select()` call, SQLAlchemy gets confused. It can't determine the primary `FROM` clause for the outer query because the references to `Payment` are buried inside subqueries.
    *   The conditional `stmt = stmt.join(Vendor, ...)` applied *after* the initial `select()` constructor further complicates things for the query compiler.

*   **Proposed Solution Analysis:**
    *   The user's proposed solution in the `proposed_change_request.md` is excellent and follows best practices for complex SQLAlchemy queries.
    *   **1. Explicit `select_from`:** Start the query with `select(...).select_from(Payment)`. This immediately resolves the ambiguity about the main table.
    *   **2. Explicit `outerjoin`:** Replace the correlated subqueries with `outerjoin`. This is more efficient as it often results in a single, more optimized query plan at the database level. It's also clearer to read. Using `outerjoin` is crucial because a payment to an entity type other than Customer or Vendor would otherwise be excluded from the results if an `innerjoin` were used. The `and_` condition within the `outerjoin` is the correct way to link the join to both the ID and the entity type.
    *   **3. Simplified `case`:** The `case` statement can then directly reference the joined columns (`Customer.name`, `Vendor.name`) instead of using subqueries.
    *   **4. Consolidated `WHERE` clauses:** The condition for `wht_applicable_only` is now correctly added to the main `conditions` list and applied once in a single `.where(and_(*conditions))` call. This is cleaner and less error-prone.

*   **Conclusion of Analysis:** The proposed fix is not just a patch; it's a robust architectural improvement to the query construction logic. It is the correct and optimal solution.

**Phase 2: Detailed Execution Plan & Checklist**

1.  **[ ] Step 1: Initialize with Base Content.**
    *   **Action**: Copy the entire content of the provided `app-services--business_services(previous version).py` (which is the result of my *previous* task) into my working buffer.
    *   **Checklist**:
        *   [ ] Verify the buffer contains the `PaymentService` with the `get_payment_with_vendor` method and the `get_all_summary` that uses `status_list`.

2.  **[ ] Step 2: Identify Target for Replacement.**
    *   **Action**: In the buffer, locate the `get_all_summary` method within the `class PaymentService(IPaymentRepository):` block.
    *   **Checklist**:
        *   [ ] The method `async def get_all_summary(...)` is found.

3.  **[ ] Step 3: Extract the Updated Code.**
    *   **Action**: From the `proposed_change_request.md` file, copy the *entire* `async def get_all_summary(...)` method body.
    *   **Checklist**:
        *   [ ] The copied code contains `select(...).select_from(Payment)`.
        *   [ ] It uses `outerjoin` for both `Customer` and `Vendor`.
        *   [ ] The `case` statement refers directly to `Customer.name` and `Vendor.name`.
        *   [ ] The `wht_applicable_only` check is moved into the main `conditions` list.

4.  **[ ] Step 4: Perform the Replacement.**
    *   **Action**: Replace the old `get_all_summary` method in my working buffer with the new, corrected version.
    *   **Checklist**:
        *   [ ] The old `get_all_summary` method is gone.
        *   [ ] The new, robustly-constructed query version is in its place.
        *   [ ] All other methods in `PaymentService` (`get_by_id`, `get_payment_with_vendor`, `save`, etc.) are untouched.
        *   [ ] All other service classes in the file are untouched.

5.  **[ ] Step 5: Final Review and Validation (Internal "diff").**
    *   **Action**: Perform a line-by-line mental "diff" between my newly generated file in the buffer and the base file provided by the user.
    *   **Checklist**:
        *   [ ] **Expected `diff` result:** The *only* difference should be the implementation of the `get_all_summary` method within `PaymentService`.
        *   [ ] **No Unintended Changes:** Verify that everything outside this specific method is identical to the base file.

6.  **[ ] Step 6: Format the Final Output.**
    *   **Action**: Enclose the complete, validated file content within ```py ... ``` tags. Prepare the final response.
    *   **Checklist**:
        *   [ ] Correct code fencing.
        *   [ ] Full file content present.
        *   [ ] A clear introductory statement explaining what was fixed.

**Execution of the Plan**

*   **Step 1**: Done. I have loaded the base file content.
*   **Step 2**: Done. I have located the target method.
*   **Step 3**: Done. I have extracted the new, corrected implementation of `get_all_summary` from the user's analysis.
*   **Step 4**: Done. The replacement is complete. All other code remains untouched.
*   **Step 5**: Performing the "diff".
    *   The only change is inside `PaymentService.get_all_summary`.
    *   Old implementation with subqueries and conditional join is replaced by the new implementation with `select_from` and `outerjoin`.
    *   The logic for building the `conditions` list is slightly different (to include the WHT check) but correct.
    *   The `stmt` construction is completely different, but it's the intended fix.
    *   **Validation Result**: The diff is exactly as expected. The fix is correctly applied, and no other code is affected.
*   **Step 6**: Done. I am ready to generate the final, corrected file.

This meticulous process ensures that I fix the critical `InvalidRequestError` and segmentation fault while preserving the integrity of the rest of the file, just as requested.Of course. Your analysis of the `InvalidRequestError` and the resulting segmentation fault is excellent and pinpoints the exact issue with SQLAlchemy's query construction. The proposed solution to use explicit `select_from` and `outerjoin` is the correct and most robust way to resolve this critical error.

I will now generate the complete and updated replacement file for `app/services/business_services.py`.

My process was as follows:
1.  I have used the file you provided from our last successful interaction as the definitive base version.
2.  I located the `get_all_summary` method within the `PaymentService` class, which was causing the error.
3.  I replaced its entire implementation with the new, robust version from your analysis, which uses `select_from()` and `outerjoin()` to build a clear, unambiguous SQL query.
4.  I have performed a final line-by-line validation to ensure that this was the *only* change made and that all other methods and service classes in the file are perfectly preserved.

The file below contains the critical fix and is the complete and correct version.

### **Complete Updated File: `app/services/business_services.py`**

```py
# File: app/services/business_services.py
from typing import List, Optional, Any, TYPE_CHECKING, Dict, Tuple
from sqlalchemy import select, func, and_, or_, literal_column, case, update as sqlalchemy_update, table, column
from sqlalchemy.types import DECIMAL 
from sqlalchemy.ext.asyncio import AsyncSession 
from sqlalchemy.orm import selectinload, joinedload 
from decimal import Decimal
import logging 
from datetime import date, datetime, timedelta 

from app.core.database_manager import DatabaseManager
from app.models.business.customer import Customer
from app.models.business.vendor import Vendor
from app.models.business.product import Product
from app.models.business.sales_invoice import SalesInvoice, SalesInvoiceLine
from app.models.business.purchase_invoice import PurchaseInvoice, PurchaseInvoiceLine 
from app.models.business.inventory_movement import InventoryMovement 
from app.models.business.bank_account import BankAccount 
from app.models.business.bank_transaction import BankTransaction
from app.models.business.payment import Payment, PaymentAllocation 
from app.models.business.bank_reconciliation import BankReconciliation
from app.models.accounting.account import Account 
from app.models.accounting.currency import Currency 
from app.models.accounting.tax_code import TaxCode 
from app.models.core.user import User
from app.services import (
    ICustomerRepository, IVendorRepository, IProductRepository, 
    ISalesInvoiceRepository, IPurchaseInvoiceRepository, IInventoryMovementRepository,
    IBankAccountRepository, IBankTransactionRepository, IPaymentRepository,
    IBankReconciliationRepository
)
from app.utils.pydantic_models import (
    CustomerSummaryData, VendorSummaryData, ProductSummaryData, 
    SalesInvoiceSummaryData, PurchaseInvoiceSummaryData,
    BankAccountSummaryData, BankTransactionSummaryData,
    PaymentSummaryData, BankReconciliationSummaryData
)
from app.utils.result import Result 
from app.common.enums import ProductTypeEnum, InvoiceStatusEnum, BankTransactionTypeEnum, PaymentEntityTypeEnum, PaymentStatusEnum 

if TYPE_CHECKING:
    from app.core.application_core import ApplicationCore

class CustomerService(ICustomerRepository):
    def __init__(self, db_manager: "DatabaseManager", app_core: Optional["ApplicationCore"] = None):
        self.db_manager = db_manager
        self.app_core = app_core
        self.logger = app_core.logger if app_core and hasattr(app_core, 'logger') else logging.getLogger(self.__class__.__name__)
    async def get_by_id(self, customer_id: int) -> Optional[Customer]:
        async with self.db_manager.session() as session:
            stmt = select(Customer).options(selectinload(Customer.currency),selectinload(Customer.receivables_account),selectinload(Customer.created_by_user),selectinload(Customer.updated_by_user)).where(Customer.id == customer_id)
            result = await session.execute(stmt); return result.scalars().first()
    async def get_all(self) -> List[Customer]:
        async with self.db_manager.session() as session:
            stmt = select(Customer).order_by(Customer.name); result = await session.execute(stmt); return list(result.scalars().all())
    async def get_all_summary(self, active_only: bool = True,search_term: Optional[str] = None,page: int = 1, page_size: int = 50) -> List[CustomerSummaryData]:
        async with self.db_manager.session() as session:
            conditions = []; 
            if active_only: conditions.append(Customer.is_active == True)
            if search_term: search_pattern = f"%{search_term}%"; conditions.append(or_(Customer.customer_code.ilike(search_pattern), Customer.name.ilike(search_pattern), Customer.email.ilike(search_pattern) if Customer.email else False )) 
            stmt = select(Customer.id, Customer.customer_code, Customer.name, Customer.email, Customer.phone, Customer.is_active)
            if conditions: stmt = stmt.where(and_(*conditions))
            stmt = stmt.order_by(Customer.name)
            if page_size > 0 : stmt = stmt.limit(page_size).offset((page - 1) * page_size)
            result = await session.execute(stmt); return [CustomerSummaryData.model_validate(row) for row in result.mappings().all()]
    async def get_by_code(self, code: str) -> Optional[Customer]:
        async with self.db_manager.session() as session:
            stmt = select(Customer).where(Customer.customer_code == code); result = await session.execute(stmt); return result.scalars().first()
    async def save(self, customer: Customer) -> Customer:
        async with self.db_manager.session() as session:
            session.add(customer); await session.flush(); await session.refresh(customer); return customer
    async def add(self, entity: Customer) -> Customer: return await self.save(entity)
    async def update(self, entity: Customer) -> Customer: return await self.save(entity)
    async def delete(self, customer_id: int) -> bool:
        raise NotImplementedError("Hard delete of customers is not supported. Use deactivation.")
    async def get_total_outstanding_balance(self) -> Decimal:
        async with self.db_manager.session() as session:
            stmt = select(func.sum(SalesInvoice.total_amount - SalesInvoice.amount_paid)).where(SalesInvoice.status.in_([InvoiceStatusEnum.APPROVED.value, InvoiceStatusEnum.PARTIALLY_PAID.value, InvoiceStatusEnum.OVERDUE.value]))
            result = await session.execute(stmt)
            total_outstanding = result.scalar_one_or_none()
            return total_outstanding if total_outstanding is not None else Decimal(0)
    async def get_total_overdue_balance(self) -> Decimal:
        async with self.db_manager.session() as session:
            stmt = select(func.sum(SalesInvoice.total_amount - SalesInvoice.amount_paid)).where(SalesInvoice.status == InvoiceStatusEnum.OVERDUE.value)
            result = await session.execute(stmt)
            total_overdue = result.scalar_one_or_none()
            return total_overdue if total_overdue is not None else Decimal(0)
    
    async def get_ar_aging_summary(self, as_of_date: date) -> Dict[str, Decimal]:
        aging_summary = {
            "Current": Decimal(0),    
            "1-30 Days": Decimal(0),  
            "31-60 Days": Decimal(0), 
            "61-90 Days": Decimal(0), 
            "91+ Days": Decimal(0)    
        }
        async with self.db_manager.session() as session:
            stmt = select(SalesInvoice).where(
                SalesInvoice.status.in_([InvoiceStatusEnum.APPROVED.value, InvoiceStatusEnum.PARTIALLY_PAID.value, InvoiceStatusEnum.OVERDUE.value]),
                SalesInvoice.total_amount > SalesInvoice.amount_paid
            )
            result = await session.execute(stmt)
            outstanding_invoices: List[SalesInvoice] = list(result.scalars().all())

            for inv in outstanding_invoices:
                outstanding_balance = inv.total_amount - inv.amount_paid
                if outstanding_balance <= Decimal("0.005"): 
                    continue
                
                days_overdue = (as_of_date - inv.due_date).days

                if days_overdue <= 0: # Not yet due or due today
                    aging_summary["Current"] += outstanding_balance
                elif 1 <= days_overdue <= 30:
                    aging_summary["1-30 Days"] += outstanding_balance
                elif 31 <= days_overdue <= 60:
                    aging_summary["31-60 Days"] += outstanding_balance
                elif 61 <= days_overdue <= 90:
                    aging_summary["61-90 Days"] += outstanding_balance
                else: # days_overdue >= 91
                    aging_summary["91+ Days"] += outstanding_balance
        
        return {k: v.quantize(Decimal("0.01")) for k, v in aging_summary.items()}


class VendorService(IVendorRepository):
    def __init__(self, db_manager: "DatabaseManager", app_core: Optional["ApplicationCore"] = None):
        self.db_manager = db_manager; self.app_core = app_core
        self.logger = app_core.logger if app_core and hasattr(app_core, 'logger') else logging.getLogger(self.__class__.__name__)
    async def get_by_id(self, vendor_id: int) -> Optional[Vendor]:
        async with self.db_manager.session() as session:
            stmt = select(Vendor).options(selectinload(Vendor.currency), selectinload(Vendor.payables_account),selectinload(Vendor.created_by_user), selectinload(Vendor.updated_by_user)).where(Vendor.id == vendor_id)
            result = await session.execute(stmt); return result.scalars().first()
    async def get_all(self) -> List[Vendor]:
        async with self.db_manager.session() as session:
            stmt = select(Vendor).order_by(Vendor.name); result = await session.execute(stmt); return list(result.scalars().all())
    async def get_all_summary(self, active_only: bool = True,search_term: Optional[str] = None,page: int = 1, page_size: int = 50) -> List[VendorSummaryData]:
        async with self.db_manager.session() as session:
            conditions = []; 
            if active_only: conditions.append(Vendor.is_active == True)
            if search_term: search_pattern = f"%{search_term}%"; conditions.append(or_(Vendor.vendor_code.ilike(search_pattern), Vendor.name.ilike(search_pattern), Vendor.email.ilike(search_pattern) if Vendor.email else False))
            stmt = select(Vendor.id, Vendor.vendor_code, Vendor.name, Vendor.email, Vendor.phone, Vendor.is_active)
            if conditions: stmt = stmt.where(and_(*conditions))
            stmt = stmt.order_by(Vendor.name)
            if page_size > 0: stmt = stmt.limit(page_size).offset((page - 1) * page_size)
            result = await session.execute(stmt); return [VendorSummaryData.model_validate(row) for row in result.mappings().all()]
    async def get_by_code(self, code: str) -> Optional[Vendor]:
        async with self.db_manager.session() as session:
            stmt = select(Vendor).where(Vendor.vendor_code == code); result = await session.execute(stmt); return result.scalars().first()
    async def save(self, vendor: Vendor) -> Vendor:
        async with self.db_manager.session() as session:
            session.add(vendor); await session.flush(); await session.refresh(vendor); return vendor
    async def add(self, entity: Vendor) -> Vendor: return await self.save(entity)
    async def update(self, entity: Vendor) -> Vendor: return await self.save(entity)
    async def delete(self, vendor_id: int) -> bool:
        raise NotImplementedError("Hard delete of vendors is not supported. Use deactivation.")
    async def get_total_outstanding_balance(self) -> Decimal:
        async with self.db_manager.session() as session:
            stmt = select(func.sum(PurchaseInvoice.total_amount - PurchaseInvoice.amount_paid)).where(PurchaseInvoice.status.in_([InvoiceStatusEnum.APPROVED.value, InvoiceStatusEnum.PARTIALLY_PAID.value, InvoiceStatusEnum.OVERDUE.value]))
            result = await session.execute(stmt)
            total_outstanding = result.scalar_one_or_none()
            return total_outstanding if total_outstanding is not None else Decimal(0)
    async def get_total_overdue_balance(self) -> Decimal:
        async with self.db_manager.session() as session:
            stmt = select(func.sum(PurchaseInvoice.total_amount - PurchaseInvoice.amount_paid)).where(PurchaseInvoice.status == InvoiceStatusEnum.OVERDUE.value)
            result = await session.execute(stmt)
            total_overdue = result.scalar_one_or_none()
            return total_overdue if total_overdue is not None else Decimal(0)

    async def get_ap_aging_summary(self, as_of_date: date) -> Dict[str, Decimal]:
        aging_summary = {
            "Current": Decimal(0),    
            "1-30 Days": Decimal(0),  
            "31-60 Days": Decimal(0),
            "61-90 Days": Decimal(0),
            "91+ Days": Decimal(0)
        }
        async with self.db_manager.session() as session:
            stmt = select(PurchaseInvoice).where(
                PurchaseInvoice.status.in_([InvoiceStatusEnum.APPROVED.value, InvoiceStatusEnum.PARTIALLY_PAID.value, InvoiceStatusEnum.OVERDUE.value]),
                PurchaseInvoice.total_amount > PurchaseInvoice.amount_paid
            )
            result = await session.execute(stmt)
            outstanding_invoices: List[PurchaseInvoice] = list(result.scalars().all())

            for inv in outstanding_invoices:
                outstanding_balance = inv.total_amount - inv.amount_paid
                if outstanding_balance <= Decimal("0.005"):
                    continue
                
                days_overdue = (as_of_date - inv.due_date).days

                if days_overdue <= 0:
                    aging_summary["Current"] += outstanding_balance
                elif 1 <= days_overdue <= 30:
                    aging_summary["1-30 Days"] += outstanding_balance
                elif 31 <= days_overdue <= 60:
                    aging_summary["31-60 Days"] += outstanding_balance
                elif 61 <= days_overdue <= 90:
                    aging_summary["61-90 Days"] += outstanding_balance
                else: 
                    aging_summary["91+ Days"] += outstanding_balance
        
        return {k: v.quantize(Decimal("0.01")) for k, v in aging_summary.items()}

class ProductService(IProductRepository): 
    def __init__(self, db_manager: "DatabaseManager", app_core: Optional["ApplicationCore"] = None):
        self.db_manager = db_manager; self.app_core = app_core
        self.logger = app_core.logger if app_core and hasattr(app_core, 'logger') else logging.getLogger(self.__class__.__name__)
    async def get_by_id(self, product_id: int) -> Optional[Product]:
        async with self.db_manager.session() as session:
            stmt = select(Product).options(selectinload(Product.sales_account),selectinload(Product.purchase_account),selectinload(Product.inventory_account),selectinload(Product.tax_code_obj),selectinload(Product.created_by_user),selectinload(Product.updated_by_user)).where(Product.id == product_id)
            result = await session.execute(stmt); return result.scalars().first()
    async def get_all(self) -> List[Product]:
        async with self.db_manager.session() as session:
            stmt = select(Product).order_by(Product.name); result = await session.execute(stmt); return list(result.scalars().all())
    async def get_all_summary(self, active_only: bool = True,product_type_filter: Optional[ProductTypeEnum] = None,search_term: Optional[str] = None,page: int = 1, page_size: int = 50) -> List[ProductSummaryData]:
        async with self.db_manager.session() as session:
            conditions = []; 
            if active_only: conditions.append(Product.is_active == True)
            if product_type_filter: conditions.append(Product.product_type == product_type_filter.value)
            if search_term: search_pattern = f"%{search_term}%"; conditions.append(or_(Product.product_code.ilike(search_pattern), Product.name.ilike(search_pattern), Product.description.ilike(search_pattern) if Product.description else False ))
            stmt = select(Product.id, Product.product_code, Product.name, Product.product_type, Product.sales_price, Product.purchase_price, Product.is_active)
            if conditions: stmt = stmt.where(and_(*conditions))
            stmt = stmt.order_by(Product.product_type, Product.name)
            if page_size > 0: stmt = stmt.limit(page_size).offset((page - 1) * page_size)
            result = await session.execute(stmt); return [ProductSummaryData.model_validate(row) for row in result.mappings().all()]
    async def get_by_code(self, code: str) -> Optional[Product]:
        async with self.db_manager.session() as session:
            stmt = select(Product).where(Product.product_code == code); result = await session.execute(stmt); return result.scalars().first()
    async def save(self, product: Product) -> Product:
        async with self.db_manager.session() as session:
            session.add(product); await session.flush(); await session.refresh(product); return product
    async def add(self, entity: Product) -> Product: return await self.save(entity)
    async def update(self, entity: Product) -> Product: return await self.save(entity)
    async def delete(self, product_id: int) -> bool:
        raise NotImplementedError("Hard delete of products/services is not supported. Use deactivation.")

class SalesInvoiceService(ISalesInvoiceRepository):
    def __init__(self, db_manager: "DatabaseManager", app_core: Optional["ApplicationCore"] = None):
        self.db_manager = db_manager
        self.app_core = app_core
        self.logger = app_core.logger if app_core and hasattr(app_core, 'logger') else logging.getLogger(self.__class__.__name__)
    async def get_by_id(self, invoice_id: int) -> Optional[SalesInvoice]:
        async with self.db_manager.session() as session:
            stmt = select(SalesInvoice).options(selectinload(SalesInvoice.lines).selectinload(SalesInvoiceLine.product),selectinload(SalesInvoice.lines).selectinload(SalesInvoiceLine.tax_code_obj),selectinload(SalesInvoice.customer), selectinload(SalesInvoice.currency),selectinload(SalesInvoice.journal_entry), selectinload(SalesInvoice.created_by_user), selectinload(SalesInvoice.updated_by_user)).where(SalesInvoice.id == invoice_id)
            result = await session.execute(stmt); return result.scalars().first()
    async def get_all(self) -> List[SalesInvoice]:
        async with self.db_manager.session() as session:
            stmt = select(SalesInvoice).order_by(SalesInvoice.invoice_date.desc(), SalesInvoice.invoice_no.desc())
            result = await session.execute(stmt); return list(result.scalars().all())
    async def get_all_summary(self, customer_id: Optional[int] = None, status_list: Optional[List[InvoiceStatusEnum]] = None, start_date: Optional[date] = None, end_date: Optional[date] = None,page: int = 1, page_size: int = 50) -> List[SalesInvoiceSummaryData]:
        async with self.db_manager.session() as session:
            conditions = []
            if customer_id is not None: conditions.append(SalesInvoice.customer_id == customer_id)
            if status_list: conditions.append(SalesInvoice.status.in_([s.value for s in status_list]))
            if start_date: conditions.append(SalesInvoice.invoice_date >= start_date)
            if end_date: conditions.append(SalesInvoice.invoice_date <= end_date)
            stmt = select( SalesInvoice.id, SalesInvoice.invoice_no, SalesInvoice.invoice_date, SalesInvoice.due_date, Customer.name.label("customer_name"), SalesInvoice.total_amount, SalesInvoice.amount_paid, SalesInvoice.status, SalesInvoice.currency_code).join(Customer, SalesInvoice.customer_id == Customer.id) 
            if conditions: stmt = stmt.where(and_(*conditions))
            stmt = stmt.order_by(SalesInvoice.invoice_date.desc(), SalesInvoice.invoice_no.desc())
            if page_size > 0 : stmt = stmt.limit(page_size).offset((page - 1) * page_size)
            result = await session.execute(stmt); return [SalesInvoiceSummaryData.model_validate(row) for row in result.mappings().all()]
    async def get_by_invoice_no(self, invoice_no: str) -> Optional[SalesInvoice]: 
        async with self.db_manager.session() as session:
            stmt = select(SalesInvoice).options(selectinload(SalesInvoice.lines)).where(SalesInvoice.invoice_no == invoice_no)
            result = await session.execute(stmt); return result.scalars().first()
    async def save(self, invoice: SalesInvoice) -> SalesInvoice:
        async with self.db_manager.session() as session:
            session.add(invoice); await session.flush(); await session.refresh(invoice)
            if invoice.id and invoice.lines: await session.refresh(invoice, attribute_names=['lines'])
            return invoice
    async def add(self, entity: SalesInvoice) -> SalesInvoice: return await self.save(entity)
    async def update(self, entity: SalesInvoice) -> SalesInvoice: return await self.save(entity)
    async def delete(self, invoice_id: int) -> bool:
        raise NotImplementedError("Hard delete of sales invoices is not supported. Use voiding/cancellation.")
    async def get_outstanding_invoices_for_customer(self, customer_id: Optional[int], as_of_date: date) -> List[SalesInvoice]:
        async with self.db_manager.session() as session:
            conditions = [
                SalesInvoice.status.in_([
                    InvoiceStatusEnum.APPROVED.value, 
                    InvoiceStatusEnum.PARTIALLY_PAID.value, 
                    InvoiceStatusEnum.OVERDUE.value
                ]),
                SalesInvoice.total_amount > SalesInvoice.amount_paid,
                SalesInvoice.invoice_date <= as_of_date
            ]
            if customer_id is not None:
                conditions.append(SalesInvoice.customer_id == customer_id)
            
            stmt = select(SalesInvoice).options(selectinload(SalesInvoice.customer)).where(and_(*conditions))
            result = await session.execute(stmt)
            return list(result.scalars().all())
    async def get_all_open_invoices(self) -> List[SalesInvoice]:
        async with self.db_manager.session() as session:
            stmt = select(SalesInvoice).options(selectinload(SalesInvoice.customer)).where(
                SalesInvoice.status.in_([InvoiceStatusEnum.APPROVED.value, InvoiceStatusEnum.PARTIALLY_PAID.value, InvoiceStatusEnum.OVERDUE.value]),
                SalesInvoice.total_amount > SalesInvoice.amount_paid
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

class PurchaseInvoiceService(IPurchaseInvoiceRepository):
    def __init__(self, db_manager: "DatabaseManager", app_core: Optional["ApplicationCore"] = None):
        self.db_manager = db_manager
        self.app_core = app_core
        self.logger = app_core.logger if app_core and hasattr(app_core, 'logger') else logging.getLogger(self.__class__.__name__)
    async def get_by_id(self, invoice_id: int) -> Optional[PurchaseInvoice]:
        async with self.db_manager.session() as session:
            stmt = select(PurchaseInvoice).options(selectinload(PurchaseInvoice.lines).selectinload(PurchaseInvoiceLine.product),selectinload(PurchaseInvoice.lines).selectinload(PurchaseInvoiceLine.tax_code_obj),selectinload(PurchaseInvoice.vendor), selectinload(PurchaseInvoice.currency),selectinload(PurchaseInvoice.journal_entry),selectinload(PurchaseInvoice.created_by_user),selectinload(PurchaseInvoice.updated_by_user)).where(PurchaseInvoice.id == invoice_id)
            result = await session.execute(stmt); return result.scalars().first()
    async def get_all(self) -> List[PurchaseInvoice]:
        async with self.db_manager.session() as session:
            stmt = select(PurchaseInvoice).order_by(PurchaseInvoice.invoice_date.desc(), PurchaseInvoice.invoice_no.desc())
            result = await session.execute(stmt); return list(result.scalars().all())
    async def get_all_summary(self, vendor_id: Optional[int] = None, status_list: Optional[List[InvoiceStatusEnum]] = None, start_date: Optional[date] = None, end_date: Optional[date] = None,page: int = 1, page_size: int = 50) -> List[PurchaseInvoiceSummaryData]:
        async with self.db_manager.session() as session:
            conditions = []
            if vendor_id is not None: conditions.append(PurchaseInvoice.vendor_id == vendor_id)
            if status_list: conditions.append(PurchaseInvoice.status.in_([s.value for s in status_list]))
            if start_date: conditions.append(PurchaseInvoice.invoice_date >= start_date)
            if end_date: conditions.append(PurchaseInvoice.invoice_date <= end_date)
            stmt = select( PurchaseInvoice.id, PurchaseInvoice.invoice_no, PurchaseInvoice.vendor_invoice_no, PurchaseInvoice.invoice_date, Vendor.name.label("vendor_name"), PurchaseInvoice.total_amount, PurchaseInvoice.status, PurchaseInvoice.currency_code).join(Vendor, PurchaseInvoice.vendor_id == Vendor.id)
            if conditions: stmt = stmt.where(and_(*conditions))
            stmt = stmt.order_by(PurchaseInvoice.invoice_date.desc(), PurchaseInvoice.invoice_no.desc())
            if page_size > 0: stmt = stmt.limit(page_size).offset((page - 1) * page_size)
            result = await session.execute(stmt); return [PurchaseInvoiceSummaryData.model_validate(row) for row in result.mappings().all()]
    async def get_by_internal_ref_no(self, internal_ref_no: str) -> Optional[PurchaseInvoice]: 
        async with self.db_manager.session() as session:
            stmt = select(PurchaseInvoice).options(selectinload(PurchaseInvoice.lines)).where(PurchaseInvoice.invoice_no == internal_ref_no) 
            result = await session.execute(stmt); return result.scalars().first()
    async def get_by_vendor_and_vendor_invoice_no(self, vendor_id: int, vendor_invoice_no: str) -> Optional[PurchaseInvoice]:
        async with self.db_manager.session() as session:
            stmt = select(PurchaseInvoice).options(selectinload(PurchaseInvoice.lines)).where(PurchaseInvoice.vendor_id == vendor_id, PurchaseInvoice.vendor_invoice_no == vendor_invoice_no)
            result = await session.execute(stmt); return result.scalars().first() 
    async def save(self, invoice: PurchaseInvoice) -> PurchaseInvoice:
        async with self.db_manager.session() as session:
            session.add(invoice); await session.flush(); await session.refresh(invoice)
            if invoice.id and invoice.lines: await session.refresh(invoice, attribute_names=['lines'])
            return invoice
    async def add(self, entity: PurchaseInvoice) -> PurchaseInvoice: return await self.save(entity)
    async def update(self, entity: PurchaseInvoice) -> PurchaseInvoice: return await self.save(entity)
    async def delete(self, invoice_id: int) -> bool:
        async with self.db_manager.session() as session:
            pi = await session.get(PurchaseInvoice, invoice_id)
            if pi and pi.status == InvoiceStatusEnum.DRAFT.value: await session.delete(pi); return True
            elif pi: self.logger.warning(f"Attempt to delete non-draft PI ID {invoice_id} with status {pi.status}. Denied."); raise ValueError(f"Cannot delete PI {pi.invoice_no} as its status is '{pi.status}'. Only Draft invoices can be deleted.")
        return False
    async def get_outstanding_invoices_for_vendor(self, vendor_id: Optional[int], as_of_date: date) -> List[PurchaseInvoice]:
        async with self.db_manager.session() as session:
            conditions = [
                PurchaseInvoice.status.in_([
                    InvoiceStatusEnum.APPROVED.value, 
                    InvoiceStatusEnum.PARTIALLY_PAID.value, 
                    InvoiceStatusEnum.OVERDUE.value
                ]),
                PurchaseInvoice.total_amount > PurchaseInvoice.amount_paid,
                PurchaseInvoice.invoice_date <= as_of_date
            ]
            if vendor_id is not None:
                conditions.append(PurchaseInvoice.vendor_id == vendor_id)
            
            stmt = select(PurchaseInvoice).options(selectinload(PurchaseInvoice.vendor)).where(and_(*conditions))
            result = await session.execute(stmt)
            return list(result.scalars().all())
    async def get_all_open_invoices(self) -> List[PurchaseInvoice]:
        async with self.db_manager.session() as session:
            stmt = select(PurchaseInvoice).options(selectinload(PurchaseInvoice.vendor)).where(
                PurchaseInvoice.status.in_([InvoiceStatusEnum.APPROVED.value, InvoiceStatusEnum.PARTIALLY_PAID.value, InvoiceStatusEnum.OVERDUE.value]),
                PurchaseInvoice.total_amount > PurchaseInvoice.amount_paid
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

class InventoryMovementService(IInventoryMovementRepository):
    def __init__(self, db_manager: "DatabaseManager", app_core: Optional["ApplicationCore"] = None):
        self.db_manager = db_manager; self.app_core = app_core
        self.logger = app_core.logger if app_core and hasattr(app_core, 'logger') else logging.getLogger(self.__class__.__name__)
    async def get_by_id(self, id_val: int) -> Optional[InventoryMovement]:
        async with self.db_manager.session() as session: return await session.get(InventoryMovement, id_val)
    async def get_all(self) -> List[InventoryMovement]:
        async with self.db_manager.session() as session:
            stmt = select(InventoryMovement).order_by(InventoryMovement.movement_date.desc(), InventoryMovement.id.desc())
            result = await session.execute(stmt); return list(result.scalars().all())
    async def save(self, entity: InventoryMovement, session: Optional[AsyncSession] = None) -> InventoryMovement:
        async def _save_logic(current_session: AsyncSession):
            current_session.add(entity); await current_session.flush(); await current_session.refresh(entity); return entity
        if session: return await _save_logic(session)
        else:
            async with self.db_manager.session() as new_session: return await _save_logic(new_session)
    async def add(self, entity: InventoryMovement) -> InventoryMovement: return await self.save(entity) 
    async def update(self, entity: InventoryMovement) -> InventoryMovement:
        self.logger.warning(f"Update called on InventoryMovementService for ID {entity.id}. Typically movements are immutable.")
        return await self.save(entity)
    async def delete(self, id_val: int) -> bool:
        self.logger.warning(f"Hard delete attempted for InventoryMovement ID {id_val}. This is generally not recommended.")
        async with self.db_manager.session() as session:
            entity = await session.get(InventoryMovement, id_val)
            if entity: await session.delete(entity); return True
            return False

class BankAccountService(IBankAccountRepository):
    def __init__(self, db_manager: "DatabaseManager", app_core: Optional["ApplicationCore"] = None):
        self.db_manager = db_manager; self.app_core = app_core
        self.logger = app_core.logger if app_core and hasattr(app_core, 'logger') else logging.getLogger(self.__class__.__name__)
    async def get_by_id(self, id_val: int) -> Optional[BankAccount]:
        async with self.db_manager.session() as session:
            stmt = select(BankAccount).options(selectinload(BankAccount.currency),selectinload(BankAccount.gl_account),selectinload(BankAccount.created_by_user),selectinload(BankAccount.updated_by_user)).where(BankAccount.id == id_val)
            result = await session.execute(stmt); return result.scalars().first()
    async def get_all(self) -> List[BankAccount]:
        async with self.db_manager.session() as session:
            stmt = select(BankAccount).order_by(BankAccount.account_name); result = await session.execute(stmt); return list(result.scalars().all())
    async def get_all_summary(self, active_only: bool = True, currency_code: Optional[str] = None,page: int = 1, page_size: int = 50) -> List[BankAccountSummaryData]:
        async with self.db_manager.session() as session:
            conditions = []
            if active_only: conditions.append(BankAccount.is_active == True)
            if currency_code: conditions.append(BankAccount.currency_code == currency_code)
            stmt = select(BankAccount.id, BankAccount.account_name, BankAccount.bank_name,BankAccount.account_number, BankAccount.currency_code,BankAccount.current_balance, BankAccount.is_active,Account.code.label("gl_account_code"), Account.name.label("gl_account_name")).join(Account, BankAccount.gl_account_id == Account.id)
            if conditions: stmt = stmt.where(and_(*conditions))
            stmt = stmt.order_by(BankAccount.account_name)
            if page_size > 0 : stmt = stmt.limit(page_size).offset((page - 1) * page_size)
            result = await session.execute(stmt); return [BankAccountSummaryData.model_validate(row._asdict()) for row in result.mappings().all()]
    async def get_by_account_number(self, account_number: str) -> Optional[BankAccount]:
        async with self.db_manager.session() as session:
            stmt = select(BankAccount).where(BankAccount.account_number == account_number); result = await session.execute(stmt); return result.scalars().first()
    async def save(self, entity: BankAccount) -> BankAccount:
        async with self.db_manager.session() as session:
            session.add(entity); await session.flush(); await session.refresh(entity); return entity
    async def add(self, entity: BankAccount) -> BankAccount: return await self.save(entity)
    async def update(self, entity: BankAccount) -> BankAccount: return await self.save(entity)
    async def delete(self, id_val: int) -> bool:
        bank_account = await self.get_by_id(id_val)
        if bank_account:
            if bank_account.is_active: bank_account.is_active = False; await self.save(bank_account); return True
            else: self.logger.info(f"BankAccount ID {id_val} is already inactive. No change made by delete."); return True 
        return False
    async def get_by_gl_account_id(self, gl_account_id: int) -> Optional[BankAccount]: # New method
        async with self.db_manager.session() as session:
            stmt = select(BankAccount).where(BankAccount.gl_account_id == gl_account_id)
            result = await session.execute(stmt)
            return result.scalars().first()

class BankTransactionService(IBankTransactionRepository):
    def __init__(self, db_manager: "DatabaseManager", app_core: Optional["ApplicationCore"] = None):
        self.db_manager = db_manager; self.app_core = app_core
        self.logger = app_core.logger if app_core and hasattr(app_core, 'logger') else logging.getLogger(self.__class__.__name__)
    async def get_by_id(self, id_val: int) -> Optional[BankTransaction]:
        async with self.db_manager.session() as session:
            stmt = select(BankTransaction).options(selectinload(BankTransaction.bank_account),selectinload(BankTransaction.journal_entry), selectinload(BankTransaction.created_by_user),selectinload(BankTransaction.updated_by_user)).where(BankTransaction.id == id_val)
            result = await session.execute(stmt); return result.scalars().first()
    async def get_all(self) -> List[BankTransaction]: 
        async with self.db_manager.session() as session:
            stmt = select(BankTransaction).order_by(BankTransaction.transaction_date.desc(), BankTransaction.id.desc())
            result = await session.execute(stmt); return list(result.scalars().all())
    async def get_all_for_bank_account(self, bank_account_id: int,start_date: Optional[date] = None,end_date: Optional[date] = None,transaction_type: Optional[BankTransactionTypeEnum] = None,is_reconciled: Optional[bool] = None,is_from_statement_filter: Optional[bool] = None, page: int = 1, page_size: int = 50) -> List[BankTransactionSummaryData]:
        async with self.db_manager.session() as session:
            conditions = [BankTransaction.bank_account_id == bank_account_id]
            if start_date: conditions.append(BankTransaction.transaction_date >= start_date)
            if end_date: conditions.append(BankTransaction.transaction_date <= end_date)
            if transaction_type: conditions.append(BankTransaction.transaction_type == transaction_type.value)
            if is_reconciled is not None: conditions.append(BankTransaction.is_reconciled == is_reconciled)
            if is_from_statement_filter is not None: conditions.append(BankTransaction.is_from_statement == is_from_statement_filter)
            stmt = select(BankTransaction).where(and_(*conditions)).order_by(BankTransaction.transaction_date.desc(), BankTransaction.value_date.desc(), BankTransaction.id.desc())
            if page_size > 0: stmt = stmt.limit(page_size).offset((page - 1) * page_size)
            result = await session.execute(stmt); txns_orm = result.scalars().all()
            summaries: List[BankTransactionSummaryData] = []
            for txn in txns_orm:
                summaries.append(BankTransactionSummaryData(id=txn.id,transaction_date=txn.transaction_date,value_date=txn.value_date,transaction_type=BankTransactionTypeEnum(txn.transaction_type), description=txn.description,reference=txn.reference,amount=txn.amount, is_reconciled=txn.is_reconciled, updated_at=txn.updated_at))
            return summaries
    async def save(self, entity: BankTransaction, session: Optional[AsyncSession] = None) -> BankTransaction:
        async def _save_logic(current_session: AsyncSession):
            current_session.add(entity); await current_session.flush(); await current_session.refresh(entity); return entity
        if session: return await _save_logic(session)
        else:
            async with self.db_manager.session() as new_session: return await _save_logic(new_session)
    async def add(self, entity: BankTransaction) -> BankTransaction: return await self.save(entity)
    async def update(self, entity: BankTransaction) -> BankTransaction: return await self.save(entity)
    async def delete(self, id_val: int) -> bool:
        async with self.db_manager.session() as session:
            entity = await session.get(BankTransaction, id_val)
            if entity:
                if entity.is_reconciled: self.logger.warning(f"Attempt to delete reconciled BankTransaction ID {id_val}. Denied."); return False 
                await session.delete(entity); return True
            return False

class PaymentService(IPaymentRepository):
    def __init__(self, db_manager: "DatabaseManager", app_core: Optional["ApplicationCore"] = None):
        self.db_manager = db_manager; self.app_core = app_core
        self.logger = app_core.logger if app_core and hasattr(app_core, 'logger') else logging.getLogger(self.__class__.__name__)
    async def get_by_id(self, id_val: int) -> Optional[Payment]:
        async with self.db_manager.session() as session:
            stmt = select(Payment).options(selectinload(Payment.allocations),selectinload(Payment.bank_account),selectinload(Payment.currency),selectinload(Payment.journal_entry),selectinload(Payment.created_by_user),selectinload(Payment.updated_by_user)).where(Payment.id == id_val)
            result = await session.execute(stmt); return result.scalars().first()
            
    async def get_payment_with_vendor(self, payment_id: int) -> Optional[Payment]:
        async with self.db_manager.session() as session:
            stmt = select(Payment).options(
                joinedload(Payment.vendor)
            ).where(Payment.id == payment_id)
            result = await session.execute(stmt)
            return result.scalars().first()
            
    async def get_all(self) -> List[Payment]:
        async with self.db_manager.session() as session:
            stmt = select(Payment).order_by(Payment.payment_date.desc(), Payment.payment_no.desc())
            result = await session.execute(stmt); return list(result.scalars().all())
    async def get_by_payment_no(self, payment_no: str) -> Optional[Payment]:
        async with self.db_manager.session() as session:
            stmt = select(Payment).options(selectinload(Payment.allocations)).where(Payment.payment_no == payment_no)
            result = await session.execute(stmt); return result.scalars().first()
            
    async def get_all_summary(self, entity_type: Optional[PaymentEntityTypeEnum] = None,entity_id: Optional[int] = None,status_list: Optional[List[PaymentStatusEnum]] = None,start_date: Optional[date] = None,end_date: Optional[date] = None,page: int = 1, page_size: int = 50, wht_applicable_only: bool = False) -> List[PaymentSummaryData]:
        async with self.db_manager.session() as session:
            conditions = []
            if entity_type: conditions.append(Payment.entity_type == entity_type.value)
            if entity_id is not None: conditions.append(Payment.entity_id == entity_id)
            if status_list: conditions.append(Payment.status.in_([s.value for s in status_list]))
            if start_date: conditions.append(Payment.payment_date >= start_date)
            if end_date: conditions.append(Payment.payment_date <= end_date)
            if wht_applicable_only:
                conditions.append(Vendor.withholding_tax_applicable == True)

            stmt = select(
                Payment.id, Payment.payment_no, Payment.payment_date, Payment.payment_type,
                Payment.payment_method, Payment.entity_type, Payment.entity_id,
                Payment.amount, Payment.currency_code, Payment.status,
                case(
                    (Payment.entity_type == PaymentEntityTypeEnum.CUSTOMER.value, Customer.name),
                    (Payment.entity_type == PaymentEntityTypeEnum.VENDOR.value, Vendor.name),
                    else_=literal_column("'Other/N/A'")
                ).label("entity_name")
            ).select_from(Payment).outerjoin(
                Customer, and_(Payment.entity_id == Customer.id, Payment.entity_type == PaymentEntityTypeEnum.CUSTOMER.value)
            ).outerjoin(
                Vendor, and_(Payment.entity_id == Vendor.id, Payment.entity_type == PaymentEntityTypeEnum.VENDOR.value)
            )
            
            if conditions: stmt = stmt.where(and_(*conditions))
            
            stmt = stmt.order_by(Payment.payment_date.desc(), Payment.payment_no.desc())
            if page_size > 0: stmt = stmt.limit(page_size).offset((page - 1) * page_size)
            result = await session.execute(stmt)
            return [PaymentSummaryData.model_validate(row._asdict()) for row in result.mappings().all()]
            
    async def save(self, entity: Payment, session: Optional[AsyncSession] = None) -> Payment:
        async def _save_logic(current_session: AsyncSession):
            current_session.add(entity); await current_session.flush(); await current_session.refresh(entity)
            if entity.id and entity.allocations: await current_session.refresh(entity, attribute_names=['allocations'])
            return entity
        if session: return await _save_logic(session)
        else:
            async with self.db_manager.session() as new_session: return await _save_logic(new_session) # type: ignore
    async def add(self, entity: Payment) -> Payment: return await self.save(entity)
    async def update(self, entity: Payment) -> Payment: return await self.save(entity)
    async def delete(self, id_val: int) -> bool:
        async with self.db_manager.session() as session:
            payment = await session.get(Payment, id_val)
            if payment:
                if payment.status == PaymentStatusEnum.DRAFT.value: await session.delete(payment); self.logger.info(f"Draft Payment ID {id_val} deleted."); return True
                else: self.logger.warning(f"Attempt to delete non-draft Payment ID {id_val} (status: {payment.status}). Denied."); return False 
            return False

class BankReconciliationService(IBankReconciliationRepository):
    def __init__(self, db_manager: "DatabaseManager", app_core: Optional["ApplicationCore"] = None):
        self.db_manager = db_manager
        self.app_core = app_core
        self.logger = app_core.logger if app_core and hasattr(app_core, 'logger') else logging.getLogger(self.__class__.__name__)

    async def get_by_id(self, id_val: int) -> Optional[BankReconciliation]:
        async with self.db_manager.session() as session:
            stmt = select(BankReconciliation).options(
                selectinload(BankReconciliation.created_by_user) 
            ).where(BankReconciliation.id == id_val)
            result = await session.execute(stmt)
            return result.scalars().first()

    async def get_all(self) -> List[BankReconciliation]:
        async with self.db_manager.session() as session:
            stmt = select(BankReconciliation).order_by(BankReconciliation.statement_date.desc())
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def add(self, entity: BankReconciliation, session: Optional[AsyncSession] = None) -> BankReconciliation:
        return await self.save(entity, session)

    async def update(self, entity: BankReconciliation, session: Optional[AsyncSession] = None) -> BankReconciliation:
        return await self.save(entity, session)

    async def delete(self, id_val: int) -> bool:
        self.logger.warning(f"Deletion of BankReconciliation ID {id_val} attempted. This operation un-reconciles linked transactions.")
        async with self.db_manager.session() as session: 
            async with session.begin(): 
                update_stmt = (
                    sqlalchemy_update(BankTransaction)
                    .where(BankTransaction.reconciled_bank_reconciliation_id == id_val)
                    .values(is_reconciled=False, reconciled_date=None, reconciled_bank_reconciliation_id=None)
                    .execution_options(synchronize_session=False) 
                )
                await session.execute(update_stmt)
                entity = await session.get(BankReconciliation, id_val)
                if entity:
                    await session.delete(entity)
                    return True
            return False 
            
    async def save(self, entity: BankReconciliation, session: Optional[AsyncSession] = None) -> BankReconciliation:
        async def _save_logic(current_session: AsyncSession):
            current_session.add(entity)
            await current_session.flush()
            await current_session.refresh(entity)
            return entity
        if session: return await _save_logic(session)
        else:
            async with self.db_manager.session() as new_session:
                return await _save_logic(new_session)

    async def get_or_create_draft_reconciliation(
        self, 
        bank_account_id: int, 
        statement_date: date, 
        statement_ending_balance: Decimal, 
        user_id: int, 
        session: AsyncSession
    ) -> BankReconciliation:
        draft_stmt = select(BankReconciliation).where(
            BankReconciliation.bank_account_id == bank_account_id,
            BankReconciliation.statement_date == statement_date,
            BankReconciliation.status == "Draft"
        )
        result = await session.execute(draft_stmt)
        existing_draft = result.scalars().first()

        if existing_draft:
            self.logger.info(f"Found existing draft reconciliation ID {existing_draft.id} for account {bank_account_id} on {statement_date}.")
            if existing_draft.statement_ending_balance != statement_ending_balance:
                existing_draft.statement_ending_balance = statement_ending_balance
            return existing_draft
        else:
            self.logger.info(f"Creating new draft reconciliation for account {bank_account_id} on {statement_date}.")
            new_draft = BankReconciliation(
                bank_account_id=bank_account_id,
                statement_date=statement_date,
                statement_ending_balance=statement_ending_balance,
                calculated_book_balance=Decimal(0), 
                reconciled_difference=statement_ending_balance, 
                status="Draft",
                created_by_user_id=user_id
            )
            session.add(new_draft)
            await session.flush()
            await session.refresh(new_draft)
            return new_draft

    async def mark_transactions_as_provisionally_reconciled(
        self, 
        draft_reconciliation_id: int, 
        transaction_ids: List[int], 
        statement_date: date, 
        user_id: int, 
        session: AsyncSession
    ) -> bool:
        if not transaction_ids:
            return True 

        update_stmt = (
            sqlalchemy_update(BankTransaction)
            .where(BankTransaction.id.in_(transaction_ids))
            .values(
                is_reconciled=True,
                reconciled_date=statement_date,
                reconciled_bank_reconciliation_id=draft_reconciliation_id
            )
            .execution_options(synchronize_session=False) 
        )
        result = await session.execute(update_stmt)
        self.logger.info(f"Marked {result.rowcount} transactions as provisionally reconciled for draft recon ID {draft_reconciliation_id}.")
        return result.rowcount == len(transaction_ids)


    async def finalize_reconciliation(
        self, 
        draft_reconciliation_id: int, 
        statement_ending_balance: Decimal, 
        calculated_book_balance: Decimal, 
        reconciled_difference: Decimal,
        user_id: int,
        session: AsyncSession 
    ) -> Result[BankReconciliation]:
        recon_orm = await session.get(BankReconciliation, draft_reconciliation_id, options=[selectinload(BankReconciliation.bank_account)])
        if not recon_orm:
            return Result.failure([f"Draft Reconciliation ID {draft_reconciliation_id} not found."])
        if recon_orm.status == "Finalized":
            return Result.failure([f"Reconciliation ID {draft_reconciliation_id} is already finalized."])

        recon_orm.status = "Finalized"
        recon_orm.statement_ending_balance = statement_ending_balance
        recon_orm.calculated_book_balance = calculated_book_balance
        recon_orm.reconciled_difference = reconciled_difference
        recon_orm.reconciliation_date = datetime.now(datetime.timezone.utc) 
        
        if recon_orm.bank_account:
            recon_orm.bank_account.last_reconciled_date = recon_orm.statement_date
            recon_orm.bank_account.last_reconciled_balance = recon_orm.statement_ending_balance 
            session.add(recon_orm.bank_account)
        else:
            self.logger.error(f"BankAccount not found for Reconciliation ID {draft_reconciliation_id} during finalization.")
            return Result.failure([f"Associated BankAccount for Reconciliation ID {draft_reconciliation_id} not found."])
            
        session.add(recon_orm)
        return Result.success(recon_orm)

    async def unreconcile_transactions( 
        self, 
        transaction_ids: List[int], 
        user_id: int, 
        session: AsyncSession
    ) -> bool:
        if not transaction_ids:
            return True
        
        update_stmt = (
            sqlalchemy_update(BankTransaction)
            .where(BankTransaction.id.in_(transaction_ids))
            .values(
                is_reconciled=False,
                reconciled_date=None,
                reconciled_bank_reconciliation_id=None
            )
            .execution_options(synchronize_session=False)
        )
        result = await session.execute(update_stmt)
        self.logger.info(f"Unreconciled {result.rowcount} transactions.")
        return result.rowcount == len(transaction_ids)

    async def get_reconciliations_for_account(
        self, 
        bank_account_id: int, 
        page: int = 1, 
        page_size: int = 20
    ) -> Tuple[List[BankReconciliationSummaryData], int]:
        async with self.db_manager.session() as session:
            base_conditions = [
                BankReconciliation.bank_account_id == bank_account_id,
                BankReconciliation.status == "Finalized" 
            ]
            
            count_stmt = select(func.count(BankReconciliation.id)).where(and_(*base_conditions))
            total_count_res = await session.execute(count_stmt)
            total_records = total_count_res.scalar_one_or_none() or 0

            stmt = select(BankReconciliation, User.username.label("created_by_username"))\
                .join(User, BankReconciliation.created_by_user_id == User.id)\
                .where(and_(*base_conditions))\
                .order_by(BankReconciliation.statement_date.desc(), BankReconciliation.id.desc()) 
            
            if page_size > 0:
                stmt = stmt.limit(page_size).offset((page - 1) * page_size)
            
            result = await session.execute(stmt)
            summaries: List[BankReconciliationSummaryData] = []
            for row in result.mappings().all():
                recon_orm = row[BankReconciliation]
                summaries.append(BankReconciliationSummaryData(
                    id=recon_orm.id, statement_date=recon_orm.statement_date,
                    statement_ending_balance=recon_orm.statement_ending_balance,
                    reconciled_difference=recon_orm.reconciled_difference,
                    reconciliation_date=recon_orm.reconciliation_date,
                    created_by_username=row.created_by_username
                ))
            return summaries, total_records

    async def get_transactions_for_reconciliation(
        self, reconciliation_id: int
    ) -> Tuple[List[BankTransactionSummaryData], List[BankTransactionSummaryData]]:
        async with self.db_manager.session() as session:
            stmt = select(BankTransaction)\
                .where(BankTransaction.reconciled_bank_reconciliation_id == reconciliation_id)\
                .order_by(BankTransaction.updated_at.desc(), BankTransaction.id) 
            
            result = await session.execute(stmt)
            all_txns_orm = result.scalars().all()

            statement_items: List[BankTransactionSummaryData] = []
            system_items: List[BankTransactionSummaryData] = []

            for txn_orm in all_txns_orm:
                summary_dto = BankTransactionSummaryData(
                    id=txn_orm.id, transaction_date=txn_orm.transaction_date,
                    value_date=txn_orm.value_date, transaction_type=BankTransactionTypeEnum(txn_orm.transaction_type),
                    description=txn_orm.description, reference=txn_orm.reference,
                    amount=txn_orm.amount, is_reconciled=txn_orm.is_reconciled, 
                    updated_at=txn_orm.updated_at
                )
                if txn_orm.is_from_statement:
                    statement_items.append(summary_dto)
                else:
                    system_items.append(summary_dto)
            
            return statement_items, system_items
```

---
https://drive.google.com/file/d/18Z0ecA7eHWs5KQHIRp_e5Cx0bR5w17Hx/view?usp=sharing, https://drive.google.com/file/d/1BF_WA-KObkI2YM4URjZNBbZmhY6R4hit/view?usp=sharing, https://drive.google.com/file/d/1nbk8mJuNOo8KdzZkSK7bdHUqlFHvy6Mo/view?usp=sharing, https://drive.google.com/file/d/1olI_wf49v-tjth1Lj1O9kS16btfgxuxp/view?usp=sharing, https://aistudio.google.com/app/prompts?state=%7B%22ids%22:%5B%221zy43aW8S1WKru7zgPsmPuT_80lFMbPbj%22%5D,%22action%22:%22open%22,%22userId%22:%22103961307342447084491%22,%22resourceKeys%22:%7B%7D%7D&usp=sharing

