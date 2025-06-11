<think>
The user has provided the existing versions of two files:
1.  `app/accounting/forex_manager.py`
2.  `app/ui/company/company_creation_wizard.py`

My task is to review them, compare them against my plan, and determine if any changes are necessary.

**1. Analyze `app/accounting/forex_manager.py`:**

*   **User's Goal:** Implement the Forex Revaluation manager.
*   **My Plan:**
    *   Create a `ForexManager` class.
    *   Implement `create_unrealized_gain_loss_je`.
    *   The method should handle AR, AP, and Bank accounts.
    *   It should calculate adjustments based on revaluation rates.
    *   It should create a main JE and a reversing JE.
*   **Review of Provided File:**
    *   The provided file contains a `ForexManager` class.
    *   It has the `create_unrealized_gain_loss_je` method with the correct signature.
    *   The logic inside the method follows my plan almost exactly:
        *   It gets company settings and base currency.
        *   It initializes the `adjustments` dictionary.
        *   Section 1 processes open sales invoices (AR).
        *   Section 2 processes open purchase invoices (AP).
        *   Section 3 processes foreign currency bank accounts.
        *   The logic for calculating adjustments seems correct (`revalued_base_balance - booked_base_balance`).
        *   It checks if the total adjustment is material before proceeding.
        *   Section 4 creates the Journal Entry lines, including the balancing gain/loss line.
        *   It calls `journal_entry_manager.create_journal_entry` and `post_journal_entry`.
        *   Section 5 creates and posts the reversing entry.
        *   It returns a `Result` object.
*   **Validation and Potential Issues:**
    *   The logic `booked_base_balance = (inv.total_amount - inv.amount_paid) * inv.exchange_rate` is noted in a comment as an approximation. This is a correct observation; a highly precise system might need to track the base currency value of each payment, but for an unrealized gain/loss calculation on the remaining balance, this is a very common and acceptable accounting practice. It's not an error.
    *   The code correctly fetches rates from the `exchange_rate_service`.
    *   The error handling (returning `Result.failure`) for missing rates is correct.
    *   The logic for determining gain vs. loss and debiting/crediting the correct P&L accounts is correct.
    *   The logic for creating and posting both the main JE and its reversal is correct.
    *   One subtle point: in section 1 (AR), it does `total_adjustment += adjustment`. In section 2 (AP), it does `total_adjustment -= adjustment`. And in section 3 (Banks), it does `total_adjustment += adjustment`. Let's verify this logic.
        *   AR is an asset. If its base value goes up, it's a gain. `adjustment` will be positive. `total_adjustment` increases. Correct.
        *   AP is a liability. If its base value goes up, it's a loss. `adjustment` will be positive. `total_adjustment` *should* decrease (or the loss account should be debited). The code does `total_adjustment -= adjustment`. This is correct. A positive adjustment (liability increased in base currency) correctly contributes to a net loss.
        *   Bank is an asset. Same as AR. `total_adjustment += adjustment`. Correct.
    *   The logic is sound.

*   **Conclusion for `forex_manager.py`:** The provided file is a complete and correct implementation of the feature as planned. It does not require any changes. It perfectly matches the functionality I intended to build.

**2. Analyze `app/ui/company/company_creation_wizard.py`:**

*   **User's Goal:** Implement a new `QWizard` for company creation.
*   **My Plan:**
    *   Create `CompanyCreationWizard`, `IntroPage`, `DetailsPage`, `FinalPage`.
    *   `DetailsPage` should have the necessary fields (`companyName`, `dbName`, `useDefaultCoa`), use `registerField`, have validation, and an auto-populate helper.
    *   `FinalPage` should show a summary.
*   **Review of Provided File:**
    *   The file contains the `CompanyCreationWizard` class.
    *   It contains the three required page classes: `IntroPage`, `DetailsPage`, `FinalPage`.
    *   `IntroPage` has the correct informational text.
    *   `DetailsPage` has the `company_name_edit`, `db_name_edit`, and `use_default_coa_check` widgets.
    *   It correctly uses `registerField` for all three.
    *   It has the `auto_populate_db_name` helper function with correct logic for sanitizing the string.
    *   It has the `validatePage` method with correct checks for empty names and a valid database name format (using a regex).
    *   `FinalPage` has the `initializePage` method which correctly reads the fields from the previous page and populates the summary label.
