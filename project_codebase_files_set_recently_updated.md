# app/main.py
```py
# File: app/main.py
import sys
import asyncio
import threading
from pathlib import Path
from typing import Optional, Any, List, Dict

from PySide6.QtWidgets import QApplication, QSplashScreen, QLabel, QMessageBox
from PySide6.QtCore import Qt, QSettings, QTimer, QCoreApplication, QMetaObject, Signal, Slot, Q_ARG, QProcess
from PySide6.QtGui import QPixmap, QColor 

# --- Globals for asyncio loop management ---
_ASYNC_LOOP: Optional[asyncio.AbstractEventLoop] = None
_ASYNC_LOOP_THREAD: Optional[threading.Thread] = None
_ASYNC_LOOP_STARTED = threading.Event() 

def start_asyncio_event_loop_thread():
    """Target function for the asyncio thread."""
    global _ASYNC_LOOP
    try:
        _ASYNC_LOOP = asyncio.new_event_loop()
        asyncio.set_event_loop(_ASYNC_LOOP)
        _ASYNC_LOOP_STARTED.set() 
        print(f"Asyncio event loop {_ASYNC_LOOP} started in thread {threading.current_thread().name} and set as current.")
        _ASYNC_LOOP.run_forever()
    except Exception as e:
        print(f"Critical error in asyncio event loop thread: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if _ASYNC_LOOP and _ASYNC_LOOP.is_running():
             pass 
        if _ASYNC_LOOP: 
             _ASYNC_LOOP.close()
        print("Asyncio event loop from dedicated thread has been stopped and closed.")

def schedule_task_from_qt(coro) -> Optional[asyncio.Future]:
    global _ASYNC_LOOP
    if _ASYNC_LOOP and _ASYNC_LOOP.is_running():
        return asyncio.run_coroutine_threadsafe(coro, _ASYNC_LOOP)
    else:
        print("Error: Global asyncio event loop is not available or not running when trying to schedule task.")
        return None
# --- End Globals for asyncio loop management ---

from app.ui.main_window import MainWindow
from app.core.application_core import ApplicationCore
from app.core.config_manager import ConfigManager
from app.core.database_manager import DatabaseManager

class Application(QApplication):
    initialization_done_signal = Signal(bool, object) 

    def __init__(self, argv):
        super().__init__(argv)
        self.setApplicationName("SGBookkeeper"); self.setApplicationVersion("1.0.0"); self.setOrganizationName("SGBookkeeperOrg"); self.setOrganizationDomain("sgbookkeeper.org") 
        
        splash_pixmap = None
        try: import app.resources_rc; splash_pixmap = QPixmap(":/images/splash.png")
        except ImportError:
            base_path = Path(__file__).resolve().parent.parent 
            splash_image_path = base_path / "resources" / "images" / "splash.png"
            if splash_image_path.exists(): splash_pixmap = QPixmap(str(splash_image_path))
            else: print(f"Warning: Splash image not found at {splash_image_path}.")

        if splash_pixmap is None or splash_pixmap.isNull():
            self.splash = QSplashScreen(); pm = QPixmap(400,200); pm.fill(Qt.GlobalColor.lightGray)
            self.splash.setPixmap(pm); self.splash.showMessage("Loading SG Bookkeeper...", Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignBottom, Qt.GlobalColor.black)
        else: self.splash = QSplashScreen(splash_pixmap, Qt.WindowType.WindowStaysOnTopHint); self.splash.setObjectName("SplashScreen")

        self.splash.show(); self.processEvents() 
        
        self.main_window: Optional[MainWindow] = None 
        self.app_core: Optional[ApplicationCore] = None

        self.initialization_done_signal.connect(self._on_initialization_done)
        
        future = schedule_task_from_qt(self.initialize_app())
        if future is None: self._on_initialization_done(False, RuntimeError("Failed to schedule app initialization (async loop not ready)."))
            
    @Slot(bool, object)
    def _on_initialization_done(self, success: bool, result_or_error: Any):
        if success:
            self.app_core = result_or_error 
            if not self.app_core: QMessageBox.critical(None, "Fatal Error", "App core not received on successful initialization."); self.quit(); return
            self.main_window = MainWindow(self.app_core); self.main_window.show(); self.splash.finish(self.main_window)
        else:
            self.splash.hide()
            error_message = str(result_or_error) if result_or_error else "An unknown error occurred during initialization."
            print(f"Critical error during application startup: {error_message}") 
            if isinstance(result_or_error, Exception) and result_or_error.__traceback__:
                import traceback; traceback.print_exception(type(result_or_error), result_or_error, result_or_error.__traceback__)
            # For the "No company database selected" error, we create a dummy core and let MainWindow handle it.
            if isinstance(result_or_error, ValueError) and "No company database selected" in str(result_or_error):
                config_manager = ConfigManager(app_name=QCoreApplication.applicationName())
                db_manager = DatabaseManager(config_manager) # Will have no DB name
                self.app_core = ApplicationCore(config_manager, db_manager, minimal_init=True)
                self.main_window = MainWindow(self.app_core); self.main_window.show()
            else:
                QMessageBox.critical(None, "Application Initialization Error", f"An error occurred during application startup:\n{error_message[:500]}\n\nThe application will now exit."); self.quit()

    async def initialize_app(self):
        current_app_core = None
        try:
            def update_splash_threadsafe(message):
                if hasattr(self, 'splash') and self.splash:
                    QMetaObject.invokeMethod(self.splash, "showMessage", Qt.ConnectionType.QueuedConnection, Q_ARG(str, message), Q_ARG(int, Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignCenter), Q_ARG(QColor, QColor(Qt.GlobalColor.white)))
            
            update_splash_threadsafe("Loading configuration...")
            config_manager = ConfigManager(app_name=QCoreApplication.applicationName())
            db_config = config_manager.get_database_config()
            if not db_config.database or db_config.database == "sg_bookkeeper_default":
                raise ValueError("No company database selected. Please select or create a company.")

            update_splash_threadsafe("Initializing database manager...")
            db_manager = DatabaseManager(config_manager)
            update_splash_threadsafe("Initializing application core...")
            current_app_core = ApplicationCore(config_manager, db_manager)
            await current_app_core.startup() 

            if not current_app_core.current_user: 
                authenticated_user = await current_app_core.security_manager.authenticate_user("admin", "password")
                if not authenticated_user: print("Default admin/password authentication failed or no such user. MainWindow should handle login.")

            update_splash_threadsafe("Finalizing initialization...")
            self.initialization_done_signal.emit(True, current_app_core) 
        except Exception as e:
            self.initialization_done_signal.emit(False, e) 

    def actual_shutdown_sequence(self): 
        print("Application shutting down (actual_shutdown_sequence)...")
        global _ASYNC_LOOP, _ASYNC_LOOP_THREAD
        
        if self.app_core:
            print("Scheduling ApplicationCore shutdown...")
            future = schedule_task_from_qt(self.app_core.shutdown())
            if future:
                try: future.result(timeout=2); print("ApplicationCore shutdown completed.")
                except TimeoutError: print("Warning: ApplicationCore async shutdown timed out.")
                except Exception as e: print(f"Error during ApplicationCore async shutdown via future: {e}")
            else: print("Warning: Could not schedule ApplicationCore async shutdown task.")
        
        if _ASYNC_LOOP and _ASYNC_LOOP.is_running():
            print("Requesting global asyncio event loop to stop..."); _ASYNC_LOOP.call_soon_threadsafe(_ASYNC_LOOP.stop)
        
        if _ASYNC_LOOP_THREAD and _ASYNC_LOOP_THREAD.is_alive():
            print("Joining asyncio event loop thread..."); _ASYNC_LOOP_THREAD.join(timeout=2)
            if _ASYNC_LOOP_THREAD.is_alive(): print("Warning: Asyncio event loop thread did not terminate cleanly.")
            else: print("Asyncio event loop thread joined.")
        
        print("Application shutdown process finalized.")

def main():
    global _ASYNC_LOOP_THREAD, _ASYNC_LOOP_STARTED, _ASYNC_LOOP
    print("Starting global asyncio event loop thread...")
    _ASYNC_LOOP_THREAD = threading.Thread(target=start_asyncio_event_loop_thread, daemon=True, name="AsyncioLoopThread")
    _ASYNC_LOOP_THREAD.start()
    if not _ASYNC_LOOP_STARTED.wait(timeout=5): 
        print("Fatal: Global asyncio event loop did not start in time. Exiting."); sys.exit(1)
    print(f"Global asyncio event loop {_ASYNC_LOOP} confirmed running in dedicated thread.")

    try: import app.resources_rc 
    except ImportError:
        print("Warning: Compiled Qt resources (resources_rc.py) not found. Direct file paths will be used for icons/images.")
        print("Consider running from project root: pyside6-rcc resources/resources.qrc -o app/resources_rc.py")

    app = Application(sys.argv)
    app.aboutToQuit.connect(app.actual_shutdown_sequence) 
    exit_code = app.exec()
    
    if _ASYNC_LOOP and _ASYNC_LOOP.is_running():
        print("Post app.exec(): Forcing asyncio loop stop (fallback)."); _ASYNC_LOOP.call_soon_threadsafe(_ASYNC_LOOP.stop)
    if _ASYNC_LOOP_THREAD and _ASYNC_LOOP_THREAD.is_alive():
        print("Post app.exec(): Joining asyncio thread (fallback)."); _ASYNC_LOOP_THREAD.join(timeout=1)
            
    sys.exit(exit_code)

if __name__ == "__main__":
    main()

```

# app/tax/income_tax_manager.py
```py
# File: app/tax/income_tax_manager.py
from typing import TYPE_CHECKING, Dict, Any

if TYPE_CHECKING:
    from app.core.application_core import ApplicationCore 
    from app.services.journal_service import JournalService 
    from app.services.account_service import AccountService
    from app.services.fiscal_period_service import FiscalPeriodService


class IncomeTaxManager:
    def __init__(self, app_core: "ApplicationCore"): 
        self.app_core = app_core
        self.account_service: "AccountService" = app_core.account_service
        self.journal_service: "JournalService" = app_core.journal_service
        self.fiscal_period_service: "FiscalPeriodService" = app_core.fiscal_period_service
        self.logger = app_core.logger
        self.logger.info("IncomeTaxManager initialized.")
    
    async def calculate_provisional_tax(self, fiscal_year_id: int) -> Dict[str, Any]:
        self.logger.info(f"Calculating provisional tax for fiscal year ID {fiscal_year_id} (stub).")
        # This would fetch the financial data for the ECI period,
        # apply rules (e.g., 75% of taxable income up to a cap is exempt), calculate tax,
        # and determine the provisional tax payable.
        return {"provisional_tax_payable": 0.00, "estimated_chargeable_income": 0.00}

    async def get_form_cs_data(self, fiscal_year_id: int) -> Dict[str, Any]:
        self.logger.info(f"Fetching data for Form C-S for fiscal year ID {fiscal_year_id} (stub).")
        # A real implementation would call the FinancialStatementGenerator, get the P&L and BS,
        # and populate a dictionary that maps directly to the fields on Form C-S.
        fy = await self.app_core.fiscal_year_service.get_by_id(fiscal_year_id)
        if not fy:
            return {"error": "Fiscal year not found."}
        
        report = await self.app_core.financial_statement_generator.generate_income_tax_computation(fy)
        
        company_settings = await self.app_core.company_settings_service.get_company_settings()
        
        return {
            "company_name": company_settings.company_name if company_settings else "N/A",
            "revenue": report.get('revenue', {}).get('total', 0.00),
            "profit_before_tax": report.get('net_profit_before_tax', 0.00),
            "chargeable_income": report.get('chargeable_income', 0.00)
        }

```

# app/tax/gst_manager.py
```py
# File: app/tax/gst_manager.py
from typing import Optional, Any, TYPE_CHECKING, List, Dict
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta 
from decimal import Decimal

from app.utils.result import Result
from app.utils.pydantic_models import GSTReturnData, JournalEntryData, JournalEntryLineData, GSTTransactionLineDetail
from app.models.accounting.gst_return import GSTReturn 
from app.models.accounting.journal_entry import JournalEntry, JournalEntryLine
from app.models.accounting.account import Account
from app.models.accounting.tax_code import TaxCode
from app.common.enums import GSTReturnStatusEnum 

if TYPE_CHECKING:
    from app.core.application_core import ApplicationCore 
    from app.services.journal_service import JournalService 
    from app.services.tax_service import TaxCodeService, GSTReturnService
    from app.services.account_service import AccountService
    from app.services.fiscal_period_service import FiscalPeriodService
    from app.services.core_services import CompanySettingsService, SequenceService


class GSTManager:
    def __init__(self, app_core: "ApplicationCore"): 
        self.app_core = app_core
        self.tax_code_service: "TaxCodeService" = app_core.tax_code_service
        self.journal_service: "JournalService" = app_core.journal_service
        self.company_settings_service: "CompanySettingsService" = app_core.company_settings_service
        self.gst_return_service: "GSTReturnService" = app_core.gst_return_service
        self.account_service: "AccountService" = app_core.account_service
        self.fiscal_period_service: "FiscalPeriodService" = app_core.fiscal_period_service
        self.sequence_service: "SequenceService" = app_core.sequence_service
        self.logger = app_core.logger

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
            self.app_core.logger.error(f"Failed to save GST return: {e}", exc_info=True)
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
            
            output_tax_acc = await self.account_service.get_by_code(gst_output_tax_acc_code)
            input_tax_acc = await self.account_service.get_by_code(gst_input_tax_acc_code)
            control_acc = await self.account_service.get_by_code(gst_control_acc_code) if gst_control_acc_code else None

            if not (output_tax_acc and input_tax_acc and control_acc):
                missing_accs = []
                if not output_tax_acc: missing_accs.append(str(gst_output_tax_acc_code))
                if not input_tax_acc: missing_accs.append(str(gst_input_tax_acc_code))
                if not control_acc: missing_accs.append(str(gst_control_acc_code))
                error_msg = f"Essential GST GL accounts not found: {', '.join(missing_accs)}. Cannot create settlement journal entry."
                self.app_core.logger.error(error_msg)
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
                        self.app_core.logger.warning(f"GST Settlement JE (ID: {je_result.value.id}) created but failed to auto-post: {post_result.errors}")
        try:
            updated_return = await self.gst_return_service.save_gst_return(gst_return)
            return Result.success(updated_return)
        except Exception as e:
            self.app_core.logger.error(f"Failed to save finalized GST return: {e}", exc_info=True)
            return Result.failure([f"Failed to save finalized GST return: {str(e)}"])

```

# app/tax/withholding_tax_manager.py
```py
# File: app/tax/withholding_tax_manager.py
from typing import TYPE_CHECKING, Dict, Any, Optional
from app.models.business.payment import Payment
from app.models.accounting.withholding_tax_certificate import WithholdingTaxCertificate
from app.utils.result import Result
from decimal import Decimal

if TYPE_CHECKING:
    from app.core.application_core import ApplicationCore 
    from app.services.journal_service import JournalService 
    from app.services.tax_service import TaxCodeService, WHTCertificateService
    from app.services.core_services import SequenceService

class WithholdingTaxManager:
    def __init__(self, app_core: "ApplicationCore"): 
        self.app_core = app_core
        self.tax_code_service: "TaxCodeService" = app_core.tax_code_service
        self.journal_service: "JournalService" = app_core.journal_service
        self.sequence_service: "SequenceService" = app_core.sequence_service
        self.logger = app_core.logger
        self.logger.info("WithholdingTaxManager initialized.")

    async def create_wht_certificate_from_payment(self, payment: Payment, user_id: int) -> Result[WithholdingTaxCertificate]:
        """
        Creates and saves a WithholdingTaxCertificate record based on a given vendor payment.
        """
        if not payment or not payment.vendor:
            return Result.failure(["Payment or associated vendor not provided."])
        
        if not payment.vendor.withholding_tax_applicable or payment.vendor.withholding_tax_rate is None:
            return Result.failure([f"Vendor '{payment.vendor.name}' is not marked for WHT."])
        
        async with self.app_core.db_manager.session() as session:
            # Check if a certificate for this payment already exists
            existing_cert = await session.get(WithholdingTaxCertificate, payment.id, options=[]) # Assuming 1-to-1 on payment.id
            if existing_cert:
                return Result.failure([f"A WHT Certificate ({existing_cert.certificate_no}) already exists for this payment (ID: {payment.id})."])

            form_data = await self.generate_s45_form_data(payment)
            if not form_data:
                return Result.failure(["Failed to generate S45 form data."])

            try:
                certificate_no = await self.sequence_service.get_next_sequence("wht_certificate")
                
                new_certificate = WithholdingTaxCertificate(
                    certificate_no=certificate_no,
                    vendor_id=payment.vendor_id,
                    payment_id=payment.id,
                    tax_rate=form_data["s45_wht_rate_percent"],
                    gross_payment_amount=form_data["s45_gross_payment"],
                    tax_amount=form_data["s45_wht_amount"],
                    payment_date=form_data["s45_payment_date"],
                    nature_of_payment=form_data["s45_nature_of_payment"],
                    status='Draft', # Always starts as Draft
                    created_by_user_id=user_id,
                    updated_by_user_id=user_id
                )
                session.add(new_certificate)
                await session.flush()
                await session.refresh(new_certificate)
                
                self.logger.info(f"Created WHT Certificate '{certificate_no}' for Payment ID {payment.id}.")
                return Result.success(new_certificate)

            except Exception as e:
                self.logger.error(f"Error creating WHT certificate for Payment ID {payment.id}: {e}", exc_info=True)
                return Result.failure([f"An unexpected error occurred: {str(e)}"])


    async def generate_s45_form_data(self, payment: Payment) -> Dict[str, Any]:
        """
        Generates a dictionary of data required for IRAS Form S45, based on a vendor payment.
        """
        self.logger.info(f"Generating S45 form data for Payment ID {payment.id}")
        
        if not payment or not payment.vendor:
            self.logger.error(f"Cannot generate S45 data: Payment {payment.id} or its vendor is not loaded.")
            return {}

        vendor = payment.vendor
        if not vendor.withholding_tax_applicable or vendor.withholding_tax_rate is None:
            self.logger.warning(f"S45 data requested for payment {payment.id}, but vendor '{vendor.name}' is not marked for WHT.")
            return {}
            
        wht_rate = vendor.withholding_tax_rate
        gross_payment_amount = payment.amount
        wht_amount = (gross_payment_amount * wht_rate) / 100

        company_settings = await self.app_core.company_settings_service.get_company_settings()
        payer_details = {
            "name": company_settings.company_name if company_settings else "N/A",
            "tax_ref_no": company_settings.uen_no if company_settings else "N/A",
        }

        nature_of_payment = f"Payment for services rendered by {vendor.name}"

        form_data = {
            "s45_payee_name": vendor.name,
            "s45_payee_address": f"{vendor.address_line1 or ''}, {vendor.address_line2 or ''}".strip(", "),
            "s45_payee_tax_ref": vendor.uen_no or "N/A",
            "s45_payer_name": payer_details["name"],
            "s45_payer_tax_ref": payer_details["tax_ref_no"],
            "s45_payment_date": payment.payment_date,
            "s45_nature_of_payment": nature_of_payment,
            "s45_gross_payment": gross_payment_amount,
            "s45_wht_rate_percent": wht_rate,
            "s45_wht_amount": wht_amount,
        }
        self.logger.info(f"S45 data generated for Payment ID {payment.id}: {form_data}")
        return form_data

    async def record_wht_payment(self, certificate_id: int, payment_date: str, reference: str):
        self.logger.info(f"Recording WHT payment for certificate {certificate_id} (stub).")
        return True

```

# app/tax/tax_calculator.py
```py
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

# app/ui/company/__init__.py
```py
# File: app/ui/company/__init__.py
from .company_manager_dialog import CompanyManagerDialog
from .company_creation_wizard import CompanyCreationWizard

__all__ = [
    "CompanyManagerDialog",
    "CompanyCreationWizard",
]


```

# app/ui/company/company_creation_wizard.py
```py
# File: app/ui/company/company_creation_wizard.py
from PySide6.QtWidgets import (
    QWizard, QWizardPage, QVBoxLayout, QFormLayout, QLineEdit, 
    QLabel, QCheckBox, QMessageBox
)
from typing import Optional, Dict

class CompanyCreationWizard(QWizard):
    """
    A multi-step wizard to guide the user through creating a new company.
    This provides a more structured and user-friendly experience than a single dialog.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.addPage(IntroPage())
        self.addPage(DetailsPage())
        self.addPage(FinalPage())
        self.setWindowTitle("New Company Setup Wizard")
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
        self.setMinimumSize(500, 400)


class IntroPage(QWizardPage):
    """The first page of the wizard, explaining the process."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Welcome to SG Bookkeeper Setup")
        self.setSubTitle("This wizard will guide you through creating a new company file.")
        
        layout = QVBoxLayout(self)
        label = QLabel(
            "A new, separate database will be created to store all data for this company, "
            "ensuring complete data isolation.\n\n"
            "You will need PostgreSQL administrator credentials configured in your `config.ini` "
            "file for the initial database creation."
        )
        label.setWordWrap(True)
        layout.addWidget(label)
        self.setLayout(layout)


class DetailsPage(QWizardPage):
    """The second page, for collecting company and database names."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Company Details")
        self.setSubTitle("Please provide the basic details for your new company.")
        
        layout = QFormLayout(self)
        
        self.company_name_edit = QLineEdit()
        self.company_name_edit.setPlaceholderText("e.g., My Awesome Bakery Pte. Ltd.")
        
        self.db_name_edit = QLineEdit()
        self.db_name_edit.setPlaceholderText("e.g., my_awesome_bakery")
        
        self.use_default_coa_check = QCheckBox("Load default Chart of Accounts and settings")
        self.use_default_coa_check.setChecked(True)
        
        # Register fields so the wizard can access their values
        self.registerField("companyName*", self.company_name_edit)
        self.registerField("dbName*", self.db_name_edit)
        self.registerField("useDefaultCoa", self.use_default_coa_check)
        
        layout.addRow("Company Display Name*:", self.company_name_edit)
        layout.addRow("Database Name*:", self.db_name_edit)
        
        hint_label = QLabel("Database name must be lowercase, with no spaces or special characters (underscores are allowed).")
        hint_label.setWordWrap(True)
        layout.addRow("", hint_label)
        
        layout.addRow(self.use_default_coa_check)
        
        self.setLayout(layout)
        
        self.company_name_edit.textChanged.connect(self.auto_populate_db_name)

    def auto_populate_db_name(self, text: str):
        """Suggests a valid database name based on the company name."""
        import re
        db_name_suggestion = text.lower()
        db_name_suggestion = re.sub(r'[^a-z0-9_]+', '_', db_name_suggestion)
        db_name_suggestion = re.sub(r'__+', '_', db_name_suggestion)
        db_name_suggestion = db_name_suggestion.strip('_')
        self.db_name_edit.setText("sgb_" + db_name_suggestion[:40])

    def validatePage(self) -> bool:
        """Validates the input fields before allowing the user to proceed."""
        import re
        if not self.field("companyName"):
            QMessageBox.warning(self, "Input Error", "Company Name cannot be empty.")
            return False
            
        db_name = self.field("dbName")
        if not db_name:
            QMessageBox.warning(self, "Input Error", "Database Name cannot be empty.")
            return False
            
        if not re.match(r'^[a-z_][a-z0-9_]*$', db_name):
            QMessageBox.warning(self, "Invalid Database Name", 
                "Database name must start with a lowercase letter or underscore, "
                "and contain only lowercase letters, numbers, and underscores.")
            return False
            
        return True


class FinalPage(QWizardPage):
    """The final confirmation page before creation."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Ready to Create")
        self.setSubTitle("Click 'Finish' to create the company file.")
        
        layout = QVBoxLayout(self)
        self.summary_label = QLabel()
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)
        self.setLayout(layout)

    def initializePage(self):
        """Called when this page is shown. Populates the summary label."""
        company_name = self.field("companyName")
        db_name = self.field("dbName")
        use_coa = "Yes" if self.field("useDefaultCoa") else "No"
        
        summary_text = (
            f"A new company will be created with the following details:\n\n"
            f"<b>Company Name:</b> {company_name}\n"
            f"<b>Database Name:</b> {db_name}\n"
            f"<b>Load Default Chart of Accounts:</b> {use_coa}\n\n"
            "This may take a moment. The application will restart to open the new company file upon successful creation."
        )
        self.summary_label.setText(summary_text)

```

# app/ui/main_window.py
```py
# File: app/ui/main_window.py
from PySide6.QtWidgets import (
    QMainWindow, QTabWidget, QToolBar, QStatusBar, 
    QVBoxLayout, QWidget, QMessageBox, QLabel, QProgressDialog, QDialog
)
from PySide6.QtGui import QIcon, QKeySequence, QAction 
from PySide6.QtCore import Qt, QSettings, Signal, Slot, QCoreApplication, QSize, QProcess, QTimer

from typing import Optional, Dict
import sys
import asyncio

from app.ui.dashboard.dashboard_widget import DashboardWidget
from app.ui.accounting.accounting_widget import AccountingWidget
from app.ui.sales_invoices.sales_invoices_widget import SalesInvoicesWidget
from app.ui.purchase_invoices.purchase_invoices_widget import PurchaseInvoicesWidget
from app.ui.payments.payments_widget import PaymentsWidget 
from app.ui.customers.customers_widget import CustomersWidget
from app.ui.vendors.vendors_widget import VendorsWidget
from app.ui.products.products_widget import ProductsWidget
from app.ui.banking.banking_widget import BankingWidget
from app.ui.banking.bank_reconciliation_widget import BankReconciliationWidget 
from app.ui.reports.reports_widget import ReportsWidget
from app.ui.settings.settings_widget import SettingsWidget
from app.core.application_core import ApplicationCore
from app.ui.company.company_manager_dialog import CompanyManagerDialog
from app.ui.company.company_creation_wizard import CompanyCreationWizard
from app.core.db_initializer import initialize_new_database, DBInitArgs
from app.main import schedule_task_from_qt

