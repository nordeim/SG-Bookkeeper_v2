Excellent. The startup log shows that the application is now launching successfully without any tracebacks or errors. This indicates that the refactoring of the core components and the initial set of managers that are accessed on startup has been successful.

However, as per my analysis, the refactoring is not yet complete. The remaining business logic managers still need to be updated to the new architectural standard to prevent `TypeError` exceptions if they are accessed later during the application's use.

I will now proceed with the next batch of files from my refactoring plan.

### **CodeNavigator Analysis and Execution Plan (Manager Refactoring - Part 3)**

**Goal:** Continue the systematic refactoring of all manager classes to use the `app_core` dependency injection pattern, ensuring consistency and preventing future runtime errors.

**Plan for Each File:**
1.  **Modify `__init__` Signature:** Change the constructor to `def __init__(self, app_core: "ApplicationCore"):`.
2.  **Update Attribute Initialization:** Remove the direct parameter-to-attribute assignments. Initialize all required service instances from the `app_core` object.
3.  **Validate and Generate:** Perform a line-by-line comparison to ensure only the constructor is changed and that no business logic is altered. Generate the complete, updated file.

This process will now be applied to the next set of manager files.

***

### **Complete Updated Files (Set 2 of 3)**

Here are the next two refactored manager files, focusing on the banking-related logic.

#### **File 1: `app/business_logic/bank_account_manager.py` (Corrected)**