*   **Validation and Potential Issues:**
    *   The code is clean, well-structured, and directly implements all the requirements of a wizard-based UI for this purpose.
    *   The use of `registerField` is the correct Qt pattern for this.
    *   The validation logic is robust.
    *   There are no apparent bugs or issues.

*   **Conclusion for `company_creation_wizard.py`:** The provided file is a complete and correct implementation of the new company wizard. It does not require any changes.

**3. Overall Conclusion & Next Steps:**

The user has provided two files that were planned as "new" files in my execution plan. My review shows that these files are already complete and correct according to that plan. This means I don't need to generate them from scratch.

My task now shifts. The user asked me to "carefully review and validate them, then make the necessary changes to the existing version as per what you have planned." Since my review concludes no changes are needed *to these two files*, I must now proceed with the *other* parts of my plan that modify *other* files to integrate these new components.

My remaining execution plan is:
*   Modify `app/accounting/__init__.py`.
*   Modify `app/core/application_core.py`.
*   Modify `app/tax/withholding_tax_manager.py` (minor enhancement).
*   Modify `app/ui/accounting/accounting_widget.py`.
*   Modify `app/ui/main_window.py`.

I have all the necessary files for these modifications from the previous turn (`project_codebase_updated_files_set-new.md`). I can now proceed to generate the complete, updated replacement files for these remaining five files.

**Revised Execution Plan for Final Response:**

1.  **Acknowledge and Report:** Start by acknowledging the user's provision of the files. Report my findings: that `forex_manager.py` and `company_creation_wizard.py` are already complete and correct according to the plan and require no changes.
2.  **State the Next Steps:** Explain that I will now proceed with the remaining parts of the plan, which involve modifying other files to integrate these new components.
3.  **Generate `app/accounting/__init__.py`:** Add the `ForexManager` export.
4.  **Generate `app/core/application_core.py`:** Add the `ForexManager` instantiation and property. I'll also need to adjust the `__init__` signature to add `minimal_init: bool = False` because I saw that was added in `app/main.py` to handle the "no company selected" case. I need to make sure `ApplicationCore` can be instantiated minimally. Looking at `main.py`, the `ApplicationCore` is created with this flag. I'll review its `startup` method. The `startup` method correctly handles this by skipping DB initialization if no DB is selected. This is good. The call to `CompanyManager` is outside this block, which is also correct. The rest of the `ApplicationCore` provided in the previous turn seems to be missing this `minimal_init` logic, so I'll need to add it.
5.  **Generate `app/tax/withholding_tax_manager.py`:** I will make the minor enhancement to the "nature of payment" string to make it more generic.
6.  **Generate `app/ui/accounting/accounting_widget.py`:** Implement the new "Period-End Procedures" tab and the forex revaluation UI and logic as planned.
7.  **Generate `app/ui/main_window.py`:** Implement the change from `NewCompanyDialog` to `CompanyCreationWizard` as planned.
8.  **Final Summary:** Conclude the task, summarizing all the new and updated files provided in this single response.

This revised plan is comprehensive and addresses the full scope of the user's roadmap request, incorporating the pre-existing new files correctly. I will now generate the final response.Of course. I will now proceed with the full implementation of the roadmap features.

### **CodeNavigator Analysis and Validation Report**

I have meticulously reviewed the files you provided, including the existing versions of `app/accounting/forex_manager.py` and `app/ui/company/company_creation_wizard.py`.

My analysis concludes the following:

1.  **`app/accounting/forex_manager.py`**: The provided file is a **complete and correct** implementation of the unrealized forex gain/loss calculation logic as outlined in the plan. It correctly handles AR, AP, and Bank balances, calculates adjustments, and orchestrates the creation of both the main and reversing journal entries. **No changes are required for this file.**

2.  **`app/ui/company/company_creation_wizard.py`**: The provided file is a **complete and correct** implementation of the new multi-step company creation wizard. It properly uses `QWizardPage`, registers fields for data transfer, and includes robust validation. **No changes are required for this file.**

My task now is to integrate these new, correct components into the rest of the application and complete the other parts of the roadmap.

### **Execution Plan**

I will now execute the remaining steps of the plan, modifying existing files to integrate the new features and logic.

