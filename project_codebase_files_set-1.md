# app/tax/gst_manager.py
```py
# File: app/tax/gst_manager.py
from typing import Optional, Any, TYPE_CHECKING, List, Dict
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta 
from decimal import Decimal

# REMOVED: from app.services.tax_service import TaxCodeService, GSTReturnService 
# REMOVED: from app.services.account_service import AccountService
# REMOVED: from app.services.fiscal_period_service import FiscalPeriodService
# REMOVED: from app.services.core_services import CompanySettingsService 
from app.utils.result import Result
from app.utils.pydantic_models import GSTReturnData, JournalEntryData, JournalEntryLineData, GSTTransactionLineDetail
from app.models.accounting.gst_return import GSTReturn 
from app.models.accounting.journal_entry import JournalEntry, JournalEntryLine # Keep specific model imports
from app.models.accounting.account import Account
from app.models.accounting.tax_code import TaxCode
from app.common.enums import GSTReturnStatusEnum 

if TYPE_CHECKING:
    from app.core.application_core import ApplicationCore 
    from app.services.journal_service import JournalService 
    from app.utils.sequence_generator import SequenceGenerator
    from app.services.tax_service import TaxCodeService, GSTReturnService # ADDED
    from app.services.account_service import AccountService # ADDED
    from app.services.fiscal_period_service import FiscalPeriodService # ADDED
    from app.services.core_services import CompanySettingsService # ADDED


class GSTManager:
    def __init__(self, 
                 tax_code_service: "TaxCodeService", 
                 journal_service: "JournalService", 
                 company_settings_service: "CompanySettingsService", 
                 gst_return_service: "GSTReturnService",
                 account_service: "AccountService", 
                 fiscal_period_service: "FiscalPeriodService", 
                 sequence_generator: "SequenceGenerator", 
                 app_core: "ApplicationCore"): 
        self.tax_code_service = tax_code_service
        self.journal_service = journal_service
        self.company_settings_service = company_settings_service
        self.gst_return_service = gst_return_service
        self.account_service = account_service 
        self.fiscal_period_service = fiscal_period_service 
        self.sequence_generator = sequence_generator
        self.app_core = app_core

    async def prepare_gst_return_data(self, start_date: date, end_date: date, user_id: int) -> Result[GSTReturnData]:
        company_settings = await self.company_settings_service.get_company_settings()
        if not company_settings:
            return Result.failure(["Company settings not found."])

        std_rated_supplies = Decimal('0.00') 
        zero_rated_supplies = Decimal('0.00')  
        exempt_supplies = Decimal('0.00')     
        taxable_purchases = Decimal('0.00')   
        output_tax_calc = Decimal('0.00') 
        input_tax_calc = Decimal('0.00')  
        
        detailed_breakdown: Dict[str, List[GSTTransactionLineDetail]] = {
            "box1_standard_rated_supplies": [], "box2_zero_rated_supplies": [],
            "box3_exempt_supplies": [], "box5_taxable_purchases": [],
            "box6_output_tax_details": [], "box7_input_tax_details": []
        }
        
        posted_entries: List[JournalEntry] = await self.journal_service.get_posted_entries_by_date_range(start_date, end_date)

        for entry in posted_entries:
            for line in entry.lines:
                if not line.account or not line.tax_code_obj: continue

                account_orm: Account = line.account
                tax_code_orm: TaxCode = line.tax_code_obj
                
                line_net_value_for_gst_box: Decimal = Decimal('0.00')
                if account_orm.account_type == 'Revenue':
                    line_net_value_for_gst_box = line.credit_amount - line.debit_amount 
                elif account_orm.account_type in ['Expense', 'Asset']:
                    line_net_value_for_gst_box = line.debit_amount - line.credit_amount 

                if tax_code_orm.tax_type != 'GST' or abs(line_net_value_for_gst_box) < Decimal('0.01') and abs(line.tax_amount) < Decimal('0.01'):
                    continue

                transaction_detail = GSTTransactionLineDetail(
                    transaction_date=entry.entry_date,
                    document_no=entry.reference or entry.entry_no, 
                    entity_name=None, 
                    description=line.description or entry.description or "N/A",
                    account_code=account_orm.code,
                    account_name=account_orm.name,
                    net_amount=line_net_value_for_gst_box.quantize(Decimal("0.01")),
                    gst_amount=line.tax_amount.quantize(Decimal("0.01")),
                    tax_code_applied=tax_code_orm.code
                )

                if account_orm.account_type == 'Revenue':
                    if tax_code_orm.code == 'SR': 
                        std_rated_supplies += line_net_value_for_gst_box
                        output_tax_calc += line.tax_amount
                        detailed_breakdown["box1_standard_rated_supplies"].append(transaction_detail)
                        if line.tax_amount != Decimal(0):
                             detailed_breakdown["box6_output_tax_details"].append(transaction_detail)
                    elif tax_code_orm.code == 'ZR': 
                        zero_rated_supplies += line_net_value_for_gst_box
                        detailed_breakdown["box2_zero_rated_supplies"].append(transaction_detail)
                    elif tax_code_orm.code == 'ES': 
                        exempt_supplies += line_net_value_for_gst_box
                        detailed_breakdown["box3_exempt_supplies"].append(transaction_detail)
                    
                elif account_orm.account_type in ['Expense', 'Asset']:
                    if tax_code_orm.code == 'TX': 
                        taxable_purchases += line_net_value_for_gst_box
                        input_tax_calc += line.tax_amount
                        detailed_breakdown["box5_taxable_purchases"].append(transaction_detail)
                        if line.tax_amount != Decimal(0):
                            detailed_breakdown["box7_input_tax_details"].append(transaction_detail)
                    elif tax_code_orm.code == 'BL': 
                        taxable_purchases += line_net_value_for_gst_box
                        detailed_breakdown["box5_taxable_purchases"].append(transaction_detail)
        
        total_supplies = std_rated_supplies + zero_rated_supplies + exempt_supplies
        tax_payable = output_tax_calc - input_tax_calc 

        temp_due_date = end_date + relativedelta(months=1)
        filing_due_date = temp_due_date + relativedelta(day=31) 

        return_data = GSTReturnData(
            return_period=f"{start_date.strftime('%d%m%Y')}-{end_date.strftime('%d%m%Y')}",
            start_date=start_date, end_date=end_date,
            filing_due_date=filing_due_date,
            standard_rated_supplies=std_rated_supplies.quantize(Decimal("0.01")),
            zero_rated_supplies=zero_rated_supplies.quantize(Decimal("0.01")),
            exempt_supplies=exempt_supplies.quantize(Decimal("0.01")),
            total_supplies=total_supplies.quantize(Decimal("0.01")), 
            taxable_purchases=taxable_purchases.quantize(Decimal("0.01")), 
            output_tax=output_tax_calc.quantize(Decimal("0.01")), 
            input_tax=input_tax_calc.quantize(Decimal("0.01")),   
            tax_adjustments=Decimal(0),
            tax_payable=tax_payable.quantize(Decimal("0.01")), 
            status=GSTReturnStatusEnum.DRAFT.value,
            user_id=user_id,
            detailed_breakdown=detailed_breakdown
        )
        return Result.success(return_data)

    async def save_gst_return(self, gst_return_data: GSTReturnData) -> Result[GSTReturn]:
        current_user_id = gst_return_data.user_id
        orm_return: GSTReturn
        core_data_dict = gst_return_data.model_dump(exclude={'id', 'user_id', 'detailed_breakdown'}, exclude_none=True)

        if gst_return_data.id: 
            existing_return = await self.gst_return_service.get_by_id(gst_return_data.id)
            if not existing_return:
                return Result.failure([f"GST Return with ID {gst_return_data.id} not found for update."])
            orm_return = existing_return
            for key, value in core_data_dict.items():
                if hasattr(orm_return, key):
                    setattr(orm_return, key, value)
            orm_return.updated_by_user_id = current_user_id
        else: 
            orm_return = GSTReturn(
                **core_data_dict,
                created_by_user_id=current_user_id,
                updated_by_user_id=current_user_id
            )
            if not orm_return.filing_due_date and orm_return.end_date: 
                 temp_due_date = orm_return.end_date + relativedelta(months=1)
                 orm_return.filing_due_date = temp_due_date + relativedelta(day=31)
        try:
            saved_return = await self.gst_return_service.save_gst_return(orm_return)
            return Result.success(saved_return)
        except Exception as e:
            self.app_core.logger.error(f"Failed to save GST return: {e}", exc_info=True) # type: ignore
            return Result.failure([f"Failed to save GST return: {str(e)}"])

    async def finalize_gst_return(self, return_id: int, submission_reference: str, submission_date: date, user_id: int) -> Result[GSTReturn]:
        gst_return = await self.gst_return_service.get_by_id(return_id)
        if not gst_return:
            return Result.failure([f"GST Return ID {return_id} not found."])
        if gst_return.status != GSTReturnStatusEnum.DRAFT.value:
            return Result.failure([f"GST Return must be in Draft status to be finalized. Current status: {gst_return.status}"])

        gst_return.status = GSTReturnStatusEnum.SUBMITTED.value
        gst_return.submission_date = submission_date
        gst_return.submission_reference = submission_reference
        gst_return.updated_by_user_id = user_id

        if gst_return.tax_payable != Decimal(0):
            gst_output_tax_acc_code = await self.app_core.configuration_service.get_config_value("SysAcc_DefaultGSTOutput", "SYS-GST-OUTPUT")
            gst_input_tax_acc_code = await self.app_core.configuration_service.get_config_value("SysAcc_DefaultGSTInput", "SYS-GST-INPUT")
            gst_control_acc_code = await self.app_core.configuration_service.get_config_value("SysAcc_GSTControl", "SYS-GST-CONTROL")
            
            output_tax_acc = await self.account_service.get_by_code(gst_output_tax_acc_code) # type: ignore
            input_tax_acc = await self.account_service.get_by_code(gst_input_tax_acc_code) # type: ignore
            control_acc = await self.account_service.get_by_code(gst_control_acc_code) if gst_control_acc_code else None # type: ignore

            if not (output_tax_acc and input_tax_acc and control_acc):
                missing_accs = []
                if not output_tax_acc: missing_accs.append(str(gst_output_tax_acc_code))
                if not input_tax_acc: missing_accs.append(str(gst_input_tax_acc_code))
                if not control_acc: missing_accs.append(str(gst_control_acc_code))
                error_msg = f"Essential GST GL accounts not found: {', '.join(missing_accs)}. Cannot create settlement journal entry."
                self.app_core.logger.error(error_msg) # type: ignore
                try:
                    updated_return_no_je = await self.gst_return_service.save_gst_return(gst_return)
                    return Result.failure([f"GST Return finalized (ID: {updated_return_no_je.id}), but JE creation failed: " + error_msg])
                except Exception as e_save:
                    return Result.failure([f"Failed to finalize GST return and also failed to save it before JE creation: {str(e_save)}"] + [error_msg])

            lines: List[JournalEntryLineData] = []
            desc_period = f"GST for period {gst_return.start_date.strftime('%d/%m/%y')}-{gst_return.end_date.strftime('%d/%m/%y')}"
            
            if gst_return.output_tax != Decimal(0):
                 lines.append(JournalEntryLineData(account_id=output_tax_acc.id, debit_amount=gst_return.output_tax, credit_amount=Decimal(0), description=f"Clear Output Tax - {desc_period}"))
            if gst_return.input_tax != Decimal(0):
                 lines.append(JournalEntryLineData(account_id=input_tax_acc.id, debit_amount=Decimal(0), credit_amount=gst_return.input_tax, description=f"Clear Input Tax - {desc_period}"))
            
            if gst_return.tax_payable > Decimal(0): 
                lines.append(JournalEntryLineData(account_id=control_acc.id, debit_amount=Decimal(0), credit_amount=gst_return.tax_payable, description=f"GST Payable - {desc_period}"))
            elif gst_return.tax_payable < Decimal(0): 
                lines.append(JournalEntryLineData(account_id=control_acc.id, debit_amount=abs(gst_return.tax_payable), credit_amount=Decimal(0), description=f"GST Refundable - {desc_period}"))
            
            if lines:
                if not hasattr(self.app_core, 'journal_entry_manager') or not self.app_core.journal_entry_manager:
                    return Result.failure(["Journal Entry Manager not available in Application Core. Cannot create GST settlement JE."])

                je_data = JournalEntryData(
                    journal_type="General", entry_date=submission_date, 
                    description=f"GST Settlement for period {gst_return.return_period}",
                    reference=f"GST F5 Finalized: {gst_return.submission_reference or gst_return.return_period}", 
                    user_id=user_id, lines=lines,
                    source_type="GSTReturnSettlement", source_id=gst_return.id
                )
                je_result: Result[JournalEntry] = await self.app_core.journal_entry_manager.create_journal_entry(je_data) 
                if not je_result.is_success:
                    try:
                        updated_return_je_fail = await self.gst_return_service.save_gst_return(gst_return)
                        return Result.failure([f"GST Return finalized and saved (ID: {updated_return_je_fail.id}) but settlement JE creation failed."] + (je_result.errors or []))
                    except Exception as e_save_2:
                         return Result.failure([f"Failed to finalize GST return and also failed during JE creation and subsequent save: {str(e_save_2)}"] + (je_result.errors or []))
                else:
                    assert je_result.value is not None
                    gst_return.journal_entry_id = je_result.value.id
                    post_result: Result[JournalEntry] = await self.app_core.journal_entry_manager.post_journal_entry(je_result.value.id, user_id)
                    if not post_result.is_success:
                        self.app_core.logger.warning(f"GST Settlement JE (ID: {je_result.value.id}) created but failed to auto-post: {post_result.errors}") # type: ignore
        try:
            updated_return = await self.gst_return_service.save_gst_return(gst_return)
            return Result.success(updated_return)
        except Exception as e:
            self.app_core.logger.error(f"Failed to save finalized GST return: {e}", exc_info=True) # type: ignore
            return Result.failure([f"Failed to save finalized GST return: {str(e)}"])

```

