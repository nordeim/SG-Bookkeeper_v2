<think>
I acknowledge the new error report. I will follow my established rigorous process to diagnose, plan, and resolve this issue, ensuring the fix is precise and does not introduce regressions.

### **1. Initial Diagnosis: Understanding the Traceback**

The traceback points to a new error that occurred after my previous fix.

```
Traceback (most recent call last):
  ...
  File "/cdrom/project/SG-Bookkeeper/app/main.py", line 90, in _on_initialization_done
    self.main_window = MainWindow(self.app_core); ...
                       ^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/cdrom/project/SG-Bookkeeper/app/ui/main_window.py", line 37, in __init__
    company_info = self.app_core.company_manager.get_company_by_db_name(db_name)
                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AttributeError: 'ApplicationCore' object has no attribute 'company_manager'. Did you mean: 'config_manager'?
```

*   **Error Type:** `AttributeError`. This means I'm trying to access an attribute or method on an object that doesn't exist.
*   **Location of Error:** The error occurs in `app/ui/main_window.py` inside the `__init__` method, specifically on the line `self.app_core.company_manager.get_company_by_db_name(db_name)`.
*   **Root Cause:** The `ApplicationCore` object (`self.app_core`) does not have an attribute named `company_manager`. The helpful `Did you mean: 'config_manager'?` from Python confirms that `company_manager` is not a recognized attribute of the `app_core` instance at the time of the call.

### **2. Analysis of the Problem & Goal**

The previous fix correctly moved the `db_init` logic into the `app` package. The current problem is one of object initialization and lifecycle. `MainWindow` is instantiated and it immediately tries to use `app_core.company_manager`. However, the `ApplicationCore` class, while it defines a placeholder for `_company_manager_instance`, has not actually created an instance of `CompanyManager` and assigned it to the `company_manager` property.

Looking at the `ApplicationCore` code:
```python
# app/core/application_core.py

class ApplicationCore:
    def __init__(self, config_manager: ConfigManager, db_manager: DatabaseManager):
        # ...
        self.security_manager = SecurityManager(self.db_manager)
        self.module_manager = ModuleManager(self)

        # Manager Instance Placeholders
        self._coa_manager_instance: Optional[ChartOfAccountsManager] = None
        self._je_manager_instance: Optional["JournalEntryManager"] = None 
        # ... and so on for all managers...
        # There is no placeholder for _company_manager_instance. This is an omission.

    async def startup(self):
        # ... initializes a lot of services and managers...
        # ... but there is no line here that initializes CompanyManager.

    # ... Manager Properties ...
    # There is no @property for company_manager.
```

I have identified three distinct omissions in `app/core/application_core.py`:
1.  There is no instance variable placeholder (e.g., `self._company_manager_instance`) in the `__init__` method.
2.  The `startup` method does not instantiate the `CompanyManager`.
3.  There is no `@property` defined for `company_manager` to allow access like `app_core.company_manager`.

The goal is to correctly instantiate `CompanyManager` within `ApplicationCore` and make it available through a property, just like all the other managers.

### **3. Exploring Implementation Options**

This is a straightforward initialization problem. There's really only one correct way to fix this that aligns with the existing architecture.

*   **Option 1: The Correct Architectural Fix**
    *   **Description:**
        1.  Add `from app.core.company_manager import CompanyManager` to `application_core.py`.
        2.  In `ApplicationCore.__init__`, add the placeholder: `self._company_manager_instance: Optional[CompanyManager] = None`.
        3.  In `ApplicationCore.startup`, instantiate the manager: `self._company_manager_instance = CompanyManager(self)`. Unlike other managers, `CompanyManager` doesn't need services passed to its constructor, just the `app_core` reference. This should happen early in the `startup` process, as other components might depend on it.
        4.  In `ApplicationCore`, add the corresponding property:
            ```python
            @property
            def company_manager(self) -> "CompanyManager":
                if not self._company_manager_instance:
                    raise RuntimeError("CompanyManager not initialized.")
                return self._company_manager_instance
            ```
    *   **Pros:** This is the standard pattern used for every other manager in the `ApplicationCore`. It is consistent, correct, and directly resolves the `AttributeError`.
    *   **Cons:** None. This is the intended design.

*   **Option 2: Instantiate in `MainWindow`**
    *   **Description:** Instead of making it part of `ApplicationCore`, `MainWindow` could create its own `CompanyManager` instance.
    *   **Pros:** Fixes the immediate problem in `MainWindow`.
    *   **Cons:** Architecturally incorrect. It violates the principle of the `ApplicationCore` being the central service container. If any other part of the application needs to access company information in the future, it would have no way to get to the `CompanyManager` instance. This creates tight coupling between the UI and a core service. I will **reject** this option.

