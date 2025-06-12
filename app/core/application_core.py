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