# app/tax/__init__.py
```py
# File: app/tax/__init__.py
from .gst_manager import GSTManager
from .tax_calculator import TaxCalculator
from .income_tax_manager import IncomeTaxManager
from .withholding_tax_manager import WithholdingTaxManager

__all__ = [
    "GSTManager",
    "TaxCalculator",
    "IncomeTaxManager",
    "WithholdingTaxManager",
]

```

# app/tax/tax_calculator.py
```py
# File: app/tax/tax_calculator.py
from decimal import Decimal
from typing import List, Optional, Any, TYPE_CHECKING

# REMOVED: from app.services.tax_service import TaxCodeService 
from app.utils.pydantic_models import TaxCalculationResultData, TransactionTaxData, TransactionLineTaxData
from app.models.accounting.tax_code import TaxCode as TaxCodeModel

if TYPE_CHECKING:
    from app.services.tax_service import TaxCodeService # ADDED

class TaxCalculator:
    def __init__(self, tax_code_service: "TaxCodeService"):
        self.tax_code_service = tax_code_service
    
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
        
        tax_code_info: Optional[TaxCodeModel] = await self.tax_code_service.get_tax_code(tax_code_str) # Use TYPE_CHECKING for TaxCodeModel
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

# app/reporting/__init__.py
```py
# File: app/reporting/__init__.py
from .financial_statement_generator import FinancialStatementGenerator
from .tax_report_generator import TaxReportGenerator
from .report_engine import ReportEngine
from .dashboard_manager import DashboardManager # New Import

__all__ = [
    "FinancialStatementGenerator",
    "TaxReportGenerator",
    "ReportEngine",
    "DashboardManager", # New Export
]

```

# app/reporting/financial_statement_generator.py
```py
# File: app/reporting/financial_statement_generator.py
from typing import List, Dict, Any, Optional, TYPE_CHECKING
from datetime import date, timedelta 
from decimal import Decimal

from app.models.accounting.account import Account 
from app.models.accounting.fiscal_year import FiscalYear
from app.models.accounting.account_type import AccountType 
from app.models.accounting.journal_entry import JournalEntryLine 

if TYPE_CHECKING:
    from app.core.application_core import ApplicationCore 
    from app.services.account_service import AccountService
    from app.services.journal_service import JournalService
    from app.services.fiscal_period_service import FiscalPeriodService
    from app.services.tax_service import TaxCodeService
    from app.services.core_services import CompanySettingsService, ConfigurationService
    from app.services.accounting_services import AccountTypeService, DimensionService