class MainWindow(QMainWindow):
    def __init__(self, app_core: ApplicationCore):
        super().__init__()
        self.app_core = app_core
        
        db_name = self.app_core.db_manager.config.database
        company_info = self.app_core.company_manager.get_company_by_db_name(db_name)
        company_display_name = company_info.get("display_name") if company_info else db_name

        self.setWindowTitle(f"{QCoreApplication.applicationName()} - {company_display_name}")
        self.setMinimumSize(1280, 800)
        
        self.icon_path_prefix = "resources/icons/" 
        try: import app.resources_rc; self.icon_path_prefix = ":/icons/"
        except ImportError: pass

        settings = QSettings(); 
        if settings.contains("MainWindow/geometry"): self.restoreGeometry(settings.value("MainWindow/geometry")) 
        else: self.resize(1366, 768)
        
        self._init_ui()
        if settings.contains("MainWindow/state"): self.restoreState(settings.value("MainWindow/state")) 

        db_config = self.app_core.config_manager.get_database_config()
        if not db_config.database or db_config.database == "sg_bookkeeper_default":
            QTimer.singleShot(100, self._prompt_for_company_selection)
    
    def _init_ui(self):
        self.central_widget = QWidget(); self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0); self.main_layout.setSpacing(0)
        self._create_toolbar(); self.tab_widget = QTabWidget(); self.tab_widget.setTabPosition(QTabWidget.TabPosition.North)
        self.tab_widget.setDocumentMode(True); self.tab_widget.setMovable(True)
        self.main_layout.addWidget(self.tab_widget); self._add_module_tabs()
        self._create_status_bar(); self._create_actions(); self._create_menus()
    
    def _create_toolbar(self):
        self.toolbar = QToolBar("Main Toolbar"); self.toolbar.setObjectName("MainToolbar") 
        self.toolbar.setMovable(False); self.toolbar.setIconSize(QSize(24, 24)) 
        self.toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.toolbar) 
    
    def _add_module_tabs(self):
        self.dashboard_widget = DashboardWidget(self.app_core); self.tab_widget.addTab(self.dashboard_widget, QIcon(self.icon_path_prefix + "dashboard.svg"), "Dashboard")
        self.accounting_widget = AccountingWidget(self.app_core); self.tab_widget.addTab(self.accounting_widget, QIcon(self.icon_path_prefix + "accounting.svg"), "Accounting")
        self.sales_invoices_widget = SalesInvoicesWidget(self.app_core); self.tab_widget.addTab(self.sales_invoices_widget, QIcon(self.icon_path_prefix + "transactions.svg"), "Sales") 
        self.purchase_invoices_widget = PurchaseInvoicesWidget(self.app_core); self.tab_widget.addTab(self.purchase_invoices_widget, QIcon(self.icon_path_prefix + "vendors.svg"), "Purchases") 
        self.payments_widget = PaymentsWidget(self.app_core); self.tab_widget.addTab(self.payments_widget, QIcon(self.icon_path_prefix + "banking.svg"), "Payments") 
        self.customers_widget = CustomersWidget(self.app_core); self.tab_widget.addTab(self.customers_widget, QIcon(self.icon_path_prefix + "customers.svg"), "Customers")
        self.vendors_widget = VendorsWidget(self.app_core); self.tab_widget.addTab(self.vendors_widget, QIcon(self.icon_path_prefix + "vendors.svg"), "Vendors")
        self.products_widget = ProductsWidget(self.app_core); self.tab_widget.addTab(self.products_widget, QIcon(self.icon_path_prefix + "product.svg"), "Products & Services")
        self.banking_widget = BankingWidget(self.app_core); self.tab_widget.addTab(self.banking_widget, QIcon(self.icon_path_prefix + "banking.svg"), "Banking (Transactions)") 
        self.bank_reconciliation_widget = BankReconciliationWidget(self.app_core); self.tab_widget.addTab(self.bank_reconciliation_widget, QIcon(self.icon_path_prefix + "transactions.svg"), "Bank Reconciliation") 
        self.reports_widget = ReportsWidget(self.app_core); self.tab_widget.addTab(self.reports_widget, QIcon(self.icon_path_prefix + "reports.svg"), "Reports")
        self.settings_widget = SettingsWidget(self.app_core); self.tab_widget.addTab(self.settings_widget, QIcon(self.icon_path_prefix + "settings.svg"), "Settings")
    
    def _create_status_bar(self):
        self.status_bar = QStatusBar(); self.setStatusBar(self.status_bar)
        self.status_label = QLabel("Ready"); self.status_bar.addWidget(self.status_label, 1) 
        user_text = "User: Guest"; 
        if self.app_core.current_user: user_text = f"User: {self.app_core.current_user.username}"
        self.user_label = QLabel(user_text); self.status_bar.addPermanentWidget(self.user_label)
        self.version_label = QLabel(f"Version: {QCoreApplication.applicationVersion()}"); self.status_bar.addPermanentWidget(self.version_label)

    def _create_actions(self):
        self.new_company_action = QAction(QIcon(self.icon_path_prefix + "new_company.svg"), "New Company...", self); self.new_company_action.triggered.connect(self.on_new_company)
        self.open_company_action = QAction(QIcon(self.icon_path_prefix + "open_company.svg"), "Open Company...", self); self.open_company_action.triggered.connect(self.on_open_company)
        self.backup_action = QAction(QIcon(self.icon_path_prefix + "backup.svg"), "Backup Data...", self); self.backup_action.triggered.connect(self.on_backup)
        self.restore_action = QAction(QIcon(self.icon_path_prefix + "restore.svg"), "Restore Data...", self); self.restore_action.triggered.connect(self.on_restore)
        self.exit_action = QAction(QIcon(self.icon_path_prefix + "exit.svg"), "Exit", self); self.exit_action.setShortcut(QKeySequence(QKeySequence.StandardKey.Quit)); self.exit_action.triggered.connect(self.close) 
        self.preferences_action = QAction(QIcon(self.icon_path_prefix + "preferences.svg"), "Preferences...", self); self.preferences_action.setShortcut(QKeySequence(QKeySequence.StandardKey.Preferences)); self.preferences_action.triggered.connect(self.on_preferences)
        self.help_contents_action = QAction(QIcon(self.icon_path_prefix + "help.svg"), "Help Contents", self); self.help_contents_action.setShortcut(QKeySequence(QKeySequence.StandardKey.HelpContents)); self.help_contents_action.triggered.connect(self.on_help_contents)
        self.about_action = QAction(QIcon(self.icon_path_prefix + "about.svg"), "About " + QCoreApplication.applicationName(), self); self.about_action.triggered.connect(self.on_about)

    def _create_menus(self):
        self.file_menu = self.menuBar().addMenu("&File"); self.file_menu.addAction(self.new_company_action); self.file_menu.addAction(self.open_company_action); self.file_menu.addSeparator(); self.file_menu.addAction(self.backup_action); self.file_menu.addAction(self.restore_action); self.file_menu.addSeparator(); self.file_menu.addAction(self.exit_action)
        self.edit_menu = self.menuBar().addMenu("&Edit"); self.edit_menu.addAction(self.preferences_action)
        self.view_menu = self.menuBar().addMenu("&View"); self.tools_menu = self.menuBar().addMenu("&Tools")
        self.help_menu = self.menuBar().addMenu("&Help"); self.help_menu.addAction(self.help_contents_action); self.help_menu.addSeparator(); self.help_menu.addAction(self.about_action)
        self.toolbar.addAction(self.new_company_action); self.toolbar.addAction(self.open_company_action); self.toolbar.addSeparator(); self.toolbar.addAction(self.backup_action); self.toolbar.addAction(self.preferences_action)

    def _prompt_for_company_selection(self):
        QMessageBox.information(self, "Welcome", "No company file is selected. Please create a new company or open an existing one.")
        self.on_open_company()
    
    @Slot()
    def on_new_company(self):
        self._handle_new_company_request()

    @Slot()
    def on_open_company(self):
        self._open_company_manager()
    
    def _open_company_manager(self):
        dialog = CompanyManagerDialog(self.app_core, self)
        result = dialog.exec()
        if result == CompanyManagerDialog.NewCompanyRequest:
            self._handle_new_company_request()
        elif result == CompanyManagerDialog.OpenCompanyRequest:
            selected_info = dialog.get_selected_company_info()
            if selected_info:
                self.switch_company_database(selected_info['database_name'])
    
    def _handle_new_company_request(self):
        wizard = CompanyCreationWizard(self)
        if wizard.exec() == QDialog.DialogCode.Accepted:
            company_details = {
                "display_name": wizard.field("companyName"),
                "database_name": wizard.field("dbName")
            }
            if company_details:
                self._create_new_company_db(company_details)

    def _create_new_company_db(self, company_details: Dict[str, str]):
        progress = QProgressDialog("Creating new company database...", "Cancel", 0, 0, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal); progress.setCancelButton(None)
        progress.show(); QApplication.processEvents()

        db_config = self.app_core.config_manager.get_database_config()
        db_args = DBInitArgs(user=db_config.username, password=db_config.password, host=db_config.host, port=db_config.port, dbname=company_details['database_name'], drop_existing=False)
        future = schedule_task_from_qt(initialize_new_database(db_args))
        if future: future.add_done_callback(lambda res: self._handle_db_creation_result(res, company_details))
        else: QMessageBox.critical(self, "Error", "Failed to schedule database creation task."); progress.close()

    def _handle_db_creation_result(self, future, company_details: Dict[str, str]):
        progress = self.findChild(QProgressDialog)
        if progress: progress.close()
        try:
            success = future.result()
            if success:
                self.app_core.company_manager.add_company(company_details)
                QMessageBox.information(self, "Success", f"Company '{company_details['display_name']}' created successfully.\nThe application will now restart to open it.")
                self.switch_company_database(company_details['database_name'])
            else: QMessageBox.critical(self, "Database Creation Failed", "Could not create the new company database. Please check the logs.")
        except Exception as e: QMessageBox.critical(self, "Error", f"An unexpected error occurred during database creation: {e}")

    def switch_company_database(self, db_name: str):
        self.app_core.config_manager.set_setting("Database", "database", db_name)
        QTimer.singleShot(100, self._restart_application)

    def _restart_application(self):
        app_instance = QApplication.instance()
        if app_instance:
            app_instance.quit()
        QProcess.startDetached(sys.executable, sys.argv)
    
    @Slot()
    def on_backup(self): QMessageBox.information(self, "Backup Data", "Backup functionality not yet implemented.")
    @Slot()
    def on_restore(self): QMessageBox.information(self, "Restore Data", "Restore functionality not yet implemented.")
    @Slot()
    def on_preferences(self): 
        settings_tab_index = -1;
        for i in range(self.tab_widget.count()):
            if self.tab_widget.widget(i) == self.settings_widget: settings_tab_index = i; break
        if settings_tab_index != -1: self.tab_widget.setCurrentIndex(settings_tab_index)
        else: QMessageBox.information(self, "Preferences", "Settings tab not found.")
    @Slot()
    def on_help_contents(self): QMessageBox.information(self, "Help", "Help system not yet implemented.")
    @Slot()
    def on_about(self): QMessageBox.about(self, f"About {QCoreApplication.applicationName()}", f"{QCoreApplication.applicationName()} {QCoreApplication.applicationVersion()}\n\nA comprehensive bookkeeping application for Singapore small businesses.\n\n© 2024 {QCoreApplication.organizationName()}"); 
    
    def closeEvent(self, event): 
        settings = QSettings(); settings.setValue("MainWindow/geometry", self.saveGeometry()); settings.setValue("MainWindow/state", self.saveState()); settings.sync()
        reply = QMessageBox.question(self, "Confirm Exit", "Are you sure you want to exit?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes: event.accept() 
        else: event.ignore()

```

# app/ui/reports/__init__.py
```py
# File: app/ui/reports/__init__.py
from .reports_widget import ReportsWidget
from .trial_balance_table_model import TrialBalanceTableModel
from .general_ledger_table_model import GeneralLedgerTableModel
from .wht_payment_table_model import WHTPaymentTableModel
from .wht_reporting_widget import WHTReportingWidget

__all__ = [
    "ReportsWidget",
    "TrialBalanceTableModel",
    "GeneralLedgerTableModel",
    "WHTPaymentTableModel",
    "WHTReportingWidget",
]

```

# app/ui/reports/reports_widget.py
```py
# File: app/ui/reports/reports_widget.py
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QDateEdit, QPushButton, QFormLayout, 
    QLineEdit, QGroupBox, QHBoxLayout, QMessageBox, QSpacerItem, QSizePolicy,
    QTabWidget, QTextEdit, QComboBox, QFileDialog, QInputDialog, QCompleter,
    QStackedWidget, QTreeView, QTableView, 
    QAbstractItemView, QCheckBox 
)
from PySide6.QtCore import Qt, Slot, QDate, QTimer, QMetaObject, Q_ARG, QStandardPaths
from PySide6.QtGui import QIcon, QStandardItemModel, QStandardItem, QFont, QColor
from typing import Optional, Dict, Any, TYPE_CHECKING, List 

import json
from decimal import Decimal, InvalidOperation
import os 
from datetime import date as python_date, timedelta 

from app.core.application_core import ApplicationCore
from app.main import schedule_task_from_qt
from app.utils.json_helpers import json_converter, json_date_hook
from app.utils.pydantic_models import GSTReturnData, GSTTransactionLineDetail, FiscalYearData 
from app.utils.result import Result 
from app.models.accounting.gst_return import GSTReturn 
from app.models.accounting.account import Account 
from app.models.accounting.dimension import Dimension 
from app.models.accounting.fiscal_year import FiscalYear

from .trial_balance_table_model import TrialBalanceTableModel
from .general_ledger_table_model import GeneralLedgerTableModel
from .wht_reporting_widget import WHTReportingWidget

if TYPE_CHECKING:
    from PySide6.QtGui import QPaintDevice 