1.  **Integrate `ForexManager`**: I will update `app/accounting/__init__.py` to export the new manager and modify `app/core/application_core.py` to instantiate it and make it available to the application.
2.  **Enhance `WithholdingTaxManager`**: I will apply a minor enhancement to `app/tax/withholding_tax_manager.py` to make its output more robust.
3.  **Build Forex Revaluation UI**: I will modify `app/ui/accounting/accounting_widget.py` to add the new "Period-End Procedures" tab and the UI to trigger the forex revaluation.
4.  **Integrate Company Wizard**: I will modify `app/ui/main_window.py` to replace the call to the old dialog with the new `CompanyCreationWizard`.

I will now provide the complete, updated versions of all the necessary files.

***

### **Complete Updated and New Files**

#### **File 1: `app/accounting/__init__.py` (Updated)**
This file is updated to export the new `ForexManager`.

```python
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

#### **File 2: `app/core/application_core.py` (Updated)**
This file is updated to instantiate and provide access to the new `ForexManager`. It also incorporates the `minimal_init` logic seen in `main.py` for robustness.

```python
# File: app/core/application_core.py
from typing import Optional, Any, TYPE_CHECKING
from app.core.config_manager import ConfigManager
from app.core.database_manager import DatabaseManager 
from app.core.security_manager import SecurityManager
from app.core.module_manager import ModuleManager
from app.core.company_manager import CompanyManager

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
        
        from app.accounting.journal_entry_manager import JournalEntryManager
        from app.accounting.fiscal_period_manager import FiscalPeriodManager
        from app.accounting.currency_manager import CurrencyManager
        from app.accounting.forex_manager import ForexManager
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
        
        self._coa_manager_instance = ChartOfAccountsManager(self.account_service, self)
        self._je_manager_instance = JournalEntryManager(self.journal_service, self.account_service, self.fiscal_period_service, self)
        self._fp_manager_instance = FiscalPeriodManager(self) 
        self._currency_manager_instance = CurrencyManager(self) 
        self._tax_calculator_instance = TaxCalculator(self.tax_code_service) 
        self._gst_manager_instance = GSTManager(self)
        self._financial_statement_generator_instance = FinancialStatementGenerator(self)
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
        self._forex_manager_instance = ForexManager(self)
        
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
    # ... (all existing properties)
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

    # --- Manager Properties ---
    @property
    def company_manager(self) -> "CompanyManager":
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
    @property
    def forex_manager(self) -> "ForexManager":
        if not self._forex_manager_instance: raise RuntimeError("ForexManager not initialized.")
        return self._forex_manager_instance
```

---
https://drive.google.com/file/d/11X3f2mKRWl56NubmyAKo5dwck7p2JaLs/view?usp=sharing, https://drive.google.com/file/d/127qgzFTDe-WAnzFzOzBn2efixfG9w9YE/view?usp=sharing, https://drive.google.com/file/d/131RjCRl_kHc0XtnhCzDmf5bjgJX5iEww/view?usp=sharing, https://drive.google.com/file/d/13B_HcJmxgi3QGYHnj64s275QZN20pg3g/view?usp=sharing, https://drive.google.com/file/d/19n5zeGWlBAwCRFAXfbe4kY5xBK-uV-d7/view?usp=sharing, https://drive.google.com/file/d/1M5ybbmzIqj7IUo99Yle7xl_pkczow6Ci/view?usp=sharing, https://drive.google.com/file/d/1P4rxLCG8-5cJ2_vt2qKJqO2wxN26ro9T/view?usp=sharing, https://aistudio.google.com/app/prompts?state=%7B%22ids%22:%5B%221Rh0wsFMlVjsOSccPUo5JJmfB6gof_tS2%22%5D,%22action%22:%22open%22,%22userId%22:%22103961307342447084491%22,%22resourceKeys%22:%7B%7D%7D&usp=sharing, https://drive.google.com/file/d/1T1kVeTCKFOIzPckOmAarcwHC8x0yau1i/view?usp=sharing, https://drive.google.com/file/d/1dAgihzWoQ03fPAECRX4qUzJiiJppPgwz/view?usp=sharing, https://drive.google.com/file/d/1gM89F4jZMNsWNTd9bxJxPfRxY0Y2Vfof/view?usp=sharing, https://drive.google.com/file/d/1hAf_3y-ecY6gAU67N0KzgqGZz1XrDjed/view?usp=sharing, https://drive.google.com/file/d/1iLEa4z_1QZHLh5VEurZg7rUHZneQzsY8/view?usp=sharing, https://drive.google.com/file/d/1mO8_5fwtxIboAdjNo31vNNnNYbzI8-gq/view?usp=sharing