**Decision on Optimal Solution:**

Option 1 is clearly the correct and only professional choice. It follows the established pattern of the application's architecture and fixes the oversight that led to the `AttributeError`.

### **4. Detailed Execution Plan & Checklist**

**Step 1: Update `app/core/application_core.py`**
-   [ ] **Action:** Modify the `ApplicationCore` class.
-   [ ] **Checklist:**
    -   [ ] Add `from app.core.company_manager import CompanyManager` at the top of the file.
    -   [ ] In the `__init__` method, add the line `self._company_manager_instance: Optional[CompanyManager] = None` with the other manager placeholders.
    -   [ ] In the `startup` method, add the line `self._company_manager_instance = CompanyManager(self)`. This should be placed early, right after `self.module_manager` is initialized, as it's a fundamental component.
    -   [ ] At the end of the class, add the new property definition for `company_manager`.
    -   [ ] Perform a diff to ensure these are the only changes and no other managers or services were accidentally removed.

**Step 2: Re-validate Dependent Files**
-   [ ] **File:** `app/ui/main_window.py`
    -   [ ] The code here is actually correct in its *intent*. It was correctly trying to access `app_core.company_manager`. With the fix in `ApplicationCore`, this file now requires no changes.
-   [ ] **File:** `app/main.py`
    -   [ ] No changes required here either. The logic for initializing the app and handling the result is sound.

**Step 3: Generate Final File**
-   [ ] I will now generate the single complete and updated replacement file for `app/core/application_core.py`.

**Step 4: Final Validation**
-   [ ] I will mentally trace the execution again:
    1.  `main.py` starts the `Application`.
    2.  `Application.initialize_app` creates an `ApplicationCore` instance.
    3.  It then `await`s `current_app_core.startup()`.
    4.  The updated `startup` method will now correctly instantiate `CompanyManager` and assign it to `_company_manager_instance`.
    5.  `initialize_app` successfully completes and emits the signal with the fully initialized `app_core` instance.
    6.  `_on_initialization_done` receives this instance.
    7.  It creates `MainWindow(self.app_core)`.
    8.  `MainWindow.__init__` is called.
    9.  The line `self.app_core.company_manager.get_company_by_db_name(db_name)` is executed.
    10. This will now successfully call the `company_manager` property on `app_core`, which will return the initialized `_company_manager_instance`, resolving the `AttributeError`.

The plan is sound and addresses the root cause of the error directly and cleanly. I will now proceed.Excellent. I have analyzed the traceback and identified the root cause of the `AttributeError`. The issue is a simple but critical omission during the previous refactoring: the `CompanyManager` was never instantiated within the `ApplicationCore` nor was it exposed as a property.

Here is my systematic plan and the complete, updated file to resolve the issue.

### 1. Diagnosis of the `AttributeError`

-   **Error:** `AttributeError: 'ApplicationCore' object has no attribute 'company_manager'`.
-   **Location:** The error occurs in `app/ui/main_window.py` when it attempts to access `self.app_core.company_manager`.
-   **Root Cause:** A review of `app/core/application_core.py` reveals that while other managers are instantiated in the `startup()` method and exposed via `@property` decorators, the `CompanyManager` was overlooked. It was never created or attached to the `ApplicationCore` instance.

### 2. Optimal Solution

The most direct and architecturally consistent solution is to integrate the `CompanyManager` into the `ApplicationCore` using the same pattern as all other managers in the project. This involves three small additions to the `ApplicationCore` class:
1.  Add a placeholder attribute `self._company_manager_instance` in the `__init__` method.
2.  Instantiate the `CompanyManager` within the `startup()` method.
3.  Expose the instance via a read-only `@property` named `company_manager`.

This fix is minimal, targeted, and aligns perfectly with the existing design, ensuring maintainability and resolving the error completely.

### 3. Execution and File Update

I will now provide the single, complete, and updated replacement file required to fix the error.

---
### **File 1 of 1: `app/core/application_core.py` (Updated)**

