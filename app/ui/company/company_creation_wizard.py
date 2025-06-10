# File: app/ui/company/company_creation_wizard.py
from PySide6.QtWidgets import QWizard, QWizardPage, QVBoxLayout, QFormLayout, QLineEdit, QLabel, QCheckBox
from PySide6.QtCore import Signal
from typing import Optional, Dict

class CompanyCreationWizard(QWizard):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.addPage(IntroPage())
        self.addPage(DetailsPage())
        self.addPage(FinalPage())
        self.setWindowTitle("New Company Setup Wizard")
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)

class IntroPage(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Welcome to SG Bookkeeper Setup")
        self.setSubTitle("This wizard will guide you through creating a new company file.")
        
        layout = QVBoxLayout(self)
        label = QLabel(
            "A new, separate database will be created to store all data for this company, "
            "ensuring complete data isolation.\n\n"
            "You will need PostgreSQL administrator credentials for the initial database creation."
        )
        label.setWordWrap(True)
        layout.addWidget(label)
        self.setLayout(layout)

class DetailsPage(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Company Details")
        self.setSubTitle("Please provide the basic details for your new company.")
        
        layout = QFormLayout(self)
        self.company_name_edit = QLineEdit()
        self.db_name_edit = QLineEdit()
        self.use_default_coa_check = QCheckBox("Load default Chart of Accounts")
        self.use_default_coa_check.setChecked(True)
        
        self.registerField("companyName*", self.company_name_edit)
        self.registerField("dbName*", self.db_name_edit)
        self.registerField("useDefaultCoa", self.use_default_coa_check)
        
        layout.addRow("Company Name*:", self.company_name_edit)
        layout.addRow("Database Name*:", self.db_name_edit)
        layout.addRow(self.use_default_coa_check)
        
        hint_label = QLabel("Database name must be lowercase, with no spaces or special characters (underscores are allowed).")
        hint_label.setWordWrap(True)
        layout.addRow("", hint_label)
        
        self.setLayout(layout)
        
        self.company_name_edit.textChanged.connect(self.auto_populate_db_name)

    def auto_populate_db_name(self, text):
        import re
        db_name_suggestion = text.lower()
        db_name_suggestion = re.sub(r'[^a-z0-9_]+', '_', db_name_suggestion)
        db_name_suggestion = re.sub(r'__+', '_', db_name_suggestion)
        db_name_suggestion = db_name_suggestion.strip('_')
        self.db_name_edit.setText("sgb_" + db_name_suggestion[:40])

    def validatePage(self) -> bool:
        import re
        if not self.field("companyName"):
            QMessageBox.warning(self, "Input Error", "Company Name cannot be empty.")
            return False
        db_name = self.field("dbName")
        if not db_name:
            QMessageBox.warning(self, "Input Error", "Database Name cannot be empty.")
            return False
        if not re.match(r'^[a-z_][a-z0-9_]*$', db_name):
            QMessageBox.warning(self, "Invalid Database Name", "Database name must start with a lowercase letter or underscore, and contain only lowercase letters, numbers, and underscores.")
            return False
        return True

class FinalPage(QWizardPage):
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