```python
# File: app/business_logic/bank_account_manager.py
from typing import List, Optional, Dict, Any, TYPE_CHECKING, Union
from decimal import Decimal

from app.models.business.bank_account import BankAccount
from app.utils.result import Result
from app.utils.pydantic_models import (
    BankAccountCreateData, BankAccountUpdateData, BankAccountSummaryData
)

if TYPE_CHECKING:
    from app.core.application_core import ApplicationCore
    from app.services.business_services import BankAccountService
    from app.services.account_service import AccountService
    from app.services.accounting_services import CurrencyService


class BankAccountManager:
    def __init__(self, app_core: "ApplicationCore"):
        self.app_core = app_core
        self.bank_account_service: "BankAccountService" = self.app_core.bank_account_service
        self.account_service: "AccountService" = self.app_core.account_service
        self.currency_service: "CurrencyService" = self.app_core.currency_service
        self.logger = self.app_core.logger

    async def get_bank_account_for_dialog(self, bank_account_id: int) -> Optional[BankAccount]:
        try:
            return await self.bank_account_service.get_by_id(bank_account_id)
        except Exception as e:
            self.logger.error(f"Error fetching BankAccount ID {bank_account_id} for dialog: {e}", exc_info=True)
            return None

    async def get_bank_accounts_for_listing(
        self,
        active_only: bool = True,
        currency_code: Optional[str] = None,
        page: int = 1,
        page_size: int = 50
    ) -> Result[List[BankAccountSummaryData]]:
        try:
            summaries = await self.bank_account_service.get_all_summary(
                active_only=active_only,
                currency_code=currency_code,
                page=page,
                page_size=page_size
            )
            return Result.success(summaries)
        except Exception as e:
            self.logger.error(f"Error fetching bank account listing: {e}", exc_info=True)
            return Result.failure([f"Failed to retrieve bank account list: {str(e)}"])

    async def _validate_bank_account_data(
        self,
        dto: Union[BankAccountCreateData, BankAccountUpdateData],
        existing_bank_account_id: Optional[int] = None
    ) -> List[str]:
        errors: List[str] = []
        
        gl_account = await self.account_service.get_by_id(dto.gl_account_id)
        if not gl_account:
            errors.append(f"GL Account ID '{dto.gl_account_id}' not found.")
        else:
            if not gl_account.is_active:
                errors.append(f"GL Account '{gl_account.code} - {gl_account.name}' is not active.")
            if gl_account.account_type != 'Asset':
                errors.append(f"GL Account '{gl_account.code}' must be an Asset type account.")
            if not gl_account.is_bank_account: 
                errors.append(f"GL Account '{gl_account.code}' is not flagged as a bank account. Please update the Chart of Accounts.")

        currency = await self.currency_service.get_by_id(dto.currency_code)
        if not currency:
            errors.append(f"Currency Code '{dto.currency_code}' not found.")
        elif not currency.is_active:
            errors.append(f"Currency '{dto.currency_code}' is not active.")
            
        existing_by_acc_no = await self.bank_account_service.get_by_account_number(dto.account_number)
        if existing_by_acc_no and \
           (existing_bank_account_id is None or existing_by_acc_no.id != existing_bank_account_id):
            errors.append(f"Bank account number '{dto.account_number}' already exists.")

        return errors

    async def create_bank_account(self, dto: BankAccountCreateData) -> Result[BankAccount]:
        validation_errors = await self._validate_bank_account_data(dto)
        if validation_errors:
            return Result.failure(validation_errors)

        try:
            bank_account_orm = BankAccount(
                account_name=dto.account_name,
                account_number=dto.account_number,
                bank_name=dto.bank_name,
                bank_branch=dto.bank_branch,
                bank_swift_code=dto.bank_swift_code,
                currency_code=dto.currency_code,
                opening_balance=dto.opening_balance,
                opening_balance_date=dto.opening_balance_date,
                gl_account_id=dto.gl_account_id,
                is_active=dto.is_active,
                description=dto.description,
                current_balance=dto.opening_balance, 
                created_by_user_id=dto.user_id,
                updated_by_user_id=dto.user_id
            )
            saved_bank_account = await self.bank_account_service.save(bank_account_orm)
            self.logger.info(f"Bank account '{saved_bank_account.account_name}' created successfully.")
            return Result.success(saved_bank_account)
        except Exception as e:
            self.logger.error(f"Error creating bank account '{dto.account_name}': {e}", exc_info=True)
            return Result.failure([f"An unexpected error occurred: {str(e)}"])

    async def update_bank_account(self, bank_account_id: int, dto: BankAccountUpdateData) -> Result[BankAccount]:
        existing_bank_account = await self.bank_account_service.get_by_id(bank_account_id)
        if not existing_bank_account:
            return Result.failure([f"Bank Account with ID {bank_account_id} not found."])

        validation_errors = await self._validate_bank_account_data(dto, existing_bank_account_id=bank_account_id)
        if validation_errors:
            return Result.failure(validation_errors)

        try:
            update_data_dict = dto.model_dump(exclude={'id', 'user_id'}, exclude_unset=True)
            for key, value in update_data_dict.items():
                if hasattr(existing_bank_account, key):
                    setattr(existing_bank_account, key, value)
            
            existing_bank_account.updated_by_user_id = dto.user_id
            
            updated_bank_account = await self.bank_account_service.save(existing_bank_account)
            self.logger.info(f"Bank account '{updated_bank_account.account_name}' (ID: {bank_account_id}) updated.")
            return Result.success(updated_bank_account)
        except Exception as e:
            self.logger.error(f"Error updating bank account ID {bank_account_id}: {e}", exc_info=True)
            return Result.failure([f"An unexpected error occurred: {str(e)}"])

    async def toggle_bank_account_active_status(self, bank_account_id: int, user_id: int) -> Result[BankAccount]:
        bank_account = await self.bank_account_service.get_by_id(bank_account_id)
        if not bank_account:
            return Result.failure([f"Bank Account with ID {bank_account_id} not found."])
        
        if bank_account.current_balance != Decimal(0) and bank_account.is_active:
            self.logger.warning(f"Deactivating bank account ID {bank_account_id} ('{bank_account.account_name}') which has a non-zero balance of {bank_account.current_balance}.")

        bank_account.is_active = not bank_account.is_active
        bank_account.updated_by_user_id = user_id

        try:
            updated_bank_account = await self.bank_account_service.save(bank_account)
            action = "activated" if updated_bank_account.is_active else "deactivated"
            self.logger.info(f"Bank Account '{updated_bank_account.account_name}' (ID: {bank_account_id}) {action} by user ID {user_id}.")
            return Result.success(updated_bank_account)
        except Exception as e:
            self.logger.error(f"Error toggling active status for bank account ID {bank_account_id}: {e}", exc_info=True)
            return Result.failure([f"Failed to toggle active status: {str(e)}"])
```