```python
# File: app/core/application_core.py
from typing import Optional, Any, TYPE_CHECKING
from app.core.config_manager import ConfigManager
from app.core.database_manager import DatabaseManager 
from app.core.security_manager import SecurityManager
from app.core.module_manager import ModuleManager
from app.core.company_manager import CompanyManager # New import

# Manager imports are generally okay here if they don't cause cycles themselves
from app.accounting.chart_of_accounts_manager import ChartOfAccountsManager
from app.business_logic.customer_manager import CustomerManager 
from app.business_logic.vendor_manager import VendorManager 
from app.business_logic.product_manager import ProductManager
from app.business_logic.bank_account_manager import BankAccountManager 
from app.business_logic.bank_transaction_manager import BankTransactionManager

import logging 

if TYPE_CHECKING:
    from app.services.journal_service import JournalService
    from app.accounting.journal_entry_manager import JournalEntryManager
    from app.accounting.fiscal_period_manager import FiscalPeriodManager
    from app.accounting.currency_manager import CurrencyManager
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
    from app.utils.sequence_generator import SequenceGenerator
    
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
    def __init__(self, config_manager: ConfigManager, db_manager: DatabaseManager):
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

        # Service Instance Placeholders
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

        # Manager Instance Placeholders
        self._company_manager_instance: Optional[CompanyManager] = None # NEW
        self._coa_manager_instance: Optional[ChartOfAccountsManager] = None
        self._je_manager_instance: Optional["JournalEntryManager"] = None 
        self._fp_manager_instance: Optional["FiscalPeriodManager"] = None
        self._currency_manager_instance: Optional["CurrencyManager"] = None
        self._gst_manager_instance: Optional["GSTManager"] = None
        self._tax_calculator_instance: Optional["TaxCalculator"] = None
        self._income_tax_manager_instance: Optional["IncomeTaxManager"] = None
        self._withholding_tax_manager_instance: Optional["WithholdingTaxManager"] = None
        self._financial_statement_generator_instance: Optional["FinancialStatementGenerator"] = None
        self._report_engine_instance: Optional["ReportEngine"] = None
        self._customer_manager_instance: Optional[CustomerManager] = None
        self._vendor_manager_instance: Optional[VendorManager] = None
        self._product_manager_instance: Optional[ProductManager] = None
        self._sales_invoice_manager_instance: Optional["SalesInvoiceManager"] = None
        self._purchase_invoice_manager_instance: Optional["PurchaseInvoiceManager"] = None
        self._bank_account_manager_instance: Optional[BankAccountManager] = None
        self._bank_transaction_manager_instance: Optional[BankTransactionManager] = None
        self._payment_manager_instance: Optional["PaymentManager"] = None
        self._dashboard_manager_instance: Optional["DashboardManager"] = None
        
        self.logger.info("ApplicationCore initialized.")

    async def startup(self):
        self.logger.info("ApplicationCore starting up...")
        
        # CompanyManager must be initialized early and outside of the main DB-dependent block
        self._company_manager_instance = CompanyManager(self)
        
        # Check if we should proceed with full DB initialization
        db_config = self.config_manager.get_database_config()
        if not db_config.database or db_config.database == "sg_bookkeeper_default":
            self.logger.warning("No company database selected. Skipping full service and manager initialization.")
            return

        await self.db_manager.initialize() 
        
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
        
        from app.utils.sequence_generator import SequenceGenerator 
        from app.accounting.journal_entry_manager import JournalEntryManager
        from app.accounting.fiscal_period_manager import FiscalPeriodManager
        from app.accounting.currency_manager import CurrencyManager
        from app.tax.gst_manager import GSTManager
        from app.tax.tax_calculator import TaxCalculator
        from app.tax.income_tax_manager import IncomeTaxManager
        from app.tax.withholding_tax_manager import WithholdingTaxManager
        from app.reporting.financial_statement_generator import FinancialStatementGenerator
        from app.reporting.report_engine import ReportEngine
        from app.reporting.dashboard_manager import DashboardManager
        from app.business_logic.sales_invoice_manager import SalesInvoiceManager
        from app.business_logic.purchase_invoice_manager import PurchaseInvoiceManager
        from app.business_logic.payment_manager import PaymentManager
        
        py_sequence_generator = SequenceGenerator(self.sequence_service, app_core_ref=self) 
        
        self._coa_manager_instance = ChartOfAccountsManager(self.account_service, self)
        self._je_manager_instance = JournalEntryManager(self.journal_service, self.account_service, self.fiscal_period_service, self)
        self._fp_manager_instance = FiscalPeriodManager(self) 
        self._currency_manager_instance = CurrencyManager(self) 
        self._tax_calculator_instance = TaxCalculator(self.tax_code_service) 
        self._gst_manager_instance = GSTManager(self.tax_code_service, self.journal_service, self.company_settings_service, self.gst_return_service, self.account_service, self.fiscal_period_service, py_sequence_generator, self)
        self._financial_statement_generator_instance = FinancialStatementGenerator(self.account_service, self.journal_service, self.fiscal_period_service, self.account_type_service, self.tax_code_service, self.company_settings_service, self.dimension_service, self.configuration_service)
        self._report_engine_instance = ReportEngine(self)
        self._customer_manager_instance = CustomerManager(customer_service=self.customer_service, account_service=self.account_service, currency_service=self.currency_repo_service, app_core=self)
        self._vendor_manager_instance = VendorManager( vendor_service=self.vendor_service, account_service=self.account_service, currency_service=self.currency_repo_service, app_core=self)
        self._product_manager_instance = ProductManager( product_service=self.product_service, account_service=self.account_service, tax_code_service=self.tax_code_service, app_core=self)
        self._sales_invoice_manager_instance = SalesInvoiceManager(sales_invoice_service=self.sales_invoice_service, customer_service=self.customer_service, product_service=self.product_service, tax_code_service=self.tax_code_service, tax_calculator=self.tax_calculator, sequence_service=self.sequence_service, account_service=self.account_service, configuration_service=self.configuration_service, app_core=self, inventory_movement_service=self.inventory_movement_service)
        self._purchase_invoice_manager_instance = PurchaseInvoiceManager( purchase_invoice_service=self.purchase_invoice_service, vendor_service=self.vendor_service, product_service=self.product_service, tax_code_service=self.tax_code_service, tax_calculator=self.tax_calculator, sequence_service=self.sequence_service, account_service=self.account_service, configuration_service=self.configuration_service, app_core=self, inventory_movement_service=self.inventory_movement_service)
        self._bank_account_manager_instance = BankAccountManager( bank_account_service=self.bank_account_service, account_service=self.account_service, currency_service=self.currency_repo_service, app_core=self)
        self._bank_transaction_manager_instance = BankTransactionManager( bank_transaction_service=self.bank_transaction_service, bank_account_service=self.bank_account_service, app_core=self)
        self._payment_manager_instance = PaymentManager( payment_service=self.payment_service, sequence_service=self.sequence_service, bank_account_service=self.bank_account_service, customer_service=self.customer_service, vendor_service=self.vendor_service, sales_invoice_service=self.sales_invoice_service, purchase_invoice_service=self.purchase_invoice_service, journal_entry_manager=self.journal_entry_manager, account_service=self.account_service, configuration_service=self.configuration_service, app_core=self)
        self._dashboard_manager_instance = DashboardManager(self)
        self._income_tax_manager_instance = IncomeTaxManager(self)
        self._withholding_tax_manager_instance = WithholdingTaxManager(self)
        
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
    # ... (all other service properties) ...
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

    # --- Manager Properties ---
    @property
    def company_manager(self) -> "CompanyManager": # NEW
        if not self._company_manager_instance: raise RuntimeError("CompanyManager not initialized.")
        return self._company_manager_instance
    @property
    def chart_of_accounts_manager(self) -> ChartOfAccountsManager: 
        if not self._coa_manager_instance: raise RuntimeError("ChartOfAccountsManager not initialized.")
        return self._coa_manager_instance
    @property 
    def accounting_service(self) -> ChartOfAccountsManager: 
        return self.chart_of_accounts_manager
    @property
    def journal_entry_manager(self) -> "JournalEntryManager": 
        if not self._je_manager_instance: raise RuntimeError("JournalEntryManager not initialized.")
        return self._je_manager_instance 
    @property
    def fiscal_period_manager(self) -> "FiscalPeriodManager": 
        if not self._fp_manager_instance: raise RuntimeError("FiscalPeriodManager not initialized.")
        return self._fp_manager_instance 
    @property
    def currency_manager(self) -> "CurrencyManager": 
        if not self._currency_manager_instance: raise RuntimeError("CurrencyManager not initialized.")
        return self._currency_manager_instance 
    @property
    def gst_manager(self) -> "GSTManager": 
        if not self._gst_manager_instance: raise RuntimeError("GSTManager not initialized.")
        return self._gst_manager_instance 
    @property
    def tax_calculator(self) -> "TaxCalculator": 
        if not self._tax_calculator_instance: raise RuntimeError("TaxCalculator not initialized.")
        return self._tax_calculator_instance 
    @property
    def income_tax_manager(self) -> "IncomeTaxManager":
        if not self._income_tax_manager_instance: raise RuntimeError("IncomeTaxManager not initialized.")
        return self._income_tax_manager_instance
    @property
    def withholding_tax_manager(self) -> "WithholdingTaxManager":
        if not self._withholding_tax_manager_instance: raise RuntimeError("WithholdingTaxManager not initialized.")
        return self._withholding_tax_manager_instance
    @property
    def financial_statement_generator(self) -> "FinancialStatementGenerator": 
        if not self._financial_statement_generator_instance: raise RuntimeError("FinancialStatementGenerator not initialized.")
        return self._financial_statement_generator_instance 
    @property
    def report_engine(self) -> "ReportEngine": 
        if not self._report_engine_instance: raise RuntimeError("ReportEngine not initialized.")
        return self._report_engine_instance 
    @property
    def customer_manager(self) -> CustomerManager: 
        if not self._customer_manager_instance: raise RuntimeError("CustomerManager not initialized.")
        return self._customer_manager_instance
    @property
    def vendor_manager(self) -> VendorManager: 
        if not self._vendor_manager_instance: raise RuntimeError("VendorManager not initialized.")
        return self._vendor_manager_instance
    @property
    def product_manager(self) -> ProductManager: 
        if not self._product_manager_instance: raise RuntimeError("ProductManager not initialized.")
        return self._product_manager_instance
    @property
    def sales_invoice_manager(self) -> "SalesInvoiceManager": 
        if not self._sales_invoice_manager_instance: raise RuntimeError("SalesInvoiceManager not initialized.")
        return self._sales_invoice_manager_instance 
    @property
    def purchase_invoice_manager(self) -> "PurchaseInvoiceManager": 
        if not self._purchase_invoice_manager_instance: raise RuntimeError("PurchaseInvoiceManager not initialized.")
        return self._purchase_invoice_manager_instance 
    @property
    def bank_account_manager(self) -> BankAccountManager: 
        if not self._bank_account_manager_instance: raise RuntimeError("BankAccountManager not initialized.")
        return self._bank_account_manager_instance
    @property
    def bank_transaction_manager(self) -> BankTransactionManager: 
        if not self._bank_transaction_manager_instance: raise RuntimeError("BankTransactionManager not initialized.")
        return self._bank_transaction_manager_instance
    @property
    def payment_manager(self) -> "PaymentManager": 
        if not self._payment_manager_instance: raise RuntimeError("PaymentManager not initialized.")
        return self._payment_manager_instance 
    @property
    def dashboard_manager(self) -> "DashboardManager":
        if not self._dashboard_manager_instance: raise RuntimeError("DashboardManager not initialized.")
        return self._dashboard_manager_instance
```