class ReportsWidget(QWidget):
    def __init__(self, app_core: ApplicationCore, parent: Optional["QWidget"] = None):
        super().__init__(parent)
        self.app_core = app_core
        self._prepared_gst_data: Optional[GSTReturnData] = None 
        self._saved_draft_gst_return_orm: Optional[GSTReturn] = None 
        self._current_financial_report_data: Optional[Dict[str, Any]] = None
        self._gl_accounts_cache: List[Dict[str, Any]] = [] 
        self._dimension_types_cache: List[str] = []
        self._dimension_codes_cache: Dict[str, List[Dict[str, Any]]] = {} 
        self._fiscal_years_cache: List[FiscalYearData] = []

        self.icon_path_prefix = "resources/icons/" 
        try:
            import app.resources_rc 
            self.icon_path_prefix = ":/icons/"
        except ImportError:
            pass

        self.main_layout = QVBoxLayout(self)
        
        self.tab_widget = QTabWidget()
        self.main_layout.addWidget(self.tab_widget)

        self._create_financial_statements_tab()
        self._create_gst_f5_tab()
        self._create_wht_reporting_tab()
        
        self.setLayout(self.main_layout)
        QTimer.singleShot(0, lambda: schedule_task_from_qt(self._load_fs_combo_data()))

    def _format_decimal_for_display(self, value: Optional[Decimal], default_str: str = "0.00", show_blank_for_zero: bool = False) -> str:
        if value is None: return default_str if not show_blank_for_zero else ""
        try:
            d_value = Decimal(str(value)); 
            if show_blank_for_zero and d_value.is_zero(): return ""
            return f"{d_value:,.2f}"
        except (InvalidOperation, TypeError): return "Error" 

    def _create_gst_f5_tab(self):
        gst_f5_widget = QWidget(); gst_f5_main_layout = QVBoxLayout(gst_f5_widget); gst_f5_group = QGroupBox("GST F5 Return Data Preparation"); gst_f5_group_layout = QVBoxLayout(gst_f5_group) 
        date_selection_layout = QHBoxLayout(); date_form = QFormLayout()
        self.gst_start_date_edit = QDateEdit(QDate.currentDate().addMonths(-3).addDays(-QDate.currentDate().day()+1)); self.gst_start_date_edit.setCalendarPopup(True); self.gst_start_date_edit.setDisplayFormat("dd/MM/yyyy"); date_form.addRow("Period Start Date:", self.gst_start_date_edit)
        self.gst_end_date_edit = QDateEdit(QDate.currentDate().addDays(-QDate.currentDate().day())); 
        if self.gst_end_date_edit.date() < self.gst_start_date_edit.date(): self.gst_end_date_edit.setDate(self.gst_start_date_edit.date().addMonths(1).addDays(-1))
        self.gst_end_date_edit.setCalendarPopup(True); self.gst_end_date_edit.setDisplayFormat("dd/MM/yyyy"); date_form.addRow("Period End Date:", self.gst_end_date_edit)
        date_selection_layout.addLayout(date_form); prepare_button_layout = QVBoxLayout()
        self.prepare_gst_button = QPushButton(QIcon(self.icon_path_prefix + "reports.svg"), "Prepare GST F5 Data"); self.prepare_gst_button.clicked.connect(self._on_prepare_gst_f5_clicked)
        prepare_button_layout.addWidget(self.prepare_gst_button); prepare_button_layout.addStretch(); date_selection_layout.addLayout(prepare_button_layout); date_selection_layout.addStretch(1); gst_f5_group_layout.addLayout(date_selection_layout)
        self.gst_display_form = QFormLayout(); self.gst_std_rated_supplies_display = QLineEdit(); self.gst_std_rated_supplies_display.setReadOnly(True); self.gst_zero_rated_supplies_display = QLineEdit(); self.gst_zero_rated_supplies_display.setReadOnly(True); self.gst_exempt_supplies_display = QLineEdit(); self.gst_exempt_supplies_display.setReadOnly(True); self.gst_total_supplies_display = QLineEdit(); self.gst_total_supplies_display.setReadOnly(True); self.gst_total_supplies_display.setStyleSheet("font-weight: bold;"); self.gst_taxable_purchases_display = QLineEdit(); self.gst_taxable_purchases_display.setReadOnly(True); self.gst_output_tax_display = QLineEdit(); self.gst_output_tax_display.setReadOnly(True); self.gst_input_tax_display = QLineEdit(); self.gst_input_tax_display.setReadOnly(True); self.gst_adjustments_display = QLineEdit("0.00"); self.gst_adjustments_display.setReadOnly(True); self.gst_net_payable_display = QLineEdit(); self.gst_net_payable_display.setReadOnly(True); self.gst_net_payable_display.setStyleSheet("font-weight: bold;"); self.gst_filing_due_date_display = QLineEdit(); self.gst_filing_due_date_display.setReadOnly(True)
        self.gst_display_form.addRow("1. Standard-Rated Supplies:", self.gst_std_rated_supplies_display); self.gst_display_form.addRow("2. Zero-Rated Supplies:", self.gst_zero_rated_supplies_display); self.gst_display_form.addRow("3. Exempt Supplies:", self.gst_exempt_supplies_display); self.gst_display_form.addRow("4. Total Supplies (1+2+3):", self.gst_total_supplies_display); self.gst_display_form.addRow("5. Taxable Purchases:", self.gst_taxable_purchases_display); self.gst_display_form.addRow("6. Output Tax Due:", self.gst_output_tax_display); self.gst_display_form.addRow("7. Input Tax and Refunds Claimed:", self.gst_input_tax_display); self.gst_display_form.addRow("8. GST Adjustments:", self.gst_adjustments_display); self.gst_display_form.addRow("9. Net GST Payable / (Claimable):", self.gst_net_payable_display); self.gst_display_form.addRow("Filing Due Date:", self.gst_filing_due_date_display)
        gst_f5_group_layout.addLayout(self.gst_display_form)
        
        gst_action_button_layout = QHBoxLayout()
        self.save_draft_gst_button = QPushButton("Save Draft GST Return"); self.save_draft_gst_button.setEnabled(False); self.save_draft_gst_button.clicked.connect(self._on_save_draft_gst_return_clicked)
        self.finalize_gst_button = QPushButton("Finalize GST Return"); self.finalize_gst_button.setEnabled(False); self.finalize_gst_button.clicked.connect(self._on_finalize_gst_return_clicked)
        
        self.export_gst_detail_excel_button = QPushButton("Export Details (Excel)"); self.export_gst_detail_excel_button.setEnabled(False)
        self.export_gst_detail_excel_button.clicked.connect(self._on_export_gst_f5_details_excel_clicked)

        gst_action_button_layout.addStretch()
        gst_action_button_layout.addWidget(self.export_gst_detail_excel_button); gst_action_button_layout.addWidget(self.save_draft_gst_button); gst_action_button_layout.addWidget(self.finalize_gst_button)
        gst_f5_group_layout.addLayout(gst_action_button_layout)

        gst_f5_main_layout.addWidget(gst_f5_group); gst_f5_main_layout.addStretch(); self.tab_widget.addTab(gst_f5_widget, "GST F5 Preparation")

    def _create_wht_reporting_tab(self):
        """Creates the new Withholding Tax reporting tab."""
        self.wht_reporting_widget = WHTReportingWidget(self.app_core)
        self.tab_widget.addTab(self.wht_reporting_widget, "Withholding Tax")
        
    @Slot()
    def _on_prepare_gst_f5_clicked(self):
        start_date = self.gst_start_date_edit.date().toPython(); end_date = self.gst_end_date_edit.date().toPython()
        if start_date > end_date: QMessageBox.warning(self, "Date Error", "Start date cannot be after end date."); return
        if not self.app_core.current_user: QMessageBox.warning(self, "Authentication Error", "No user logged in."); return
        if not self.app_core.gst_manager: QMessageBox.critical(self, "Error", "GST Manager not available."); return
        self.prepare_gst_button.setEnabled(False); self.prepare_gst_button.setText("Preparing...")
        self._saved_draft_gst_return_orm = None; self.finalize_gst_button.setEnabled(False); self.export_gst_detail_excel_button.setEnabled(False) 
        future = schedule_task_from_qt(self.app_core.gst_manager.prepare_gst_return_data(start_date, end_date, self.app_core.current_user.id))
        if future: future.add_done_callback(lambda res: QMetaObject.invokeMethod(self, "_safe_handle_prepare_gst_f5_result_slot", Qt.ConnectionType.QueuedConnection, Q_ARG(object, future)))
        else: self.app_core.logger.error("Failed to schedule GST data preparation task."); self._handle_prepare_gst_f5_result(None) 

    @Slot(object)
    def _safe_handle_prepare_gst_f5_result_slot(self, future_arg):
        self._handle_prepare_gst_f5_result(future_arg)

    def _handle_prepare_gst_f5_result(self, future):
        self.prepare_gst_button.setEnabled(True); self.prepare_gst_button.setText("Prepare GST F5 Data"); self.export_gst_detail_excel_button.setEnabled(False) 
        if future is None: QMessageBox.critical(self, "Task Error", "Failed to schedule GST data preparation."); self._clear_gst_display_fields(); self.save_draft_gst_button.setEnabled(False); self.finalize_gst_button.setEnabled(False); return
        try:
            result: Result[GSTReturnData] = future.result()
            if result.is_success and result.value: 
                self._prepared_gst_data = result.value; self._update_gst_f5_display(self._prepared_gst_data)
                self.save_draft_gst_button.setEnabled(True); self.finalize_gst_button.setEnabled(False) 
                if self._prepared_gst_data and self._prepared_gst_data.detailed_breakdown: self.export_gst_detail_excel_button.setEnabled(True)
            else: self._clear_gst_display_fields(); self.save_draft_gst_button.setEnabled(False); self.finalize_gst_button.setEnabled(False); QMessageBox.warning(self, "GST Data Error", f"Failed to prepare GST data:\n{', '.join(result.errors)}")
        except Exception as e: self._clear_gst_display_fields(); self.save_draft_gst_button.setEnabled(False); self.finalize_gst_button.setEnabled(False); self.app_core.logger.error(f"Exception handling GST F5 preparation result: {e}", exc_info=True); QMessageBox.critical(self, "GST Data Error", f"An unexpected error occurred: {str(e)}")

    def _update_gst_f5_display(self, gst_data: GSTReturnData):
        self.gst_std_rated_supplies_display.setText(self._format_decimal_for_display(gst_data.standard_rated_supplies)); self.gst_zero_rated_supplies_display.setText(self._format_decimal_for_display(gst_data.zero_rated_supplies)); self.gst_exempt_supplies_display.setText(self._format_decimal_for_display(gst_data.exempt_supplies)); self.gst_total_supplies_display.setText(self._format_decimal_for_display(gst_data.total_supplies)); self.gst_taxable_purchases_display.setText(self._format_decimal_for_display(gst_data.taxable_purchases)); self.gst_output_tax_display.setText(self._format_decimal_for_display(gst_data.output_tax)); self.gst_input_tax_display.setText(self._format_decimal_for_display(gst_data.input_tax)); self.gst_adjustments_display.setText(self._format_decimal_for_display(gst_data.tax_adjustments)); self.gst_net_payable_display.setText(self._format_decimal_for_display(gst_data.tax_payable)); self.gst_filing_due_date_display.setText(gst_data.filing_due_date.strftime('%d/%m/%Y') if gst_data.filing_due_date else "")
    
    def _clear_gst_display_fields(self):
        for w in [self.gst_std_rated_supplies_display, self.gst_zero_rated_supplies_display, self.gst_exempt_supplies_display, self.gst_total_supplies_display, self.gst_taxable_purchases_display, self.gst_output_tax_display, self.gst_input_tax_display, self.gst_net_payable_display, self.gst_filing_due_date_display]: w.clear()
        self.gst_adjustments_display.setText("0.00"); self._prepared_gst_data = None; self._saved_draft_gst_return_orm = None; self.export_gst_detail_excel_button.setEnabled(False) 
    
    @Slot()
    def _on_save_draft_gst_return_clicked(self):
        if not self._prepared_gst_data: QMessageBox.warning(self, "No Data", "Please prepare GST data first."); return
        if not self.app_core.current_user: QMessageBox.warning(self, "Authentication Error", "No user logged in."); return
        self._prepared_gst_data.user_id = self.app_core.current_user.id
        if self._saved_draft_gst_return_orm and self._saved_draft_gst_return_orm.id: self._prepared_gst_data.id = self._saved_draft_gst_return_orm.id
        self.save_draft_gst_button.setEnabled(False); self.save_draft_gst_button.setText("Saving Draft..."); self.finalize_gst_button.setEnabled(False)
        future = schedule_task_from_qt(self.app_core.gst_manager.save_gst_return(self._prepared_gst_data))
        if future: future.add_done_callback(lambda res: QMetaObject.invokeMethod(self, "_safe_handle_save_draft_gst_result_slot", Qt.ConnectionType.QueuedConnection, Q_ARG(object, future)))
        else: self.app_core.logger.error("Failed to schedule GST draft save task."); self._handle_save_draft_gst_result(None)

    @Slot(object)
    def _safe_handle_save_draft_gst_result_slot(self, future_arg):
        self._handle_save_draft_gst_result(future_arg)

    def _handle_save_draft_gst_result(self, future):
        self.save_draft_gst_button.setEnabled(True); self.save_draft_gst_button.setText("Save Draft GST Return")
        if future is None: QMessageBox.critical(self, "Task Error", "Failed to schedule GST draft save."); return
        try:
            result: Result[GSTReturn] = future.result()
            if result.is_success and result.value: 
                self._saved_draft_gst_return_orm = result.value
                if self._prepared_gst_data: self._prepared_gst_data.id = result.value.id 
                QMessageBox.information(self, "Success", f"GST Return draft saved successfully (ID: {result.value.id})."); self.finalize_gst_button.setEnabled(True); self.export_gst_detail_excel_button.setEnabled(bool(self._prepared_gst_data and self._prepared_gst_data.detailed_breakdown))
            else: QMessageBox.warning(self, "Save Error", f"Failed to save GST Return draft:\n{', '.join(result.errors)}"); self.finalize_gst_button.setEnabled(False)
        except Exception as e: self.app_core.logger.error(f"Exception handling save draft GST result: {e}", exc_info=True); QMessageBox.critical(self, "Save Error", f"An unexpected error occurred: {str(e)}"); self.finalize_gst_button.setEnabled(False)

    @Slot()
    def _on_finalize_gst_return_clicked(self):
        if not self._saved_draft_gst_return_orm or not self._saved_draft_gst_return_orm.id: QMessageBox.warning(self, "No Draft", "Please prepare and save a draft GST return first."); return
        if self._saved_draft_gst_return_orm.status != "Draft": QMessageBox.information(self, "Already Processed", f"This GST Return (ID: {self._saved_draft_gst_return_orm.id}) is already '{self._saved_draft_gst_return_orm.status}'."); return
        if not self.app_core.current_user: QMessageBox.warning(self, "Authentication Error", "No user logged in."); return
        submission_ref, ok_ref = QInputDialog.getText(self, "Finalize GST Return", "Enter Submission Reference No.:")
        if not ok_ref or not submission_ref.strip(): QMessageBox.information(self, "Cancelled", "Submission reference not provided. Finalization cancelled."); return
        submission_date_str, ok_date = QInputDialog.getText(self, "Finalize GST Return", "Enter Submission Date (YYYY-MM-DD):", text=python_date.today().isoformat())
        if not ok_date or not submission_date_str.strip(): QMessageBox.information(self, "Cancelled", "Submission date not provided. Finalization cancelled."); return
        try: parsed_submission_date = python_date.fromisoformat(submission_date_str)
        except ValueError: QMessageBox.warning(self, "Invalid Date", "Submission date format is invalid. Please use YYYY-MM-DD."); return
        self.finalize_gst_button.setEnabled(False); self.finalize_gst_button.setText("Finalizing..."); self.save_draft_gst_button.setEnabled(False); self.export_gst_detail_excel_button.setEnabled(False)
        future = schedule_task_from_qt(self.app_core.gst_manager.finalize_gst_return(return_id=self._saved_draft_gst_return_orm.id, submission_reference=submission_ref.strip(), submission_date=parsed_submission_date, user_id=self.app_core.current_user.id))
        if future: future.add_done_callback(lambda res: QMetaObject.invokeMethod(self, "_safe_handle_finalize_gst_result_slot", Qt.ConnectionType.QueuedConnection, Q_ARG(object, future)))
        else: self.app_core.logger.error("Failed to schedule GST finalization task."); self._handle_finalize_gst_result(None)

    @Slot(object)
    def _safe_handle_finalize_gst_result_slot(self, future_arg):
        self._handle_finalize_gst_result(future_arg)

    def _handle_finalize_gst_result(self, future): 
        self.finalize_gst_button.setText("Finalize GST Return"); can_finalize_default = self._saved_draft_gst_return_orm and self._saved_draft_gst_return_orm.status == "Draft"; can_save_draft_default = self._prepared_gst_data is not None and (not self._saved_draft_gst_return_orm or self._saved_draft_gst_return_orm.status == "Draft"); can_export_detail_default = bool(self._prepared_gst_data and self._prepared_gst_data.detailed_breakdown)
        if future is None: QMessageBox.critical(self, "Task Error", "Failed to schedule GST finalization."); self.finalize_gst_button.setEnabled(can_finalize_default); self.save_draft_gst_button.setEnabled(can_save_draft_default); self.export_gst_detail_excel_button.setEnabled(can_export_detail_default); return
        try:
            result: Result[GSTReturn] = future.result()
            if result.is_success and result.value: 
                QMessageBox.information(self, "Success", f"GST Return (ID: {result.value.id}) finalized successfully.\nStatus: {result.value.status}.\nSettlement JE ID: {result.value.journal_entry_id or 'N/A'}"); self._saved_draft_gst_return_orm = result.value; self.save_draft_gst_button.setEnabled(False); self.finalize_gst_button.setEnabled(False); self.export_gst_detail_excel_button.setEnabled(can_export_detail_default) 
                if self._prepared_gst_data: self._prepared_gst_data.status = result.value.status
            else: QMessageBox.warning(self, "Finalization Error", f"Failed to finalize GST Return:\n{', '.join(result.errors)}"); self.finalize_gst_button.setEnabled(can_finalize_default); self.save_draft_gst_button.setEnabled(can_save_draft_default); self.export_gst_detail_excel_button.setEnabled(can_export_detail_default)
        except Exception as e: self.app_core.logger.error(f"Exception handling finalize GST result: {e}", exc_info=True); QMessageBox.critical(self, "Finalization Error", f"An unexpected error occurred: {str(e)}"); self.finalize_gst_button.setEnabled(can_finalize_default); self.save_draft_gst_button.setEnabled(can_save_draft_default); self.export_gst_detail_excel_button.setEnabled(can_export_detail_default)

    @Slot()
    def _on_export_gst_f5_details_excel_clicked(self):
        if not self._prepared_gst_data or not self._prepared_gst_data.detailed_breakdown: QMessageBox.warning(self, "No Data", "Please prepare GST data with details first."); return
        default_filename = f"GST_F5_Details_{self._prepared_gst_data.start_date.strftime('%Y%m%d')}_{self._prepared_gst_data.end_date.strftime('%Y%m%d')}.xlsx"; documents_path = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
        file_path, _ = QFileDialog.getSaveFileName(self, "Save GST F5 Detail Report (Excel)", os.path.join(documents_path, default_filename), "Excel Files (*.xlsx);;All Files (*)")
        if file_path: 
            self.export_gst_detail_excel_button.setEnabled(False)
            future = schedule_task_from_qt(self.app_core.report_engine.export_report(self._prepared_gst_data, "gst_excel_detail"))
            if future: future.add_done_callback(lambda res, fp=file_path: QMetaObject.invokeMethod(self, "_safe_handle_gst_detail_export_result_slot", Qt.ConnectionType.QueuedConnection, Q_ARG(object, future), Q_ARG(str, fp)))
            else: self.app_core.logger.error("Failed to schedule GST detail export task."); self.export_gst_detail_excel_button.setEnabled(True) 

    @Slot(object, str)
    def _safe_handle_gst_detail_export_result_slot(self, future_arg, file_path_arg: str):
        self._handle_gst_detail_export_result(future_arg, file_path_arg)

    def _handle_gst_detail_export_result(self, future, file_path: str):
        self.export_gst_detail_excel_button.setEnabled(True) 
        if future is None: QMessageBox.critical(self, "Task Error", "Failed to schedule GST detail export."); return
        try:
            report_bytes: Optional[bytes] = future.result()
            if report_bytes:
                with open(file_path, "wb") as f: f.write(report_bytes)
                QMessageBox.information(self, "Export Successful", f"GST F5 Detail Report exported to:\n{file_path}")
            else: QMessageBox.warning(self, "Export Failed", "Failed to generate GST F5 Detail report bytes.")
        except Exception as e: self.app_core.logger.error(f"Exception handling GST detail export result: {e}", exc_info=True); QMessageBox.critical(self, "Export Error", f"An error occurred during GST detail export: {str(e)}")
    
    def _create_financial_statements_tab(self):
        fs_widget = QWidget(); fs_main_layout = QVBoxLayout(fs_widget); fs_group = QGroupBox("Financial Statements"); fs_group_layout = QVBoxLayout(fs_group) 
        controls_layout = QHBoxLayout(); self.fs_params_form = QFormLayout() 
        self.fs_report_type_combo = QComboBox(); self.fs_report_type_combo.addItems(["Balance Sheet", "Profit & Loss Statement", "Trial Balance", "General Ledger", "Income Tax Computation"]); self.fs_params_form.addRow("Report Type:", self.fs_report_type_combo)
        self.fs_fiscal_year_label = QLabel("Fiscal Year:"); self.fs_fiscal_year_combo = QComboBox(); self.fs_fiscal_year_combo.setMinimumWidth(200); self.fs_params_form.addRow(self.fs_fiscal_year_label, self.fs_fiscal_year_combo)
        self.fs_gl_account_label = QLabel("Account for GL:"); self.fs_gl_account_combo = QComboBox(); self.fs_gl_account_combo.setMinimumWidth(250); self.fs_gl_account_combo.setEditable(True)
        completer = QCompleter([f"{item.get('code')} - {item.get('name')}" for item in self._gl_accounts_cache]); completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion); completer.setFilterMode(Qt.MatchFlag.MatchContains); self.fs_gl_account_combo.setCompleter(completer); self.fs_params_form.addRow(self.fs_gl_account_label, self.fs_gl_account_combo)
        self.fs_as_of_date_edit = QDateEdit(QDate.currentDate()); self.fs_as_of_date_edit.setCalendarPopup(True); self.fs_as_of_date_edit.setDisplayFormat("dd/MM/yyyy"); self.fs_params_form.addRow("As of Date:", self.fs_as_of_date_edit)
        self.fs_start_date_edit = QDateEdit(QDate.currentDate().addMonths(-1).addDays(-QDate.currentDate().day()+1)); self.fs_start_date_edit.setCalendarPopup(True); self.fs_start_date_edit.setDisplayFormat("dd/MM/yyyy"); self.fs_params_form.addRow("Period Start Date:", self.fs_start_date_edit)
        self.fs_end_date_edit = QDateEdit(QDate.currentDate().addDays(-QDate.currentDate().day())); self.fs_end_date_edit.setCalendarPopup(True); self.fs_end_date_edit.setDisplayFormat("dd/MM/yyyy"); self.fs_params_form.addRow("Period End Date:", self.fs_end_date_edit)
        self.fs_include_zero_balance_check = QCheckBox("Include Zero-Balance Accounts"); self.fs_params_form.addRow(self.fs_include_zero_balance_check) 
        self.fs_include_comparative_check = QCheckBox("Include Comparative Period"); self.fs_params_form.addRow(self.fs_include_comparative_check)
        self.fs_comparative_as_of_date_label = QLabel("Comparative As of Date:"); self.fs_comparative_as_of_date_edit = QDateEdit(QDate.currentDate().addYears(-1)); self.fs_comparative_as_of_date_edit.setCalendarPopup(True); self.fs_comparative_as_of_date_edit.setDisplayFormat("dd/MM/yyyy"); self.fs_params_form.addRow(self.fs_comparative_as_of_date_label, self.fs_comparative_as_of_date_edit)
        self.fs_comparative_start_date_label = QLabel("Comparative Start Date:"); self.fs_comparative_start_date_edit = QDateEdit(QDate.currentDate().addYears(-1).addMonths(-1).addDays(-QDate.currentDate().day()+1)); self.fs_comparative_start_date_edit.setCalendarPopup(True); self.fs_comparative_start_date_edit.setDisplayFormat("dd/MM/yyyy"); self.fs_params_form.addRow(self.fs_comparative_start_date_label, self.fs_comparative_start_date_edit)
        self.fs_comparative_end_date_label = QLabel("Comparative End Date:"); self.fs_comparative_end_date_edit = QDateEdit(QDate.currentDate().addYears(-1).addDays(-QDate.currentDate().day())); self.fs_comparative_end_date_edit.setCalendarPopup(True); self.fs_comparative_end_date_edit.setDisplayFormat("dd/MM/yyyy"); self.fs_params_form.addRow(self.fs_comparative_end_date_label, self.fs_comparative_end_date_edit)
        self.fs_dim1_type_label = QLabel("Dimension 1 Type:"); self.fs_dim1_type_combo = QComboBox(); self.fs_dim1_type_combo.addItem("All Types", None); self.fs_dim1_type_combo.setObjectName("fs_dim1_type_combo"); self.fs_params_form.addRow(self.fs_dim1_type_label, self.fs_dim1_type_combo)
        self.fs_dim1_code_label = QLabel("Dimension 1 Code:"); self.fs_dim1_code_combo = QComboBox(); self.fs_dim1_code_combo.addItem("All Codes", None); self.fs_dim1_code_combo.setObjectName("fs_dim1_code_combo"); self.fs_params_form.addRow(self.fs_dim1_code_label, self.fs_dim1_code_combo)
        self.fs_dim2_type_label = QLabel("Dimension 2 Type:"); self.fs_dim2_type_combo = QComboBox(); self.fs_dim2_type_combo.addItem("All Types", None); self.fs_dim2_type_combo.setObjectName("fs_dim2_type_combo"); self.fs_params_form.addRow(self.fs_dim2_type_label, self.fs_dim2_type_combo)
        self.fs_dim2_code_label = QLabel("Dimension 2 Code:"); self.fs_dim2_code_combo = QComboBox(); self.fs_dim2_code_combo.addItem("All Codes", None); self.fs_dim2_code_combo.setObjectName("fs_dim2_code_combo"); self.fs_params_form.addRow(self.fs_dim2_code_label, self.fs_dim2_code_combo)
        controls_layout.addLayout(self.fs_params_form)
        generate_fs_button_layout = QVBoxLayout(); self.generate_fs_button = QPushButton(QIcon(self.icon_path_prefix + "reports.svg"), "Generate Report"); self.generate_fs_button.clicked.connect(self._on_generate_financial_report_clicked)
        generate_fs_button_layout.addWidget(self.generate_fs_button); generate_fs_button_layout.addStretch(); controls_layout.addLayout(generate_fs_button_layout); controls_layout.addStretch(1); fs_group_layout.addLayout(controls_layout)
        self.fs_display_stack = QStackedWidget(); fs_group_layout.addWidget(self.fs_display_stack, 1)
        self.bs_tree_view = QTreeView(); self.bs_tree_view.setAlternatingRowColors(True); self.bs_tree_view.setHeaderHidden(False); self.bs_tree_view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers); self.bs_model = QStandardItemModel(); self.bs_tree_view.setModel(self.bs_model); self.fs_display_stack.addWidget(self.bs_tree_view)
        self.pl_tree_view = QTreeView(); self.pl_tree_view.setAlternatingRowColors(True); self.pl_tree_view.setHeaderHidden(False); self.pl_tree_view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers); self.pl_model = QStandardItemModel(); self.pl_tree_view.setModel(self.pl_model); self.fs_display_stack.addWidget(self.pl_tree_view)
        self.tb_table_view = QTableView(); self.tb_table_view.setAlternatingRowColors(True); self.tb_table_view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows); self.tb_table_view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection); self.tb_table_view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers); self.tb_table_view.setSortingEnabled(True); self.tb_model = TrialBalanceTableModel(); self.tb_table_view.setModel(self.tb_model); self.fs_display_stack.addWidget(self.tb_table_view)
        gl_widget_container = QWidget(); gl_layout = QVBoxLayout(gl_widget_container); gl_layout.setContentsMargins(0,0,0,0)
        self.gl_summary_label_account = QLabel("Account: N/A"); self.gl_summary_label_account.setStyleSheet("font-weight: bold;"); self.gl_summary_label_period = QLabel("Period: N/A"); self.gl_summary_label_ob = QLabel("Opening Balance: 0.00"); gl_summary_header_layout = QHBoxLayout(); gl_summary_header_layout.addWidget(self.gl_summary_label_account); gl_summary_header_layout.addStretch(); gl_summary_header_layout.addWidget(self.gl_summary_label_period); gl_layout.addLayout(gl_summary_header_layout); gl_layout.addWidget(self.gl_summary_label_ob)
        self.gl_table_view = QTableView(); self.gl_table_view.setAlternatingRowColors(True); self.gl_table_view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows); self.gl_table_view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection); self.gl_table_view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers); self.gl_table_view.setSortingEnabled(True); self.gl_model = GeneralLedgerTableModel(); self.gl_table_view.setModel(self.gl_model); gl_layout.addWidget(self.gl_table_view)
        self.gl_summary_label_cb = QLabel("Closing Balance: 0.00"); self.gl_summary_label_cb.setAlignment(Qt.AlignmentFlag.AlignRight); gl_layout.addWidget(self.gl_summary_label_cb)
        self.fs_display_stack.addWidget(gl_widget_container); self.gl_widget_container = gl_widget_container 
        
        self.tax_comp_tree_view = QTreeView(); self.tax_comp_tree_view.setAlternatingRowColors(True); self.tax_comp_tree_view.setHeaderHidden(False); self.tax_comp_tree_view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers); self.tax_comp_model = QStandardItemModel(); self.tax_comp_tree_view.setModel(self.tax_comp_model); self.fs_display_stack.addWidget(self.tax_comp_tree_view)

        export_button_layout = QHBoxLayout(); self.export_pdf_button = QPushButton("Export to PDF"); self.export_pdf_button.setEnabled(False); self.export_pdf_button.clicked.connect(lambda: self._on_export_report_clicked("pdf")); self.export_excel_button = QPushButton("Export to Excel"); self.export_excel_button.setEnabled(False); self.export_excel_button.clicked.connect(lambda: self._on_export_report_clicked("excel")); export_button_layout.addStretch(); export_button_layout.addWidget(self.export_pdf_button); export_button_layout.addWidget(self.export_excel_button); fs_group_layout.addLayout(export_button_layout)
        fs_main_layout.addWidget(fs_group); self.tab_widget.addTab(fs_widget, "Financial Statements")
        self.fs_report_type_combo.currentTextChanged.connect(self._on_fs_report_type_changed)
        self.fs_include_comparative_check.stateChanged.connect(self._on_comparative_check_changed)
        self.fs_dim1_type_combo.currentIndexChanged.connect(lambda index, tc=self.fs_dim1_type_combo, cc=self.fs_dim1_code_combo: self._on_dimension_type_selected(tc, cc))
        self.fs_dim2_type_combo.currentIndexChanged.connect(lambda index, tc=self.fs_dim2_type_combo, cc=self.fs_dim2_code_combo: self._on_dimension_type_selected(tc, cc))
        self._on_fs_report_type_changed(self.fs_report_type_combo.currentText()) 

    async def _load_fs_combo_data(self):
        await self._load_gl_accounts_for_combo()
        await self._load_fiscal_years_for_combo()

    @Slot(str)
    def _on_fs_report_type_changed(self, report_type: str):
        is_bs = (report_type == "Balance Sheet"); is_pl = (report_type == "Profit & Loss Statement"); is_gl = (report_type == "General Ledger"); is_tb = (report_type == "Trial Balance"); is_tax = (report_type == "Income Tax Computation")
        self.fs_as_of_date_edit.setVisible(is_bs or is_tb); self.fs_start_date_edit.setVisible(is_pl or is_gl); self.fs_end_date_edit.setVisible(is_pl or is_gl)
        self.fs_fiscal_year_combo.setVisible(is_tax); self.fs_fiscal_year_label.setVisible(is_tax)
        self.fs_gl_account_combo.setVisible(is_gl); self.fs_gl_account_label.setVisible(is_gl); self.fs_include_zero_balance_check.setVisible(is_bs); self.fs_include_comparative_check.setVisible(is_bs or is_pl)
        for w in [self.fs_dim1_type_label, self.fs_dim1_type_combo, self.fs_dim1_code_label, self.fs_dim1_code_combo, self.fs_dim2_type_label, self.fs_dim2_type_combo, self.fs_dim2_code_label, self.fs_dim2_code_combo]: w.setVisible(is_gl)
        if is_gl and self.fs_dim1_type_combo.count() <= 1 : schedule_task_from_qt(self._load_dimension_types())
        self._on_comparative_check_changed(self.fs_include_comparative_check.checkState().value) 
        if is_gl: self.fs_display_stack.setCurrentWidget(self.gl_widget_container)
        elif is_bs: self.fs_display_stack.setCurrentWidget(self.bs_tree_view)
        elif is_pl: self.fs_display_stack.setCurrentWidget(self.pl_tree_view)
        elif is_tb: self.fs_display_stack.setCurrentWidget(self.tb_table_view)
        elif is_tax: self.fs_display_stack.setCurrentWidget(self.tax_comp_tree_view)
        self._clear_current_financial_report_display(); self.export_pdf_button.setEnabled(False); self.export_excel_button.setEnabled(False)
    async def _load_dimension_types(self):
        if not self.app_core.dimension_service: self.app_core.logger.error("DimensionService not available."); return
        try:
            dim_types = await self.app_core.dimension_service.get_distinct_dimension_types(); json_data = json.dumps(dim_types)
            QMetaObject.invokeMethod(self, "_populate_dimension_types_slot", Qt.ConnectionType.QueuedConnection, Q_ARG(str, json_data))
        except Exception as e: self.app_core.logger.error(f"Error loading dimension types: {e}", exc_info=True)
    @Slot(str)
    def _populate_dimension_types_slot(self, dim_types_json_str: str):
        try: dim_types = json.loads(dim_types_json_str)
        except json.JSONDecodeError: self.app_core.logger.error("Failed to parse dimension types JSON."); return
        self._dimension_types_cache = ["All Types"] + dim_types 
        for combo in [self.fs_dim1_type_combo, self.fs_dim2_type_combo]:
            current_data = combo.currentData(); combo.clear(); combo.addItem("All Types", None)
            for dt in dim_types: combo.addItem(dt, dt)
            idx = combo.findData(current_data); 
            if idx != -1: combo.setCurrentIndex(idx)
            else: combo.setCurrentIndex(0) 
        self._on_dimension_type_selected(self.fs_dim1_type_combo, self.fs_dim1_code_combo); self._on_dimension_type_selected(self.fs_dim2_type_combo, self.fs_dim2_code_combo)
    @Slot(QComboBox, QComboBox) 
    def _on_dimension_type_selected(self, type_combo: QComboBox, code_combo: QComboBox):
        selected_type_str = type_combo.currentData() 
        if selected_type_str: schedule_task_from_qt(self._load_dimension_codes_for_type(selected_type_str, code_combo.objectName() or ""))
        else: code_combo.clear(); code_combo.addItem("All Codes", None)
    async def _load_dimension_codes_for_type(self, dim_type_str: str, target_code_combo_name: str):
        if not self.app_core.dimension_service: self.app_core.logger.error("DimensionService not available."); return
        try:
            dimensions: List[Dimension] = await self.app_core.dimension_service.get_dimensions_by_type(dim_type_str)
            dim_codes_data = [{"id": d.id, "code": d.code, "name": d.name} for d in dimensions]; self._dimension_codes_cache[dim_type_str] = dim_codes_data
            json_data = json.dumps(dim_codes_data, default=json_converter)
            QMetaObject.invokeMethod(self, "_populate_dimension_codes_slot", Qt.ConnectionType.QueuedConnection, Q_ARG(str, json_data), Q_ARG(str, target_code_combo_name))
        except Exception as e: self.app_core.logger.error(f"Error loading dimension codes for type '{dim_type_str}': {e}", exc_info=True)
    @Slot(str, str)
    def _populate_dimension_codes_slot(self, dim_codes_json_str: str, target_code_combo_name: str):
        target_combo: Optional[QComboBox] = self.findChild(QComboBox, target_code_combo_name)
        if not target_combo: self.app_core.logger.error(f"Target code combo '{target_code_combo_name}' not found."); return
        current_data = target_combo.currentData(); target_combo.clear(); target_combo.addItem("All Codes", None) 
        try:
            dim_codes = json.loads(dim_codes_json_str, object_hook=json_date_hook)
            for dc in dim_codes: target_combo.addItem(f"{dc['code']} - {dc['name']}", dc['id'])
            idx = target_combo.findData(current_data)
            if idx != -1: target_combo.setCurrentIndex(idx)
            else: target_combo.setCurrentIndex(0) 
        except json.JSONDecodeError: self.app_core.logger.error(f"Failed to parse dim codes JSON for {target_code_combo_name}")
    @Slot(int)
    def _on_comparative_check_changed(self, state: int):
        is_checked = (state == Qt.CheckState.Checked.value); report_type = self.fs_report_type_combo.currentText(); is_bs = (report_type == "Balance Sheet"); is_pl = (report_type == "Profit & Loss Statement")
        self.fs_comparative_as_of_date_label.setVisible(is_bs and is_checked); self.fs_comparative_as_of_date_edit.setVisible(is_bs and is_checked)
        self.fs_comparative_start_date_label.setVisible(is_pl and is_checked); self.fs_comparative_start_date_edit.setVisible(is_pl and is_checked)
        self.fs_comparative_end_date_label.setVisible(is_pl and is_checked); self.fs_comparative_end_date_edit.setVisible(is_pl and is_checked)
    async def _load_gl_accounts_for_combo(self):
        if not self.app_core.chart_of_accounts_manager: self.app_core.logger.error("ChartOfAccountsManager not available for GL account combo."); return
        try:
            accounts_orm: List[Account] = await self.app_core.chart_of_accounts_manager.get_accounts_for_selection(active_only=True)
            self._gl_accounts_cache = [{"id": acc.id, "code": acc.code, "name": acc.name} for acc in accounts_orm]
            accounts_json = json.dumps(self._gl_accounts_cache, default=json_converter)
            QMetaObject.invokeMethod(self, "_populate_gl_account_combo_slot", Qt.ConnectionType.QueuedConnection, Q_ARG(str, accounts_json))
        except Exception as e: self.app_core.logger.error(f"Error loading accounts for GL combo: {e}", exc_info=True); QMessageBox.warning(self, "Account Load Error", "Could not load accounts for General Ledger selection.")
    @Slot(str)
    def _populate_gl_account_combo_slot(self, accounts_json_str: str):
        self.fs_gl_account_combo.clear()
        try:
            accounts_data = json.loads(accounts_json_str); self._gl_accounts_cache = accounts_data if accounts_data else []
            self.fs_gl_account_combo.addItem("-- Select Account --", 0) 
            for acc_data in self._gl_accounts_cache: self.fs_gl_account_combo.addItem(f"{acc_data['code']} - {acc_data['name']}", acc_data['id'])
            if isinstance(self.fs_gl_account_combo.completer(), QCompleter): self.fs_gl_account_combo.completer().setModel(self.fs_gl_account_combo.model())
        except json.JSONDecodeError: self.app_core.logger.error("Failed to parse accounts JSON for GL combo."); self.fs_gl_account_combo.addItem("Error loading accounts", 0)

    async def _load_fiscal_years_for_combo(self):
        if not self.app_core.fiscal_period_manager: self.app_core.logger.error("FiscalPeriodManager not available."); return
        try:
            fy_orms = await self.app_core.fiscal_period_manager.get_all_fiscal_years()
            self._fiscal_years_cache = [FiscalYearData.model_validate(fy) for fy in fy_orms]
            fy_json = json.dumps([fy.model_dump(mode='json') for fy in self._fiscal_years_cache])
            QMetaObject.invokeMethod(self, "_populate_fiscal_years_combo_slot", Qt.ConnectionType.QueuedConnection, Q_ARG(str, fy_json))
        except Exception as e: self.app_core.logger.error(f"Error loading fiscal years for combo: {e}", exc_info=True)

    @Slot(str)
    def _populate_fiscal_years_combo_slot(self, fy_json_str: str):
        self.fs_fiscal_year_combo.clear()
        try:
            fy_dicts = json.loads(fy_json_str, object_hook=json_date_hook)
            self._fiscal_years_cache = [FiscalYearData.model_validate(fy) for fy in fy_dicts]
            if not self._fiscal_years_cache: self.fs_fiscal_year_combo.addItem("No fiscal years found", 0); return
            for fy_data in sorted(self._fiscal_years_cache, key=lambda fy: fy.start_date, reverse=True):
                self.fs_fiscal_year_combo.addItem(f"{fy_data.year_name} ({fy_data.start_date.strftime('%d/%m/%Y')} - {fy_data.end_date.strftime('%d/%m/%Y')})", fy_data.id)
        except Exception as e: self.app_core.logger.error(f"Error parsing fiscal years for combo: {e}"); self.fs_fiscal_year_combo.addItem("Error loading", 0)

    def _clear_current_financial_report_display(self):
        self._current_financial_report_data = None; current_view = self.fs_display_stack.currentWidget()
        if isinstance(current_view, QTreeView): 
            model = current_view.model()
            if isinstance(model, QStandardItemModel): model.clear() 
        elif isinstance(current_view, QTableView): 
            model = current_view.model()
            if hasattr(model, 'update_data'): model.update_data([]) 
        elif current_view == self.gl_widget_container : 
            self.gl_model.update_data({}); self.gl_summary_label_account.setText("Account: N/A"); self.gl_summary_label_period.setText("Period: N/A"); self.gl_summary_label_ob.setText("Opening Balance: 0.00"); self.gl_summary_label_cb.setText("Closing Balance: 0.00")
    
    @Slot()
    def _on_generate_financial_report_clicked(self):
        report_type = self.fs_report_type_combo.currentText()
        if not self.app_core.financial_statement_generator: QMessageBox.critical(self, "Error", "Financial Statement Generator not available."); return
        self._clear_current_financial_report_display(); self.generate_fs_button.setEnabled(False); self.generate_fs_button.setText("Generating..."); self.export_pdf_button.setEnabled(False); self.export_excel_button.setEnabled(False)
        coro: Optional[Any] = None; comparative_date_bs: Optional[python_date] = None; comparative_start_pl: Optional[python_date] = None; comparative_end_pl: Optional[python_date] = None; include_zero_bal_bs: bool = False
        dim1_id_val = self.fs_dim1_code_combo.currentData() if self.fs_dim1_type_label.isVisible() else None ; dim2_id_val = self.fs_dim2_code_combo.currentData() if self.fs_dim2_type_label.isVisible() else None
        dimension1_id = int(dim1_id_val) if dim1_id_val and dim1_id_val !=0 else None; dimension2_id = int(dim2_id_val) if dim2_id_val and dim2_id_val !=0 else None
        if self.fs_include_comparative_check.isVisible() and self.fs_include_comparative_check.isChecked():
            if report_type == "Balance Sheet": comparative_date_bs = self.fs_comparative_as_of_date_edit.date().toPython()
            elif report_type == "Profit & Loss Statement":
                comparative_start_pl = self.fs_comparative_start_date_edit.date().toPython(); comparative_end_pl = self.fs_comparative_end_date_edit.date().toPython()
                if comparative_start_pl and comparative_end_pl and comparative_start_pl > comparative_end_pl: QMessageBox.warning(self, "Date Error", "Comparative start date cannot be after comparative end date for P&L."); self.generate_fs_button.setEnabled(True); self.generate_fs_button.setText("Generate Report"); return
        if report_type == "Balance Sheet": as_of_date_val = self.fs_as_of_date_edit.date().toPython(); include_zero_bal_bs = self.fs_include_zero_balance_check.isChecked() if self.fs_include_zero_balance_check.isVisible() else False; coro = self.app_core.financial_statement_generator.generate_balance_sheet(as_of_date_val, comparative_date=comparative_date_bs, include_zero_balances=include_zero_bal_bs)
        elif report_type == "Profit & Loss Statement": 
            start_date_val = self.fs_start_date_edit.date().toPython(); end_date_val = self.fs_end_date_edit.date().toPython()
            if start_date_val > end_date_val: QMessageBox.warning(self, "Date Error", "Start date cannot be after end date for P&L."); self.generate_fs_button.setEnabled(True); self.generate_fs_button.setText("Generate Report"); return
            coro = self.app_core.financial_statement_generator.generate_profit_loss(start_date_val, end_date_val, comparative_start=comparative_start_pl, comparative_end=comparative_end_pl)
        elif report_type == "Trial Balance": as_of_date_val = self.fs_as_of_date_edit.date().toPython(); coro = self.app_core.financial_statement_generator.generate_trial_balance(as_of_date_val)
        elif report_type == "General Ledger":
            account_id = self.fs_gl_account_combo.currentData(); 
            if not isinstance(account_id, int) or account_id == 0: QMessageBox.warning(self, "Selection Error", "Please select a valid account for the General Ledger report."); self.generate_fs_button.setEnabled(True); self.generate_fs_button.setText("Generate Report"); return
            start_date_val = self.fs_start_date_edit.date().toPython(); end_date_val = self.fs_end_date_edit.date().toPython() 
            if start_date_val > end_date_val: QMessageBox.warning(self, "Date Error", "Start date cannot be after end date for General Ledger."); self.generate_fs_button.setEnabled(True); self.generate_fs_button.setText("Generate Report"); return
            coro = self.app_core.financial_statement_generator.generate_general_ledger(account_id, start_date_val, end_date_val, dimension1_id, dimension2_id)
        elif report_type == "Income Tax Computation":
            fy_id = self.fs_fiscal_year_combo.currentData()
            if not isinstance(fy_id, int) or fy_id == 0: QMessageBox.warning(self, "Selection Error", "Please select a Fiscal Year for the Tax Computation report."); self.generate_fs_button.setEnabled(True); self.generate_fs_button.setText("Generate Report"); return
            fy_data_obj = next((fy for fy in self._fiscal_years_cache if fy.id == fy_id), None)
            if not fy_data_obj: QMessageBox.warning(self, "Data Error", f"Could not find data for selected fiscal year ID {fy_id}."); self.generate_fs_button.setEnabled(True); self.generate_fs_button.setText("Generate Report"); return
            fy_orm = FiscalYear(id=fy_data_obj.id, year_name=fy_data_obj.year_name, start_date=fy_data_obj.start_date, end_date=fy_data_obj.end_date, is_closed=fy_data_obj.is_closed, created_by_user_id=1, updated_by_user_id=1) # Recreate ORM for passing
            coro = self.app_core.financial_statement_generator.generate_income_tax_computation(fy_orm)

        future_obj: Optional[Any] = None ; 
        if coro: future_obj = schedule_task_from_qt(coro)
        if future_obj: future_obj.add_done_callback( lambda res: QMetaObject.invokeMethod( self, "_safe_handle_financial_report_result_slot", Qt.ConnectionType.QueuedConnection, Q_ARG(object, future_obj)))
        else: self.app_core.logger.error(f"Failed to schedule report generation for {report_type}."); self.generate_fs_button.setEnabled(True); self.generate_fs_button.setText("Generate Report"); self._handle_financial_report_result(None) 
    
    @Slot(object)
    def _safe_handle_financial_report_result_slot(self, future_arg): self._handle_financial_report_result(future_arg)
    
    def _handle_financial_report_result(self, future):
        self.generate_fs_button.setEnabled(True); self.generate_fs_button.setText("Generate Report"); self.export_pdf_button.setEnabled(False) ; self.export_excel_button.setEnabled(False); self._current_financial_report_data = None
        if future is None: QMessageBox.critical(self, "Task Error", "Failed to schedule report generation."); return
        try:
            report_data: Optional[Dict[str, Any]] = future.result()
            if report_data: self._current_financial_report_data = report_data; self._display_financial_report(report_data); self.export_pdf_button.setEnabled(True); self.export_excel_button.setEnabled(True)
            else: QMessageBox.warning(self, "Report Error", "Failed to generate report data or report data is empty.")
        except Exception as e: self.app_core.logger.error(f"Exception handling financial report result: {e}", exc_info=True); QMessageBox.critical(self, "Report Generation Error", f"An unexpected error occurred: {str(e)}")

    def _populate_balance_sheet_model(self, model: QStandardItemModel, report_data: Dict[str, Any]):
        model.clear(); has_comparative = bool(report_data.get('comparative_date')); headers = ["Description", "Amount"]; 
        if has_comparative: headers.append(f"Comparative ({report_data.get('comparative_date','Prev').strftime('%d/%m/%Y') if isinstance(report_data.get('comparative_date'), python_date) else 'Prev'})")
        model.setHorizontalHeaderLabels(headers); root_node = model.invisibleRootItem(); bold_font = QFont(); bold_font.setBold(True)
        def add_account_rows(parent_item: QStandardItem, accounts: List[Dict[str,Any]], comparative_accounts: Optional[List[Dict[str,Any]]]):
            for acc_dict in accounts:
                desc_item = QStandardItem(f"  {acc_dict.get('code','')} - {acc_dict.get('name','')}"); amount_item = QStandardItem(self._format_decimal_for_display(acc_dict.get('balance'))); amount_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter); row_items = [desc_item, amount_item]
                if has_comparative:
                    comp_val_str = ""; 
                    if comparative_accounts: comp_acc = next((ca for ca in comparative_accounts if ca['id'] == acc_dict['id']), None); comp_val_str = self._format_decimal_for_display(comp_acc['balance']) if comp_acc and comp_acc['balance'] is not None else ""
                    comp_amount_item = QStandardItem(comp_val_str); comp_amount_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter); row_items.append(comp_amount_item)
                parent_item.appendRow(row_items)
        for section_key, section_title_display in [('assets', "Assets"), ('liabilities', "Liabilities"), ('equity', "Equity")]:
            section_data = report_data.get(section_key); 
            if not section_data or not isinstance(section_data, dict): continue
            section_header_item = QStandardItem(section_title_display); section_header_item.setFont(bold_font); empty_amount_item = QStandardItem(""); empty_amount_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter); header_row = [section_header_item, empty_amount_item]; 
            if has_comparative: header_row.append(QStandardItem("")); root_node.appendRow(header_row)
            add_account_rows(section_header_item, section_data.get("accounts", []), section_data.get("comparative_accounts"))
            total_desc_item = QStandardItem(f"Total {section_title_display}"); total_desc_item.setFont(bold_font); total_amount_item = QStandardItem(self._format_decimal_for_display(section_data.get("total"))); total_amount_item.setFont(bold_font); total_amount_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter); total_row_items = [total_desc_item, total_amount_item]; 
            if has_comparative: comp_total_item = QStandardItem(self._format_decimal_for_display(section_data.get("comparative_total"))); comp_total_item.setFont(bold_font); comp_total_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter); total_row_items.append(comp_total_item)
            root_node.appendRow(total_row_items); 
            if section_key != 'equity': root_node.appendRow([QStandardItem(""), QStandardItem("")] + ([QStandardItem("")] if has_comparative else []))
        if 'total_liabilities_equity' in report_data:
            root_node.appendRow([QStandardItem(""), QStandardItem("")] + ([QStandardItem("")] if has_comparative else [])); tle_desc = QStandardItem("Total Liabilities & Equity"); tle_desc.setFont(bold_font); tle_amount = QStandardItem(self._format_decimal_for_display(report_data.get('total_liabilities_equity'))); tle_amount.setFont(bold_font); tle_amount.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter); tle_row = [tle_desc, tle_amount]; 
            if has_comparative: comp_tle_amount = QStandardItem(self._format_decimal_for_display(report_data.get('comparative_total_liabilities_equity'))); comp_tle_amount.setFont(bold_font); comp_tle_amount.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter); tle_row.append(comp_tle_amount)
            root_node.appendRow(tle_row)
        if report_data.get('is_balanced') is False: warning_item = QStandardItem("Warning: Balance Sheet is out of balance!"); warning_item.setForeground(QColor("red")); warning_item.setFont(bold_font); warning_row = [warning_item, QStandardItem("")]; 
        if has_comparative: warning_row.append(QStandardItem("")); root_node.appendRow(warning_row)
    
    def _populate_profit_loss_model(self, model: QStandardItemModel, report_data: Dict[str, Any]):
        model.clear(); has_comparative = bool(report_data.get('comparative_start')); comp_header_text = "Comparative"; 
        if has_comparative and report_data.get('comparative_start') and report_data.get('comparative_end'): comp_start_str = report_data['comparative_start'].strftime('%d/%m/%y'); comp_end_str = report_data['comparative_end'].strftime('%d/%m/%y'); comp_header_text = f"Comp. ({comp_start_str}-{comp_end_str})"
        headers = ["Description", "Amount"]; 
        if has_comparative: headers.append(comp_header_text); 
        model.setHorizontalHeaderLabels(headers); root_node = model.invisibleRootItem(); bold_font = QFont(); bold_font.setBold(True)
        def add_pl_account_rows(parent_item: QStandardItem, accounts: List[Dict[str,Any]], comparative_accounts: Optional[List[Dict[str,Any]]]):
            for acc_dict in accounts:
                desc_item = QStandardItem(f"  {acc_dict.get('code','')} - {acc_dict.get('name','')}"); amount_item = QStandardItem(self._format_decimal_for_display(acc_dict.get('balance'))); amount_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter); row_items = [desc_item, amount_item]
                if has_comparative:
                    comp_val_str = ""; 
                    if comparative_accounts: comp_acc = next((ca for ca in comparative_accounts if ca['id'] == acc_dict['id']), None); comp_val_str = self._format_decimal_for_display(comp_acc['balance']) if comp_acc and comp_acc['balance'] is not None else ""
                    comp_amount_item = QStandardItem(comp_val_str); comp_amount_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter); row_items.append(comp_amount_item)
                parent_item.appendRow(row_items)
        for section_key, section_title_display in [('revenue', "Revenue"), ('expenses', "Operating Expenses")]: 
            section_data = report_data.get(section_key); 
            if not section_data or not isinstance(section_data, dict): continue
            section_header_item = QStandardItem(section_title_display); section_header_item.setFont(bold_font); empty_amount_item = QStandardItem(""); empty_amount_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter); header_row = [section_header_item, empty_amount_item]; 
            if has_comparative: header_row.append(QStandardItem("")); root_node.appendRow(header_row)
            add_pl_account_rows(section_header_item, section_data.get("accounts", []), section_data.get("comparative_accounts"))
            total_desc_item = QStandardItem(f"Total {section_title_display}"); total_desc_item.setFont(bold_font); total_amount_item = QStandardItem(self._format_decimal_for_display(section_data.get("total"))); total_amount_item.setFont(bold_font); total_amount_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter); total_row_items = [total_desc_item, total_amount_item]; 
            if has_comparative: comp_total_item = QStandardItem(self._format_decimal_for_display(section_data.get("comparative_total"))); comp_total_item.setFont(bold_font); comp_total_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter); total_row_items.append(comp_total_item)
            root_node.appendRow(total_row_items); root_node.appendRow([QStandardItem(""), QStandardItem("")] + ([QStandardItem("")] if has_comparative else [])) 
        if 'net_profit' in report_data:
            np_desc = QStandardItem("Net Profit / (Loss)"); np_desc.setFont(bold_font); np_amount = QStandardItem(self._format_decimal_for_display(report_data.get('net_profit'))); np_amount.setFont(bold_font); np_amount.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter); np_row = [np_desc, np_amount]; 
            if has_comparative: comp_np_amount = QStandardItem(self._format_decimal_for_display(report_data.get('comparative_net_profit'))); comp_np_amount.setFont(bold_font); comp_np_amount.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter); np_row.append(comp_np_amount)
            root_node.appendRow(np_row)

    def _populate_tax_computation_model(self, model: QStandardItemModel, report_data: Dict[str, Any]):
        model.clear(); headers = ["Description", "Amount"]; model.setHorizontalHeaderLabels(headers); root_node = model.invisibleRootItem(); bold_font = QFont(); bold_font.setBold(True)
        def add_row(parent: QStandardItem, desc: str, amt: Optional[Decimal] = None, is_bold: bool = False, is_underline: bool = False):
            desc_item = QStandardItem(desc); amt_item = QStandardItem(self._format_decimal_for_display(amt) if amt is not None else ""); amt_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            if is_bold: desc_item.setFont(bold_font); amt_item.setFont(bold_font)
            if is_underline: desc_item.setData(QColor('black'), Qt.ItemDataRole.ForegroundRole); amt_item.setData(QColor('black'), Qt.ItemDataRole.ForegroundRole) # This doesn't create underline, just for concept
            parent.appendRow([desc_item, amt_item])
        
        add_row(root_node, "Net Profit Before Tax", report_data.get('net_profit_before_tax'), is_bold=True)
        add_row(root_node, "") # Spacer
        
        add_row(root_node, "Add: Non-Deductible Expenses", is_bold=True)
        for adj in report_data.get('add_back_adjustments', []): add_row(root_node, f"  {adj['name']}", adj['amount'])
        add_row(root_node, "Total Additions", report_data.get('total_add_back'), is_underline=True)
        add_row(root_node, "") # Spacer
        
        add_row(root_node, "Less: Non-Taxable Income", is_bold=True)
        for adj in report_data.get('less_adjustments', []): add_row(root_node, f"  {adj['name']}", adj['amount'])
        add_row(root_node, "Total Subtractions", report_data.get('total_less'), is_underline=True)
        add_row(root_node, "") # Spacer

        add_row(root_node, "Chargeable Income", report_data.get('chargeable_income'), is_bold=True)
        add_row(root_node, f"Tax at {report_data.get('tax_rate', 0):.2f}%", is_bold=False) # Description only
        add_row(root_node, "Estimated Tax Payable", report_data.get('estimated_tax'), is_bold=True)


    def _display_financial_report(self, report_data: Dict[str, Any]):
        report_title = report_data.get('title', '')
        if report_title == "Balance Sheet":
            self.fs_display_stack.setCurrentWidget(self.bs_tree_view); self._populate_balance_sheet_model(self.bs_model, report_data)
            self.bs_tree_view.expandAll(); [self.bs_tree_view.resizeColumnToContents(i) for i in range(self.bs_model.columnCount())]
        elif report_title == "Profit & Loss Statement":
            self.fs_display_stack.setCurrentWidget(self.pl_tree_view); self._populate_profit_loss_model(self.pl_model, report_data)
            self.pl_tree_view.expandAll(); [self.pl_tree_view.resizeColumnToContents(i) for i in range(self.pl_model.columnCount())]
        elif report_title == "Trial Balance":
            self.fs_display_stack.setCurrentWidget(self.tb_table_view); self.tb_model.update_data(report_data)
            [self.tb_table_view.resizeColumnToContents(i) for i in range(self.tb_model.columnCount())]
        elif report_title == "General Ledger": 
            self.fs_display_stack.setCurrentWidget(self.gl_widget_container); self.gl_model.update_data(report_data)
            gl_summary_data = self.gl_model.get_report_summary(); self.gl_summary_label_account.setText(f"Account: {gl_summary_data['account_name']}"); self.gl_summary_label_period.setText(gl_summary_data['period_description'])
            self.gl_summary_label_ob.setText(f"Opening Balance: {self._format_decimal_for_display(gl_summary_data['opening_balance'], show_blank_for_zero=False)}"); self.gl_summary_label_cb.setText(f"Closing Balance: {self._format_decimal_for_display(gl_summary_data['closing_balance'], show_blank_for_zero=False)}")
            [self.gl_table_view.resizeColumnToContents(i) for i in range(self.gl_model.columnCount())]
        elif report_title == "Income Tax Computation":
            self.fs_display_stack.setCurrentWidget(self.tax_comp_tree_view); self._populate_tax_computation_model(self.tax_comp_model, report_data)
            self.tax_comp_tree_view.expandAll(); [self.tax_comp_tree_view.resizeColumnToContents(i) for i in range(self.tax_comp_model.columnCount())]
        else: self._clear_current_financial_report_display(); self.app_core.logger.warning(f"Unhandled report title '{report_title}' for specific display."); QMessageBox.warning(self, "Display Error", f"Display format for '{report_title}' is not fully implemented in this view.")

    @Slot(str)
    def _on_export_report_clicked(self, format_type: str):
        if not self._current_financial_report_data: QMessageBox.warning(self, "No Report", "Please generate a report first before exporting."); return
        report_title_str = self._current_financial_report_data.get('title', 'FinancialReport')
        if not isinstance(report_title_str, str): report_title_str = "FinancialReport"
        default_filename = f"{report_title_str.replace(' ', '_').replace('&', 'And').replace('/', '-').replace(':', '')}_{python_date.today().strftime('%Y%m%d')}.{format_type}"
        documents_path = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation); 
        if not documents_path: documents_path = os.path.expanduser("~") 
        file_path, _ = QFileDialog.getSaveFileName(self, f"Save {format_type.upper()} Report", os.path.join(documents_path, default_filename), f"{format_type.upper()} Files (*.{format_type});;All Files (*)")
        if file_path: 
            self.export_pdf_button.setEnabled(False); self.export_excel_button.setEnabled(False)
            future = schedule_task_from_qt(self.app_core.report_engine.export_report(self._current_financial_report_data, format_type)); 
            if future: future.add_done_callback( lambda res, fp=file_path, ft=format_type: QMetaObject.invokeMethod( self, "_safe_handle_export_result_slot", Qt.ConnectionType.QueuedConnection, Q_ARG(object, future), Q_ARG(str, fp), Q_ARG(str, ft)))
            else: self.app_core.logger.error("Failed to schedule report export task."); self._handle_export_result(None, file_path, format_type) 
    @Slot(object, str, str)
    def _safe_handle_export_result_slot(self, future_arg, file_path_arg: str, format_type_arg: str): self._handle_export_result(future_arg, file_path_arg, format_type_arg)
    def _handle_export_result(self, future, file_path: str, format_type: str):
        self.export_pdf_button.setEnabled(True); self.export_excel_button.setEnabled(True)
        if future is None: QMessageBox.critical(self, "Task Error", "Failed to schedule report export."); return
        try:
            report_bytes: Optional[bytes] = future.result()
            if report_bytes:
                with open(file_path, "wb") as f: f.write(report_bytes)
                QMessageBox.information(self, "Export Successful", f"Report exported to:\n{file_path}")
            else: QMessageBox.warning(self, "Export Failed", f"Failed to generate report bytes for {format_type.upper()}.")
        except Exception as e: self.app_core.logger.error(f"Exception handling report export result: {e}", exc_info=True); QMessageBox.critical(self, "Export Error", f"An error occurred during export: {str(e)}")