#### **File 2: `app/business_logic/bank_transaction_manager.py` (Corrected)**

```python
# File: app/business_logic/bank_transaction_manager.py
import csv 
from datetime import date, datetime 
from decimal import Decimal, InvalidOperation
from typing import List, Optional, Dict, Any, TYPE_CHECKING, Union, cast, Tuple 

from sqlalchemy import select 

from app.models.business.bank_transaction import BankTransaction
from app.utils.result import Result
from app.utils.pydantic_models import (
    BankTransactionCreateData, BankTransactionSummaryData, CSVImportErrorData
)
from app.common.enums import BankTransactionTypeEnum

if TYPE_CHECKING:
    from app.core.application_core import ApplicationCore
    from sqlalchemy.ext.asyncio import AsyncSession
    from app.services.business_services import BankTransactionService, BankAccountService

class BankTransactionManager:
    def __init__(self, app_core: "ApplicationCore"):
        self.app_core = app_core
        self.bank_transaction_service: "BankTransactionService" = self.app_core.bank_transaction_service
        self.bank_account_service: "BankAccountService" = self.app_core.bank_account_service
        self.logger = self.app_core.logger

    async def _validate_transaction_data(
        self,
        dto: BankTransactionCreateData,
        existing_transaction_id: Optional[int] = None 
    ) -> List[str]:
        errors: List[str] = []
        bank_account = await self.bank_account_service.get_by_id(dto.bank_account_id)
        if not bank_account:
            errors.append(f"Bank Account with ID {dto.bank_account_id} not found.")
        elif not bank_account.is_active:
            errors.append(f"Bank Account '{bank_account.account_name}' is not active.")
        if dto.value_date and dto.value_date < dto.transaction_date:
            errors.append("Value date cannot be before transaction date.")
        return errors

    async def create_manual_bank_transaction(self, dto: BankTransactionCreateData) -> Result[BankTransaction]:
        validation_errors = await self._validate_transaction_data(dto)
        if validation_errors:
            return Result.failure(validation_errors)
        try:
            bank_transaction_orm = BankTransaction(
                bank_account_id=dto.bank_account_id,
                transaction_date=dto.transaction_date,
                value_date=dto.value_date,
                transaction_type=dto.transaction_type.value, 
                description=dto.description,
                reference=dto.reference,
                amount=dto.amount, 
                is_reconciled=False, 
                is_from_statement=False, 
                raw_statement_data=None,
                created_by_user_id=dto.user_id,
                updated_by_user_id=dto.user_id
            )
            saved_transaction = await self.bank_transaction_service.save(bank_transaction_orm)
            self.logger.info(f"Manual bank transaction ID {saved_transaction.id} created for bank account ID {dto.bank_account_id}.")
            return Result.success(saved_transaction)
        except Exception as e:
            self.logger.error(f"Error creating manual bank transaction: {e}", exc_info=True)
            return Result.failure([f"An unexpected error occurred: {str(e)}"])


    async def get_transactions_for_bank_account(
        self,
        bank_account_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        transaction_type: Optional[BankTransactionTypeEnum] = None,
        is_reconciled: Optional[bool] = None,
        is_from_statement_filter: Optional[bool] = None, 
        page: int = 1,
        page_size: int = 50
    ) -> Result[List[BankTransactionSummaryData]]:
        try:
            summaries = await self.bank_transaction_service.get_all_for_bank_account(
                bank_account_id=bank_account_id,
                start_date=start_date,
                end_date=end_date,
                transaction_type=transaction_type,
                is_reconciled=is_reconciled,
                is_from_statement_filter=is_from_statement_filter, 
                page=page,
                page_size=page_size
            )
            return Result.success(summaries)
        except Exception as e:
            self.logger.error(f"Error fetching bank transactions for account ID {bank_account_id}: {e}", exc_info=True)
            return Result.failure([f"Failed to retrieve bank transaction list: {str(e)}"])

    async def get_bank_transaction_for_dialog(self, transaction_id: int) -> Optional[BankTransaction]:
        try:
            return await self.bank_transaction_service.get_by_id(transaction_id)
        except Exception as e:
            self.logger.error(f"Error fetching BankTransaction ID {transaction_id} for dialog: {e}", exc_info=True)
            return None
            
    async def import_bank_statement_csv(
        self, 
        bank_account_id: int, 
        csv_file_path: str, 
        user_id: int,
        column_mapping: Dict[str, Any], 
        import_options: Dict[str, Any]
    ) -> Result[Dict[str, Any]]:
        imported_count = 0; skipped_duplicates_count = 0; zero_amount_skipped_count = 0; total_rows_processed = 0
        detailed_errors: List[CSVImportErrorData] = []
        date_format_str = import_options.get("date_format_str", "%d/%m/%Y"); skip_header = import_options.get("skip_header", True)
        use_single_amount_col = import_options.get("use_single_amount_column", False); debit_is_negative = import_options.get("debit_is_negative_in_single_col", False)
        bank_account = await self.bank_account_service.get_by_id(bank_account_id)
        if not bank_account or not bank_account.is_active: return Result.failure([f"Bank Account ID {bank_account_id} not found or is inactive."])
        
        try:
            with open(csv_file_path, 'r', encoding='utf-8-sig') as csvfile:
                using_header_names = any(isinstance(v, str) for v in column_mapping.values()); reader: Any
                if using_header_names: reader = csv.DictReader(csvfile)
                else: reader = csv.reader(csvfile); 
                if skip_header and not using_header_names: 
                    try: next(reader) 
                    except StopIteration: return Result.failure(["CSV file is empty or only contains a header."])
                
                async with self.app_core.db_manager.session() as session:
                    start_row_num = 2 if skip_header else 1
                    for row_num, raw_row_data in enumerate(reader, start=start_row_num):
                        total_rows_processed += 1
                        original_row_list = list(raw_row_data.values()) if isinstance(raw_row_data, dict) else raw_row_data
                        
                        def add_error(msg: str):
                            nonlocal detailed_errors
                            detailed_errors.append(CSVImportErrorData(row_number=row_num, row_data=original_row_list, error_message=msg))

                        try:
                            def get_field_value(field_key: str) -> Optional[str]:
                                specifier = column_mapping.get(field_key); 
                                if specifier is None: return None; val: Optional[str] = None
                                if using_header_names and isinstance(raw_row_data, dict): val = raw_row_data.get(str(specifier))
                                elif not using_header_names and isinstance(raw_row_data, list) and isinstance(specifier, int):
                                    if 0 <= specifier < len(raw_row_data): val = raw_row_data[specifier]
                                return val.strip() if val else None
                            
                            raw_row_dict_for_json: Dict[str, str] = {k: str(v) for k,v in raw_row_data.items()} if isinstance(raw_row_data, dict) else {f"column_{i}": str(val) for i, val in enumerate(raw_row_data)}
                            
                            transaction_date_str = get_field_value("date"); description_str = get_field_value("description")
                            if not transaction_date_str or not description_str: add_error("Skipping: Missing required Date or Description field."); continue
                            try: parsed_transaction_date = datetime.strptime(transaction_date_str, date_format_str).date()
                            except ValueError: add_error(f"Invalid transaction date format '{transaction_date_str}'. Expected '{date_format_str}'."); continue
                            
                            value_date_str = get_field_value("value_date"); parsed_value_date: Optional[date] = None
                            if value_date_str:
                                try: parsed_value_date = datetime.strptime(value_date_str, date_format_str).date()
                                except ValueError: add_error(f"Invalid value date format '{value_date_str}'. Ignored.")
                            
                            final_bt_amount = Decimal(0)
                            if use_single_amount_col:
                                amount_str = get_field_value("amount")
                                if not amount_str: add_error("Single amount column specified but value is missing."); continue
                                try: parsed_csv_amount = Decimal(amount_str.replace(',', '')); final_bt_amount = -parsed_csv_amount if debit_is_negative else parsed_csv_amount
                                except InvalidOperation: add_error(f"Invalid amount '{amount_str}' in single amount column."); continue
                            else:
                                debit_str = get_field_value("debit"); credit_str = get_field_value("credit")
                                try:
                                    parsed_debit = Decimal(debit_str.replace(',', '')) if debit_str else Decimal(0)
                                    parsed_credit = Decimal(credit_str.replace(',', '')) if credit_str else Decimal(0)
                                    final_bt_amount = parsed_credit - parsed_debit
                                except InvalidOperation: add_error(f"Invalid debit '{debit_str}' or credit '{credit_str}' amount."); continue
                            
                            if abs(final_bt_amount) < Decimal("0.005"): zero_amount_skipped_count += 1; continue
                            
                            reference_str = get_field_value("reference")
                            stmt_dup = select(BankTransaction).where(BankTransaction.bank_account_id == bank_account_id,BankTransaction.transaction_date == parsed_transaction_date,BankTransaction.amount == final_bt_amount,BankTransaction.description == description_str,BankTransaction.is_from_statement == True)
                            if (await session.execute(stmt_dup)).scalars().first(): skipped_duplicates_count += 1; continue
                            
                            txn_type_enum = BankTransactionTypeEnum.DEPOSIT if final_bt_amount > 0 else BankTransactionTypeEnum.WITHDRAWAL
                            txn_orm = BankTransaction(bank_account_id=bank_account_id,transaction_date=parsed_transaction_date,value_date=parsed_value_date,transaction_type=txn_type_enum.value,description=description_str,reference=reference_str if reference_str else None,amount=final_bt_amount,is_reconciled=False,is_from_statement=True,raw_statement_data=raw_row_dict_for_json, created_by_user_id=user_id,updated_by_user_id=user_id)
                            session.add(txn_orm); imported_count += 1
                        except Exception as e_row: add_error(f"Unexpected error: {str(e_row)}")

            summary = {"total_rows_processed": total_rows_processed, "imported_count": imported_count, "skipped_duplicates_count": skipped_duplicates_count, "failed_rows_count": len(detailed_errors), "zero_amount_skipped_count": zero_amount_skipped_count, "detailed_errors": detailed_errors}
            self.logger.info(f"Bank statement import complete for account ID {bank_account_id}: {summary}")
            return Result.success(summary)

        except FileNotFoundError: self.logger.error(f"CSV Import: File not found at path: {csv_file_path}"); return Result.failure([f"CSV file not found: {csv_file_path}"])
        except Exception as e: self.logger.error(f"CSV Import: General error for account ID {bank_account_id}: {e}", exc_info=True); return Result.failure([f"General error during CSV import: {str(e)}"])

    async def get_unreconciled_transactions_for_matching(
        self, 
        bank_account_id: int, 
        statement_end_date: date,
        page_size_override: int = -1 
    ) -> Result[Tuple[List[BankTransactionSummaryData], List[BankTransactionSummaryData]]]:
        try:
            statement_items_result = await self.get_transactions_for_bank_account(
                bank_account_id=bank_account_id, end_date=statement_end_date, 
                is_reconciled=False, is_from_statement_filter=True, page=1, page_size=page_size_override 
            )
            if not statement_items_result.is_success:
                return Result.failure(["Failed to fetch statement items for reconciliation."] + (statement_items_result.errors or []))
            
            system_items_result = await self.get_transactions_for_bank_account(
                bank_account_id=bank_account_id, end_date=statement_end_date, 
                is_reconciled=False, is_from_statement_filter=False, page=1, page_size=page_size_override
            )
            if not system_items_result.is_success:
                return Result.failure(["Failed to fetch system transactions for reconciliation."] + (system_items_result.errors or []))
            
            return Result.success((statement_items_result.value or [], system_items_result.value or []))

        except Exception as e:
            self.logger.error(f"Error fetching transactions for matching UI (Account ID: {bank_account_id}): {e}", exc_info=True)
            return Result.failure([f"Unexpected error fetching transactions for reconciliation: {str(e)}"])
```

I have received the first 3 files. please proceed to provide the remaining files that need to be modified.