class FinancialStatementGenerator:
    def __init__(self, 
                 account_service: "AccountService", 
                 journal_service: "JournalService", 
                 fiscal_period_service: "FiscalPeriodService", 
                 account_type_service: "AccountTypeService", 
                 tax_code_service: Optional["TaxCodeService"] = None, 
                 company_settings_service: Optional["CompanySettingsService"] = None,
                 dimension_service: Optional["DimensionService"] = None,
                 configuration_service: Optional["ConfigurationService"] = None
                 ):
        self.account_service = account_service
        self.journal_service = journal_service
        self.fiscal_period_service = fiscal_period_service
        self.account_type_service = account_type_service
        self.tax_code_service = tax_code_service
        self.company_settings_service = company_settings_service
        self.dimension_service = dimension_service 
        self.configuration_service = configuration_service
        self._account_type_map_cache: Optional[Dict[str, AccountType]] = None


    async def _get_account_type_map(self) -> Dict[str, AccountType]:
        if self._account_type_map_cache is None:
             ats = await self.account_type_service.get_all()
             self._account_type_map_cache = {at.category: at for at in ats} 
        return self._account_type_map_cache

    async def _calculate_account_balances_for_report(self, accounts: List[Account], as_of_date: date) -> List[Dict[str, Any]]:
        result_list = []; acc_type_map = await self._get_account_type_map()
        for account in accounts:
            balance_value = await self.journal_service.get_account_balance(account.id, as_of_date); display_balance = balance_value 
            acc_detail = acc_type_map.get(account.account_type); is_debit_nature = acc_detail.is_debit_balance if acc_detail else (account.account_type in ['Asset', 'Expense'])
            if not is_debit_nature: display_balance = -balance_value 
            result_list.append({'id': account.id, 'code': account.code, 'name': account.name, 'balance': display_balance})
        return result_list

    async def _calculate_account_period_activity_for_report(self, accounts: List[Account], start_date: date, end_date: date) -> List[Dict[str, Any]]:
        result_list = []; acc_type_map = await self._get_account_type_map()
        for account in accounts:
            activity_value = await self.journal_service.get_account_balance_for_period(account.id, start_date, end_date); display_activity = activity_value
            acc_detail = acc_type_map.get(account.account_type); is_debit_nature = acc_detail.is_debit_balance if acc_detail else (account.account_type in ['Asset', 'Expense'])
            if not is_debit_nature: display_activity = -activity_value 
            result_list.append({'id': account.id, 'code': account.code, 'name': account.name, 'balance': display_activity})
        return result_list

    async def generate_balance_sheet(self, as_of_date: date, comparative_date: Optional[date] = None, include_zero_balances: bool = False) -> Dict[str, Any]:
        accounts = await self.account_service.get_all_active(); assets_orm = [a for a in accounts if a.account_type == 'Asset']; liabilities_orm = [a for a in accounts if a.account_type == 'Liability']; equity_orm = [a for a in accounts if a.account_type == 'Equity']
        asset_accounts = await self._calculate_account_balances_for_report(assets_orm, as_of_date); liability_accounts = await self._calculate_account_balances_for_report(liabilities_orm, as_of_date); equity_accounts = await self._calculate_account_balances_for_report(equity_orm, as_of_date)
        comp_asset_accs, comp_liab_accs, comp_equity_accs = None, None, None
        if comparative_date: comp_asset_accs = await self._calculate_account_balances_for_report(assets_orm, comparative_date); comp_liab_accs = await self._calculate_account_balances_for_report(liabilities_orm, comparative_date); comp_equity_accs = await self._calculate_account_balances_for_report(equity_orm, comparative_date)
        if not include_zero_balances:
            asset_accounts = [a for a in asset_accounts if a['balance'] != Decimal(0)]; liability_accounts = [a for a in liability_accounts if a['balance'] != Decimal(0)]; equity_accounts = [a for a in equity_accounts if a['balance'] != Decimal(0)]
            if comparative_date: comp_asset_accs = [a for a in comp_asset_accs if a['balance'] != Decimal(0)] if comp_asset_accs else None; comp_liab_accs = [a for a in comp_liab_accs if a['balance'] != Decimal(0)] if comp_liab_accs else None; comp_equity_accs = [a for a in comp_equity_accs if a['balance'] != Decimal(0)] if comp_equity_accs else None
        total_assets = sum(a['balance'] for a in asset_accounts); total_liabilities = sum(a['balance'] for a in liability_accounts); total_equity = sum(a['balance'] for a in equity_accounts)
        comp_total_assets = sum(a['balance'] for a in comp_asset_accs) if comp_asset_accs else None; comp_total_liabilities = sum(a['balance'] for a in comp_liab_accs) if comp_liab_accs else None; comp_total_equity = sum(a['balance'] for a in comp_equity_accs) if comp_equity_accs else None
        return {'title': 'Balance Sheet', 'report_date_description': f"As of {as_of_date.strftime('%d %b %Y')}",'as_of_date': as_of_date, 'comparative_date': comparative_date,'assets': {'accounts': asset_accounts, 'total': total_assets, 'comparative_accounts': comp_asset_accs, 'comparative_total': comp_total_assets},'liabilities': {'accounts': liability_accounts, 'total': total_liabilities, 'comparative_accounts': comp_liab_accs, 'comparative_total': comp_total_liabilities},'equity': {'accounts': equity_accounts, 'total': total_equity, 'comparative_accounts': comp_equity_accs, 'comparative_total': comp_total_equity},'total_liabilities_equity': total_liabilities + total_equity,'comparative_total_liabilities_equity': (comp_total_liabilities + comp_total_equity) if comparative_date and comp_total_liabilities is not None and comp_total_equity is not None else None,'is_balanced': abs(total_assets - (total_liabilities + total_equity)) < Decimal("0.01")}

    async def generate_profit_loss(self, start_date: date, end_date: date, comparative_start: Optional[date] = None, comparative_end: Optional[date] = None) -> Dict[str, Any]:
        accounts = await self.account_service.get_all_active(); revenues_orm = [a for a in accounts if a.account_type == 'Revenue']; expenses_orm = [a for a in accounts if a.account_type == 'Expense'] 
        revenue_accounts = await self._calculate_account_period_activity_for_report(revenues_orm, start_date, end_date); expense_accounts = await self._calculate_account_period_activity_for_report(expenses_orm, start_date, end_date)
        comp_rev_accs, comp_exp_accs = None, None
        if comparative_start and comparative_end: comp_rev_accs = await self._calculate_account_period_activity_for_report(revenues_orm, comparative_start, comparative_end); comp_exp_accs = await self._calculate_account_period_activity_for_report(expenses_orm, comparative_start, comparative_end)
        total_revenue = sum(a['balance'] for a in revenue_accounts); total_expenses = sum(a['balance'] for a in expense_accounts) 
        net_profit = total_revenue - total_expenses
        comp_total_revenue = sum(a['balance'] for a in comp_rev_accs) if comp_rev_accs else None; comp_total_expenses = sum(a['balance'] for a in comp_exp_accs) if comp_exp_accs else None
        comp_net_profit = (comp_total_revenue - comp_total_expenses) if comp_total_revenue is not None and comp_total_expenses is not None else None
        return {'title': 'Profit & Loss Statement', 'report_date_description': f"For the period {start_date.strftime('%d %b %Y')} to {end_date.strftime('%d %b %Y')}",'start_date': start_date, 'end_date': end_date, 'comparative_start': comparative_start, 'comparative_end': comparative_end,'revenue': {'accounts': revenue_accounts, 'total': total_revenue, 'comparative_accounts': comp_rev_accs, 'comparative_total': comp_total_revenue},'expenses': {'accounts': expense_accounts, 'total': total_expenses, 'comparative_accounts': comp_exp_accs, 'comparative_total': comp_total_expenses},'net_profit': net_profit, 'comparative_net_profit': comp_net_profit}

    async def generate_trial_balance(self, as_of_date: date) -> Dict[str, Any]:
        accounts = await self.account_service.get_all_active(); debit_accounts_list, credit_accounts_list = [], []; total_debits_val, total_credits_val = Decimal(0), Decimal(0) 
        acc_type_map = await self._get_account_type_map()
        for account in accounts:
            raw_balance = await self.journal_service.get_account_balance(account.id, as_of_date)
            if abs(raw_balance) < Decimal("0.01"): continue
            account_data = {'id': account.id, 'code': account.code, 'name': account.name, 'balance': abs(raw_balance)}
            acc_detail = acc_type_map.get(account.account_type); is_debit_nature = acc_detail.is_debit_balance if acc_detail else (account.account_type in ['Asset', 'Expense'])
            if is_debit_nature: 
                if raw_balance >= Decimal(0): debit_accounts_list.append(account_data); total_debits_val += raw_balance
                else: account_data['balance'] = abs(raw_balance); credit_accounts_list.append(account_data); total_credits_val += abs(raw_balance)
            else: 
                if raw_balance <= Decimal(0): credit_accounts_list.append(account_data); total_credits_val += abs(raw_balance)
                else: account_data['balance'] = raw_balance; debit_accounts_list.append(account_data); total_debits_val += raw_balance
        debit_accounts_list.sort(key=lambda a: a['code']); credit_accounts_list.sort(key=lambda a: a['code'])
        return {'title': 'Trial Balance', 'report_date_description': f"As of {as_of_date.strftime('%d %b %Y')}",'as_of_date': as_of_date,'debit_accounts': debit_accounts_list, 'credit_accounts': credit_accounts_list,'total_debits': total_debits_val, 'total_credits': total_credits_val,'is_balanced': abs(total_debits_val - total_credits_val) < Decimal("0.01")}

    async def generate_income_tax_computation(self, fiscal_year: FiscalYear) -> Dict[str, Any]:
        if not self.configuration_service:
            raise RuntimeError("ConfigurationService not available for tax computation.")
            
        start_date, end_date = fiscal_year.start_date, fiscal_year.end_date
        
        pl_data = await self.generate_profit_loss(start_date, end_date)
        net_profit_before_tax = pl_data.get('net_profit', Decimal(0))

        add_back_adjustments: List[Dict[str, Any]] = []
        less_adjustments: List[Dict[str, Any]] = []
        total_add_back = Decimal(0)
        total_less = Decimal(0)

        non_deductible_accounts = await self.account_service.get_accounts_by_tax_treatment('Non-Deductible')
        for account in non_deductible_accounts:
            activity = await self.journal_service.get_account_balance_for_period(account.id, start_date, end_date)
            if activity != Decimal(0):
                add_back_adjustments.append({'name': f"{account.code} - {account.name}", 'amount': activity})
                total_add_back += activity

        non_taxable_accounts = await self.account_service.get_accounts_by_tax_treatment('Non-Taxable Income')
        for account in non_taxable_accounts:
            activity = await self.journal_service.get_account_balance_for_period(account.id, start_date, end_date)
            if activity != Decimal(0):
                # Revenue has negative balance, so activity is negative. We subtract a negative -> add.
                # To show it as a subtraction, we use the absolute value.
                less_adjustments.append({'name': f"{account.code} - {account.name}", 'amount': abs(activity)})
                total_less += abs(activity)
        
        chargeable_income = net_profit_before_tax + total_add_back - total_less
        
        tax_rate_str = await self.configuration_service.get_config_value("CorpTaxRate_Default", "17.0")
        tax_rate = Decimal(tax_rate_str if tax_rate_str else "17.0")
        
        # Note: This is a simplified calculation. Real tax computation involves capital allowances, PTE, etc.
        estimated_tax = chargeable_income * (tax_rate / Decimal(100))
        if estimated_tax < 0:
            estimated_tax = Decimal(0)

        return {
            'title': 'Income Tax Computation',
            'report_date_description': f"For Financial Year Ended {fiscal_year.end_date.strftime('%d %b %Y')}",
            'fiscal_year_name': fiscal_year.year_name,
            'net_profit_before_tax': net_profit_before_tax,
            'add_back_adjustments': add_back_adjustments,
            'total_add_back': total_add_back,
            'less_adjustments': less_adjustments,
            'total_less': total_less,
            'chargeable_income': chargeable_income,
            'tax_rate': tax_rate,
            'estimated_tax': estimated_tax
        }

    async def generate_gst_f5(self, start_date: date, end_date: date) -> Dict[str, Any]:
        if not self.company_settings_service or not self.tax_code_service: raise RuntimeError("TaxCodeService and CompanySettingsService are required for GST F5.")
        company = await self.company_settings_service.get_company_settings();
        if not company: raise ValueError("Company settings not found.")
        report_data: Dict[str, Any] = {'title': f"GST F5 Return for period {start_date.strftime('%d %b %Y')} to {end_date.strftime('%d %b %Y')}",'company_name': company.company_name,'gst_registration_no': company.gst_registration_no,'period_start': start_date, 'period_end': end_date,'standard_rated_supplies': Decimal(0), 'zero_rated_supplies': Decimal(0),'exempt_supplies': Decimal(0), 'total_supplies': Decimal(0),'taxable_purchases': Decimal(0), 'output_tax': Decimal(0),'input_tax': Decimal(0), 'tax_adjustments': Decimal(0), 'tax_payable': Decimal(0)}
        entries = await self.journal_service.get_posted_entries_by_date_range(start_date, end_date)
        for entry in entries:
            for line in entry.lines: 
                if not line.tax_code or not line.account: continue
                tax_code_info = await self.tax_code_service.get_tax_code(line.tax_code)
                if not tax_code_info or tax_code_info.tax_type != 'GST': continue
                line_net_amount = (line.debit_amount if line.debit_amount > Decimal(0) else line.credit_amount) 
                tax_on_line = line.tax_amount if line.tax_amount is not None else Decimal(0)
                if line.account.account_type == 'Revenue':
                    if tax_code_info.code == 'SR': report_data['standard_rated_supplies'] += line_net_amount; report_data['output_tax'] += tax_on_line
                    elif tax_code_info.code == 'ZR': report_data['zero_rated_supplies'] += line_net_amount
                    elif tax_code_info.code == 'ES': report_data['exempt_supplies'] += line_net_amount
                elif line.account.account_type in ['Expense', 'Asset']:
                    if tax_code_info.code == 'TX': report_data['taxable_purchases'] += line_net_amount; report_data['input_tax'] += tax_on_line
                    elif tax_code_info.code == 'BL': report_data['taxable_purchases'] += line_net_amount 
        report_data['total_supplies'] = (report_data['standard_rated_supplies'] + report_data['zero_rated_supplies'] + report_data['exempt_supplies'])
        report_data['tax_payable'] = report_data['output_tax'] - report_data['input_tax'] + report_data['tax_adjustments']
        return report_data

    async def generate_general_ledger(self, account_id: int, start_date: date, end_date: date,
                                      dimension1_id: Optional[int] = None, 
                                      dimension2_id: Optional[int] = None) -> Dict[str, Any]:
        account_orm = await self.account_service.get_by_id(account_id)
        if not account_orm:
            raise ValueError(f"Account with ID {account_id} not found.")

        ob_date = start_date - timedelta(days=1)
        opening_balance = await self.journal_service.get_account_balance(account_id, ob_date)

        lines: List[JournalEntryLine] = await self.journal_service.get_posted_lines_for_account_in_range(
            account_id, start_date, end_date, dimension1_id, dimension2_id 
        )

        transactions_data = []
        current_balance = opening_balance
        for line in lines:
            if not line.journal_entry: continue 
            movement = line.debit_amount - line.credit_amount
            current_balance += movement
            transactions_data.append({
                "date": line.journal_entry.entry_date, "entry_no": line.journal_entry.entry_no,
                "je_description": line.journal_entry.description or "", "line_description": line.description or "",
                "debit": line.debit_amount, "credit": line.credit_amount, "balance": current_balance,
                "dim1_id": line.dimension1_id, "dim2_id": line.dimension2_id 
            })
        closing_balance = current_balance
        
        report_desc = f"For Account: {account_orm.code} - {account_orm.name} from {start_date.strftime('%d %b %Y')} to {end_date.strftime('%d %b %Y')}"
        if dimension1_id and self.dimension_service:
            dim1 = await self.dimension_service.get_by_id(dimension1_id)
            if dim1: report_desc += f" (Dim1: {dim1.dimension_type}-{dim1.code})"
        if dimension2_id and self.dimension_service:
            dim2 = await self.dimension_service.get_by_id(dimension2_id)
            if dim2: report_desc += f" (Dim2: {dim2.dimension_type}-{dim2.code})"

        return {
            "title": "General Ledger", "report_date_description": report_desc,
            "account_code": account_orm.code, "account_name": account_orm.name,
            "start_date": start_date, "end_date": end_date,
            "opening_balance": opening_balance, "transactions": transactions_data,
            "closing_balance": closing_balance
        }