```

# app/ui/reports/wht_payment_table_model.py
```py
# File: app/ui/reports/wht_payment_table_model.py
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from typing import List, Dict, Any, Optional
from decimal import Decimal
from datetime import date

from app.utils.pydantic_models import PaymentSummaryData

class WHTPaymentTableModel(QAbstractTableModel):
    def __init__(self, data: Optional[List[PaymentSummaryData]] = None, parent=None):
        super().__init__(parent)
        self._headers = ["ID", "Payment No", "Payment Date", "Vendor Name", "Gross Amount", "Currency", "WHT Applied?"]
        self._data: List[PaymentSummaryData] = data or []

    def rowCount(self, parent=QModelIndex()) -> int:
        if parent.isValid(): return 0
        return len(self._data)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(self._headers)

    def headerData(self, section: int, orientation: Qt.Orientation, role=Qt.ItemDataRole.DisplayRole) -> Optional[str]:
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            if 0 <= section < len(self._headers):
                return self._headers[section]
        return None

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid(): return None
        
        row, col = index.row(), index.column()
        if not (0 <= row < len(self._data)): return None
            
        payment = self._data[row]

        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0: return payment.id
            if col == 1: return payment.payment_no
            if col == 2: return payment.payment_date.strftime('%Y-%m-%d') if payment.payment_date else ""
            if col == 3: return payment.entity_name
            if col == 4: return f"{payment.amount:,.2f}"
            if col == 5: return payment.currency_code
            if col == 6: return "Yes" # This view only shows applicable payments
        
        elif role == Qt.ItemDataRole.TextAlignmentRole:
            if col == 4: # Amount
                return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        
        elif role == Qt.ItemDataRole.UserRole:
            return payment

        return None

    def update_data(self, new_data: List[PaymentSummaryData]):
        self.beginResetModel()
        self._data = new_data or []
        self.endResetModel()

```

# app/ui/reports/wht_reporting_widget.py
```py
# File: app/ui/reports/wht_reporting_widget.py
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QHBoxLayout, QTableView, QPushButton,
    QMessageBox, QLabel, QHeaderView, QAbstractItemView
)
from PySide6.QtCore import Qt, Slot, QTimer, QMetaObject, Q_ARG
from PySide6.QtGui import QIcon
from typing import Optional, TYPE_CHECKING

from app.core.application_core import ApplicationCore
from app.main import schedule_task_from_qt
from app.utils.result import Result
from app.common.enums import PaymentTypeEnum
from app.ui.reports.wht_payment_table_model import WHTPaymentTableModel
from app.models.accounting.withholding_tax_certificate import WithholdingTaxCertificate
from app.models.business.payment import Payment

if TYPE_CHECKING:
    from PySide6.QtGui import QPaintDevice

class WHTReportingWidget(QWidget):
    def __init__(self, app_core: ApplicationCore, parent: Optional["QWidget"] = None):
        super().__init__(parent)
        self.app_core = app_core
        self._init_ui()
        QTimer.singleShot(0, self._on_refresh_clicked)

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        
        controls_group = QGroupBox("Withholding Tax Payments")
        controls_layout = QHBoxLayout(controls_group)
        controls_layout.addWidget(QLabel("This lists vendor payments where Withholding Tax was applicable."))
        controls_layout.addStretch()
        self.refresh_button = QPushButton(QIcon(":/icons/refresh.svg"), "Refresh List")
        controls_layout.addWidget(self.refresh_button)
        main_layout.addWidget(controls_group)

        self.payments_table = QTableView()
        self.payments_table.setAlternatingRowColors(True)
        self.payments_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.payments_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.payments_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.payments_table.setSortingEnabled(True)
        
        self.table_model = WHTPaymentTableModel()
        self.payments_table.setModel(self.table_model)
        header = self.payments_table.horizontalHeader()
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch) # Vendor Name
        self.payments_table.setColumnHidden(0, True) # Hide ID column
        main_layout.addWidget(self.payments_table)

        action_layout = QHBoxLayout()
        action_layout.addStretch()
        self.generate_cert_button = QPushButton(QIcon(":/icons/reports.svg"), "Generate S45 Certificate")
        self.generate_cert_button.setEnabled(False)
        action_layout.addWidget(self.generate_cert_button)
        main_layout.addLayout(action_layout)

        self.setLayout(main_layout)
        self._connect_signals()

    def _connect_signals(self):
        self.refresh_button.clicked.connect(self._on_refresh_clicked)
        self.payments_table.selectionModel().selectionChanged.connect(self._on_selection_changed)
        self.generate_cert_button.clicked.connect(self._on_generate_certificate_clicked)

    @Slot()
    def _on_refresh_clicked(self):
        if not self.app_core.current_user:
            QMessageBox.warning(self, "Authentication Error", "No user logged in.")
            return
        
        self.refresh_button.setEnabled(False)
        self.generate_cert_button.setEnabled(False)

        future = schedule_task_from_qt(self.app_core.payment_manager.get_payments_for_listing(
            entity_type=PaymentTypeEnum.VENDOR_PAYMENT,
            page_size=-1,
            wht_applicable_only=True # Use the new service parameter
        ))
        if future:
            future.add_done_callback(self._handle_load_payments_result)

    def _handle_load_payments_result(self, future):
        self.refresh_button.setEnabled(True)
        try:
            result = future.result()
            if result.is_success:
                self.table_model.update_data(result.value or [])
            else:
                QMessageBox.warning(self, "Error", f"Failed to load payments:\n{', '.join(result.errors)}")
        except Exception as e:
            self.app_core.logger.error(f"Error handling WHT payment list result: {e}", exc_info=True)
            QMessageBox.critical(self, "Error", f"An unexpected error occurred while loading payments: {e}")

    @Slot()
    def _on_selection_changed(self):
        self.generate_cert_button.setEnabled(bool(self.payments_table.selectionModel().hasSelection()))

    @Slot()
    def _on_generate_certificate_clicked(self):
        selected_indexes = self.payments_table.selectionModel().selectedRows()
        if not selected_indexes:
            return
        
        selected_payment_summary = self.table_model.data(selected_indexes[0], Qt.ItemDataRole.UserRole)
        if not selected_payment_summary:
            return
            
        self.generate_cert_button.setEnabled(False)
        future = schedule_task_from_qt(self._fetch_payment_and_generate_cert(selected_payment_summary.id))
        if future:
            future.add_done_callback(self._handle_generate_cert_result)

    async def _fetch_payment_and_generate_cert(self, payment_id: int):
        if not self.app_core.current_user:
            return Result.failure(["No user is logged in."])
            
        payment_orm = await self.app_core.payment_service.get_payment_with_vendor(payment_id)
        if not payment_orm:
            return Result.failure([f"Payment with ID {payment_id} not found or vendor details could not be loaded."])
        
        return await self.app_core.withholding_tax_manager.create_wht_certificate_from_payment(
            payment=payment_orm,
            user_id=self.app_core.current_user.id
        )

    def _handle_generate_cert_result(self, future):
        self.generate_cert_button.setEnabled(bool(self.payments_table.selectionModel().hasSelection()))
        try:
            result: Result[WithholdingTaxCertificate] = future.result()
            if result.is_success and result.value:
                cert = result.value
                QMessageBox.information(self, "Success", 
                    f"Successfully created Withholding Tax Certificate.\n\n"
                    f"Certificate No: {cert.certificate_no}\n"
                    f"Vendor: {cert.vendor.name}\n"
                    f"Tax Amount: {cert.tax_amount:,.2f}"
                )
            else:
                QMessageBox.warning(self, "Generation Failed", f"Could not generate certificate:\n{', '.join(result.errors)}")
        except Exception as e:
            self.app_core.logger.error(f"Error handling WHT certificate generation result: {e}", exc_info=True)
            QMessageBox.critical(self, "Fatal Error", f"An unexpected error occurred: {e}")

```

# app/ui/accounting/chart_of_accounts_widget.py
```py
# File: app/ui/accounting/chart_of_accounts_widget.py
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTreeView, QHeaderView,
    QPushButton, QToolBar, QMenu, QDialog, QMessageBox, QLabel, QSpacerItem, QSizePolicy 
)
from PySide6.QtCore import Qt, QModelIndex, Signal, Slot, QPoint, QSortFilterProxyModel, QTimer, QMetaObject, Q_ARG
from PySide6.QtGui import QIcon, QStandardItemModel, QStandardItem, QAction, QColor
from decimal import Decimal, InvalidOperation
from datetime import date 
import asyncio 
import json
from typing import Optional, Dict, Any, List 

from app.ui.accounting.account_dialog import AccountDialog
from app.core.application_core import ApplicationCore
from app.utils.result import Result 
from app.main import schedule_task_from_qt 

def json_converter(obj):
    if isinstance(obj, Decimal): return str(obj)
    if isinstance(obj, date): return obj.isoformat()
    raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")