---
https://drive.google.com/file/d/13a54HCe719DE9LvoTL2G3fufXVAZ68s9/view?usp=sharing, https://drive.google.com/file/d/16sEyvS8ZfOJFIHl3N-L34xQnhEo5XPcI/view?usp=sharing, https://drive.google.com/file/d/17Lx6TxeEQJauqxEwWQIjL_Vounz-OOuU/view?usp=sharing, https://drive.google.com/file/d/17M3-d4q02eUhkRMgogRQMxwSbiDkCJow/view?usp=sharing, https://drive.google.com/file/d/1MxP_SNNW86u44e2wupzz6i2gb0ibGeUE/view?usp=sharing, https://drive.google.com/file/d/1QsDwk2m_1Nh4JHOshQw4zjEI3x1mgGkM/view?usp=sharing, https://drive.google.com/file/d/1RkrdC_e7A_-nbzKVAiL_fX48uib6mu1T/view?usp=sharing, https://drive.google.com/file/d/1Wvi2CiVPY0EL2kErW2muu_LbMy4J_sRF/view?usp=sharing, https://drive.google.com/file/d/1XPEV3rOOikcWVvhB7GwX0raI__osRg-Z/view?usp=sharing, https://drive.google.com/file/d/1Z0gGlgu698IMIFg56GxD60l4xKNg1fIt/view?usp=sharing, https://drive.google.com/file/d/1cJjbc9s6IGkKHeAhk-dh7ey9i7ArJMJe/view?usp=sharing, https://drive.google.com/file/d/1jNlP9TOSJtMzQMeLH1RoqmU2Hx7iwQkJ/view?usp=sharing, https://drive.google.com/file/d/1q3W6Cs4WVx7dLwL1XGN9aQ6bb-hyHmWS/view?usp=sharing, https://drive.google.com/file/d/1qYszGazA6Zm1-3YGdaKdDlPEr3HipU5k/view?usp=sharing, https://drive.google.com/file/d/1uYEc0AZDEBE2A4qrR5O1OFcFVHJsCtds/view?usp=sharing, https://aistudio.google.com/app/prompts?state=%7B%22ids%22:%5B%221v7mZ4CEkZueuPt-aoH1XmYRmOooNELC3%22%5D,%22action%22:%22open%22,%22userId%22:%22103961307342447084491%22,%22resourceKeys%22:%7B%7D%7D&usp=sharing