```

# app/reporting/report_engine.py
```py
# File: app/reporting/report_engine.py
from typing import Dict, Any, Literal, List, Optional, TYPE_CHECKING, cast 
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepInFrame
from reportlab.platypus.flowables import KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle 
from reportlab.lib import colors 
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import inch, cm 
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from io import BytesIO
import openpyxl 
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill 
from openpyxl.utils import get_column_letter 
from decimal import Decimal, InvalidOperation
from datetime import date

from app.utils.pydantic_models import GSTReturnData, GSTTransactionLineDetail

if TYPE_CHECKING:
    from app.core.application_core import ApplicationCore 

class ReportEngine:
    def __init__(self, app_core: "ApplicationCore"): 
        self.app_core = app_core
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

    def _setup_custom_styles(self):
        self.styles.add(ParagraphStyle(name='ReportTitle', parent=self.styles['h1'], alignment=TA_CENTER, spaceAfter=0.2*inch))
        self.styles.add(ParagraphStyle(name='ReportSubTitle', parent=self.styles['h2'], alignment=TA_CENTER, fontSize=12, spaceAfter=0.2*inch))
        self.styles.add(ParagraphStyle(name='SectionHeader', parent=self.styles['h3'], fontSize=11, spaceBefore=0.2*inch, spaceAfter=0.1*inch, textColor=colors.HexColor("#2F5496")))
        self.styles.add(ParagraphStyle(name='AccountName', parent=self.styles['Normal'], leftIndent=0.2*inch))
        self.styles.add(ParagraphStyle(name='AccountNameBold', parent=self.styles['AccountName'], fontName='Helvetica-Bold'))
        self.styles.add(ParagraphStyle(name='Amount', parent=self.styles['Normal'], alignment=TA_RIGHT))
        self.styles.add(ParagraphStyle(name='AmountBold', parent=self.styles['Amount'], fontName='Helvetica-Bold'))
        self.styles.add(ParagraphStyle(name='TableHeader', parent=self.styles['Normal'], fontName='Helvetica-Bold', alignment=TA_CENTER, textColor=colors.whitesmoke))
        self.styles.add(ParagraphStyle(name='Footer', parent=self.styles['Normal'], alignment=TA_CENTER, fontSize=8))
        self.styles.add(ParagraphStyle(name='NormalRight', parent=self.styles['Normal'], alignment=TA_RIGHT))
        self.styles.add(ParagraphStyle(name='NormalCenter', parent=self.styles['Normal'], alignment=TA_CENTER))
        self.styles.add(ParagraphStyle(name='GLAccountHeader', parent=self.styles['h3'], fontSize=10, spaceBefore=0.1*inch, spaceAfter=0.05*inch, alignment=TA_LEFT))

    async def export_report(self, report_data: Dict[str, Any], format_type: Literal["pdf", "excel", "gst_excel_detail"]) -> Optional[bytes]:
        title = report_data.get('title', "Financial Report")
        is_gst_detail_export = isinstance(report_data, GSTReturnData) and "gst_excel_detail" in format_type

        if format_type == "pdf":
            if title == "Balance Sheet": return await self._export_balance_sheet_to_pdf(report_data)
            elif title == "Profit & Loss Statement": return await self._export_profit_loss_to_pdf(report_data)
            elif title == "Trial Balance": return await self._export_trial_balance_to_pdf(report_data)
            elif title == "General Ledger": return await self._export_general_ledger_to_pdf(report_data)
            elif title == "Income Tax Computation": return await self._export_tax_computation_to_pdf(report_data)
            else: return self._export_generic_table_to_pdf(report_data) 
        elif format_type == "excel":
            if title == "Balance Sheet": return await self._export_balance_sheet_to_excel(report_data)
            elif title == "Profit & Loss Statement": return await self._export_profit_loss_to_excel(report_data)
            elif title == "Trial Balance": return await self._export_trial_balance_to_excel(report_data)
            elif title == "General Ledger": return await self._export_general_ledger_to_excel(report_data)
            elif title == "Income Tax Computation": return await self._export_tax_computation_to_excel(report_data)
            else: return self._export_generic_table_to_excel(report_data) 
        elif is_gst_detail_export:
            return await self._export_gst_f5_details_to_excel(cast(GSTReturnData, report_data))
        else:
            self.app_core.logger.error(f"Unsupported report format or data type mismatch: {format_type}, type: {type(report_data)}")
            return None

    def _format_decimal(self, value: Optional[Decimal], places: int = 2, show_blank_for_zero: bool = False) -> str:
        if value is None: return "" if show_blank_for_zero else self._format_decimal(Decimal(0), places) 
        if not isinstance(value, Decimal): 
            try: value = Decimal(str(value))
            except InvalidOperation: return "ERR_DEC" 
        if show_blank_for_zero and value.is_zero(): return ""
        return f"{value:,.{places}f}"

    async def _get_company_name(self) -> str:
        settings = await self.app_core.company_settings_service.get_company_settings()
        return settings.company_name if settings else "Your Company"

    def _add_pdf_header_footer(self, canvas, doc, company_name: str, report_title: str, date_desc: str):
        canvas.saveState(); page_width = doc.width + doc.leftMargin + doc.rightMargin; header_y_start = doc.height + doc.topMargin - 0.5*inch
        canvas.setFont('Helvetica-Bold', 14); canvas.drawCentredString(page_width/2, header_y_start, company_name)
        canvas.setFont('Helvetica-Bold', 12); canvas.drawCentredString(page_width/2, header_y_start - 0.25*inch, report_title)
        canvas.setFont('Helvetica', 10); canvas.drawCentredString(page_width/2, header_y_start - 0.5*inch, date_desc)
        footer_y = 0.5*inch; canvas.setFont('Helvetica', 8); canvas.drawString(doc.leftMargin, footer_y, f"Generated on: {date.today().strftime('%d %b %Y')}"); canvas.drawRightString(page_width - doc.rightMargin, footer_y, f"Page {doc.page}"); canvas.restoreState()

    async def _export_balance_sheet_to_pdf(self, report_data: Dict[str, Any]) -> bytes:
        buffer = BytesIO(); company_name = await self._get_company_name(); report_title = report_data.get('title', "Balance Sheet"); date_desc = report_data.get('report_date_description', "")
        doc = SimpleDocTemplate(buffer, pagesize=A4,rightMargin=0.75*inch, leftMargin=0.75*inch,topMargin=1.25*inch, bottomMargin=0.75*inch)
        story: List[Any] = []; has_comparative = bool(report_data.get('comparative_date')); col_widths = [3.5*inch, 1.5*inch]; 
        if has_comparative: col_widths.append(1.5*inch)
        header_texts = ["Description", "Current Period"]; 
        if has_comparative: header_texts.append("Comparative")
        table_header_row = [Paragraph(text, self.styles['TableHeader']) for text in header_texts]
        def build_section_data(section_key: str, title: str):
            data: List[List[Any]] = []; section = report_data.get(section_key, {})
            data.append([Paragraph(title, self.styles['SectionHeader'])] + (["", ""] if has_comparative else [""]))
            for acc in section.get('accounts', []):
                row = [Paragraph(f"{acc['code']} - {acc['name']}", self.styles['AccountName']), Paragraph(self._format_decimal(acc['balance']), self.styles['Amount'])]
                if has_comparative:
                    comp_bal_str = ""; 
                    if section.get('comparative_accounts'):
                        comp_acc_list = section['comparative_accounts']; comp_acc_match = next((ca for ca in comp_acc_list if ca['id'] == acc['id']), None)
                        if comp_acc_match and comp_acc_match.get('balance') is not None: comp_bal_str = self._format_decimal(comp_acc_match['balance'])
                    row.append(Paragraph(comp_bal_str, self.styles['Amount']))
                data.append(row)
            total_row = [Paragraph(f"Total {title}", self.styles['AccountNameBold']), Paragraph(self._format_decimal(section.get('total')), self.styles['AmountBold'])]
            if has_comparative: total_row.append(Paragraph(self._format_decimal(section.get('comparative_total')), self.styles['AmountBold']))
            data.append(total_row); data.append([Spacer(1, 0.1*inch)] * len(col_widths)); return data
        bs_data: List[List[Any]] = [table_header_row]; bs_data.extend(build_section_data('assets', 'Assets')); bs_data.extend(build_section_data('liabilities', 'Liabilities')); bs_data.extend(build_section_data('equity', 'Equity'))
        total_lia_eq_row = [Paragraph("Total Liabilities & Equity", self.styles['AccountNameBold']), Paragraph(self._format_decimal(report_data.get('total_liabilities_equity')), self.styles['AmountBold'])]
        if has_comparative: total_lia_eq_row.append(Paragraph(self._format_decimal(report_data.get('comparative_total_liabilities_equity')), self.styles['AmountBold']))
        bs_data.append(total_lia_eq_row); bs_table = Table(bs_data, colWidths=col_widths)
        style = TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.grey), ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#4F81BD")), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('LINEABOVE', (0, -1), (-1,-1), 1, colors.black), ('LINEBELOW', (1, -1), (-1, -1), 1, colors.black, None, (2,2), 0, 1), ('LINEBELOW', (1, -1), (-1, -1), 0.5, colors.black, None, (1,1), 0, 1),])
        current_row_idx = 1 
        for section_key in ['assets', 'liabilities', 'equity']:
            if section_key in report_data: style.add('SPAN', (0, current_row_idx), (len(col_widths)-1, current_row_idx)); current_row_idx += len(report_data[section_key].get('accounts', [])) + 2 
        bs_table.setStyle(style); story.append(bs_table)
        if report_data.get('is_balanced') is False: story.append(Spacer(1, 0.2*inch)); story.append(Paragraph("Warning: Balance Sheet is out of balance!", ParagraphStyle(name='Warning', parent=self.styles['Normal'], textColor=colors.red, fontName='Helvetica-Bold')))
        doc.build(story, onFirstPage=lambda c, d: self._add_pdf_header_footer(c, d, company_name, report_title, date_desc), onLaterPages=lambda c, d: self._add_pdf_header_footer(c, d, company_name, report_title, date_desc)); return buffer.getvalue()

    async def _export_profit_loss_to_pdf(self, report_data: Dict[str, Any]) -> bytes:
        buffer = BytesIO(); company_name = await self._get_company_name(); report_title = report_data.get('title', "Profit & Loss Statement"); date_desc = report_data.get('report_date_description', "")
        doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=0.75*inch, leftMargin=0.75*inch,topMargin=1.25*inch, bottomMargin=0.75*inch)
        story: List[Any] = []; has_comparative = bool(report_data.get('comparative_start')); comp_header_text = "Comparative"; 
        if has_comparative and report_data.get('comparative_start') and report_data.get('comparative_end'): comp_start_str = report_data['comparative_start'].strftime('%d/%m/%y'); comp_end_str = report_data['comparative_end'].strftime('%d/%m/%y'); comp_header_text = f"Comp. ({comp_start_str}-{comp_end_str})"
        headers = ["Description", "Amount"]; 
        if has_comparative: headers.append(comp_header_text); 
        table_header_row = [Paragraph(text, self.styles['TableHeader']) for text in headers]; col_widths = [3.5*inch, 1.5*inch]; 
        if has_comparative: col_widths.append(1.5*inch)
        def build_pl_section_data(section_key: str, title: str, is_subtraction: bool = False):
            data: List[List[Any]] = []; section = report_data.get(section_key, {})
            data.append([Paragraph(title, self.styles['SectionHeader'])] + (["", ""] if has_comparative else [""]))
            for acc in section.get('accounts', []):
                balance = acc['balance']; row = [Paragraph(f"  {acc['code']} - {acc['name']}", self.styles['AccountName']), Paragraph(self._format_decimal(balance), self.styles['Amount'])]
                if has_comparative:
                    comp_bal_str = ""; 
                    if section.get('comparative_accounts'):
                        comp_acc_list = section['comparative_accounts']; comp_acc_match = next((ca for ca in comp_acc_list if ca['id'] == acc['id']), None)
                        if comp_acc_match and comp_acc_match.get('balance') is not None: comp_bal_str = self._format_decimal(comp_acc_match['balance'])
                    row.append(Paragraph(comp_bal_str, self.styles['Amount']))
                data.append(row)
            total = section.get('total'); total_row = [Paragraph(f"Total {title}", self.styles['AccountNameBold']), Paragraph(self._format_decimal(total), self.styles['AmountBold'])]
            if has_comparative: comp_total = section.get('comparative_total'); total_row.append(Paragraph(self._format_decimal(comp_total), self.styles['AmountBold']))
            data.append(total_row); data.append([Spacer(1, 0.1*inch)] * len(col_widths)); return data, total, section.get('comparative_total') if has_comparative else None
        pl_data: List[List[Any]] = [table_header_row]; rev_data, total_revenue, comp_total_revenue = build_pl_section_data('revenue', 'Revenue'); pl_data.extend(rev_data)
        exp_data, total_expenses, comp_total_expenses = build_pl_section_data('expenses', 'Operating Expenses', is_subtraction=True); pl_data.extend(exp_data)
        net_profit = report_data.get('net_profit', Decimal(0)); comp_net_profit = report_data.get('comparative_net_profit')
        net_profit_row = [Paragraph("Net Profit / (Loss)", self.styles['AccountNameBold']), Paragraph(self._format_decimal(net_profit), self.styles['AmountBold'])]
        if has_comparative: net_profit_row.append(Paragraph(self._format_decimal(comp_net_profit), self.styles['AmountBold']))
        pl_data.append(net_profit_row); pl_table = Table(pl_data, colWidths=col_widths)
        style = TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.grey), ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#4F81BD")), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('LINEABOVE', (1, -1), (-1,-1), 1, colors.black), ('LINEBELOW', (1, -1), (-1, -1), 1, colors.black, None, (2,2), 0, 1), ('LINEBELOW', (1, -1), (-1, -1), 0.5, colors.black, None, (1,1), 0, 1),])
        current_row_idx = 1
        for section_key in ['revenue', 'expenses']: 
            if section_key in report_data: style.add('SPAN', (0, current_row_idx), (len(col_widths)-1, current_row_idx)); current_row_idx += len(report_data[section_key].get('accounts', [])) + 2
        pl_table.setStyle(style); story.append(pl_table)
        doc.build(story, onFirstPage=lambda c, d: self._add_pdf_header_footer(c, d, company_name, report_title, date_desc), onLaterPages=lambda c, d: self._add_pdf_header_footer(c, d, company_name, report_title, date_desc)); return buffer.getvalue()

    async def _export_trial_balance_to_pdf(self, report_data: Dict[str, Any]) -> bytes:
        buffer = BytesIO(); company_name = await self._get_company_name(); report_title = report_data.get('title', "Trial Balance"); date_desc = report_data.get('report_date_description', f"As of {date.today().strftime('%d %b %Y')}")
        doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=0.75*inch, leftMargin=0.75*inch,topMargin=1.25*inch, bottomMargin=0.75*inch)
        story: List[Any] = []; col_widths = [1.5*inch, 3*inch, 1.25*inch, 1.25*inch]; header_texts = ["Account Code", "Account Name", "Debit", "Credit"]
        table_header_row = [Paragraph(text, self.styles['TableHeader']) for text in header_texts]; tb_data: List[List[Any]] = [table_header_row]
        for acc in report_data.get('debit_accounts', []): tb_data.append([Paragraph(acc['code'], self.styles['Normal']), Paragraph(acc['name'], self.styles['Normal']), Paragraph(self._format_decimal(acc['balance']), self.styles['NormalRight']), Paragraph("", self.styles['NormalRight'])])
        for acc in report_data.get('credit_accounts', []): tb_data.append([Paragraph(acc['code'], self.styles['Normal']), Paragraph(acc['name'], self.styles['Normal']), Paragraph("", self.styles['NormalRight']), Paragraph(self._format_decimal(acc['balance']), self.styles['NormalRight'])])
        tb_data.append([Paragraph(""), Paragraph("TOTALS", self.styles['AccountNameBold']), Paragraph(self._format_decimal(report_data.get('total_debits')), self.styles['AmountBold']), Paragraph(self._format_decimal(report_data.get('total_credits')), self.styles['AmountBold'])])
        tb_table = Table(tb_data, colWidths=col_widths)
        style = TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.grey), ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#4F81BD")), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('LINEABOVE', (2, -1), (3, -1), 1, colors.black), ('LINEBELOW', (2, -1), (3, -1), 1, colors.black), ('ALIGN', (2,1), (3,-1), 'RIGHT'),])
        tb_table.setStyle(style); story.append(tb_table)
        if report_data.get('is_balanced') is False: story.append(Spacer(1,0.2*inch)); story.append(Paragraph("Warning: Trial Balance is out of balance!", ParagraphStyle(name='Warning', parent=self.styles['Normal'], textColor=colors.red, fontName='Helvetica-Bold')))
        doc.build(story, onFirstPage=lambda c, d: self._add_pdf_header_footer(c, d, company_name, report_title, date_desc), onLaterPages=lambda c, d: self._add_pdf_header_footer(c, d, company_name, report_title, date_desc)); return buffer.getvalue()

    async def _export_general_ledger_to_pdf(self, report_data: Dict[str, Any]) -> bytes:
        buffer = BytesIO(); company_name = await self._get_company_name(); report_title = report_data.get('title', "General Ledger"); date_desc = report_data.get('report_date_description', "") 
        doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), rightMargin=0.5*inch, leftMargin=0.5*inch, topMargin=1.25*inch, bottomMargin=0.75*inch)
        story: List[Any] = []; story.append(Paragraph(f"Account: {report_data.get('account_code')} - {report_data.get('account_name')}", self.styles['GLAccountHeader'])); story.append(Spacer(1, 0.1*inch)); story.append(Paragraph(f"Opening Balance: {self._format_decimal(report_data.get('opening_balance'))}", self.styles['AccountNameBold'])); story.append(Spacer(1, 0.2*inch))
        headers = ["Date", "Entry No.", "JE Description", "Line Description", "Debit", "Credit", "Balance"]
        table_header_row = [Paragraph(h, self.styles['TableHeader']) for h in headers]; gl_data: List[List[Any]] = [table_header_row]
        for txn in report_data.get('transactions', []): gl_data.append([Paragraph(txn['date'].strftime('%d/%m/%Y') if isinstance(txn['date'], date) else str(txn['date']), self.styles['NormalCenter']), Paragraph(txn['entry_no'], self.styles['Normal']), Paragraph(txn.get('je_description','')[:40], self.styles['Normal']), Paragraph(txn.get('line_description','')[:40], self.styles['Normal']), Paragraph(self._format_decimal(txn['debit'], show_blank_for_zero=True), self.styles['NormalRight']), Paragraph(self._format_decimal(txn['credit'], show_blank_for_zero=True), self.styles['NormalRight']), Paragraph(self._format_decimal(txn['balance']), self.styles['NormalRight'])])
        col_widths_gl = [0.9*inch, 1.0*inch, 2.8*inch, 2.8*inch, 1.0*inch, 1.0*inch, 1.19*inch]
        gl_table = Table(gl_data, colWidths=col_widths_gl); style = TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.grey), ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#4F81BD")), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('ALIGN', (0,1), (1,-1), 'CENTER'), ('ALIGN', (4,1), (6,-1), 'RIGHT'),]); gl_table.setStyle(style); story.append(gl_table); story.append(Spacer(1, 0.1*inch)); story.append(Paragraph(f"Closing Balance: {self._format_decimal(report_data.get('closing_balance'))}", self.styles['AmountBold']))
        doc.build(story, onFirstPage=lambda c, d: self._add_pdf_header_footer(c, d, company_name, report_title, date_desc), onLaterPages=lambda c, d: self._add_pdf_header_footer(c, d, company_name, report_title, date_desc)); return buffer.getvalue()

    async def _export_tax_computation_to_pdf(self, report_data: Dict[str, Any]) -> bytes:
        buffer = BytesIO(); company_name = await self._get_company_name(); report_title = report_data.get('title', "Tax Computation"); date_desc = report_data.get('report_date_description', "")
        doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=0.75*inch, leftMargin=0.75*inch, topMargin=1.25*inch, bottomMargin=0.75*inch)
        story: List[Any] = []; col_widths = [5*inch, 1.5*inch]; table_header_row = [Paragraph("Description", self.styles['TableHeader']), Paragraph("Amount", self.styles['TableHeader'])]; data: List[List[Any]] = [table_header_row]
        data.append([Paragraph("Net Profit Before Tax", self.styles['AccountNameBold']), Paragraph(self._format_decimal(report_data.get('net_profit_before_tax')), self.styles['AmountBold'])])
        data.append([Paragraph("Add: Non-Deductible Expenses", self.styles['SectionHeader']), ""]); 
        for adj in report_data.get('add_back_adjustments', []): data.append([Paragraph(f"  {adj['name']}", self.styles['AccountName']), Paragraph(self._format_decimal(adj['amount']), self.styles['Amount'])])
        data.append([Paragraph("Less: Non-Taxable Income", self.styles['SectionHeader']), ""])
        for adj in report_data.get('less_adjustments', []): data.append([Paragraph(f"  {adj['name']}", self.styles['AccountName']), Paragraph(f"({self._format_decimal(adj['amount'])})", self.styles['Amount'])])
        data.append([Paragraph("Chargeable Income", self.styles['AccountNameBold']), Paragraph(self._format_decimal(report_data.get('chargeable_income')), self.styles['AmountBold'])])
        data.append([Paragraph(f"Estimated Tax @ {report_data.get('tax_rate', 0):.2f}%", self.styles['AccountNameBold']), Paragraph(self._format_decimal(report_data.get('estimated_tax')), self.styles['AmountBold'])])
        table = Table(data, colWidths=col_widths)
        style = TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.grey), ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#4F81BD")), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('LINEABOVE', (1, -1), (1,-1), 1, colors.black), ('LINEBELOW', (1, -1), (1, -1), 1, colors.black, None, (2,2), 0, 1),])
        style.add('SPAN', (0, 2), (1, 2)); style.add('SPAN', (0, len(data)-5), (1, len(data)-5)); 
        table.setStyle(style); story.append(table)
        doc.build(story, onFirstPage=lambda c, d: self._add_pdf_header_footer(c, d, company_name, report_title, date_desc), onLaterPages=lambda c, d: self._add_pdf_header_footer(c, d, company_name, report_title, date_desc)); return buffer.getvalue()

    def _export_generic_table_to_pdf(self, report_data: Dict[str, Any]) -> bytes:
        self.app_core.logger.warning(f"Using generic PDF export for report: {report_data.get('title')}")
        buffer = BytesIO(); doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=0.5*inch, leftMargin=0.5*inch, topMargin=0.5*inch, bottomMargin=0.5*inch)
        story: List[Any] = [Paragraph(report_data.get('title', "Report"), self.styles['h1'])]; 
        if report_data.get('report_date_description'): story.append(Paragraph(report_data.get('report_date_description'), self.styles['h3']))
        story.append(Spacer(1, 0.2*inch)); data_to_display = report_data.get('data_rows', []); headers = report_data.get('headers', [])
        if headers and data_to_display:
            table_data: List[List[Any]] = [[Paragraph(str(h), self.styles['TableHeader']) for h in headers]]
            for row_dict in data_to_display: table_data.append([Paragraph(str(row_dict.get(h_key, '')), self.styles['Normal']) for h_key in headers]) 
            num_cols = len(headers); col_widths_generic = [doc.width/num_cols]*num_cols
            table = Table(table_data, colWidths=col_widths_generic); table.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.grey), ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#4F81BD"))])); story.append(table)
        else: story.append(Paragraph("No data or headers provided for generic export.", self.styles['Normal']))
        doc.build(story); return buffer.getvalue()

    def _apply_excel_header_style(self, cell, bold=True, size=12, alignment='center', fill_color: Optional[str]=None):
        cell.font = Font(bold=bold, size=size, color="FFFFFF" if fill_color else "000000")
        if alignment == 'center': cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        elif alignment == 'right': cell.alignment = Alignment(horizontal='right', vertical='center')
        else: cell.alignment = Alignment(horizontal='left', vertical='center', wrap_text=True)
        if fill_color: cell.fill = PatternFill(start_color=fill_color, end_color=fill_color, fill_type="solid")

    def _apply_excel_amount_style(self, cell, bold=False, underline: Optional[str]=None):
        cell.number_format = '#,##0.00;[Red](#,##0.00);"-"' 
        cell.alignment = Alignment(horizontal='right')
        if bold: cell.font = Font(bold=True)
        if underline: cell.border = Border(bottom=Side(style=underline))
        
    async def _export_balance_sheet_to_excel(self, report_data: Dict[str, Any]) -> bytes:
        wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Balance Sheet"; company_name = await self._get_company_name(); has_comparative = bool(report_data.get('comparative_date')); row_num = 1
        ws.merge_cells(start_row=row_num, start_column=1, end_row=row_num, end_column=3 if has_comparative else 2); self._apply_excel_header_style(ws.cell(row=row_num, column=1, value=company_name), size=14); row_num +=1
        ws.merge_cells(start_row=row_num, start_column=1, end_row=row_num, end_column=3 if has_comparative else 2); self._apply_excel_header_style(ws.cell(row=row_num, column=1, value=report_data.get('title')), size=12); row_num +=1
        ws.merge_cells(start_row=row_num, start_column=1, end_row=row_num, end_column=3 if has_comparative else 2); self._apply_excel_header_style(ws.cell(row=row_num, column=1, value=report_data.get('report_date_description')), size=10, bold=False); row_num += 2
        headers = ["Description", "Current Period"]; 
        if has_comparative: headers.append("Comparative")
        for col, header_text in enumerate(headers, 1): self._apply_excel_header_style(ws.cell(row=row_num, column=col, value=header_text), alignment='center' if col>0 else 'left', fill_color="4F81BD")
        row_num +=1
        def write_section(section_key: str, title: str):
            nonlocal row_num; section = report_data.get(section_key, {})
            ws.cell(row=row_num, column=1, value=title).font = Font(bold=True, size=11, color="2F5496"); row_num +=1
            for acc in section.get('accounts', []):
                ws.cell(row=row_num, column=1, value=f"  {acc['code']} - {acc['name']}")
                self._apply_excel_amount_style(ws.cell(row=row_num, column=2, value=float(acc['balance'] if acc.get('balance') is not None else 0)))
                if has_comparative:
                    comp_val = None
                    if section.get('comparative_accounts'):
                        comp_acc_match = next((ca for ca in section['comparative_accounts'] if ca['id'] == acc['id']), None)
                        if comp_acc_match and comp_acc_match.get('balance') is not None: comp_val = float(comp_acc_match['balance'])
                    self._apply_excel_amount_style(ws.cell(row=row_num, column=3, value=comp_val if comp_val is not None else "-"))
                row_num +=1
            ws.cell(row=row_num, column=1, value=f"Total {title}").font = Font(bold=True)
            self._apply_excel_amount_style(ws.cell(row=row_num, column=2, value=float(section.get('total',0))), bold=True, underline="thin")
            if has_comparative: self._apply_excel_amount_style(ws.cell(row=row_num, column=3, value=float(section.get('comparative_total',0))), bold=True, underline="thin")
            row_num += 2
        write_section('assets', 'Assets'); write_section('liabilities', 'Liabilities'); write_section('equity', 'Equity')
        ws.cell(row=row_num, column=1, value="Total Liabilities & Equity").font = Font(bold=True, size=11)
        self._apply_excel_amount_style(ws.cell(row=row_num, column=2, value=float(report_data.get('total_liabilities_equity',0))), bold=True, underline="double")
        if has_comparative: self._apply_excel_amount_style(ws.cell(row=row_num, column=3, value=float(report_data.get('comparative_total_liabilities_equity',0))), bold=True, underline="double")
        row_num +=1
        if report_data.get('is_balanced') is False: ws.cell(row=row_num, column=1, value="Warning: Balance Sheet out of balance!").font = Font(color="FF0000", bold=True)
        for i, col_letter in enumerate(['A','B','C'][:len(headers)]): ws.column_dimensions[col_letter].width = 45 if i==0 else 20
        excel_bytes_io = BytesIO(); wb.save(excel_bytes_io); return excel_bytes_io.getvalue()

    async def _export_profit_loss_to_excel(self, report_data: Dict[str, Any]) -> bytes:
        wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Profit and Loss"; company_name = await self._get_company_name(); has_comparative = bool(report_data.get('comparative_start')); row_num = 1
        ws.merge_cells(start_row=row_num, start_column=1, end_row=row_num, end_column=3 if has_comparative else 2); self._apply_excel_header_style(ws.cell(row=row_num, column=1, value=company_name), size=14); row_num +=1
        ws.merge_cells(start_row=row_num, start_column=1, end_row=row_num, end_column=3 if has_comparative else 2); self._apply_excel_header_style(ws.cell(row=row_num, column=1, value=report_data.get('title')), size=12); row_num +=1
        ws.merge_cells(start_row=row_num, start_column=1, end_row=row_num, end_column=3 if has_comparative else 2); self._apply_excel_header_style(ws.cell(row=row_num, column=1, value=report_data.get('report_date_description')), size=10, bold=False); row_num += 2
        headers = ["Description", "Current Period"]; 
        if has_comparative: headers.append("Comparative")
        for col, header_text in enumerate(headers, 1): self._apply_excel_header_style(ws.cell(row=row_num, column=col, value=header_text), alignment='center' if col>0 else 'left', fill_color="4F81BD")
        row_num +=1
        def write_pl_section(section_key: str, title: str):
            nonlocal row_num; section = report_data.get(section_key, {})
            ws.cell(row=row_num, column=1, value=title).font = Font(bold=True, size=11, color="2F5496"); row_num +=1
            for acc in section.get('accounts', []):
                ws.cell(row=row_num, column=1, value=f"  {acc['code']} - {acc['name']}")
                self._apply_excel_amount_style(ws.cell(row=row_num, column=2, value=float(acc['balance'] if acc.get('balance') is not None else 0)))
                if has_comparative:
                    comp_val = None
                    if section.get('comparative_accounts'):
                        comp_acc_match = next((ca for ca in section['comparative_accounts'] if ca['id'] == acc['id']), None)
                        if comp_acc_match and comp_acc_match.get('balance') is not None: comp_val = float(comp_acc_match['balance'])
                    self._apply_excel_amount_style(ws.cell(row=row_num, column=3, value=comp_val if comp_val is not None else "-"))
                row_num +=1
            ws.cell(row=row_num, column=1, value=f"Total {title}").font = Font(bold=True)
            self._apply_excel_amount_style(ws.cell(row=row_num, column=2, value=float(section.get('total',0))), bold=True, underline="thin")
            if has_comparative: self._apply_excel_amount_style(ws.cell(row=row_num, column=3, value=float(section.get('comparative_total',0))), bold=True, underline="thin")
            row_num +=1; return section.get('total', Decimal(0)), section.get('comparative_total') if has_comparative else Decimal(0)
        total_revenue, comp_total_revenue = write_pl_section('revenue', 'Revenue'); row_num +=1 
        total_expenses, comp_total_expenses = write_pl_section('expenses', 'Operating Expenses'); row_num +=1 
        ws.cell(row=row_num, column=1, value="Net Profit / (Loss)").font = Font(bold=True, size=11)
        self._apply_excel_amount_style(ws.cell(row=row_num, column=2, value=float(report_data.get('net_profit',0))), bold=True, underline="double")
        if has_comparative: self._apply_excel_amount_style(ws.cell(row=row_num, column=3, value=float(report_data.get('comparative_net_profit',0))), bold=True, underline="double")
        for i, col_letter in enumerate(['A','B','C'][:len(headers)]): ws.column_dimensions[col_letter].width = 45 if i==0 else 20
        excel_bytes_io = BytesIO(); wb.save(excel_bytes_io); return excel_bytes_io.getvalue()
    
    async def _export_trial_balance_to_excel(self, report_data: Dict[str, Any]) -> bytes:
        wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Trial Balance"; company_name = await self._get_company_name(); row_num = 1
        ws.merge_cells(start_row=row_num, start_column=1, end_row=row_num, end_column=4); self._apply_excel_header_style(ws.cell(row=row_num, column=1, value=company_name), size=14, alignment='center'); row_num += 1
        ws.merge_cells(start_row=row_num, start_column=1, end_row=row_num, end_column=4); self._apply_excel_header_style(ws.cell(row=row_num, column=1, value=report_data.get('title')), size=12, alignment='center'); row_num += 1
        ws.merge_cells(start_row=row_num, start_column=1, end_row=row_num, end_column=4); self._apply_excel_header_style(ws.cell(row=row_num, column=1, value=report_data.get('report_date_description')), size=10, bold=False, alignment='center'); row_num += 2
        headers = ["Account Code", "Account Name", "Debit", "Credit"]
        for col, header_text in enumerate(headers, 1): self._apply_excel_header_style(ws.cell(row=row_num, column=col, value=header_text), fill_color="4F81BD", alignment='center' if col > 1 else 'left')
        row_num += 1
        for acc in report_data.get('debit_accounts', []): ws.cell(row=row_num, column=1, value=acc['code']); ws.cell(row=row_num, column=2, value=acc['name']); self._apply_excel_amount_style(ws.cell(row=row_num, column=3, value=float(acc['balance'] if acc.get('balance') is not None else 0))); ws.cell(row=row_num, column=4, value=None); row_num += 1
        for acc in report_data.get('credit_accounts', []): ws.cell(row=row_num, column=1, value=acc['code']); ws.cell(row=row_num, column=2, value=acc['name']); ws.cell(row=row_num, column=3, value=None); self._apply_excel_amount_style(ws.cell(row=row_num, column=4, value=float(acc['balance'] if acc.get('balance') is not None else 0))); row_num += 1
        row_num +=1; ws.cell(row=row_num, column=2, value="TOTALS").font = Font(bold=True); ws.cell(row=row_num, column=2).alignment = Alignment(horizontal='right')
        self._apply_excel_amount_style(ws.cell(row=row_num, column=3, value=float(report_data.get('total_debits', 0))), bold=True, underline="thin"); self._apply_excel_amount_style(ws.cell(row=row_num, column=4, value=float(report_data.get('total_credits', 0))), bold=True, underline="thin")
        if report_data.get('is_balanced', True) is False: row_num +=2; ws.cell(row=row_num, column=1, value="Warning: Trial Balance is out of balance!").font = Font(color="FF0000", bold=True)
        ws.column_dimensions[get_column_letter(1)].width = 15; ws.column_dimensions[get_column_letter(2)].width = 45; ws.column_dimensions[get_column_letter(3)].width = 20; ws.column_dimensions[get_column_letter(4)].width = 20
        excel_bytes_io = BytesIO(); wb.save(excel_bytes_io); return excel_bytes_io.getvalue()

    async def _export_general_ledger_to_excel(self, report_data: Dict[str, Any]) -> bytes:
        wb = openpyxl.Workbook(); ws = wb.active; ws.title = f"GL-{report_data.get('account_code', 'Account')}"[:30]; company_name = await self._get_company_name(); row_num = 1
        ws.merge_cells(start_row=row_num, start_column=1, end_row=row_num, end_column=7); self._apply_excel_header_style(ws.cell(row=row_num, column=1, value=company_name), size=14, alignment='center'); row_num += 1
        ws.merge_cells(start_row=row_num, start_column=1, end_row=row_num, end_column=7); self._apply_excel_header_style(ws.cell(row=row_num, column=1, value=report_data.get('title')), size=12, alignment='center'); row_num += 1
        ws.merge_cells(start_row=row_num, start_column=1, end_row=row_num, end_column=7); self._apply_excel_header_style(ws.cell(row=row_num, column=1, value=report_data.get('report_date_description')), size=10, bold=False, alignment='center'); row_num += 2
        headers = ["Date", "Entry No.", "JE Description", "Line Description", "Debit", "Credit", "Balance"]
        for col, header_text in enumerate(headers, 1): self._apply_excel_header_style(ws.cell(row=row_num, column=col, value=header_text), fill_color="4F81BD", alignment='center' if col > 3 else 'left')
        row_num += 1
        ws.cell(row=row_num, column=4, value="Opening Balance").font = Font(bold=True); ws.cell(row=row_num, column=4).alignment = Alignment(horizontal='right'); self._apply_excel_amount_style(ws.cell(row=row_num, column=7, value=float(report_data.get('opening_balance',0))), bold=True); row_num += 1
        for txn in report_data.get('transactions', []):
            ws.cell(row=row_num, column=1, value=txn['date'].strftime('%d/%m/%Y') if isinstance(txn['date'], date) else txn['date']); ws.cell(row=row_num, column=1).alignment = Alignment(horizontal='center')
            ws.cell(row=row_num, column=2, value=txn['entry_no']); ws.cell(row=row_num, column=3, value=txn.get('je_description','')); ws.cell(row=row_num, column=4, value=txn.get('line_description',''))
            self._apply_excel_amount_style(ws.cell(row=row_num, column=5, value=float(txn['debit'] if txn['debit'] else 0))); self._apply_excel_amount_style(ws.cell(row=row_num, column=6, value=float(txn['credit'] if txn['credit'] else 0))); self._apply_excel_amount_style(ws.cell(row=row_num, column=7, value=float(txn['balance']))); row_num += 1
        ws.cell(row=row_num, column=4, value="Closing Balance").font = Font(bold=True); ws.cell(row=row_num, column=4).alignment = Alignment(horizontal='right'); self._apply_excel_amount_style(ws.cell(row=row_num, column=7, value=float(report_data.get('closing_balance',0))), bold=True, underline="thin")
        ws.column_dimensions[get_column_letter(1)].width = 12; ws.column_dimensions[get_column_letter(2)].width = 15; ws.column_dimensions[get_column_letter(3)].width = 40; ws.column_dimensions[get_column_letter(4)].width = 40
        for i in [5,6,7]: ws.column_dimensions[get_column_letter(i)].width = 18
        excel_bytes_io = BytesIO(); wb.save(excel_bytes_io); return excel_bytes_io.getvalue()

    async def _export_tax_computation_to_excel(self, report_data: Dict[str, Any]) -> bytes:
        wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Tax Computation"; company_name = await self._get_company_name(); row_num = 1
        ws.merge_cells(start_row=row_num, start_column=1, end_row=row_num, end_column=2); self._apply_excel_header_style(ws.cell(row=row_num, column=1, value=company_name), size=14, alignment='center'); row_num += 1
        ws.merge_cells(start_row=row_num, start_column=1, end_row=row_num, end_column=2); self._apply_excel_header_style(ws.cell(row=row_num, column=1, value=report_data.get('title')), size=12, alignment='center'); row_num += 1
        ws.merge_cells(start_row=row_num, start_column=1, end_row=row_num, end_column=2); self._apply_excel_header_style(ws.cell(row=row_num, column=1, value=report_data.get('report_date_description')), size=10, bold=False, alignment='center'); row_num += 2
        for col, header_text in enumerate(["Description", "Amount"], 1): self._apply_excel_header_style(ws.cell(row=row_num, column=col, value=header_text), fill_color="4F81BD")
        row_num +=1
        ws.cell(row=row_num, column=1, value="Net Profit Before Tax").font = Font(bold=True); self._apply_excel_amount_style(ws.cell(row=row_num, column=2, value=float(report_data.get('net_profit_before_tax',0))), bold=True); row_num += 2
        ws.cell(row=row_num, column=1, value="Add: Non-Deductible Expenses").font = Font(bold=True, color="2F5496"); row_num +=1
        for adj in report_data.get('add_back_adjustments', []): ws.cell(row=row_num, column=1, value=f"  {adj['name']}"); self._apply_excel_amount_style(ws.cell(row=row_num, column=2, value=float(adj['amount']))); row_num += 1
        ws.cell(row=row_num, column=1, value="Less: Non-Taxable Income").font = Font(bold=True, color="2F5496"); row_num +=1
        for adj in report_data.get('less_adjustments', []): ws.cell(row=row_num, column=1, value=f"  {adj['name']}"); self._apply_excel_amount_style(ws.cell(row=row_num, column=2, value=float(adj['amount']))); row_num += 1
        row_num += 1; ws.cell(row=row_num, column=1, value="Chargeable Income").font = Font(bold=True); self._apply_excel_amount_style(ws.cell(row=row_num, column=2, value=float(report_data.get('chargeable_income',0))), bold=True, underline="thin"); row_num += 2
        ws.cell(row=row_num, column=1, value=f"Estimated Tax @ {report_data.get('tax_rate', 0):.2f}%").font = Font(bold=True); self._apply_excel_amount_style(ws.cell(row=row_num, column=2, value=float(report_data.get('estimated_tax',0))), bold=True, underline="double");
        ws.column_dimensions[get_column_letter(1)].width = 60; ws.column_dimensions[get_column_letter(2)].width = 20
        excel_bytes_io = BytesIO(); wb.save(excel_bytes_io); return excel_bytes_io.getvalue()
        
    async def _export_gst_f5_details_to_excel(self, report_data: GSTReturnData) -> bytes:
        wb = openpyxl.Workbook()
        ws_summary = wb.active; ws_summary.title = "GST F5 Summary"; company_name = await self._get_company_name(); row_num = 1
        ws_summary.merge_cells(start_row=row_num, start_column=1, end_row=row_num, end_column=3); self._apply_excel_header_style(ws_summary.cell(row=row_num, column=1, value=company_name), size=14); row_num += 1
        ws_summary.merge_cells(start_row=row_num, start_column=1, end_row=row_num, end_column=3); self._apply_excel_header_style(ws_summary.cell(row=row_num, column=1, value="GST F5 Return"), size=12); row_num += 1
        ws_summary.merge_cells(start_row=row_num, start_column=1, end_row=row_num, end_column=3); date_desc = f"For period: {report_data.start_date.strftime('%d %b %Y')} to {report_data.end_date.strftime('%d %b %Y')}"; self._apply_excel_header_style(ws_summary.cell(row=row_num, column=1, value=date_desc), size=10, bold=False); row_num += 2
        f5_boxes = [("1. Standard-Rated Supplies", report_data.standard_rated_supplies),("2. Zero-Rated Supplies", report_data.zero_rated_supplies),("3. Exempt Supplies", report_data.exempt_supplies),("4. Total Supplies (1+2+3)", report_data.total_supplies, True),("5. Taxable Purchases", report_data.taxable_purchases),("6. Output Tax Due", report_data.output_tax),("7. Input Tax and Refunds Claimed", report_data.input_tax),("8. GST Adjustments (e.g. Bad Debt Relief)", report_data.tax_adjustments),("9. Net GST Payable / (Claimable)", report_data.tax_payable, True)]
        for desc, val, *is_bold in f5_boxes: ws_summary.cell(row=row_num, column=1, value=desc).font = Font(bold=bool(is_bold and is_bold[0])); self._apply_excel_amount_style(ws_summary.cell(row=row_num, column=2, value=float(val)), bold=bool(is_bold and is_bold[0])); row_num +=1
        ws_summary.column_dimensions['A'].width = 45; ws_summary.column_dimensions['B'].width = 20
        detail_headers = ["Date", "Doc No.", "Entity", "Description", "GL Code", "GL Name", "Net Amount", "GST Amount", "Tax Code"]
        box_map_to_detail_key = {"Box 1: Std Supplies": "box1_standard_rated_supplies","Box 2: Zero Supplies": "box2_zero_rated_supplies","Box 3: Exempt Supplies": "box3_exempt_supplies","Box 5: Taxable Purchases": "box5_taxable_purchases","Box 6: Output Tax": "box6_output_tax_details","Box 7: Input Tax": "box7_input_tax_details"}
        if report_data.detailed_breakdown:
            for sheet_title_prefix, detail_key in box_map_to_detail_key.items():
                transactions: List[GSTTransactionLineDetail] = report_data.detailed_breakdown.get(detail_key, [])
                if not transactions: continue
                ws_detail = wb.create_sheet(title=sheet_title_prefix[:30]); row_num_detail = 1
                for col, header_text in enumerate(detail_headers, 1): self._apply_excel_header_style(ws_detail.cell(row=row_num_detail, column=col, value=header_text), fill_color="4F81BD")
                row_num_detail +=1
                for txn in transactions:
                    ws_detail.cell(row=row_num_detail, column=1, value=txn.transaction_date.strftime('%d/%m/%Y') if txn.transaction_date else None); ws_detail.cell(row=row_num_detail, column=2, value=txn.document_no); ws_detail.cell(row=row_num_detail, column=3, value=txn.entity_name); ws_detail.cell(row=row_num_detail, column=4, value=txn.description); ws_detail.cell(row=row_num_detail, column=5, value=txn.account_code); ws_detail.cell(row=row_num_detail, column=6, value=txn.account_name); self._apply_excel_amount_style(ws_detail.cell(row=row_num_detail, column=7, value=float(txn.net_amount))); self._apply_excel_amount_style(ws_detail.cell(row=row_num_detail, column=8, value=float(txn.gst_amount))); ws_detail.cell(row=row_num_detail, column=9, value=txn.tax_code_applied); row_num_detail += 1
                for i, col_letter in enumerate([get_column_letter(j+1) for j in range(len(detail_headers))]):
                    if i in [0,1,8]: ws_detail.column_dimensions[col_letter].width = 15
                    elif i in [2,3,4,5]: ws_detail.column_dimensions[col_letter].width = 30
                    else: ws_detail.column_dimensions[col_letter].width = 18
        excel_bytes_io = BytesIO(); wb.save(excel_bytes_io); return excel_bytes_io.getvalue()
        
    def _export_generic_table_to_excel(self, report_data: Dict[str, Any]) -> bytes:
        self.app_core.logger.warning(f"Using generic Excel export for report: {report_data.get('title')}")
        wb = openpyxl.Workbook(); ws = wb.active; ws.title = report_data.get('title', "Report")[:30] # type: ignore
        row_num = 1; ws.cell(row=row_num, column=1, value=report_data.get('title')).font = Font(bold=True, size=14); row_num += 1 # type: ignore
        if report_data.get('report_date_description'): ws.cell(row=row_num, column=1, value=report_data.get('report_date_description')).font = Font(italic=True); row_num += 1 # type: ignore
        row_num += 1; headers = report_data.get('headers', []); data_rows = report_data.get('data_rows', []) 
        if headers:
            for col, header_text in enumerate(headers,1): self._apply_excel_header_style(ws.cell(row=row_num, column=col, value=header_text), fill_color="4F81BD")
            row_num +=1
        if data_rows:
            for data_item in data_rows:
                if isinstance(data_item, dict):
                    for col, header_text in enumerate(headers, 1): ws.cell(row=row_num, column=col, value=data_item.get(header_text, data_item.get(header_text.lower().replace(' ','_'))))
                elif isinstance(data_item, list):
                     for col, cell_val in enumerate(data_item, 1): ws.cell(row=row_num, column=col, value=cell_val)
                row_num +=1
        for col_idx_generic in range(1, len(headers) + 1): ws.column_dimensions[get_column_letter(col_idx_generic)].width = 20
        excel_bytes_io = BytesIO(); wb.save(excel_bytes_io); return excel_bytes_io.getvalue()