class ChartOfAccountsWidget(QWidget):
    account_selected = Signal(int)
    
    def __init__(self, app_core: ApplicationCore, parent=None):
        super().__init__(parent)
        self.app_core = app_core
        self._init_ui()

    def _init_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.account_tree = QTreeView(); self.account_tree.setAlternatingRowColors(True); self.account_tree.setUniformRowHeights(True)
        self.account_tree.setEditTriggers(QTreeView.EditTrigger.NoEditTriggers); self.account_tree.setSelectionBehavior(QTreeView.SelectionBehavior.SelectRows)
        self.account_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu); self.account_tree.customContextMenuRequested.connect(self.on_context_menu)
        self.account_tree.doubleClicked.connect(self.on_account_double_clicked)
        self.account_model = QStandardItemModel(); self.account_model.setHorizontalHeaderLabels(["Code", "Name", "Type", "Cash Flow", "Opening Balance", "Is Active"]) 
        self.proxy_model = QSortFilterProxyModel(); self.proxy_model.setSourceModel(self.account_model); self.proxy_model.setRecursiveFilteringEnabled(True)
        self.account_tree.setModel(self.proxy_model)
        header = self.account_tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents); header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents); header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents); header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self._create_toolbar(); self.main_layout.addWidget(self.toolbar) 
        self.main_layout.addWidget(self.account_tree) 
        self.button_layout = QHBoxLayout(); self.button_layout.setContentsMargins(0, 10, 0, 0)
        icon_path_prefix = "" 
        try: import app.resources_rc; icon_path_prefix = ":/icons/"
        except ImportError: icon_path_prefix = "resources/icons/"
        self.add_button = QPushButton(QIcon(icon_path_prefix + "add.svg"), "Add Account"); self.add_button.clicked.connect(self.on_add_account) # Changed icon
        self.button_layout.addWidget(self.add_button)
        self.edit_button = QPushButton(QIcon(icon_path_prefix + "edit.svg"), "Edit Account"); self.edit_button.clicked.connect(self.on_edit_account); self.button_layout.addWidget(self.edit_button)
        self.deactivate_button = QPushButton(QIcon(icon_path_prefix + "deactivate.svg"), "Toggle Active"); self.deactivate_button.clicked.connect(self.on_toggle_active_status); self.button_layout.addWidget(self.deactivate_button)
        self.button_layout.addStretch(); self.main_layout.addLayout(self.button_layout)
        QTimer.singleShot(0, lambda: schedule_task_from_qt(self._load_accounts()))

    def _create_toolbar(self):
        from PySide6.QtCore import QSize 
        self.toolbar = QToolBar("COA Toolbar"); self.toolbar.setObjectName("COAToolbar"); self.toolbar.setIconSize(QSize(16, 16))
        icon_path_prefix = ""
        try: import app.resources_rc; icon_path_prefix = ":/icons/"
        except ImportError: icon_path_prefix = "resources/icons/"
        self.filter_action = QAction(QIcon(icon_path_prefix + "filter.svg"), "Filter", self); self.filter_action.setCheckable(True); self.filter_action.toggled.connect(self.on_filter_toggled); self.toolbar.addAction(self.filter_action)
        self.toolbar.addSeparator()
        self.expand_all_action = QAction(QIcon(icon_path_prefix + "expand_all.svg"), "Expand All", self); self.expand_all_action.triggered.connect(self.account_tree.expandAll); self.toolbar.addAction(self.expand_all_action)
        self.collapse_all_action = QAction(QIcon(icon_path_prefix + "collapse_all.svg"), "Collapse All", self); self.collapse_all_action.triggered.connect(self.account_tree.collapseAll); self.toolbar.addAction(self.collapse_all_action)
        self.toolbar.addSeparator()
        self.refresh_action = QAction(QIcon(icon_path_prefix + "refresh.svg"), "Refresh", self); self.refresh_action.triggered.connect(lambda: schedule_task_from_qt(self._load_accounts())); self.toolbar.addAction(self.refresh_action)
        
    async def _load_accounts(self):
        try:
            manager = self.app_core.accounting_service 
            if not (manager and hasattr(manager, 'get_account_tree')):
                QMetaObject.invokeMethod(QMessageBox.staticMetaObject, "critical", Qt.ConnectionType.QueuedConnection, Q_ARG(QWidget, self), Q_ARG(str, "Error"), Q_ARG(str,"Accounting service (ChartOfAccountsManager) or get_account_tree method not available."))
                return
            account_tree_data: List[Dict[str, Any]] = await manager.get_account_tree(active_only=False) 
            json_data = json.dumps(account_tree_data, default=json_converter)
            QMetaObject.invokeMethod(self, "_update_account_model_slot", Qt.ConnectionType.QueuedConnection, Q_ARG(str, json_data))
        except Exception as e:
            error_message = f"Failed to load accounts: {str(e)}"; print(error_message) 
            QMetaObject.invokeMethod(QMessageBox.staticMetaObject, "critical", Qt.ConnectionType.QueuedConnection, Q_ARG(QWidget, self), Q_ARG(str, "Error"), Q_ARG(str, error_message))

    @Slot(str) 
    def _update_account_model_slot(self, account_tree_json_str: str):
        try: account_tree_data: List[Dict[str, Any]] = json.loads(account_tree_json_str)
        except json.JSONDecodeError as e: QMessageBox.critical(self, "Error", f"Failed to parse account data: {e}"); return
        self.account_model.clear(); self.account_model.setHorizontalHeaderLabels(["Code", "Name", "Type", "Cash Flow", "Opening Balance", "Is Active"])
        root_item = self.account_model.invisibleRootItem()
        if account_tree_data: 
            for account_node in account_tree_data: self._add_account_to_model_item(account_node, root_item) 
        self.account_tree.expandToDepth(0) 

    def _add_account_to_model_item(self, account_data: dict, parent_item: QStandardItem):
        code_item = QStandardItem(account_data['code']); code_item.setData(account_data['id'], Qt.ItemDataRole.UserRole)
        name_item = QStandardItem(account_data['name']); type_text = account_data.get('sub_type') or account_data.get('account_type', '')
        type_item = QStandardItem(type_text); cash_flow_item = QStandardItem(account_data.get('cash_flow_category') or "")
        try: ob_val = Decimal(str(account_data.get('opening_balance', "0.00")))
        except InvalidOperation: ob_val = Decimal(0)
        ob_item = QStandardItem(f"{ob_val:,.2f}"); ob_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        is_active_item = QStandardItem("Yes" if account_data.get('is_active', False) else "No")
        parent_item.appendRow([code_item, name_item, type_item, cash_flow_item, ob_item, is_active_item])
        if 'children' in account_data:
            for child_data in account_data['children']: self._add_account_to_model_item(child_data, code_item) 
    
    @Slot()
    def on_add_account(self):
        if not self.app_core.current_user: QMessageBox.warning(self, "Authentication Error", "No user logged in. Cannot add account."); return
        dialog = AccountDialog(self.app_core, current_user_id=self.app_core.current_user.id, parent=self) 
        if dialog.exec() == QDialog.DialogCode.Accepted: schedule_task_from_qt(self._load_accounts())
    
    @Slot()
    def on_edit_account(self):
        index = self.account_tree.currentIndex()
        if not index.isValid(): QMessageBox.warning(self, "Warning", "Please select an account to edit."); return
        source_index = self.proxy_model.mapToSource(index); item = self.account_model.itemFromIndex(source_index.siblingAtColumn(0))
        if not item: return
        account_id = item.data(Qt.ItemDataRole.UserRole)
        if not account_id: QMessageBox.warning(self, "Warning", "Cannot edit this item. Please select an account."); return
        if not self.app_core.current_user: QMessageBox.warning(self, "Authentication Error", "No user logged in. Cannot edit account."); return
        dialog = AccountDialog(self.app_core, account_id=account_id, current_user_id=self.app_core.current_user.id, parent=self) 
        if dialog.exec() == QDialog.DialogCode.Accepted: schedule_task_from_qt(self._load_accounts())
            
    @Slot()
    def on_toggle_active_status(self): 
        index = self.account_tree.currentIndex()
        if not index.isValid(): QMessageBox.warning(self, "Warning", "Please select an account."); return
        source_index = self.proxy_model.mapToSource(index); item_id_qstandarditem = self.account_model.itemFromIndex(source_index.siblingAtColumn(0))
        account_id = item_id_qstandarditem.data(Qt.ItemDataRole.UserRole) if item_id_qstandarditem else None
        if not account_id: QMessageBox.warning(self, "Warning", "Cannot determine account. Please select a valid account."); return
        if not self.app_core.current_user: QMessageBox.warning(self, "Authentication Error", "No user logged in."); return
        schedule_task_from_qt(self._perform_toggle_active_status_logic(account_id, self.app_core.current_user.id))

    async def _perform_toggle_active_status_logic(self, account_id: int, user_id: int):
        try:
            manager = self.app_core.accounting_service 
            if not manager: raise RuntimeError("Accounting service not available.")
            account = await manager.account_service.get_by_id(account_id) 
            if not account: QMetaObject.invokeMethod(QMessageBox.staticMetaObject, "warning", Qt.ConnectionType.QueuedConnection, Q_ARG(QWidget, self), Q_ARG(str, "Error"), Q_ARG(str,f"Account ID {account_id} not found.")); return
            data_to_pass = {"id": account_id, "is_active": account.is_active, "code": account.code, "name": account.name, "user_id": user_id}
            json_data_to_pass = json.dumps(data_to_pass, default=json_converter)
            QMetaObject.invokeMethod(self, "_confirm_and_toggle_status_slot", Qt.ConnectionType.QueuedConnection, Q_ARG(str, json_data_to_pass))
        except Exception as e:
            error_message = f"Failed to prepare toggle account active status: {str(e)}"; print(error_message)
            QMetaObject.invokeMethod(QMessageBox.staticMetaObject, "critical", Qt.ConnectionType.QueuedConnection, Q_ARG(QWidget, self), Q_ARG(str, "Error"), Q_ARG(str, error_message))

    @Slot(str) 
    def _confirm_and_toggle_status_slot(self, data_json_str: str):
        try: data: Dict[str, Any] = json.loads(data_json_str)
        except json.JSONDecodeError as e: QMessageBox.critical(self, "Error", f"Failed to parse toggle status data: {e}"); return
        account_id, is_currently_active, acc_code, acc_name, user_id = data["id"], data["is_active"], data["code"], data["name"], data["user_id"]
        action_verb_present = "deactivate" if is_currently_active else "activate"; action_verb_past = "deactivated" if is_currently_active else "activated"
        confirm_msg = f"Are you sure you want to {action_verb_present} account '{acc_code} - {acc_name}'?"
        reply = QMessageBox.question(self, f"Confirm {action_verb_present.capitalize()}", confirm_msg, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes: schedule_task_from_qt(self._finish_toggle_status(account_id, not is_currently_active, user_id, action_verb_past))

    async def _finish_toggle_status(self, account_id: int, new_active_status: bool, user_id: int, action_verb_past: str):
        try:
            manager = self.app_core.accounting_service; account = await manager.account_service.get_by_id(account_id)
            if not account: return 
            result: Optional[Result] = None
            if not new_active_status: result = await manager.deactivate_account(account_id, user_id)
            else: account.is_active = True; account.updated_by_user_id = user_id; saved_acc = await manager.account_service.save(account); result = Result.success(saved_acc)
            if result and result.is_success:
                QMetaObject.invokeMethod(QMessageBox.staticMetaObject, "information", Qt.ConnectionType.QueuedConnection, Q_ARG(QWidget, self), Q_ARG(str, "Success"), Q_ARG(str,f"Account {action_verb_past} successfully."))
                schedule_task_from_qt(self._load_accounts()) 
            elif result: QMetaObject.invokeMethod(QMessageBox.staticMetaObject, "warning", Qt.ConnectionType.QueuedConnection, Q_ARG(QWidget, self), Q_ARG(str, "Error"), Q_ARG(str, f"Failed to {action_verb_past.replace('ed','e')} account:\n{', '.join(result.errors)}"))
        except Exception as e:
            error_message = f"Error finishing toggle status: {str(e)}"; print(error_message)
            QMetaObject.invokeMethod(QMessageBox.staticMetaObject, "critical", Qt.ConnectionType.QueuedConnection, Q_ARG(QWidget, self), Q_ARG(str, "Error"), Q_ARG(str, error_message))

    @Slot(QModelIndex)
    def on_account_double_clicked(self, index: QModelIndex):
        if not index.isValid(): return
        source_index = self.proxy_model.mapToSource(index); item = self.account_model.itemFromIndex(source_index.siblingAtColumn(0))
        if not item: return
        account_id = item.data(Qt.ItemDataRole.UserRole)
        if account_id: self.account_selected.emit(account_id)
    
    @Slot(bool)
    def on_filter_toggled(self, checked: bool):
        if checked: QMessageBox.information(self, "Filter", "Filter functionality to be implemented."); self.filter_action.setChecked(False) 
        else: self.proxy_model.setFilterFixedString("") 
    
    @Slot(QPoint)
    def on_context_menu(self, pos: QPoint):
        index = self.account_tree.indexAt(pos); 
        if not index.isValid(): return
        source_index = self.proxy_model.mapToSource(index); item_id_qstandarditem = self.account_model.itemFromIndex(source_index.siblingAtColumn(0))
        if not item_id_qstandarditem : return
        account_id = item_id_qstandarditem.data(Qt.ItemDataRole.UserRole)
        if not account_id: return 
        icon_path_prefix = ""
        try: import app.resources_rc; icon_path_prefix = ":/icons/"
        except ImportError: icon_path_prefix = "resources/icons/"
        context_menu = QMenu(self)
        edit_action = QAction(QIcon(icon_path_prefix + "edit.svg"), "Edit Account", self); edit_action.triggered.connect(self.on_edit_account); context_menu.addAction(edit_action)
        view_trans_action = QAction(QIcon(icon_path_prefix + "transactions.svg"), "View Transactions", self); view_trans_action.triggered.connect(lambda: self.on_view_transactions(account_id)); context_menu.addAction(view_trans_action)
        toggle_active_action = QAction(QIcon(icon_path_prefix + "deactivate.svg"), "Toggle Active Status", self); toggle_active_action.triggered.connect(self.on_toggle_active_status); context_menu.addAction(toggle_active_action)
        context_menu.exec(self.account_tree.viewport().mapToGlobal(pos))
    
    @Slot(int)
    def on_view_transactions(self, account_id: int):
        QMessageBox.information(self, "View Transactions", f"View transactions for account ID {account_id} (To be implemented).")

```

# app/ui/accounting/accounting_widget.py
```py
# File: app/ui/accounting/accounting_widget.py
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTabWidget, QGroupBox, QHBoxLayout, QPushButton, QDateEdit, QMessageBox, QDialog, QDialogButtonBox
from PySide6.QtGui import QIcon
from PySide6.QtCore import Slot, QDate, QTimer, QMetaObject, Q_ARG, Qt

from app.ui.accounting.chart_of_accounts_widget import ChartOfAccountsWidget
from app.ui.accounting.journal_entries_widget import JournalEntriesWidget
from app.core.application_core import ApplicationCore 
from app.main import schedule_task_from_qt
from app.utils.result import Result
from app.models.accounting.journal_entry import JournalEntry
from datetime import date

class AccountingWidget(QWidget):
    def __init__(self, app_core: ApplicationCore, parent=None): 
        super().__init__(parent)
        self.app_core = app_core
        
        self.layout = QVBoxLayout(self)
        
        self.tab_widget = QTabWidget()
        self.layout.addWidget(self.tab_widget)
        
        self.coa_widget = ChartOfAccountsWidget(self.app_core)
        self.tab_widget.addTab(self.coa_widget, "Chart of Accounts")
        
        self.journal_entries_widget = JournalEntriesWidget(self.app_core)
        self.tab_widget.addTab(self.journal_entries_widget, "Journal Entries")
        
        self.period_end_widget = self._create_period_end_widget()
        self.tab_widget.addTab(self.period_end_widget, "Period-End Procedures")
        
        self.setLayout(self.layout)
    
    def _create_period_end_widget(self) -> QWidget:
        widget = QWidget()
        main_layout = QVBoxLayout(widget)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        icon_path_prefix = "" 
        try: import app.resources_rc; icon_path_prefix = ":/icons/"
        except ImportError: icon_path_prefix = "resources/icons/"

        forex_group = QGroupBox("Foreign Currency Revaluation")
        forex_layout = QHBoxLayout(forex_group)
        forex_layout.addWidget(QLabel("This process calculates and posts reversing journal entries for unrealized gains or losses on open foreign currency balances."))
        forex_layout.addStretch()
        self.run_forex_button = QPushButton(QIcon(icon_path_prefix + "accounting.svg"), "Run Forex Revaluation...")
        self.run_forex_button.clicked.connect(self._on_run_forex_revaluation)
        forex_layout.addWidget(self.run_forex_button)
        main_layout.addWidget(forex_group)

        # Placeholder for other period-end procedures
        main_layout.addStretch()

        return widget

    @Slot()
    def _on_run_forex_revaluation(self):
        if not self.app_core.current_user:
            QMessageBox.warning(self, "Authentication Error", "Please log in to perform this action.")
            return

        today = QDate.currentDate()
        last_day_prev_month = today.addDays(-today.day())
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Forex Revaluation")
        layout = QVBoxLayout(dialog)
        
        label = QLabel("Select the date as of which to revalue foreign currency balances.\nThis is typically a month-end, quarter-end, or year-end date.")
        layout.addWidget(label)
        
        date_edit = QDateEdit(last_day_prev_month)
        date_edit.setCalendarPopup(True)
        date_edit.setDisplayFormat("dd/MM/yyyy")
        layout.addWidget(date_edit)
        
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            reval_date = date_edit.date().toPython()
            confirm_msg = (f"This will calculate and post unrealized foreign exchange gains/losses for all open items as of {reval_date.strftime('%Y-%m-%d')}.\n\n"
                           "A reversing journal entry will also be posted for the following day.\n\n"
                           "Do you want to continue?")
            reply = QMessageBox.question(self, "Confirm Forex Revaluation", confirm_msg, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)

            if reply == QMessageBox.StandardButton.Yes:
                if not hasattr(self.app_core, "forex_manager"):
                    QMessageBox.critical(self, "Error", "Forex Manager component is not available.")
                    return
                self.run_forex_button.setEnabled(False)
                self.run_forex_button.setText("Processing...")
                future = schedule_task_from_qt(self.app_core.forex_manager.create_unrealized_gain_loss_je(reval_date, self.app_core.current_user.id))
                if future:
                    future.add_done_callback(self._handle_forex_revaluation_result)
                else:
                    self.run_forex_button.setEnabled(True)
                    self.run_forex_button.setText("Run Forex Revaluation...")
                    QMessageBox.critical(self, "Error", "Failed to schedule the forex revaluation task.")

    def _handle_forex_revaluation_result(self, future):
        self.run_forex_button.setEnabled(True)
        self.run_forex_button.setText("Run Forex Revaluation...")
        try:
            result: Result[JournalEntry] = future.result()
            if result.is_success:
                if result.value:
                    QMessageBox.information(self, "Success", f"Foreign currency revaluation complete.\nJournal Entry '{result.value.entry_no}' and its reversal have been created and posted.")
                else:
                    QMessageBox.information(self, "Completed", "Foreign currency revaluation run successfully. No significant adjustments were needed.")
            else:
                QMessageBox.critical(self, "Error", f"Forex revaluation failed:\n{', '.join(result.errors)}")
        except Exception as e:
            self.app_core.logger.error(f"An unexpected error occurred during forex revaluation callback: {e}", exc_info=True)
            QMessageBox.critical(self, "Fatal Error", f"An unexpected error occurred: {str(e)}")

```

# app/utils/__init__.py
```py
# File: app/utils/__init__.py
from .converters import to_decimal
from .formatting import format_currency, format_date, format_datetime
from .json_helpers import json_converter, json_date_hook
from .pydantic_models import (
    AppBaseModel, UserAuditData, 
    AccountBaseData, AccountCreateData, AccountUpdateData,
    JournalEntryLineData, JournalEntryData,
    GSTReturnData, TaxCalculationResultData, GSTTransactionLineDetail,
    TransactionLineTaxData, TransactionTaxData,
    AccountValidationResult, AccountValidator, CompanySettingData,
    FiscalYearCreateData, FiscalYearData, FiscalPeriodData,
    CustomerBaseData, CustomerCreateData, CustomerUpdateData, CustomerSummaryData, CustomerData,
    VendorBaseData, VendorCreateData, VendorUpdateData, VendorSummaryData, VendorData,
    ProductBaseData, ProductCreateData, ProductUpdateData, ProductSummaryData, ProductData,
    SalesInvoiceLineBaseData, SalesInvoiceBaseData, SalesInvoiceCreateData, SalesInvoiceUpdateData, SalesInvoiceData, SalesInvoiceSummaryData,
    RoleData, UserSummaryData, UserRoleAssignmentData, UserBaseData, UserCreateInternalData, UserCreateData, UserUpdateData, UserPasswordChangeData,
    RoleCreateData, RoleUpdateData, PermissionData,
    PurchaseInvoiceLineBaseData, PurchaseInvoiceBaseData, PurchaseInvoiceCreateData, PurchaseInvoiceUpdateData, PurchaseInvoiceData, PurchaseInvoiceSummaryData,
    BankAccountBaseData, BankAccountCreateData, BankAccountUpdateData, BankAccountSummaryData,
    BankTransactionBaseData, BankTransactionCreateData, BankTransactionSummaryData,
    PaymentAllocationBaseData, PaymentBaseData, PaymentCreateData, PaymentSummaryData,
    AuditLogEntryData, DataChangeHistoryEntryData,
    BankReconciliationBaseData, BankReconciliationCreateData, BankReconciliationData,
    BankReconciliationSummaryData,
    DashboardKPIData,
    CSVImportErrorData
)
from .result import Result
from .validation import is_valid_uen

__all__ = [
    "to_decimal", "format_currency", "format_date", "format_datetime",
    "json_converter", "json_date_hook",
    "AppBaseModel", "UserAuditData", 
    "AccountBaseData", "AccountCreateData", "AccountUpdateData",
    "JournalEntryLineData", "JournalEntryData",
    "GSTReturnData", "TaxCalculationResultData", "GSTTransactionLineDetail",
    "TransactionLineTaxData", "TransactionTaxData",
    "AccountValidationResult", "AccountValidator", "CompanySettingData",
    "FiscalYearCreateData", "FiscalYearData", "FiscalPeriodData",
    "CustomerBaseData", "CustomerCreateData", "CustomerUpdateData", "CustomerSummaryData", "CustomerData",
    "VendorBaseData", "VendorCreateData", "VendorUpdateData", "VendorSummaryData", "VendorData",
    "ProductBaseData", "ProductCreateData", "ProductUpdateData", "ProductSummaryData", "ProductData",
    "SalesInvoiceLineBaseData", "SalesInvoiceBaseData", "SalesInvoiceCreateData", "SalesInvoiceUpdateData", "SalesInvoiceData", "SalesInvoiceSummaryData",
    "RoleData", "UserSummaryData", "UserRoleAssignmentData", "UserBaseData", "UserCreateInternalData", "UserCreateData", "UserUpdateData", "UserPasswordChangeData",
    "RoleCreateData", "RoleUpdateData", "PermissionData",
    "PurchaseInvoiceLineBaseData", "PurchaseInvoiceBaseData", "PurchaseInvoiceCreateData", "PurchaseInvoiceUpdateData", "PurchaseInvoiceData", "PurchaseInvoiceSummaryData",
    "BankAccountBaseData", "BankAccountCreateData", "BankAccountUpdateData", "BankAccountSummaryData",
    "BankTransactionBaseData", "BankTransactionCreateData", "BankTransactionSummaryData",
    "PaymentAllocationBaseData", "PaymentBaseData", "PaymentCreateData", "PaymentSummaryData",
    "AuditLogEntryData", "DataChangeHistoryEntryData",
    "BankReconciliationBaseData", "BankReconciliationCreateData", "BankReconciliationData",
    "BankReconciliationSummaryData",
    "DashboardKPIData",
    "CSVImportErrorData",
    "Result", "is_valid_uen"
]

```

# app/services/core_services.py
```py
# File: app/services/core_services.py
from typing import List, Optional, Any, TYPE_CHECKING
from sqlalchemy import select, update, text
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.core.sequence import Sequence
from app.models.core.configuration import Configuration
from app.models.core.company_setting import CompanySetting

if TYPE_CHECKING:
    from app.core.database_manager import DatabaseManager
    from app.core.application_core import ApplicationCore


class SequenceService:
    def __init__(self, db_manager: "DatabaseManager"):
        self.db_manager = db_manager

    async def get_sequence_by_name(self, name: str) -> Optional[Sequence]:
        async with self.db_manager.session() as session:
            stmt = select(Sequence).where(Sequence.sequence_name == name)
            result = await session.execute(stmt)
            return result.scalars().first()

    async def get_next_sequence(self, sequence_name: str) -> str:
        """
        Generates the next number in a sequence by calling the database function.
        """
        # This simplifies the Python-side logic significantly, relying on the robust DB function.
        db_func_call = text("SELECT core.get_next_sequence_value(:seq_name);")
        async with self.db_manager.session() as session:
            result = await session.execute(db_func_call, {"seq_name": sequence_name})
            next_val = result.scalar_one_or_none()
            if next_val is None:
                raise RuntimeError(f"Database function get_next_sequence_value failed for sequence '{sequence_name}'.")
            return str(next_val)

    async def save_sequence(self, sequence_obj: Sequence, session: Optional[AsyncSession] = None) -> Sequence:
        async def _save(sess: AsyncSession):
            sess.add(sequence_obj)
            await sess.flush()
            await sess.refresh(sequence_obj)
            return sequence_obj

        if session:
            return await _save(session)
        else:
            async with self.db_manager.session() as new_session: # type: ignore
                return await _save(new_session)

class ConfigurationService:
    def __init__(self, db_manager: "DatabaseManager"):
        self.db_manager = db_manager
    
    async def get_config_by_key(self, key: str) -> Optional[Configuration]:
        async with self.db_manager.session() as session:
            stmt = select(Configuration).where(Configuration.config_key == key)
            result = await session.execute(stmt)
            return result.scalars().first()

    async def get_config_value(self, key: str, default_value: Optional[str] = None) -> Optional[str]:
        """Fetches a configuration value by key, returning default if not found."""
        config_entry = await self.get_config_by_key(key)
        if config_entry and config_entry.config_value is not None:
            return config_entry.config_value
        return default_value

    async def save_config(self, config_obj: Configuration) -> Configuration:
        async with self.db_manager.session() as session:
            session.add(config_obj)
            await session.flush()
            await session.refresh(config_obj)
            return config_obj

class CompanySettingsService:
    def __init__(self, db_manager: "DatabaseManager", app_core: Optional["ApplicationCore"] = None):
        self.db_manager = db_manager
        self.app_core = app_core

    async def get_company_settings(self, settings_id: int = 1) -> Optional[CompanySetting]:
        async with self.db_manager.session() as session:
            return await session.get(CompanySetting, settings_id)

    async def save_company_settings(self, settings_obj: CompanySetting) -> CompanySetting:
        if self.app_core and self.app_core.current_user:
            settings_obj.updated_by_user_id = self.app_core.current_user.id # type: ignore
        async with self.db_manager.session() as session:
            session.add(settings_obj)
            await session.flush()
            await session.refresh(settings_obj)
            return settings_obj

```

# app/services/business_services.py
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

# app/core/application_core.py
```py
# File: app/core/application_core.py
from typing import Optional, Any, TYPE_CHECKING
from app.core.config_manager import ConfigManager
from app.core.database_manager import DatabaseManager 
from app.core.security_manager import SecurityManager
from app.core.module_manager import ModuleManager
from app.core.company_manager import CompanyManager

import logging 

if TYPE_CHECKING:
    from app.accounting.chart_of_accounts_manager import ChartOfAccountsManager
    from app.business_logic.customer_manager import CustomerManager 
    from app.business_logic.vendor_manager import VendorManager 
    from app.business_logic.product_manager import ProductManager
    from app.business_logic.bank_account_manager import BankAccountManager 
    from app.business_logic.bank_transaction_manager import BankTransactionManager
    from app.services.journal_service import JournalService
    from app.accounting.journal_entry_manager import JournalEntryManager
    from app.accounting.fiscal_period_manager import FiscalPeriodManager
    from app.accounting.currency_manager import CurrencyManager
    from app.accounting.forex_manager import ForexManager
    from app.business_logic.sales_invoice_manager import SalesInvoiceManager
    from app.business_logic.purchase_invoice_manager import PurchaseInvoiceManager
    from app.business_logic.payment_manager import PaymentManager
    from app.tax.gst_manager import GSTManager
    from app.tax.tax_calculator import TaxCalculator
    from app.tax.income_tax_manager import IncomeTaxManager
    from app.tax.withholding_tax_manager import WithholdingTaxManager
    from app.reporting.financial_statement_generator import FinancialStatementGenerator
    from app.reporting.report_engine import ReportEngine
    from app.reporting.dashboard_manager import DashboardManager
    
    from app.services.account_service import AccountService
    from app.services.fiscal_period_service import FiscalPeriodService
    from app.services.core_services import SequenceService, CompanySettingsService, ConfigurationService
    from app.services.tax_service import TaxCodeService, GSTReturnService 
    from app.services.accounting_services import (
        AccountTypeService, CurrencyService as CurrencyRepoService, 
        ExchangeRateService, FiscalYearService, DimensionService 
    )
    from app.services.business_services import (
        CustomerService, VendorService, ProductService, 
        SalesInvoiceService, PurchaseInvoiceService, InventoryMovementService,
        BankAccountService, BankTransactionService, PaymentService, 
        BankReconciliationService
    )
    from app.services.audit_services import AuditLogService

class ApplicationCore:
    def __init__(self, config_manager: ConfigManager, db_manager: DatabaseManager, minimal_init: bool = False):
        self.config_manager = config_manager
        self.db_manager = db_manager
        self.db_manager.app_core = self 
        
        self.logger = logging.getLogger("SGBookkeeperAppCore")
        if not self.logger.handlers:
            handler = logging.StreamHandler(); formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter); self.logger.addHandler(handler); self.logger.setLevel(logging.INFO) 
        if not hasattr(self.db_manager, 'logger') or self.db_manager.logger is None: self.db_manager.logger = self.logger

        self.security_manager = SecurityManager(self.db_manager)
        self.module_manager = ModuleManager(self)
        self._company_manager_instance: Optional[CompanyManager] = CompanyManager(self)

        # Service/Manager Placeholders
        self._account_service_instance: Optional["AccountService"] = None
        self._journal_service_instance: Optional["JournalService"] = None
        self._fiscal_period_service_instance: Optional["FiscalPeriodService"] = None
        self._fiscal_year_service_instance: Optional["FiscalYearService"] = None
        self._sequence_service_instance: Optional["SequenceService"] = None
        self._company_settings_service_instance: Optional["CompanySettingsService"] = None
        self._configuration_service_instance: Optional["ConfigurationService"] = None
        self._tax_code_service_instance: Optional["TaxCodeService"] = None
        self._gst_return_service_instance: Optional["GSTReturnService"] = None
        self._account_type_service_instance: Optional["AccountTypeService"] = None
        self._currency_repo_service_instance: Optional["CurrencyRepoService"] = None
        self._exchange_rate_service_instance: Optional["ExchangeRateService"] = None
        self._dimension_service_instance: Optional["DimensionService"] = None
        self._customer_service_instance: Optional["CustomerService"] = None
        self._vendor_service_instance: Optional["VendorService"] = None
        self._product_service_instance: Optional["ProductService"] = None
        self._sales_invoice_service_instance: Optional["SalesInvoiceService"] = None
        self._purchase_invoice_service_instance: Optional["PurchaseInvoiceService"] = None
        self._inventory_movement_service_instance: Optional["InventoryMovementService"] = None
        self._bank_account_service_instance: Optional["BankAccountService"] = None
        self._bank_transaction_service_instance: Optional["BankTransactionService"] = None
        self._payment_service_instance: Optional["PaymentService"] = None
        self._audit_log_service_instance: Optional["AuditLogService"] = None
        self._bank_reconciliation_service_instance: Optional["BankReconciliationService"] = None
        
        self._forex_manager_instance: Optional["ForexManager"] = None
        self._coa_manager_instance: Optional["ChartOfAccountsManager"] = None
        self._je_manager_instance: Optional["JournalEntryManager"] = None
        self._fp_manager_instance: Optional["FiscalPeriodManager"] = None
        self._currency_manager_instance: Optional["CurrencyManager"] = None
        self._gst_manager_instance: Optional["GSTManager"] = None
        self._tax_calculator_instance: Optional["TaxCalculator"] = None
        self._income_tax_manager_instance: Optional["IncomeTaxManager"] = None
        self._withholding_tax_manager_instance: Optional["WithholdingTaxManager"] = None
        self._financial_statement_generator_instance: Optional["FinancialStatementGenerator"] = None
        self._report_engine_instance: Optional["ReportEngine"] = None
        self._customer_manager_instance: Optional["CustomerManager"] = None
        self._vendor_manager_instance: Optional["VendorManager"] = None
        self._product_manager_instance: Optional["ProductManager"] = None
        self._sales_invoice_manager_instance: Optional["SalesInvoiceManager"] = None
        self._purchase_invoice_manager_instance: Optional["PurchaseInvoiceManager"] = None
        self._bank_account_manager_instance: Optional["BankAccountManager"] = None
        self._bank_transaction_manager_instance: Optional["BankTransactionManager"] = None
        self._payment_manager_instance: Optional["PaymentManager"] = None
        self._dashboard_manager_instance: Optional["DashboardManager"] = None
        
        if not minimal_init:
            self.logger.info("ApplicationCore initialized.")
        else:
            self.logger.info("ApplicationCore initialized in minimal mode.")

    async def startup(self):
        self.logger.info("ApplicationCore starting up...")
        
        db_config = self.config_manager.get_database_config()
        if not db_config.database or db_config.database == "sg_bookkeeper_default":
            self.logger.warning("No company database selected. Skipping full service and manager initialization.")
            return

        await self.db_manager.initialize() 
        
        # Instantiate all services upon startup
        from app.services.core_services import SequenceService, CompanySettingsService, ConfigurationService
        from app.services.account_service import AccountService
        from app.services.fiscal_period_service import FiscalPeriodService
        from app.services.accounting_services import AccountTypeService, CurrencyService as CurrencyRepoService, ExchangeRateService, FiscalYearService, DimensionService
        from app.services.tax_service import TaxCodeService, GSTReturnService 
        from app.services.business_services import CustomerService, VendorService, ProductService, SalesInvoiceService, PurchaseInvoiceService, InventoryMovementService, BankAccountService, BankTransactionService, PaymentService, BankReconciliationService
        from app.services.audit_services import AuditLogService
        from app.services.journal_service import JournalService 
        
        self._sequence_service_instance = SequenceService(self.db_manager)
        self._company_settings_service_instance = CompanySettingsService(self.db_manager, self)
        self._configuration_service_instance = ConfigurationService(self.db_manager)
        self._account_service_instance = AccountService(self.db_manager, self)
        self._fiscal_period_service_instance = FiscalPeriodService(self.db_manager)
        self._fiscal_year_service_instance = FiscalYearService(self.db_manager, self)
        self._account_type_service_instance = AccountTypeService(self.db_manager, self) 
        self._currency_repo_service_instance = CurrencyRepoService(self.db_manager, self)
        self._exchange_rate_service_instance = ExchangeRateService(self.db_manager, self)
        self._dimension_service_instance = DimensionService(self.db_manager, self)
        self._tax_code_service_instance = TaxCodeService(self.db_manager, self)
        self._gst_return_service_instance = GSTReturnService(self.db_manager, self)
        self._customer_service_instance = CustomerService(self.db_manager, self)
        self._vendor_service_instance = VendorService(self.db_manager, self) 
        self._product_service_instance = ProductService(self.db_manager, self)
        self._sales_invoice_service_instance = SalesInvoiceService(self.db_manager, self)
        self._purchase_invoice_service_instance = PurchaseInvoiceService(self.db_manager, self) 
        self._inventory_movement_service_instance = InventoryMovementService(self.db_manager, self) 
        self._bank_account_service_instance = BankAccountService(self.db_manager, self) 
        self._bank_transaction_service_instance = BankTransactionService(self.db_manager, self)
        self._payment_service_instance = PaymentService(self.db_manager, self) 
        self._audit_log_service_instance = AuditLogService(self.db_manager, self)
        self._bank_reconciliation_service_instance = BankReconciliationService(self.db_manager, self)
        self._journal_service_instance = JournalService(self.db_manager, self)
        
        self.module_manager.load_all_modules() 
        self.logger.info("ApplicationCore startup complete.")

    async def shutdown(self): 
        self.logger.info("ApplicationCore shutting down...")
        await self.db_manager.close_connections()
        self.logger.info("ApplicationCore shutdown complete.")

    @property
    def current_user(self): 
        return self.security_manager.get_current_user()

    # --- Service Properties ---
    @property
    def account_service(self) -> "AccountService": 
        if not self._account_service_instance: raise RuntimeError("AccountService not initialized.")
        return self._account_service_instance
    @property
    def journal_service(self) -> "JournalService": 
        if not self._journal_service_instance: raise RuntimeError("JournalService not initialized.")
        return self._journal_service_instance
    @property
    def fiscal_period_service(self) -> "FiscalPeriodService": 
        if not self._fiscal_period_service_instance: raise RuntimeError("FiscalPeriodService not initialized.")
        return self._fiscal_period_service_instance
    @property
    def fiscal_year_service(self) -> "FiscalYearService": 
        if not self._fiscal_year_service_instance: raise RuntimeError("FiscalYearService not initialized.")
        return self._fiscal_year_service_instance
    @property
    def sequence_service(self) -> "SequenceService": 
        if not self._sequence_service_instance: raise RuntimeError("SequenceService not initialized.")
        return self._sequence_service_instance
    @property
    def company_settings_service(self) -> "CompanySettingsService": 
        if not self._company_settings_service_instance: raise RuntimeError("CompanySettingsService not initialized.")
        return self._company_settings_service_instance
    @property
    def configuration_service(self) -> "ConfigurationService": 
        if not self._configuration_service_instance: raise RuntimeError("ConfigurationService not initialized.")
        return self._configuration_service_instance
    @property
    def tax_code_service(self) -> "TaxCodeService": 
        if not self._tax_code_service_instance: raise RuntimeError("TaxCodeService not initialized.")
        return self._tax_code_service_instance
    @property
    def gst_return_service(self) -> "GSTReturnService": 
        if not self._gst_return_service_instance: raise RuntimeError("GSTReturnService not initialized.")
        return self._gst_return_service_instance
    @property
    def account_type_service(self) -> "AccountTypeService":  
        if not self._account_type_service_instance: raise RuntimeError("AccountTypeService not initialized.")
        return self._account_type_service_instance 
    @property
    def currency_repo_service(self) -> "CurrencyRepoService": 
        if not self._currency_repo_service_instance: raise RuntimeError("CurrencyRepoService not initialized.")
        return self._currency_repo_service_instance 
    @property 
    def currency_service(self) -> "CurrencyRepoService": 
        if not self._currency_repo_service_instance: raise RuntimeError("CurrencyService (CurrencyRepoService) not initialized.")
        return self._currency_repo_service_instance
    @property
    def exchange_rate_service(self) -> "ExchangeRateService": 
        if not self._exchange_rate_service_instance: raise RuntimeError("ExchangeRateService not initialized.")
        return self._exchange_rate_service_instance 
    @property
    def dimension_service(self) -> "DimensionService": 
        if not self._dimension_service_instance: raise RuntimeError("DimensionService not initialized.")
        return self._dimension_service_instance
    @property
    def customer_service(self) -> "CustomerService": 
        if not self._customer_service_instance: raise RuntimeError("CustomerService not initialized.")
        return self._customer_service_instance
    @property
    def vendor_service(self) -> "VendorService": 
        if not self._vendor_service_instance: raise RuntimeError("VendorService not initialized.")
        return self._vendor_service_instance
    @property
    def product_service(self) -> "ProductService": 
        if not self._product_service_instance: raise RuntimeError("ProductService not initialized.")
        return self._product_service_instance
    @property
    def sales_invoice_service(self) -> "SalesInvoiceService": 
        if not self._sales_invoice_service_instance: raise RuntimeError("SalesInvoiceService not initialized.")
        return self._sales_invoice_service_instance
    @property
    def purchase_invoice_service(self) -> "PurchaseInvoiceService": 
        if not self._purchase_invoice_service_instance: raise RuntimeError("PurchaseInvoiceService not initialized.")
        return self._purchase_invoice_service_instance
    @property
    def inventory_movement_service(self) -> "InventoryMovementService": 
        if not self._inventory_movement_service_instance: raise RuntimeError("InventoryMovementService not initialized.")
        return self._inventory_movement_service_instance
    @property
    def bank_account_service(self) -> "BankAccountService": 
        if not self._bank_account_service_instance: raise RuntimeError("BankAccountService not initialized.")
        return self._bank_account_service_instance
    @property
    def bank_transaction_service(self) -> "BankTransactionService": 
        if not self._bank_transaction_service_instance: raise RuntimeError("BankTransactionService not initialized.")
        return self._bank_transaction_service_instance
    @property
    def payment_service(self) -> "PaymentService": 
        if not self._payment_service_instance: raise RuntimeError("PaymentService not initialized.")
        return self._payment_service_instance
    @property
    def audit_log_service(self) -> "AuditLogService": 
        if not self._audit_log_service_instance: raise RuntimeError("AuditLogService not initialized.")
        return self._audit_log_service_instance
    @property
    def bank_reconciliation_service(self) -> "BankReconciliationService":
        if not self._bank_reconciliation_service_instance: raise RuntimeError("BankReconciliationService not initialized.")
        return self._bank_reconciliation_service_instance

    # --- Manager Properties (Lazy Initialization) ---
    @property
    def company_manager(self) -> "CompanyManager":
        if not self._company_manager_instance: self._company_manager_instance = CompanyManager(self)
        return self._company_manager_instance
    @property
    def chart_of_accounts_manager(self) -> "ChartOfAccountsManager": 
        if not self._coa_manager_instance:
            from app.accounting.chart_of_accounts_manager import ChartOfAccountsManager
            self._coa_manager_instance = ChartOfAccountsManager(self)
        return self._coa_manager_instance
    @property 
    def accounting_service(self) -> "ChartOfAccountsManager": 
        return self.chart_of_accounts_manager
    @property
    def journal_entry_manager(self) -> "JournalEntryManager": 
        if not self._je_manager_instance:
            from app.accounting.journal_entry_manager import JournalEntryManager
            self._je_manager_instance = JournalEntryManager(self)
        return self._je_manager_instance
    @property
    def fiscal_period_manager(self) -> "FiscalPeriodManager": 
        if not self._fp_manager_instance:
            from app.accounting.fiscal_period_manager import FiscalPeriodManager
            self._fp_manager_instance = FiscalPeriodManager(self)
        return self._fp_manager_instance
    @property
    def currency_manager(self) -> "CurrencyManager": 
        if not self._currency_manager_instance:
            from app.accounting.currency_manager import CurrencyManager
            self._currency_manager_instance = CurrencyManager(self)
        return self._currency_manager_instance
    @property
    def forex_manager(self) -> "ForexManager":
        if not self._forex_manager_instance:
            from app.accounting.forex_manager import ForexManager
            self._forex_manager_instance = ForexManager(self)
        return self._forex_manager_instance
    @property
    def tax_calculator(self) -> "TaxCalculator": 
        if not self._tax_calculator_instance:
            from app.tax.tax_calculator import TaxCalculator
            self._tax_calculator_instance = TaxCalculator(self)
        return self._tax_calculator_instance 
    @property
    def gst_manager(self) -> "GSTManager": 
        if not self._gst_manager_instance:
            from app.tax.gst_manager import GSTManager
            self._gst_manager_instance = GSTManager(self)
        return self._gst_manager_instance 
    @property
    def income_tax_manager(self) -> "IncomeTaxManager":
        if not self._income_tax_manager_instance:
            from app.tax.income_tax_manager import IncomeTaxManager
            self._income_tax_manager_instance = IncomeTaxManager(self)
        return self._income_tax_manager_instance
    @property
    def withholding_tax_manager(self) -> "WithholdingTaxManager":
        if not self._withholding_tax_manager_instance:
            from app.tax.withholding_tax_manager import WithholdingTaxManager
            self._withholding_tax_manager_instance = WithholdingTaxManager(self)
        return self._withholding_tax_manager_instance
    @property
    def financial_statement_generator(self) -> "FinancialStatementGenerator": 
        if not self._financial_statement_generator_instance:
            from app.reporting.financial_statement_generator import FinancialStatementGenerator
            self._financial_statement_generator_instance = FinancialStatementGenerator(self)
        return self._financial_statement_generator_instance
    @property
    def report_engine(self) -> "ReportEngine": 
        if not self._report_engine_instance:
            from app.reporting.report_engine import ReportEngine
            self._report_engine_instance = ReportEngine(self)
        return self._report_engine_instance
    @property
    def dashboard_manager(self) -> "DashboardManager":
        if not self._dashboard_manager_instance:
            from app.reporting.dashboard_manager import DashboardManager
            self._dashboard_manager_instance = DashboardManager(self)
        return self._dashboard_manager_instance
    @property
    def customer_manager(self) -> "CustomerManager": 
        if not self._customer_manager_instance:
            from app.business_logic.customer_manager import CustomerManager
            self._customer_manager_instance = CustomerManager(self)
        return self._customer_manager_instance
    @property
    def vendor_manager(self) -> "VendorManager": 
        if not self._vendor_manager_instance:
            from app.business_logic.vendor_manager import VendorManager
            self._vendor_manager_instance = VendorManager(self)
        return self._vendor_manager_instance
    @property
    def product_manager(self) -> "ProductManager": 
        if not self._product_manager_instance:
            from app.business_logic.product_manager import ProductManager
            self._product_manager_instance = ProductManager(self)
        return self._product_manager_instance
    @property
    def sales_invoice_manager(self) -> "SalesInvoiceManager": 
        if not self._sales_invoice_manager_instance:
            from app.business_logic.sales_invoice_manager import SalesInvoiceManager
            self._sales_invoice_manager_instance = SalesInvoiceManager(self)
        return self._sales_invoice_manager_instance 
    @property
    def purchase_invoice_manager(self) -> "PurchaseInvoiceManager": 
        if not self._purchase_invoice_manager_instance:
            from app.business_logic.purchase_invoice_manager import PurchaseInvoiceManager
            self._purchase_invoice_manager_instance = PurchaseInvoiceManager(self)
        return self._purchase_invoice_manager_instance 
    @property
    def bank_account_manager(self) -> "BankAccountManager": 
        if not self._bank_account_manager_instance:
            from app.business_logic.bank_account_manager import BankAccountManager
            self._bank_account_manager_instance = BankAccountManager(self)
        return self._bank_account_manager_instance
    @property
    def bank_transaction_manager(self) -> "BankTransactionManager": 
        if not self._bank_transaction_manager_instance:
            from app.business_logic.bank_transaction_manager import BankTransactionManager
            self._bank_transaction_manager_instance = BankTransactionManager(self)
        return self._bank_transaction_manager_instance
    @property
    def payment_manager(self) -> "PaymentManager": 
        if not self._payment_manager_instance:
            from app.business_logic.payment_manager import PaymentManager
            self._payment_manager_instance = PaymentManager(self)
        return self._payment_manager_instance

```

# app/models/business/payment.py
```py
# File: app/models/business/payment.py
from sqlalchemy import Column, Integer, String, Date, Numeric, Text, ForeignKey, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import List, Optional, TYPE_CHECKING
import datetime
from decimal import Decimal

from app.models.base import Base, TimestampMixin
from app.models.business.bank_account import BankAccount
from app.models.accounting.currency import Currency
from app.models.core.user import User
from app.models.accounting.journal_entry import JournalEntry

if TYPE_CHECKING:
    from app.models.accounting.withholding_tax_certificate import WithholdingTaxCertificate

class Payment(Base, TimestampMixin):
    __tablename__ = 'payments'
    __table_args__ = (
        CheckConstraint("payment_type IN ('Customer Payment', 'Vendor Payment', 'Refund', 'Credit Note', 'Other')", name='ck_payments_payment_type'),
        CheckConstraint("payment_method IN ('Cash', 'Check', 'Bank Transfer', 'Credit Card', 'GIRO', 'PayNow', 'Other')", name='ck_payments_payment_method'),
        CheckConstraint("entity_type IN ('Customer', 'Vendor', 'Other')", name='ck_payments_entity_type'),
        CheckConstraint("status IN ('Draft', 'Approved', 'Completed', 'Voided', 'Returned')", name='ck_payments_status'),
        {'schema': 'business'}
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    payment_no: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    payment_type: Mapped[str] = mapped_column(String(20), nullable=False)
    payment_method: Mapped[str] = mapped_column(String(20), nullable=False)
    payment_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    entity_type: Mapped[str] = mapped_column(String(20), nullable=False)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    bank_account_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('business.bank_accounts.id'), nullable=True)
    currency_code: Mapped[str] = mapped_column(String(3), ForeignKey('accounting.currencies.code'), nullable=False)
    exchange_rate: Mapped[Decimal] = mapped_column(Numeric(15,6), default=Decimal(1))
    amount: Mapped[Decimal] = mapped_column(Numeric(15,2), nullable=False)
    reference: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cheque_no: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default='Draft', nullable=False)
    journal_entry_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('accounting.journal_entries.id'), nullable=True)

    created_by_user_id: Mapped[int] = mapped_column("created_by", Integer, ForeignKey('core.users.id'), nullable=False)
    updated_by_user_id: Mapped[int] = mapped_column("updated_by", Integer, ForeignKey('core.users.id'), nullable=False)
    
    bank_account: Mapped[Optional["BankAccount"]] = relationship("BankAccount")
    currency: Mapped["Currency"] = relationship("Currency")
    journal_entry: Mapped[Optional["JournalEntry"]] = relationship("JournalEntry")
    allocations: Mapped[List["PaymentAllocation"]] = relationship("PaymentAllocation", back_populates="payment", cascade="all, delete-orphan")
    created_by_user: Mapped["User"] = relationship("User", foreign_keys=[created_by_user_id])
    updated_by_user: Mapped["User"] = relationship("User", foreign_keys=[updated_by_user_id])
    
    wht_certificate: Mapped[Optional["WithholdingTaxCertificate"]] = relationship("WithholdingTaxCertificate", back_populates="payment", uselist=False, cascade="all, delete-orphan")

class PaymentAllocation(Base, TimestampMixin):
    __tablename__ = 'payment_allocations'
    __table_args__ = (
        CheckConstraint("document_type IN ('Sales Invoice', 'Purchase Invoice', 'Credit Note', 'Debit Note', 'Other')", name='ck_payment_allocations_document_type'),
        {'schema': 'business'}
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    payment_id: Mapped[int] = mapped_column(Integer, ForeignKey('business.payments.id', ondelete="CASCADE"), nullable=False)
    document_type: Mapped[str] = mapped_column(String(20), nullable=False)
    document_id: Mapped[int] = mapped_column(Integer, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(15,2), nullable=False)
    
    created_by_user_id: Mapped[int] = mapped_column("created_by", Integer, ForeignKey('core.users.id'), nullable=False)

    payment: Mapped["Payment"] = relationship("Payment", back_populates="allocations")

```

# app/models/accounting/withholding_tax_certificate.py
```py
# File: app/models/accounting/withholding_tax_certificate.py
from sqlalchemy import Column, Integer, String, Date, Numeric, Text, ForeignKey, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin
from app.models.business.vendor import Vendor 
from app.models.core.user import User
import datetime
from decimal import Decimal
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.business.payment import Payment

class WithholdingTaxCertificate(Base, TimestampMixin):
    __tablename__ = 'withholding_tax_certificates'
    __table_args__ = (
        CheckConstraint("status IN ('Draft', 'Issued', 'Voided')", name='ck_wht_certs_status'),
        {'schema': 'accounting'}
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    certificate_no: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    vendor_id: Mapped[int] = mapped_column(Integer, ForeignKey('business.vendors.id'), nullable=False)
    payment_id: Mapped[int] = mapped_column(Integer, ForeignKey('business.payments.id'), nullable=False, unique=True)
    
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(5,2), nullable=False)
    gross_payment_amount: Mapped[Decimal] = mapped_column(Numeric(15,2), nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(15,2), nullable=False)
    payment_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    nature_of_payment: Mapped[str] = mapped_column(String(200), nullable=False)
    
    status: Mapped[str] = mapped_column(String(20), default='Draft', nullable=False)
    issue_date: Mapped[Optional[datetime.date]] = mapped_column(Date, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_by_user_id: Mapped[int] = mapped_column("created_by", Integer, ForeignKey('core.users.id'), nullable=False)
    updated_by_user_id: Mapped[int] = mapped_column("updated_by", Integer, ForeignKey('core.users.id'), nullable=False)

    vendor: Mapped["Vendor"] = relationship(back_populates="wht_certificates")
    payment: Mapped["Payment"] = relationship("Payment", back_populates="wht_certificate")
    created_by_user: Mapped["User"] = relationship("User", foreign_keys=[created_by_user_id])
    updated_by_user: Mapped["User"] = relationship("User", foreign_keys=[updated_by_user_id])

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

class FinancialStatementGenerator:
    def __init__(self, app_core: "ApplicationCore"):
        self.app_core = app_core
        self._account_type_map_cache: Optional[Dict[str, AccountType]] = None

    async def _get_account_type_map(self) -> Dict[str, AccountType]:
        if self._account_type_map_cache is None:
             ats = await self.app_core.account_type_service.get_all()
             self._account_type_map_cache = {at.category: at for at in ats} 
        return self._account_type_map_cache

    async def _calculate_account_balances_for_report(self, accounts: List[Account], as_of_date: date) -> List[Dict[str, Any]]:
        result_list = []; acc_type_map = await self._get_account_type_map()
        for account in accounts:
            balance_value = await self.app_core.journal_service.get_account_balance(account.id, as_of_date); display_balance = balance_value 
            acc_detail = acc_type_map.get(account.account_type); is_debit_nature = acc_detail.is_debit_balance if acc_detail else (account.account_type in ['Asset', 'Expense'])
            if not is_debit_nature: display_balance = -balance_value 
            result_list.append({'id': account.id, 'code': account.code, 'name': account.name, 'balance': display_balance})
        return result_list

    async def _calculate_account_period_activity_for_report(self, accounts: List[Account], start_date: date, end_date: date) -> List[Dict[str, Any]]:
        result_list = []; acc_type_map = await self._get_account_type_map()
        for account in accounts:
            activity_value = await self.app_core.journal_service.get_account_balance_for_period(account.id, start_date, end_date); display_activity = activity_value
            acc_detail = acc_type_map.get(account.account_type); is_debit_nature = acc_detail.is_debit_balance if acc_detail else (account.account_type in ['Asset', 'Expense'])
            if not is_debit_nature: display_activity = -activity_value 
            result_list.append({'id': account.id, 'code': account.code, 'name': account.name, 'balance': display_activity})
        return result_list

    async def generate_balance_sheet(self, as_of_date: date, comparative_date: Optional[date] = None, include_zero_balances: bool = False) -> Dict[str, Any]:
        accounts = await self.app_core.account_service.get_all_active(); assets_orm = [a for a in accounts if a.account_type == 'Asset']; liabilities_orm = [a for a in accounts if a.account_type == 'Liability']; equity_orm = [a for a in accounts if a.account_type == 'Equity']
        asset_accounts = await self._calculate_account_balances_for_report(assets_orm, as_of_date); liability_accounts = await self._calculate_account_balances_for_report(liabilities_orm, as_of_date); equity_accounts = await self._calculate_account_balances_for_report(equity_orm, as_of_date)
        comp_asset_accs, comp_liab_accs, comp_equity_accs = None, None, None
        if comparative_date: comp_asset_accs = await self._calculate_account_balances_for_report(assets_orm, comparative_date); comp_liab_accs = await self._calculate_account_balances_for_report(liabilities_orm, comparative_date); comp_equity_accs = await self._calculate_account_balances_for_report(equity_orm, comparative_date)
        if not include_zero_balances:
            asset_accounts = [a for a in asset_accounts if a['balance'] != Decimal(0)]; liability_accounts = [a for a in liability_accounts if a['balance'] != Decimal(0)]; equity_accounts = [a for a in equity_accounts if a['balance'] != Decimal(0)]
            if comparative_date: 
                if comp_asset_accs: comp_asset_accs = [a for a in comp_asset_accs if a['balance'] != Decimal(0)]
                if comp_liab_accs: comp_liab_accs = [a for a in comp_liab_accs if a['balance'] != Decimal(0)]
                if comp_equity_accs: comp_equity_accs = [a for a in comp_equity_accs if a['balance'] != Decimal(0)]
        total_assets = sum(a['balance'] for a in asset_accounts); total_liabilities = sum(a['balance'] for a in liability_accounts); total_equity = sum(a['balance'] for a in equity_accounts)
        comp_total_assets = sum(a['balance'] for a in comp_asset_accs) if comp_asset_accs else None; comp_total_liabilities = sum(a['balance'] for a in comp_liab_accs) if comp_liab_accs else None; comp_total_equity = sum(a['balance'] for a in comp_equity_accs) if comp_equity_accs else None
        return {'title': 'Balance Sheet', 'report_date_description': f"As of {as_of_date.strftime('%d %b %Y')}",'as_of_date': as_of_date, 'comparative_date': comparative_date,'assets': {'accounts': asset_accounts, 'total': total_assets, 'comparative_accounts': comp_asset_accs, 'comparative_total': comp_total_assets},'liabilities': {'accounts': liability_accounts, 'total': total_liabilities, 'comparative_accounts': comp_liab_accs, 'comparative_total': comp_total_liabilities},'equity': {'accounts': equity_accounts, 'total': total_equity, 'comparative_accounts': comp_equity_accs, 'comparative_total': comp_total_equity},'total_liabilities_equity': total_liabilities + total_equity,'comparative_total_liabilities_equity': (comp_total_liabilities + comp_total_equity) if comparative_date and comp_total_liabilities is not None and comp_total_equity is not None else None,'is_balanced': abs(total_assets - (total_liabilities + total_equity)) < Decimal("0.01")}

    async def generate_profit_loss(self, start_date: date, end_date: date, comparative_start: Optional[date] = None, comparative_end: Optional[date] = None) -> Dict[str, Any]:
        accounts = await self.app_core.account_service.get_all_active(); revenues_orm = [a for a in accounts if a.account_type == 'Revenue']; expenses_orm = [a for a in accounts if a.account_type == 'Expense'] 
        revenue_accounts = await self._calculate_account_period_activity_for_report(revenues_orm, start_date, end_date); expense_accounts = await self._calculate_account_period_activity_for_report(expenses_orm, start_date, end_date)
        comp_rev_accs, comp_exp_accs = None, None
        if comparative_start and comparative_end: comp_rev_accs = await self._calculate_account_period_activity_for_report(revenues_orm, comparative_start, comparative_end); comp_exp_accs = await self._calculate_account_period_activity_for_report(expenses_orm, comparative_start, comparative_end)
        total_revenue = sum(a['balance'] for a in revenue_accounts); total_expenses = sum(a['balance'] for a in expense_accounts) 
        net_profit = total_revenue - total_expenses
        comp_total_revenue = sum(a['balance'] for a in comp_rev_accs) if comp_rev_accs else None; comp_total_expenses = sum(a['balance'] for a in comp_exp_accs) if comp_exp_accs else None
        comp_net_profit = (comp_total_revenue - comp_total_expenses) if comp_total_revenue is not None and comp_total_expenses is not None else None
        return {'title': 'Profit & Loss Statement', 'report_date_description': f"For the period {start_date.strftime('%d %b %Y')} to {end_date.strftime('%d %b %Y')}",'start_date': start_date, 'end_date': end_date, 'comparative_start': comparative_start, 'comparative_end': comparative_end,'revenue': {'accounts': revenue_accounts, 'total': total_revenue, 'comparative_accounts': comp_rev_accs, 'comparative_total': comp_total_revenue},'expenses': {'accounts': expense_accounts, 'total': total_expenses, 'comparative_accounts': comp_exp_accs, 'comparative_total': comp_total_expenses},'net_profit': net_profit, 'comparative_net_profit': comp_net_profit}

    async def generate_trial_balance(self, as_of_date: date) -> Dict[str, Any]:
        accounts = await self.app_core.account_service.get_all_active(); debit_accounts_list, credit_accounts_list = [], []; total_debits_val, total_credits_val = Decimal(0), Decimal(0) 
        acc_type_map = await self._get_account_type_map()
        for account in accounts:
            raw_balance = await self.app_core.journal_service.get_account_balance(account.id, as_of_date)
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
        start_date, end_date = fiscal_year.start_date, fiscal_year.end_date
        
        pl_data = await self.generate_profit_loss(start_date, end_date)
        net_profit_before_tax = pl_data.get('net_profit', Decimal(0))

        add_back_adjustments: List[Dict[str, Any]] = []
        less_adjustments: List[Dict[str, Any]] = []
        total_add_back = Decimal(0)
        total_less = Decimal(0)

        non_deductible_accounts = await self.app_core.account_service.get_accounts_by_tax_treatment('Non-Deductible')
        for account in non_deductible_accounts:
            activity = await self.app_core.journal_service.get_account_balance_for_period(account.id, start_date, end_date)
            if activity != Decimal(0):
                add_back_adjustments.append({'name': f"{account.code} - {account.name}", 'amount': activity})
                total_add_back += activity

        non_taxable_accounts = await self.app_core.account_service.get_accounts_by_tax_treatment('Non-Taxable Income')
        for account in non_taxable_accounts:
            activity = await self.app_core.journal_service.get_account_balance_for_period(account.id, start_date, end_date)
            if activity != Decimal(0):
                less_adjustments.append({'name': f"{account.code} - {account.name}", 'amount': abs(activity)})
                total_less += abs(activity)
        
        chargeable_income = net_profit_before_tax + total_add_back - total_less
        
        tax_rate_str = await self.app_core.configuration_service.get_config_value("CorpTaxRate_Default", "17.0")
        tax_rate = Decimal(tax_rate_str if tax_rate_str else "17.0")
        
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
        company = await self.app_core.company_settings_service.get_company_settings();
        if not company: raise ValueError("Company settings not found.")
        report_data: Dict[str, Any] = {'title': f"GST F5 Return for period {start_date.strftime('%d %b %Y')} to {end_date.strftime('%d %b %Y')}",'company_name': company.company_name,'gst_registration_no': company.gst_registration_no,'period_start': start_date, 'period_end': end_date,'standard_rated_supplies': Decimal(0), 'zero_rated_supplies': Decimal(0),'exempt_supplies': Decimal(0), 'total_supplies': Decimal(0),'taxable_purchases': Decimal(0), 'output_tax': Decimal(0),'input_tax': Decimal(0), 'tax_adjustments': Decimal(0), 'tax_payable': Decimal(0)}
        entries = await self.app_core.journal_service.get_posted_entries_by_date_range(start_date, end_date)
        for entry in entries:
            for line in entry.lines: 
                if not line.tax_code or not line.account: continue
                tax_code_info = await self.app_core.tax_code_service.get_tax_code(line.tax_code)
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
        account_orm = await self.app_core.account_service.get_by_id(account_id)
        if not account_orm:
            raise ValueError(f"Account with ID {account_id} not found.")

        ob_date = start_date - timedelta(days=1)
        opening_balance = await self.app_core.journal_service.get_account_balance(account_id, ob_date)

        lines: List[JournalEntryLine] = await self.app_core.journal_service.get_posted_lines_for_account_in_range(
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
        if dimension1_id:
            dim1 = await self.app_core.dimension_service.get_by_id(dimension1_id)
            if dim1: report_desc += f" (Dim1: {dim1.dimension_type}-{dim1.code})"
        if dimension2_id:
            dim2 = await self.app_core.dimension_service.get_by_id(dimension2_id)
            if dim2: report_desc += f" (Dim2: {dim2.dimension_type}-{dim2.code})"

        return {
            "title": "General Ledger", "report_date_description": report_desc,
            "account_code": account_orm.code, "account_name": account_orm.name,
            "start_date": start_date, "end_date": end_date,
            "opening_balance": opening_balance, "transactions": transactions_data,
            "closing_balance": closing_balance
        }

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
            elif title == "Statement of Cash Flows": return await self._export_cash_flow_to_pdf(report_data)
            else: return self._export_generic_table_to_pdf(report_data) 
        elif format_type == "excel":
            if title == "Balance Sheet": return await self._export_balance_sheet_to_excel(report_data)
            elif title == "Profit & Loss Statement": return await self._export_profit_loss_to_excel(report_data)
            elif title == "Trial Balance": return await self._export_trial_balance_to_excel(report_data)
            elif title == "General Ledger": return await self._export_general_ledger_to_excel(report_data)
            elif title == "Income Tax Computation": return await self._export_tax_computation_to_excel(report_data)
            elif title == "Statement of Cash Flows": return await self._export_cash_flow_to_excel(report_data)
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
                row = [Paragraph(f"  {acc['code']} - {acc['name']}", self.styles['AccountName']), Paragraph(self._format_decimal(acc['balance']), self.styles['Amount'])]
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

    async def _export_cash_flow_to_pdf(self, report_data: Dict[str, Any]) -> bytes:
        buffer = BytesIO(); company_name = await self._get_company_name(); report_title = report_data.get('title', "Statement of Cash Flows"); date_desc = report_data.get('report_date_description', "")
        doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=0.75*inch, leftMargin=0.75*inch, topMargin=1.25*inch, bottomMargin=0.75*inch)
        story: List[Any] = []; col_widths = [5*inch, 1.5*inch]; data: List[List[Any]] = []
        
        def add_row(desc: str, amt: Optional[Decimal] = None, indent: int = 0, is_bold: bool = False, is_header: bool = False, underline: bool = False):
            style_name = 'SectionHeader' if is_header else ('AccountNameBold' if is_bold else 'AccountName')
            amount_style_name = 'AmountBold' if is_bold else 'Amount'
            desc_p = Paragraph(f"{'&nbsp;'*4*indent}{desc}", self.styles[style_name])
            amt_str = ""
            if amt is not None:
                amt_str = f"({self._format_decimal(abs(amt))})" if amt < 0 else self._format_decimal(amt, show_blank_for_zero=(amt.is_zero()))
            amt_p = Paragraph(amt_str, self.styles[amount_style_name])
            data.append([desc_p, amt_p])
            if underline: data.append([Spacer(1, 0.02*inch), Paragraph('<underline offset="-2" width="100%"> </underline>', self.styles['Amount'])])

        add_row("Cash flows from operating activities", is_header=True)
        add_row("Net income", report_data.get('net_income'), indent=1)
        add_row("Adjustments to reconcile net income to net cash provided by operating activities:", indent=1, is_bold=True)
        for adj in report_data.get('cfo_adjustments', []): add_row(adj['name'], adj['amount'], indent=2)
        add_row("Net cash provided by (used in) operating activities", report_data.get('net_cfo'), indent=0, is_bold=True, underline=True)
        data.append([Spacer(1, 0.1*inch)]*2)
        add_row("Cash flows from investing activities", is_header=True)
        for adj in report_data.get('cfi_adjustments', []): add_row(adj['name'], adj['amount'], indent=2)
        add_row("Net cash provided by (used in) investing activities", report_data.get('net_cfi'), indent=0, is_bold=True, underline=True)
        data.append([Spacer(1, 0.1*inch)]*2)
        add_row("Cash flows from financing activities", is_header=True)
        for adj in report_data.get('cff_adjustments', []): add_row(adj['name'], adj['amount'], indent=2)
        add_row("Net cash provided by (used in) financing activities", report_data.get('net_cff'), indent=0, is_bold=True, underline=True)
        data.append([Spacer(1, 0.2*inch)]*2)
        add_row("Net increase (decrease) in cash", report_data.get('net_change_in_cash'), is_bold=True)
        add_row("Cash at beginning of period", report_data.get('cash_at_start'), underline="thin")
        add_row("Cash at end of period", report_data.get('cash_at_end'), is_bold=True, underline=True)
        
        table = Table(data, colWidths=col_widths); table.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'MIDDLE')])); story.append(table)
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