```

# app/reporting/dashboard_manager.py
```py
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

            # --- Ratio Calculations ---
            total_current_assets, total_current_liabilities, total_non_current_liabilities, total_inventory, total_equity = (Decimal(0) for _ in range(5))
            all_active_accounts: List[Account] = await self.app_core.account_service.get_all_active()

            for acc in all_active_accounts:
                balance = await self.app_core.journal_service.get_account_balance(acc.id, effective_date)
                if acc.account_type == "Asset":
                    if acc.sub_type in CURRENT_ASSET_SUBTYPES: total_current_assets += balance
                    if acc.sub_type == "Inventory": total_inventory += balance
                elif acc.account_type == "Liability":
                    if acc.sub_type in CURRENT_LIABILITY_SUBTYPES: total_current_liabilities += balance
                    elif acc.sub_type in NON_CURRENT_LIABILITY_SUBTYPES: total_non_current_liabilities += balance
                elif acc.account_type == "Equity": total_equity += balance

            total_liabilities = total_current_liabilities + total_non_current_liabilities
            
            quick_ratio: Optional[Decimal] = None
            if total_current_liabilities > 0: quick_ratio = ((total_current_assets - total_inventory) / total_current_liabilities).quantize(Decimal("0.01"))
            elif (total_current_assets - total_inventory) > 0: quick_ratio = Decimal('Infinity')

            debt_to_equity_ratio: Optional[Decimal] = None
            if total_equity > 0: debt_to_equity_ratio = (total_liabilities / total_equity).quantize(Decimal("0.01"))
            elif total_liabilities > 0: debt_to_equity_ratio = Decimal('Infinity')

            current_ratio: Optional[Decimal] = None
            if total_current_liabilities > 0: current_ratio = (total_current_assets / total_current_liabilities).quantize(Decimal("0.01"))
            elif total_current_assets > 0: current_ratio = Decimal('Infinity')

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

# app/reporting/tax_report_generator.py
```py
# File: app/reporting/tax_report_generator.py
from typing import TYPE_CHECKING # Added TYPE_CHECKING
from datetime import date 

# from app.core.application_core import ApplicationCore # Removed direct import

if TYPE_CHECKING:
    from app.core.application_core import ApplicationCore # For type hinting

class TaxReportGenerator:
    def __init__(self, app_core: "ApplicationCore"): # Use string literal for ApplicationCore
        self.app_core = app_core
        # Services would be accessed via self.app_core if needed, e.g., self.app_core.journal_service
        print("TaxReportGenerator initialized (stub).")

    async def generate_gst_audit_file(self, start_date: date, end_date: date):
        print(f"Generating GST Audit File for {start_date} to {end_date} (stub).")
        # Example access: company_name = (await self.app_core.company_settings_service.get_company_settings()).company_name
        return {"filename": "gst_audit.xlsx", "content_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "data": b"dummy_excel_data"}

    async def generate_income_tax_schedules(self, fiscal_year_id: int):
        print(f"Generating Income Tax Schedules for fiscal year ID {fiscal_year_id} (stub).")
        return {"schedule_name": "Capital Allowances", "data": []}

```