# app/business_logic/vendor_manager.py
```py
# File: app/business_logic/vendor_manager.py
from typing import List, Optional, Dict, Any, TYPE_CHECKING
from decimal import Decimal

from app.models.business.vendor import Vendor
from app.utils.result import Result
from app.utils.pydantic_models import VendorCreateData, VendorUpdateData, VendorSummaryData

if TYPE_CHECKING:
    from app.core.application_core import ApplicationCore
    from app.services.business_services import VendorService
    from app.services.account_service import AccountService
    from app.services.accounting_services import CurrencyService

class VendorManager:
    def __init__(self, app_core: "ApplicationCore"):
        self.app_core = app_core
        self.vendor_service: "VendorService" = self.app_core.vendor_service
        self.account_service: "AccountService" = self.app_core.account_service
        self.currency_service: "CurrencyService" = self.app_core.currency_service
        self.logger = self.app_core.logger 

    async def get_vendor_for_dialog(self, vendor_id: int) -> Optional[Vendor]:
        """ Fetches a full vendor ORM object for dialog population. """
        try:
            return await self.vendor_service.get_by_id(vendor_id)
        except Exception as e:
            self.logger.error(f"Error fetching vendor ID {vendor_id} for dialog: {e}", exc_info=True)
            return None

    async def get_vendors_for_listing(self, 
                                       active_only: bool = True,
                                       search_term: Optional[str] = None,
                                       page: int = 1,
                                       page_size: int = 50
                                      ) -> Result[List[VendorSummaryData]]:
        """ Fetches a list of vendor summaries for table display. """
        try:
            summaries: List[VendorSummaryData] = await self.vendor_service.get_all_summary(
                active_only=active_only,
                search_term=search_term,
                page=page,
                page_size=page_size
            )
            return Result.success(summaries)
        except Exception as e:
            self.logger.error(f"Error fetching vendor listing: {e}", exc_info=True)
            return Result.failure([f"Failed to retrieve vendor list: {str(e)}"])

    async def _validate_vendor_data(self, dto: VendorCreateData | VendorUpdateData, existing_vendor_id: Optional[int] = None) -> List[str]:
        """ Common validation logic for creating and updating vendors. """
        errors: List[str] = []

        if dto.vendor_code:
            existing_by_code = await self.vendor_service.get_by_code(dto.vendor_code)
            if existing_by_code and (existing_vendor_id is None or existing_by_code.id != existing_vendor_id):
                errors.append(f"Vendor code '{dto.vendor_code}' already exists.")
        else: 
            errors.append("Vendor code is required.") 
            
        if dto.name is None or not dto.name.strip(): 
            errors.append("Vendor name is required.")

        if dto.payables_account_id is not None:
            acc = await self.account_service.get_by_id(dto.payables_account_id)
            if not acc:
                errors.append(f"Payables account ID '{dto.payables_account_id}' not found.")
            elif acc.account_type != 'Liability': 
                errors.append(f"Account '{acc.code} - {acc.name}' is not a Liability account and cannot be used as payables account.")
            elif not acc.is_active:
                 errors.append(f"Payables account '{acc.code} - {acc.name}' is not active.")

        if dto.currency_code:
            curr = await self.currency_service.get_by_id(dto.currency_code) 
            if not curr:
                errors.append(f"Currency code '{dto.currency_code}' not found.")
            elif not curr.is_active:
                 errors.append(f"Currency '{dto.currency_code}' is not active.")
        else: 
             errors.append("Currency code is required.")
        return errors

    async def create_vendor(self, dto: VendorCreateData) -> Result[Vendor]:
        validation_errors = await self._validate_vendor_data(dto)
        if validation_errors:
            return Result.failure(validation_errors)

        try:
            vendor_orm = Vendor(
                vendor_code=dto.vendor_code, name=dto.name, legal_name=dto.legal_name,
                uen_no=dto.uen_no, gst_registered=dto.gst_registered, gst_no=dto.gst_no,
                withholding_tax_applicable=dto.withholding_tax_applicable,
                withholding_tax_rate=dto.withholding_tax_rate,
                contact_person=dto.contact_person, email=str(dto.email) if dto.email else None, phone=dto.phone,
                address_line1=dto.address_line1, address_line2=dto.address_line2,
                postal_code=dto.postal_code, city=dto.city, country=dto.country,
                payment_terms=dto.payment_terms, currency_code=dto.currency_code, 
                is_active=dto.is_active, vendor_since=dto.vendor_since, notes=dto.notes,
                bank_account_name=dto.bank_account_name, bank_account_number=dto.bank_account_number,
                bank_name=dto.bank_name, bank_branch=dto.bank_branch, bank_swift_code=dto.bank_swift_code,
                payables_account_id=dto.payables_account_id,
                created_by_user_id=dto.user_id,
                updated_by_user_id=dto.user_id
            )
            saved_vendor = await self.vendor_service.save(vendor_orm)
            return Result.success(saved_vendor)
        except Exception as e:
            self.logger.error(f"Error creating vendor '{dto.vendor_code}': {e}", exc_info=True)
            return Result.failure([f"An unexpected error occurred while creating the vendor: {str(e)}"])

    async def update_vendor(self, vendor_id: int, dto: VendorUpdateData) -> Result[Vendor]:
        existing_vendor = await self.vendor_service.get_by_id(vendor_id)
        if not existing_vendor:
            return Result.failure([f"Vendor with ID {vendor_id} not found."])

        validation_errors = await self._validate_vendor_data(dto, existing_vendor_id=vendor_id)
        if validation_errors:
            return Result.failure(validation_errors)

        try:
            update_data_dict = dto.model_dump(exclude={'id', 'user_id'}, exclude_unset=True)
            for key, value in update_data_dict.items():
                if hasattr(existing_vendor, key):
                    if key == 'email' and value is not None: 
                        setattr(existing_vendor, key, str(value))
                    else:
                        setattr(existing_vendor, key, value)
            
            existing_vendor.updated_by_user_id = dto.user_id
            
            updated_vendor = await self.vendor_service.save(existing_vendor)
            return Result.success(updated_vendor)
        except Exception as e:
            self.logger.error(f"Error updating vendor ID {vendor_id}: {e}", exc_info=True)
            return Result.failure([f"An unexpected error occurred while updating the vendor: {str(e)}"])

    async def toggle_vendor_active_status(self, vendor_id: int, user_id: int) -> Result[Vendor]:
        vendor = await self.vendor_service.get_by_id(vendor_id)
        if not vendor:
            return Result.failure([f"Vendor with ID {vendor_id} not found."])
        
        vendor_name_for_log = vendor.name 
        
        vendor.is_active = not vendor.is_active
        vendor.updated_by_user_id = user_id

        try:
            updated_vendor = await self.vendor_service.save(vendor)
            action = "activated" if updated_vendor.is_active else "deactivated"
            self.logger.info(f"Vendor '{vendor_name_for_log}' (ID: {vendor_id}) {action} by user ID {user_id}.")
            return Result.success(updated_vendor)
        except Exception as e:
            self.logger.error(f"Error toggling active status for vendor ID {vendor_id}: {e}", exc_info=True)
            return Result.failure([f"Failed to toggle active status for vendor: {str(e)}"])

```

# app/business_logic/payment_manager.py
```py
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

# app/business_logic/sales_invoice_manager.py
```py
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

# app/business_logic/purchase_invoice_manager.py
```py
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

# app/business_logic/bank_account_manager.py
```py
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

# app/business_logic/product_manager.py
```py
# File: app/business_logic/product_manager.py
from typing import List, Optional, Dict, Any, TYPE_CHECKING
from decimal import Decimal

from app.models.business.product import Product
from app.utils.result import Result
from app.utils.pydantic_models import ProductCreateData, ProductUpdateData, ProductSummaryData
from app.common.enums import ProductTypeEnum 

if TYPE_CHECKING:
    from app.core.application_core import ApplicationCore
    from app.services.business_services import ProductService
    from app.services.account_service import AccountService
    from app.services.tax_service import TaxCodeService

class ProductManager:
    def __init__(self, app_core: "ApplicationCore"):
        self.app_core = app_core
        self.product_service: "ProductService" = self.app_core.product_service
        self.account_service: "AccountService" = self.app_core.account_service
        self.tax_code_service: "TaxCodeService" = self.app_core.tax_code_service
        self.logger = self.app_core.logger 

    async def get_product_for_dialog(self, product_id: int) -> Optional[Product]:
        """ Fetches a full product/service ORM object for dialog population. """
        try:
            return await self.product_service.get_by_id(product_id)
        except Exception as e:
            self.logger.error(f"Error fetching product ID {product_id} for dialog: {e}", exc_info=True)
            return None

    async def get_products_for_listing(self, 
                                       active_only: bool = True,
                                       product_type_filter: Optional[ProductTypeEnum] = None,
                                       search_term: Optional[str] = None,
                                       page: int = 1,
                                       page_size: int = 50
                                      ) -> Result[List[ProductSummaryData]]:
        """ Fetches a list of product/service summaries for table display. """
        try:
            summaries: List[ProductSummaryData] = await self.product_service.get_all_summary(
                active_only=active_only,
                product_type_filter=product_type_filter,
                search_term=search_term,
                page=page,
                page_size=page_size
            )
            return Result.success(summaries)
        except Exception as e:
            self.logger.error(f"Error fetching product listing: {e}", exc_info=True)
            return Result.failure([f"Failed to retrieve product list: {str(e)}"])

    async def _validate_product_data(self, dto: ProductCreateData | ProductUpdateData, existing_product_id: Optional[int] = None) -> List[str]:
        """ Common validation logic for creating and updating products/services. """
        errors: List[str] = []

        if dto.product_code:
            existing_by_code = await self.product_service.get_by_code(dto.product_code)
            if existing_by_code and (existing_product_id is None or existing_by_code.id != existing_product_id):
                errors.append(f"Product code '{dto.product_code}' already exists.")
        else:
             errors.append("Product code is required.") 

        if not dto.name or not dto.name.strip():
            errors.append("Product name is required.") 

        account_ids_to_check = {
            "Sales Account": (dto.sales_account_id, ['Revenue']),
            "Purchase Account": (dto.purchase_account_id, ['Expense', 'Asset']), 
        }
        if dto.product_type == ProductTypeEnum.INVENTORY:
            account_ids_to_check["Inventory Account"] = (dto.inventory_account_id, ['Asset'])
        
        for acc_label, (acc_id, valid_types) in account_ids_to_check.items():
            if acc_id is not None:
                acc = await self.account_service.get_by_id(acc_id)
                if not acc:
                    errors.append(f"{acc_label} ID '{acc_id}' not found.")
                elif not acc.is_active:
                    errors.append(f"{acc_label} '{acc.code} - {acc.name}' is not active.")
                elif acc.account_type not in valid_types:
                    errors.append(f"{acc_label} '{acc.code} - {acc.name}' is not a valid type (Expected: {', '.join(valid_types)}).")

        if dto.tax_code is not None:
            tax_code_obj = await self.tax_code_service.get_tax_code(dto.tax_code)
            if not tax_code_obj:
                errors.append(f"Tax code '{dto.tax_code}' not found.")
            elif not tax_code_obj.is_active:
                errors.append(f"Tax code '{dto.tax_code}' is not active.")
        return errors

    async def create_product(self, dto: ProductCreateData) -> Result[Product]:
        validation_errors = await self._validate_product_data(dto)
        if validation_errors:
            return Result.failure(validation_errors)

        try:
            product_orm = Product(
                product_code=dto.product_code, name=dto.name, description=dto.description,
                product_type=dto.product_type.value, 
                category=dto.category, unit_of_measure=dto.unit_of_measure, barcode=dto.barcode,
                sales_price=dto.sales_price, purchase_price=dto.purchase_price,
                sales_account_id=dto.sales_account_id, purchase_account_id=dto.purchase_account_id,
                inventory_account_id=dto.inventory_account_id,
                tax_code=dto.tax_code, is_active=dto.is_active,
                min_stock_level=dto.min_stock_level, reorder_point=dto.reorder_point,
                created_by_user_id=dto.user_id,
                updated_by_user_id=dto.user_id
            )
            saved_product = await self.product_service.save(product_orm)
            return Result.success(saved_product)
        except Exception as e:
            self.logger.error(f"Error creating product '{dto.product_code}': {e}", exc_info=True)
            return Result.failure([f"An unexpected error occurred while creating the product/service: {str(e)}"])

    async def update_product(self, product_id: int, dto: ProductUpdateData) -> Result[Product]:
        existing_product = await self.product_service.get_by_id(product_id)
        if not existing_product:
            return Result.failure([f"Product/Service with ID {product_id} not found."])

        validation_errors = await self._validate_product_data(dto, existing_product_id=product_id)
        if validation_errors:
            return Result.failure(validation_errors)

        try:
            update_data_dict = dto.model_dump(exclude={'id', 'user_id'}, exclude_unset=True)
            for key, value in update_data_dict.items():
                if hasattr(existing_product, key):
                    if key == "product_type" and isinstance(value, ProductTypeEnum): 
                        setattr(existing_product, key, value.value)
                    else:
                        setattr(existing_product, key, value)
            
            existing_product.updated_by_user_id = dto.user_id
            
            updated_product = await self.product_service.save(existing_product)
            return Result.success(updated_product)
        except Exception as e:
            self.logger.error(f"Error updating product ID {product_id}: {e}", exc_info=True)
            return Result.failure([f"An unexpected error occurred while updating the product/service: {str(e)}"])

    async def toggle_product_active_status(self, product_id: int, user_id: int) -> Result[Product]:
        product = await self.product_service.get_by_id(product_id)
        if not product:
            return Result.failure([f"Product/Service with ID {product_id} not found."])
        
        product_name_for_log = product.name 
        
        product.is_active = not product.is_active
        product.updated_by_user_id = user_id

        try:
            updated_product = await self.product_service.save(product)
            action = "activated" if updated_product.is_active else "deactivated"
            self.logger.info(f"Product/Service '{product_name_for_log}' (ID: {product_id}) {action} by user ID {user_id}.")
            return Result.success(updated_product)
        except Exception as e:
            self.logger.error(f"Error toggling active status for product ID {product_id}: {e}", exc_info=True)
            return Result.failure([f"Failed to toggle active status for product/service: {str(e)}"])

```

# app/business_logic/bank_transaction_manager.py
```py
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

# app/business_logic/customer_manager.py
```py
# File: app/business_logic/customer_manager.py
from typing import List, Optional, Dict, Any, TYPE_CHECKING
from decimal import Decimal

from app.models.business.customer import Customer
from app.utils.result import Result
from app.utils.pydantic_models import CustomerCreateData, CustomerUpdateData, CustomerSummaryData

if TYPE_CHECKING:
    from app.core.application_core import ApplicationCore
    from app.services.business_services import CustomerService
    from app.services.account_service import AccountService 
    from app.services.accounting_services import CurrencyService 

class CustomerManager:
    def __init__(self, app_core: "ApplicationCore"):
        self.app_core = app_core
        self.customer_service: "CustomerService" = self.app_core.customer_service
        self.account_service: "AccountService" = self.app_core.account_service
        self.currency_service: "CurrencyService" = self.app_core.currency_service
        self.logger = self.app_core.logger

    async def get_customer_for_dialog(self, customer_id: int) -> Optional[Customer]:
        """ Fetches a full customer ORM object for dialog population. """
        try:
            return await self.customer_service.get_by_id(customer_id)
        except Exception as e:
            self.logger.error(f"Error fetching customer ID {customer_id} for dialog: {e}", exc_info=True)
            return None

    async def get_customers_for_listing(self, 
                                       active_only: bool = True,
                                       search_term: Optional[str] = None,
                                       page: int = 1,
                                       page_size: int = 50
                                      ) -> Result[List[CustomerSummaryData]]:
        """ Fetches a list of customer summaries for table display. """
        try:
            summaries: List[CustomerSummaryData] = await self.customer_service.get_all_summary(
                active_only=active_only,
                search_term=search_term,
                page=page,
                page_size=page_size
            )
            return Result.success(summaries)
        except Exception as e:
            self.logger.error(f"Error fetching customer listing: {e}", exc_info=True)
            return Result.failure([f"Failed to retrieve customer list: {str(e)}"])

    async def _validate_customer_data(self, dto: CustomerCreateData | CustomerUpdateData, existing_customer_id: Optional[int] = None) -> List[str]:
        errors: List[str] = []

        if dto.customer_code:
            existing_by_code = await self.customer_service.get_by_code(dto.customer_code)
            if existing_by_code and (existing_customer_id is None or existing_by_code.id != existing_customer_id):
                errors.append(f"Customer code '{dto.customer_code}' already exists.")
        else: 
            errors.append("Customer code is required.") 
            
        if dto.name is None or not dto.name.strip(): 
            errors.append("Customer name is required.")

        if dto.receivables_account_id is not None:
            acc = await self.account_service.get_by_id(dto.receivables_account_id)
            if not acc:
                errors.append(f"Receivables account ID '{dto.receivables_account_id}' not found.")
            elif acc.account_type != 'Asset': 
                errors.append(f"Account '{acc.code} - {acc.name}' is not an Asset account and cannot be used as receivables account.")
            elif not acc.is_active:
                 errors.append(f"Receivables account '{acc.code} - {acc.name}' is not active.")

        if dto.currency_code:
            curr = await self.currency_service.get_by_id(dto.currency_code) 
            if not curr:
                errors.append(f"Currency code '{dto.currency_code}' not found.")
            elif not curr.is_active:
                 errors.append(f"Currency '{dto.currency_code}' is not active.")
        else: 
             errors.append("Currency code is required.")
        return errors

    async def create_customer(self, dto: CustomerCreateData) -> Result[Customer]:
        validation_errors = await self._validate_customer_data(dto)
        if validation_errors:
            return Result.failure(validation_errors)

        try:
            customer_orm = Customer(
                customer_code=dto.customer_code, name=dto.name, legal_name=dto.legal_name,
                uen_no=dto.uen_no, gst_registered=dto.gst_registered, gst_no=dto.gst_no,
                contact_person=dto.contact_person, email=str(dto.email) if dto.email else None, phone=dto.phone,
                address_line1=dto.address_line1, address_line2=dto.address_line2,
                postal_code=dto.postal_code, city=dto.city, country=dto.country,
                credit_terms=dto.credit_terms, credit_limit=dto.credit_limit,
                currency_code=dto.currency_code, is_active=dto.is_active,
                customer_since=dto.customer_since, notes=dto.notes,
                receivables_account_id=dto.receivables_account_id,
                created_by_user_id=dto.user_id,
                updated_by_user_id=dto.user_id
            )
            saved_customer = await self.customer_service.save(customer_orm)
            return Result.success(saved_customer)
        except Exception as e:
            self.logger.error(f"Error creating customer '{dto.customer_code}': {e}", exc_info=True)
            return Result.failure([f"An unexpected error occurred while creating the customer: {str(e)}"])

    async def update_customer(self, customer_id: int, dto: CustomerUpdateData) -> Result[Customer]:
        existing_customer = await self.customer_service.get_by_id(customer_id)
        if not existing_customer:
            return Result.failure([f"Customer with ID {customer_id} not found."])

        validation_errors = await self._validate_customer_data(dto, existing_customer_id=customer_id)
        if validation_errors:
            return Result.failure(validation_errors)

        try:
            update_data_dict = dto.model_dump(exclude={'id', 'user_id'}, exclude_unset=True)
            for key, value in update_data_dict.items():
                if hasattr(existing_customer, key):
                    if key == 'email' and value is not None: 
                        setattr(existing_customer, key, str(value))
                    else:
                        setattr(existing_customer, key, value)
            
            existing_customer.updated_by_user_id = dto.user_id
            
            updated_customer = await self.customer_service.save(existing_customer)
            return Result.success(updated_customer)
        except Exception as e:
            self.logger.error(f"Error updating customer ID {customer_id}: {e}", exc_info=True)
            return Result.failure([f"An unexpected error occurred while updating the customer: {str(e)}"])

    async def toggle_customer_active_status(self, customer_id: int, user_id: int) -> Result[Customer]:
        customer = await self.customer_service.get_by_id(customer_id)
        if not customer:
            return Result.failure([f"Customer with ID {customer_id} not found."])
        
        customer.is_active = not customer.is_active
        customer.updated_by_user_id = user_id

        try:
            updated_customer = await self.customer_service.save(customer)
            action = "activated" if updated_customer.is_active else "deactivated"
            self.logger.info(f"Customer '{updated_customer.name}' (ID: {customer_id}) {action} by user ID {user_id}.")
            return Result.success(updated_customer)
        except Exception as e:
            self.logger.error(f"Error toggling active status for customer ID {customer_id}: {e}", exc_info=True)
            return Result.failure([f"Failed to toggle active status for customer: {str(e)}"])

```

# app/accounting/__init__.py
```py
# File: app/accounting/__init__.py
from .chart_of_accounts_manager import ChartOfAccountsManager
from .journal_entry_manager import JournalEntryManager
from .fiscal_period_manager import FiscalPeriodManager
from .currency_manager import CurrencyManager
from .forex_manager import ForexManager

__all__ = [
    "ChartOfAccountsManager",
    "JournalEntryManager",
    "FiscalPeriodManager",
    "CurrencyManager",
    "ForexManager",
]

```

# app/accounting/journal_entry_manager.py
```py
# File: app/accounting/journal_entry_manager.py
from typing import List, Optional, Any, Dict, TYPE_CHECKING
from decimal import Decimal
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta # type: ignore

from sqlalchemy import select 
from sqlalchemy.ext.asyncio import AsyncSession 
from sqlalchemy.orm import selectinload

from app.models import JournalEntry, JournalEntryLine, RecurringPattern, FiscalPeriod, Account
from app.models.business.bank_account import BankAccount
from app.models.business.bank_transaction import BankTransaction
from app.utils.result import Result
from app.utils.pydantic_models import JournalEntryData, JournalEntryLineData 
from app.common.enums import JournalTypeEnum, BankTransactionTypeEnum

if TYPE_CHECKING:
    from app.core.application_core import ApplicationCore
    from app.services.journal_service import JournalService 
    from app.services.account_service import AccountService
    from app.services.fiscal_period_service import FiscalPeriodService

class JournalEntryManager:
    def __init__(self, app_core: "ApplicationCore"):
        self.app_core = app_core
        self.journal_service: "JournalService" = app_core.journal_service
        self.account_service: "AccountService" = app_core.account_service
        self.fiscal_period_service: "FiscalPeriodService" = app_core.fiscal_period_service
        self.logger = app_core.logger

    # ... (All other methods like create_journal_entry, post_journal_entry, etc. remain unchanged) ...
    async def create_journal_entry(self, entry_data: JournalEntryData, session: Optional[AsyncSession] = None) -> Result[JournalEntry]:
        async def _create_je_logic(current_session: AsyncSession):
            fiscal_period_stmt = select(FiscalPeriod).where(FiscalPeriod.start_date <= entry_data.entry_date, FiscalPeriod.end_date >= entry_data.entry_date, FiscalPeriod.status == 'Open')
            fiscal_period_res = await current_session.execute(fiscal_period_stmt); fiscal_period = fiscal_period_res.scalars().first()
            if not fiscal_period: return Result.failure([f"No open fiscal period for entry date {entry_data.entry_date} or period not open."])
            
            entry_no_str = await self.app_core.db_manager.execute_scalar("SELECT core.get_next_sequence_value($1);", "journal_entry", session=current_session)
            if not entry_no_str: return Result.failure(["Failed to generate journal entry number."])
            
            current_user_id = entry_data.user_id
            journal_entry_orm = JournalEntry(entry_no=entry_no_str, journal_type=entry_data.journal_type, entry_date=entry_data.entry_date, fiscal_period_id=fiscal_period.id, description=entry_data.description, reference=entry_data.reference, is_recurring=entry_data.is_recurring, recurring_pattern_id=entry_data.recurring_pattern_id, is_posted=False, source_type=entry_data.source_type, source_id=entry_data.source_id, created_by_user_id=current_user_id, updated_by_user_id=current_user_id)
            for i, line_dto in enumerate(entry_data.lines, 1):
                account_stmt = select(Account).where(Account.id == line_dto.account_id); account_res = await current_session.execute(account_stmt); account = account_res.scalars().first()
                if not account or not account.is_active: return Result.failure([f"Invalid or inactive account ID {line_dto.account_id} on line {i}."])
                line_orm = JournalEntryLine(line_number=i, account_id=line_dto.account_id, description=line_dto.description, debit_amount=line_dto.debit_amount, credit_amount=line_dto.credit_amount, currency_code=line_dto.currency_code, exchange_rate=line_dto.exchange_rate, tax_code=line_dto.tax_code, tax_amount=line_dto.tax_amount, dimension1_id=line_dto.dimension1_id, dimension2_id=line_dto.dimension2_id)
                journal_entry_orm.lines.append(line_orm)
            current_session.add(journal_entry_orm); await current_session.flush(); await current_session.refresh(journal_entry_orm)
            if journal_entry_orm.lines: await current_session.refresh(journal_entry_orm, attribute_names=['lines'])
            return Result.success(journal_entry_orm)
        if session: return await _create_je_logic(session)
        else:
            try:
                async with self.app_core.db_manager.session() as new_session: # type: ignore
                    return await _create_je_logic(new_session)
            except Exception as e: 
                self.logger.error(f"Error creating JE with new session: {e}", exc_info=True)
                return Result.failure([f"Failed to save JE: {str(e)}"])

    async def update_journal_entry(self, entry_id: int, entry_data: JournalEntryData) -> Result[JournalEntry]:
        async with self.app_core.db_manager.session() as session: # type: ignore
            existing_entry = await session.get(JournalEntry, entry_id, options=[selectinload(JournalEntry.lines)])
            if not existing_entry: return Result.failure([f"JE ID {entry_id} not found for update."])
            if existing_entry.is_posted: return Result.failure([f"Cannot update posted JE: {existing_entry.entry_no}."])
            fp_stmt = select(FiscalPeriod).where(FiscalPeriod.start_date <= entry_data.entry_date, FiscalPeriod.end_date >= entry_data.entry_date, FiscalPeriod.status == 'Open')
            fp_res = await session.execute(fp_stmt); fiscal_period = fp_res.scalars().first()
            if not fiscal_period: return Result.failure([f"No open fiscal period for new entry date {entry_data.entry_date} or period not open."])
            current_user_id = entry_data.user_id
            existing_entry.journal_type = entry_data.journal_type; existing_entry.entry_date = entry_data.entry_date
            existing_entry.fiscal_period_id = fiscal_period.id; existing_entry.description = entry_data.description
            existing_entry.reference = entry_data.reference; existing_entry.is_recurring = entry_data.is_recurring
            existing_entry.recurring_pattern_id = entry_data.recurring_pattern_id
            existing_entry.source_type = entry_data.source_type; existing_entry.source_id = entry_data.source_id
            existing_entry.updated_by_user_id = current_user_id
            for line in list(existing_entry.lines): await session.delete(line)
            existing_entry.lines.clear(); await session.flush() 
            new_lines_orm: List[JournalEntryLine] = []
            for i, line_dto in enumerate(entry_data.lines, 1):
                acc_stmt = select(Account).where(Account.id == line_dto.account_id); acc_res = await session.execute(acc_stmt); account = acc_res.scalars().first()
                if not account or not account.is_active: raise ValueError(f"Invalid or inactive account ID {line_dto.account_id} on line {i} during update.")
                new_lines_orm.append(JournalEntryLine(line_number=i, account_id=line_dto.account_id, description=line_dto.description, debit_amount=line_dto.debit_amount, credit_amount=line_dto.credit_amount, currency_code=line_dto.currency_code, exchange_rate=line_dto.exchange_rate, tax_code=line_dto.tax_code, tax_amount=line_dto.tax_amount, dimension1_id=line_dto.dimension1_id, dimension2_id=line_dto.dimension2_id))
            existing_entry.lines.extend(new_lines_orm); session.add(existing_entry) 
            try:
                await session.flush(); await session.refresh(existing_entry)
                if existing_entry.lines: await session.refresh(existing_entry, attribute_names=['lines'])
                return Result.success(existing_entry)
            except Exception as e: self.logger.error(f"Error updating JE ID {entry_id}: {e}", exc_info=True); return Result.failure([f"Failed to update JE: {str(e)}"])

    async def post_journal_entry(self, entry_id: int, user_id: int, session: Optional[AsyncSession] = None) -> Result[JournalEntry]:
        async def _post_je_logic(current_session: AsyncSession):
            entry = await current_session.get(JournalEntry, entry_id, options=[selectinload(JournalEntry.lines).selectinload(JournalEntryLine.account)])
            if not entry: return Result.failure([f"JE ID {entry_id} not found."])
            if entry.is_posted: return Result.failure([f"JE '{entry.entry_no}' is already posted."])
            fiscal_period = await current_session.get(FiscalPeriod, entry.fiscal_period_id)
            if not fiscal_period or fiscal_period.status != 'Open': return Result.failure([f"Cannot post. Fiscal period not open. Status: {fiscal_period.status if fiscal_period else 'Unknown'}."])
            entry.is_posted = True; entry.updated_by_user_id = user_id; current_session.add(entry); await current_session.flush()
            for line in entry.lines:
                if line.account and line.account.is_bank_account:
                    bank_account_stmt = select(BankAccount).where(BankAccount.gl_account_id == line.account_id)
                    bank_account_res = await current_session.execute(bank_account_stmt); linked_bank_account = bank_account_res.scalars().first()
                    if linked_bank_account:
                        bank_txn_amount = line.debit_amount - line.credit_amount; bank_txn_type_enum: BankTransactionTypeEnum
                        if bank_txn_amount > Decimal(0): bank_txn_type_enum = BankTransactionTypeEnum.DEPOSIT
                        elif bank_txn_amount < Decimal(0): bank_txn_type_enum = BankTransactionTypeEnum.WITHDRAWAL
                        else: continue 
                        new_bank_txn = BankTransaction(bank_account_id=linked_bank_account.id, transaction_date=entry.entry_date, value_date=entry.entry_date, transaction_type=bank_txn_type_enum.value, description=f"JE: {entry.entry_no} - {line.description or entry.description or 'Journal Posting'}", reference=entry.entry_no, amount=bank_txn_amount, is_from_statement=False, is_reconciled=False, journal_entry_id=entry.id, created_by_user_id=user_id, updated_by_user_id=user_id)
                        current_session.add(new_bank_txn); self.logger.info(f"Auto-created BankTransaction for JE line {line.id} (Account: {line.account.code}) linked to Bank Account {linked_bank_account.id}")
                    else: self.logger.warning(f"JE line {line.id} affects GL account {line.account.code} which is_bank_account=True, but no BankAccount record is linked to it. No BankTransaction created.")
            await current_session.flush(); await current_session.refresh(entry); return Result.success(entry)
        if session: return await _post_je_logic(session)
        else:
            try:
                async with self.app_core.db_manager.session() as new_session: # type: ignore
                    return await _post_je_logic(new_session)
            except Exception as e: self.logger.error(f"Error posting JE ID {entry_id} with new session: {e}", exc_info=True); return Result.failure([f"Failed to post JE: {str(e)}"])

    async def create_reversing_entry(self, original_entry_id: int, reversal_date: date, user_id: int, description: Optional[str] = None) -> Result[JournalEntry]:
        async with self.app_core.db_manager.session() as session: # type: ignore
            original_entry = await session.get(JournalEntry, original_entry_id, options=[selectinload(JournalEntry.lines)])
            if not original_entry: return Result.failure([f"JE ID {original_entry_id} not found for reversal."])
            if not original_entry.is_posted: return Result.failure(["Only posted entries can be reversed."])
            if original_entry.is_reversed or original_entry.reversing_entry_id is not None: return Result.failure([f"Entry '{original_entry.entry_no}' is already reversed."])
            
            reversal_lines_dto = [JournalEntryLineData(account_id=line.account_id, description=f"Reversal: {line.description or ''}", debit_amount=line.credit_amount, credit_amount=line.debit_amount, currency_code=line.currency_code, exchange_rate=line.exchange_rate, tax_code=line.tax_code, tax_amount=-(line.tax_amount or Decimal(0)), dimension1_id=line.dimension1_id, dimension2_id=line.dimension2_id) for line in original_entry.lines]
            reversal_desc = description or f"Reversal of entry {original_entry.entry_no}"
            
            reversal_je_data = JournalEntryData(journal_type=original_entry.journal_type, entry_date=reversal_date, description=reversal_desc, reference=f"REV:{original_entry.entry_no}", user_id=user_id, lines=reversal_lines_dto, source_type="JournalEntryReversalSource", source_id=original_entry.id)
            
            create_reversal_result = await self.create_journal_entry(reversal_je_data, session=session)
            if not create_reversal_result.is_success or not create_reversal_result.value: return Result.failure(["Failed to create reversal JE."] + create_reversal_result.errors)
            
            reversal_je_orm = create_reversal_result.value
            original_entry.is_reversed = True; original_entry.reversing_entry_id = reversal_je_orm.id
            original_entry.updated_by_user_id = user_id; session.add(original_entry)
            
            try:
                await session.flush(); await session.refresh(reversal_je_orm)
                if reversal_je_orm.lines: await session.refresh(reversal_je_orm, attribute_names=['lines'])
                return Result.success(reversal_je_orm)
            except Exception as e: self.logger.error(f"Error reversing JE ID {original_entry_id} (flush/commit stage): {e}", exc_info=True); return Result.failure([f"Failed to finalize reversal: {str(e)}"])

    async def reverse_journal_entry(self, entry_id: int, reversal_date: date, description: Optional[str], user_id: int) -> Result[JournalEntry]:
        return await self.create_reversing_entry(entry_id, reversal_date, user_id, description)

    def _calculate_next_generation_date(self, last_date: date, frequency: str, interval: int, day_of_month: Optional[int] = None, day_of_week: Optional[int] = None) -> date:
        next_date = last_date
        if frequency == 'Monthly':
            next_date = last_date + relativedelta(months=interval)
            if day_of_month:
                try: next_date = next_date.replace(day=day_of_month)
                except ValueError: next_date = next_date + relativedelta(day=31) 
        elif frequency == 'Yearly':
            next_date = last_date + relativedelta(years=interval)
            if day_of_month:
                try: next_date = next_date.replace(day=day_of_month, month=last_date.month)
                except ValueError: next_date = next_date.replace(month=last_date.month) + relativedelta(day=31)
        elif frequency == 'Weekly':
            next_date = last_date + relativedelta(weeks=interval)
            if day_of_week is not None: current_weekday = next_date.weekday(); days_to_add = (day_of_week - current_weekday + 7) % 7; next_date += timedelta(days=days_to_add)
        elif frequency == 'Daily': next_date = last_date + relativedelta(days=interval)
        elif frequency == 'Quarterly':
            next_date = last_date + relativedelta(months=interval * 3)
            if day_of_month:
                try: next_date = next_date.replace(day=day_of_month)
                except ValueError: next_date = next_date + relativedelta(day=31)
        else: raise NotImplementedError(f"Frequency '{frequency}' not supported for next date calculation.")
        return next_date

    async def generate_recurring_entries(self, as_of_date: date, user_id: int) -> List[Result[JournalEntry]]:
        patterns_due: List[RecurringPattern] = await self.journal_service.get_recurring_patterns_due(as_of_date); generated_results: List[Result[JournalEntry]] = []
        for pattern in patterns_due:
            if not pattern.template_journal_entry: self.logger.error(f"Template JE not loaded for pattern ID {pattern.id}. Skipping."); generated_results.append(Result.failure([f"Template JE not loaded for pattern '{pattern.name}'."])); continue
            entry_date_for_new_je = pattern.next_generation_date; 
            if not entry_date_for_new_je : continue 
            template_entry = pattern.template_journal_entry
            new_je_lines_data = [JournalEntryLineData(account_id=line.account_id, description=line.description, debit_amount=line.debit_amount, credit_amount=line.credit_amount, currency_code=line.currency_code, exchange_rate=line.exchange_rate, tax_code=line.tax_code, tax_amount=line.tax_amount, dimension1_id=line.dimension1_id, dimension2_id=line.dimension2_id) for line in template_entry.lines]
            new_je_data = JournalEntryData(journal_type=template_entry.journal_type, entry_date=entry_date_for_new_je, description=f"{pattern.description or template_entry.description or ''} (Recurring - {pattern.name})", reference=template_entry.reference, user_id=user_id, lines=new_je_lines_data, recurring_pattern_id=pattern.id, source_type="RecurringPattern", source_id=pattern.id)
            create_result = await self.create_journal_entry(new_je_data); generated_results.append(create_result)
            if create_result.is_success:
                async with self.app_core.db_manager.session() as session: # type: ignore
                    pattern_to_update = await session.get(RecurringPattern, pattern.id)
                    if pattern_to_update:
                        pattern_to_update.last_generated_date = entry_date_for_new_je
                        try:
                            next_gen = self._calculate_next_generation_date(pattern_to_update.last_generated_date, pattern_to_update.frequency, pattern_to_update.interval_value, pattern_to_update.day_of_month, pattern_to_update.day_of_week)
                            if pattern_to_update.end_date and next_gen > pattern_to_update.end_date: pattern_to_update.next_generation_date = None; pattern_to_update.is_active = False 
                            else: pattern_to_update.next_generation_date = next_gen
                        except NotImplementedError: pattern_to_update.next_generation_date = None; pattern_to_update.is_active = False; self.logger.warning(f"Next gen date calc not implemented for pattern {pattern_to_update.name}, deactivating.")
                        pattern_to_update.updated_by_user_id = user_id; session.add(pattern_to_update); await session.commit()
                    else: self.logger.error(f"Failed to re-fetch pattern ID {pattern.id} for update after recurring JE generation.") 
        return generated_results

    async def get_journal_entry_for_dialog(self, entry_id: int) -> Optional[JournalEntry]:
        return await self.journal_service.get_by_id(entry_id)

    async def get_journal_entries_for_listing(self, filters: Optional[Dict[str, Any]] = None) -> Result[List[Dict[str, Any]]]:
        filters = filters or {}
        try:
            summary_data = await self.journal_service.get_all_summary(start_date_filter=filters.get("start_date"),end_date_filter=filters.get("end_date"),status_filter=filters.get("status"),entry_no_filter=filters.get("entry_no"),description_filter=filters.get("description"),journal_type_filter=filters.get("journal_type"))
            return Result.success(summary_data)
        except Exception as e: self.logger.error(f"Error fetching JE summaries for listing: {e}", exc_info=True); return Result.failure([f"Failed to retrieve journal entry summaries: {str(e)}"])

```

# app/accounting/currency_manager.py
```py
# File: app/accounting/currency_manager.py
from typing import Optional, List, Any, TYPE_CHECKING
from datetime import date
from decimal import Decimal
from app.models.accounting.currency import Currency 
from app.models.accounting.exchange_rate import ExchangeRate
from app.utils.result import Result

if TYPE_CHECKING:
    from app.core.application_core import ApplicationCore 
    from app.services.accounting_services import CurrencyService, ExchangeRateService 

class CurrencyManager:
    def __init__(self, app_core: "ApplicationCore"): 
        self.app_core = app_core
        self.currency_service: "CurrencyService" = self.app_core.currency_repo_service
        self.exchange_rate_service: "ExchangeRateService" = self.app_core.exchange_rate_service
    
    async def get_active_currencies(self) -> List[Currency]:
        return await self.currency_service.get_all_active()

    async def get_exchange_rate(self, from_currency_code: str, to_currency_code: str, rate_date: date) -> Optional[Decimal]:
        rate_obj = await self.exchange_rate_service.get_rate_for_date(from_currency_code, to_currency_code, rate_date)
        return rate_obj.exchange_rate_value if rate_obj else None

    async def update_exchange_rate(self, from_code:str, to_code:str, r_date:date, rate:Decimal, user_id:int) -> Result[ExchangeRate]:
        existing_rate = await self.exchange_rate_service.get_rate_for_date(from_code, to_code, r_date)
        orm_object: ExchangeRate
        if existing_rate:
            existing_rate.exchange_rate_value = rate
            existing_rate.updated_by_user_id = user_id
            orm_object = existing_rate
        else:
            orm_object = ExchangeRate(
                from_currency_code=from_code, to_currency_code=to_code, rate_date=r_date,
                exchange_rate_value=rate, 
                created_by_user_id=user_id, updated_by_user_id=user_id 
            )
        
        saved_obj = await self.exchange_rate_service.save(orm_object)
        return Result.success(saved_obj)

    async def get_all_currencies(self) -> List[Currency]:
        return await self.currency_service.get_all()

    async def get_currency_by_code(self, code: str) -> Optional[Currency]:
        return await self.currency_service.get_by_id(code)

```

# app/accounting/chart_of_accounts_manager.py
```py
# File: app/accounting/chart_of_accounts_manager.py
from typing import List, Optional, Dict, Any, TYPE_CHECKING
from app.models.accounting.account import Account 
from app.utils.result import Result
from app.utils.pydantic_models import AccountCreateData, AccountUpdateData, AccountValidator
from decimal import Decimal
from datetime import date 

if TYPE_CHECKING:
    from app.core.application_core import ApplicationCore 
    from app.services.account_service import AccountService

class ChartOfAccountsManager:
    def __init__(self, app_core: "ApplicationCore"): 
        self.app_core = app_core
        self.account_service: "AccountService" = self.app_core.account_service
        self.account_validator = AccountValidator() 
        self.logger = self.app_core.logger

    async def create_account(self, account_data: AccountCreateData) -> Result[Account]:
        validation_result = self.account_validator.validate_create(account_data)
        if not validation_result.is_valid:
            return Result.failure(validation_result.errors)
        
        existing = await self.account_service.get_by_code(account_data.code)
        if existing:
            return Result.failure([f"Account code '{account_data.code}' already exists."])
        
        current_user_id = account_data.user_id

        account = Account(
            code=account_data.code, name=account_data.name,
            account_type=account_data.account_type, sub_type=account_data.sub_type,
            tax_treatment=account_data.tax_treatment, gst_applicable=account_data.gst_applicable,
            description=account_data.description, parent_id=account_data.parent_id,
            report_group=account_data.report_group, cash_flow_category=account_data.cash_flow_category,
            is_control_account=account_data.is_control_account, is_bank_account=account_data.is_bank_account, 
            opening_balance=account_data.opening_balance, opening_balance_date=account_data.opening_balance_date, 
            is_active=account_data.is_active, created_by_user_id=current_user_id, 
            updated_by_user_id=current_user_id 
        )
        
        try:
            saved_account = await self.account_service.save(account)
            return Result.success(saved_account)
        except Exception as e:
            self.logger.error(f"Failed to save account: {e}", exc_info=True)
            return Result.failure([f"Failed to save account: {str(e)}"])
    
    async def update_account(self, account_data: AccountUpdateData) -> Result[Account]:
        existing_account = await self.account_service.get_by_id(account_data.id)
        if not existing_account:
            return Result.failure([f"Account with ID {account_data.id} not found."])
        
        validation_result = self.account_validator.validate_update(account_data)
        if not validation_result.is_valid:
            return Result.failure(validation_result.errors)
        
        if account_data.code != existing_account.code:
            code_exists = await self.account_service.get_by_code(account_data.code)
            if code_exists and code_exists.id != existing_account.id:
                return Result.failure([f"Account code '{account_data.code}' already exists."])
        
        current_user_id = account_data.user_id

        existing_account.code = account_data.code; existing_account.name = account_data.name
        existing_account.account_type = account_data.account_type; existing_account.sub_type = account_data.sub_type
        existing_account.tax_treatment = account_data.tax_treatment; existing_account.gst_applicable = account_data.gst_applicable
        existing_account.description = account_data.description; existing_account.parent_id = account_data.parent_id
        existing_account.report_group = account_data.report_group; existing_account.cash_flow_category = account_data.cash_flow_category
        existing_account.is_control_account = account_data.is_control_account; existing_account.is_bank_account = account_data.is_bank_account
        existing_account.opening_balance = account_data.opening_balance; existing_account.opening_balance_date = account_data.opening_balance_date 
        existing_account.is_active = account_data.is_active; existing_account.updated_by_user_id = current_user_id
        
        try:
            updated_account = await self.account_service.save(existing_account)
            return Result.success(updated_account)
        except Exception as e:
            self.logger.error(f"Failed to update account: {e}", exc_info=True)
            return Result.failure([f"Failed to update account: {str(e)}"])
            
    async def deactivate_account(self, account_id: int, user_id: int) -> Result[Account]:
        account = await self.account_service.get_by_id(account_id)
        if not account: return Result.failure([f"Account with ID {account_id} not found."])
        if not account.is_active: return Result.failure([f"Account '{account.code}' is already inactive."])
        if not self.app_core or not hasattr(self.app_core, 'journal_service'): return Result.failure(["Journal service not available for balance check."])

        total_current_balance = await self.app_core.journal_service.get_account_balance(account_id, date.today()) 
        if total_current_balance != Decimal(0): return Result.failure([f"Cannot deactivate account '{account.code}' as it has a non-zero balance ({total_current_balance:.2f})."])

        account.is_active = False; account.updated_by_user_id = user_id 
        try:
            updated_account = await self.account_service.save(account)
            return Result.success(updated_account)
        except Exception as e:
            self.logger.error(f"Failed to deactivate account: {e}", exc_info=True)
            return Result.failure([f"Failed to deactivate account: {str(e)}"])

    async def get_account_tree(self, active_only: bool = True) -> List[Dict[str, Any]]:
        try:
            tree = await self.account_service.get_account_tree(active_only=active_only)
            return tree 
        except Exception as e:
            self.logger.error(f"Error getting account tree: {e}", exc_info=True)
            return []

    async def get_accounts_for_selection(self, account_type: Optional[str] = None, active_only: bool = True) -> List[Account]:
        if account_type:
            return await self.account_service.get_by_type(account_type, active_only=active_only)
        elif active_only:
            return await self.account_service.get_all_active()
        else:
            if hasattr(self.account_service, 'get_all'):
                 return await self.account_service.get_all()
            else: 
                 return await self.account_service.get_all_active()

```

# app/accounting/fiscal_period_manager.py
```py
# File: app/accounting/fiscal_period_manager.py
from typing import List, Optional, TYPE_CHECKING
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta # type: ignore

from sqlalchemy import select 

from app.models.accounting.fiscal_year import FiscalYear 
from app.models.accounting.fiscal_period import FiscalPeriod
from app.utils.result import Result
from app.utils.pydantic_models import FiscalYearCreateData 

if TYPE_CHECKING:
    from app.core.application_core import ApplicationCore 
    from sqlalchemy.ext.asyncio import AsyncSession
    from app.services.fiscal_period_service import FiscalPeriodService
    from app.services.accounting_services import FiscalYearService 

class FiscalPeriodManager:
    def __init__(self, app_core: "ApplicationCore"):
        self.app_core = app_core
        self.fiscal_period_service: "FiscalPeriodService" = self.app_core.fiscal_period_service 
        self.fiscal_year_service: "FiscalYearService" = self.app_core.fiscal_year_service 
        
    async def create_fiscal_year_and_periods(self, fy_data: FiscalYearCreateData) -> Result[FiscalYear]:
        if fy_data.start_date >= fy_data.end_date:
            return Result.failure(["Fiscal year start date must be before end date."])

        existing_by_name = await self.fiscal_year_service.get_by_name(fy_data.year_name)
        if existing_by_name:
            return Result.failure([f"A fiscal year with the name '{fy_data.year_name}' already exists."])

        overlapping_fy = await self.fiscal_year_service.get_by_date_overlap(fy_data.start_date, fy_data.end_date)
        if overlapping_fy:
            return Result.failure([f"The proposed date range overlaps with existing fiscal year '{overlapping_fy.year_name}' ({overlapping_fy.start_date} - {overlapping_fy.end_date})."])

        async with self.app_core.db_manager.session() as session: # type: ignore 
            fy = FiscalYear(
                year_name=fy_data.year_name, 
                start_date=fy_data.start_date, 
                end_date=fy_data.end_date, 
                created_by_user_id=fy_data.user_id, 
                updated_by_user_id=fy_data.user_id,
                is_closed=False 
            )
            session.add(fy)
            await session.flush() 
            await session.refresh(fy) 

            if fy_data.auto_generate_periods and fy_data.auto_generate_periods in ["Month", "Quarter"]:
                try:
                    await self._generate_periods_for_year_internal(
                        fy, fy_data.auto_generate_periods, fy_data.user_id, session
                    )
                except ValueError as e:
                     raise Exception(f"Failed to generate periods for '{fy.year_name}': {e}") from e
            
            return Result.success(fy)
        
    async def _generate_periods_for_year_internal(self, fiscal_year: FiscalYear, period_type: str, user_id: int, session: "AsyncSession") -> Result[List[FiscalPeriod]]:
        if not fiscal_year or not fiscal_year.id:
            raise ValueError("Valid FiscalYear object with an ID must be provided for period generation.")
        
        stmt_existing = select(FiscalPeriod).where(
            FiscalPeriod.fiscal_year_id == fiscal_year.id,
            FiscalPeriod.period_type == period_type
        )
        existing_periods_result = await session.execute(stmt_existing)
        if existing_periods_result.scalars().first():
             raise ValueError(f"{period_type} periods already exist for fiscal year '{fiscal_year.year_name}'.")

        periods: List[FiscalPeriod] = []
        current_start_date = fiscal_year.start_date
        fy_end_date = fiscal_year.end_date
        period_number = 1

        while current_start_date <= fy_end_date:
            current_end_date: date
            period_name: str

            if period_type == "Month":
                current_end_date = current_start_date + relativedelta(months=1) - relativedelta(days=1)
                if current_end_date > fy_end_date: current_end_date = fy_end_date
                period_name = f"{current_start_date.strftime('%B %Y')}"
            
            elif period_type == "Quarter":
                month_end_of_third_month = current_start_date + relativedelta(months=2, day=1) + relativedelta(months=1) - relativedelta(days=1)
                current_end_date = month_end_of_third_month
                if current_end_date > fy_end_date: current_end_date = fy_end_date
                period_name = f"Q{period_number} {fiscal_year.year_name}"
            else: 
                raise ValueError(f"Invalid period type '{period_type}' during generation.")

            fp = FiscalPeriod(
                fiscal_year_id=fiscal_year.id, name=period_name,
                start_date=current_start_date, end_date=current_end_date,
                period_type=period_type, status="Open", period_number=period_number,
                is_adjustment=False,
                created_by_user_id=user_id, updated_by_user_id=user_id
            )
            session.add(fp) 
            periods.append(fp)

            if current_end_date >= fy_end_date: break 
            current_start_date = current_end_date + relativedelta(days=1)
            period_number += 1
        
        await session.flush()
        for p in periods: 
            await session.refresh(p)
            
        return Result.success(periods)

    async def close_period(self, fiscal_period_id: int, user_id: int) -> Result[FiscalPeriod]:
        period = await self.fiscal_period_service.get_by_id(fiscal_period_id)
        if not period: return Result.failure([f"Fiscal period ID {fiscal_period_id} not found."])
        if period.status == 'Closed': return Result.failure(["Period is already closed."])
        if period.status == 'Archived': return Result.failure(["Cannot close an archived period."])
        
        period.status = 'Closed'
        period.updated_by_user_id = user_id
        updated_period = await self.fiscal_period_service.update(period) 
        return Result.success(updated_period)

    async def reopen_period(self, fiscal_period_id: int, user_id: int) -> Result[FiscalPeriod]:
        period = await self.fiscal_period_service.get_by_id(fiscal_period_id)
        if not period: return Result.failure([f"Fiscal period ID {fiscal_period_id} not found."])
        if period.status == 'Open': return Result.failure(["Period is already open."])
        if period.status == 'Archived': return Result.failure(["Cannot reopen an archived period."])
        
        fiscal_year = await self.fiscal_year_service.get_by_id(period.fiscal_year_id)
        if fiscal_year and fiscal_year.is_closed:
            return Result.failure(["Cannot reopen period as its fiscal year is closed."])

        period.status = 'Open'
        period.updated_by_user_id = user_id
        updated_period = await self.fiscal_period_service.update(period)
        return Result.success(updated_period)

    async def get_current_fiscal_period(self, target_date: Optional[date] = None) -> Optional[FiscalPeriod]:
        if target_date is None:
            target_date = date.today()
        return await self.fiscal_period_service.get_by_date(target_date)

    async def get_all_fiscal_years(self) -> List[FiscalYear]:
        return await self.fiscal_year_service.get_all()

    async def get_fiscal_year_by_id(self, fy_id: int) -> Optional[FiscalYear]:
        return await self.fiscal_year_service.get_by_id(fy_id)

    async def get_periods_for_fiscal_year(self, fiscal_year_id: int) -> List[FiscalPeriod]:
        return await self.fiscal_period_service.get_fiscal_periods_for_year(fiscal_year_id)

    async def close_fiscal_year(self, fiscal_year_id: int, user_id: int) -> Result[FiscalYear]:
        fy = await self.fiscal_year_service.get_by_id(fiscal_year_id)
        if not fy:
            return Result.failure([f"Fiscal Year ID {fiscal_year_id} not found."])
        if fy.is_closed:
            return Result.failure([f"Fiscal Year '{fy.year_name}' is already closed."])

        periods = await self.fiscal_period_service.get_fiscal_periods_for_year(fiscal_year_id)
        open_periods = [p for p in periods if p.status == 'Open']
        if open_periods:
            return Result.failure([f"Cannot close fiscal year '{fy.year_name}'. Following periods are still open: {[p.name for p in open_periods]}"])
        
        # NOTE: A real implementation would create year-end closing journal entries here.
        # This is a conceptual placeholder for that complex logic.
        self.app_core.logger.info(f"Performing year-end closing entries for FY '{fy.year_name}' (conceptual)...")

        fy.is_closed = True
        fy.closed_date = datetime.utcnow() 
        fy.closed_by_user_id = user_id # This should be set on the object
        fy.updated_by_user_id = user_id 
        
        try:
            updated_fy = await self.fiscal_year_service.save(fy)
            return Result.success(updated_fy)
        except Exception as e:
            return Result.failure([f"Error closing fiscal year: {str(e)}"])

```

