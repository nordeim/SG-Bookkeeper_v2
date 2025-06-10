# app/ui/customers/customers_widget.py
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableView, QPushButton, 
    QToolBar, QMenu, QHeaderView, QAbstractItemView, QMessageBox,
    QLabel, QLineEdit, QCheckBox # Added for filtering/search
)
from PySide6.QtCore import Qt, Slot, QTimer, QMetaObject, Q_ARG, QModelIndex, QSize
from PySide6.QtGui import QIcon, QAction
from typing import Optional, List, Dict, Any, TYPE_CHECKING

import json

from app.core.application_core import ApplicationCore
from app.main import schedule_task_from_qt
from app.ui.customers.customer_table_model import CustomerTableModel # New import
from app.ui.customers.customer_dialog import CustomerDialog # New import
from app.utils.pydantic_models import CustomerSummaryData # For type hinting
from app.utils.json_helpers import json_converter, json_date_hook
from app.utils.result import Result
from app.models.business.customer import Customer # For Result type hint from manager

if TYPE_CHECKING:
    from PySide6.QtGui import QPaintDevice

class CustomersWidget(QWidget):
    def __init__(self, app_core: ApplicationCore, parent: Optional["QWidget"] = None):
        super().__init__(parent)
        self.app_core = app_core
        
        self.icon_path_prefix = "resources/icons/" 
        try:
            import app.resources_rc 
            self.icon_path_prefix = ":/icons/"
            self.app_core.logger.info("Using compiled Qt resources for CustomersWidget.")
        except ImportError:
            self.app_core.logger.info("CustomersWidget: Compiled Qt resources not found. Using direct file paths.")
            pass
        
        self._init_ui()
        QTimer.singleShot(0, lambda: schedule_task_from_qt(self._load_customers()))

    def _init_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setSpacing(5)

        # --- Toolbar ---
        self._create_toolbar()
        self.main_layout.addWidget(self.toolbar)

        # --- Filter/Search Area ---
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Search:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Enter code, name, or email...")
        self.search_edit.returnPressed.connect(self.toolbar_refresh_action.trigger) # Trigger refresh on Enter
        filter_layout.addWidget(self.search_edit)

        self.show_inactive_check = QCheckBox("Show Inactive")
        self.show_inactive_check.stateChanged.connect(self.toolbar_refresh_action.trigger) # Trigger refresh on change
        filter_layout.addWidget(self.show_inactive_check)
        filter_layout.addStretch()
        self.main_layout.addLayout(filter_layout)

        # --- Table View ---
        self.customers_table = QTableView()
        self.customers_table.setAlternatingRowColors(True)
        self.customers_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.customers_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.customers_table.horizontalHeader().setStretchLastSection(True)
        self.customers_table.doubleClicked.connect(self._on_edit_customer) # Or view
        self.customers_table.setSortingEnabled(True)

        self.table_model = CustomerTableModel()
        self.customers_table.setModel(self.table_model)
        
        # Configure columns after model is set
        if "ID" in self.table_model._headers:
            self.customers_table.setColumnHidden(self.table_model._headers.index("ID"), True)
        if "Name" in self.table_model._headers:
            name_col_idx = self.table_model._headers.index("Name")
            self.customers_table.horizontalHeader().setSectionResizeMode(name_col_idx, QHeaderView.ResizeMode.Stretch)
        else: # Fallback if "Name" header changes
             self.customers_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)


        self.main_layout.addWidget(self.customers_table)
        self.setLayout(self.main_layout)

        if self.customers_table.selectionModel():
            self.customers_table.selectionModel().selectionChanged.connect(self._update_action_states)
        self._update_action_states()


    def _create_toolbar(self):
        self.toolbar = QToolBar("Customer Toolbar")
        self.toolbar.setIconSize(QSize(16, 16))

        self.toolbar_add_action = QAction(QIcon(self.icon_path_prefix + "add.svg"), "Add Customer", self)
        self.toolbar_add_action.triggered.connect(self._on_add_customer)
        self.toolbar.addAction(self.toolbar_add_action)

        self.toolbar_edit_action = QAction(QIcon(self.icon_path_prefix + "edit.svg"), "Edit Customer", self)
        self.toolbar_edit_action.triggered.connect(self._on_edit_customer)
        self.toolbar.addAction(self.toolbar_edit_action)

        self.toolbar_toggle_active_action = QAction(QIcon(self.icon_path_prefix + "deactivate.svg"), "Toggle Active", self)
        self.toolbar_toggle_active_action.triggered.connect(self._on_toggle_active_status)
        self.toolbar.addAction(self.toolbar_toggle_active_action)
        
        self.toolbar.addSeparator()
        self.toolbar_refresh_action = QAction(QIcon(self.icon_path_prefix + "refresh.svg"), "Refresh List", self)
        self.toolbar_refresh_action.triggered.connect(lambda: schedule_task_from_qt(self._load_customers()))
        self.toolbar.addAction(self.toolbar_refresh_action)


    @Slot()
    def _update_action_states(self):
        selected_rows = self.customers_table.selectionModel().selectedRows()
        has_selection = bool(selected_rows)
        single_selection = len(selected_rows) == 1
        
        self.toolbar_edit_action.setEnabled(single_selection)
        self.toolbar_toggle_active_action.setEnabled(single_selection)

    async def _load_customers(self):
        if not self.app_core.customer_manager:
            self.app_core.logger.error("CustomerManager not available in CustomersWidget.")
            QMetaObject.invokeMethod(QMessageBox.staticMetaObject, "critical", Qt.ConnectionType.QueuedConnection,
                Q_ARG(QWidget, self), Q_ARG(str, "Error"), Q_ARG(str,"Customer Manager component not available."))
            return
        try:
            search_term = self.search_edit.text().strip() or None
            active_only = not self.show_inactive_check.isChecked()
            
            # For MVP, pagination is handled by service if params are passed. UI doesn't have page controls yet.
            result: Result[List[CustomerSummaryData]] = await self.app_core.customer_manager.get_customers_for_listing(
                active_only=active_only, 
                search_term=search_term,
                page=1, # Default to first page
                page_size=200 # Load a reasonable number for MVP table
            )
            
            if result.is_success:
                data_for_table = result.value if result.value is not None else []
                json_data = json.dumps([dto.model_dump() for dto in data_for_table], default=json_converter)
                QMetaObject.invokeMethod(self, "_update_table_model_slot", Qt.ConnectionType.QueuedConnection, Q_ARG(str, json_data))
            else:
                error_msg = f"Failed to load customers: {', '.join(result.errors)}"
                self.app_core.logger.error(error_msg)
                QMetaObject.invokeMethod(QMessageBox.staticMetaObject, "warning", Qt.ConnectionType.QueuedConnection,
                    Q_ARG(QWidget, self), Q_ARG(str, "Load Error"), Q_ARG(str, error_msg))
        except Exception as e:
            error_msg = f"Unexpected error loading customers: {str(e)}"
            self.app_core.logger.error(error_msg, exc_info=True)
            QMetaObject.invokeMethod(QMessageBox.staticMetaObject, "critical", Qt.ConnectionType.QueuedConnection,
                Q_ARG(QWidget, self), Q_ARG(str, "Load Error"), Q_ARG(str, error_msg))

    @Slot(str)
    def _update_table_model_slot(self, json_data_str: str):
        try:
            list_of_dicts = json.loads(json_data_str, object_hook=json_date_hook)
            # Convert list of dicts to list of CustomerSummaryData DTOs
            customer_summaries: List[CustomerSummaryData] = [CustomerSummaryData.model_validate(item) for item in list_of_dicts]
            self.table_model.update_data(customer_summaries)
        except json.JSONDecodeError as e:
            QMessageBox.critical(self, "Data Error", f"Failed to parse customer data: {e}")
        except Exception as p_error: # Catch Pydantic validation errors too
            QMessageBox.critical(self, "Data Error", f"Invalid customer data format: {p_error}")
        finally:
            self._update_action_states()

    @Slot()
    def _on_add_customer(self):
        if not self.app_core.current_user:
            QMessageBox.warning(self, "Auth Error", "Please log in to add a customer.")
            return
        
        dialog = CustomerDialog(self.app_core, self.app_core.current_user.id, parent=self)
        dialog.customer_saved.connect(lambda _id: schedule_task_from_qt(self._load_customers()))
        dialog.exec()

    def _get_selected_customer_id(self) -> Optional[int]:
        selected_rows = self.customers_table.selectionModel().selectedRows()
        if not selected_rows or len(selected_rows) > 1:
            QMessageBox.information(self, "Selection", "Please select a single customer.")
            return None
        return self.table_model.get_customer_id_at_row(selected_rows[0].row())

    @Slot()
    def _on_edit_customer(self):
        customer_id = self._get_selected_customer_id()
        if customer_id is None: return

        if not self.app_core.current_user:
            QMessageBox.warning(self, "Auth Error", "Please log in to edit a customer.")
            return
            
        dialog = CustomerDialog(self.app_core, self.app_core.current_user.id, customer_id=customer_id, parent=self)
        dialog.customer_saved.connect(lambda _id: schedule_task_from_qt(self._load_customers()))
        dialog.exec()
        
    @Slot(QModelIndex)
    def _on_view_customer_double_click(self, index: QModelIndex):
        if not index.isValid(): return
        customer_id = self.table_model.get_customer_id_at_row(index.row())
        if customer_id is None: return
        # For MVP, double-click also opens for edit. Can be changed to view-only later.
        if not self.app_core.current_user:
            QMessageBox.warning(self, "Auth Error", "Please log in to view/edit customer.")
            return
        dialog = CustomerDialog(self.app_core, self.app_core.current_user.id, customer_id=customer_id, parent=self)
        dialog.customer_saved.connect(lambda _id: schedule_task_from_qt(self._load_customers()))
        dialog.exec()


    @Slot()
    def _on_toggle_active_status(self):
        customer_id = self._get_selected_customer_id()
        if customer_id is None: return

        if not self.app_core.current_user:
            QMessageBox.warning(self, "Auth Error", "Please log in to change customer status.")
            return
            
        # Confirm action
        customer_status_active = self.table_model.get_customer_status_at_row(self.customers_table.currentIndex().row())
        action_verb = "deactivate" if customer_status_active else "activate"
        reply = QMessageBox.question(self, f"Confirm {action_verb.capitalize()}",
                                     f"Are you sure you want to {action_verb} this customer?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.No:
            return

        future = schedule_task_from_qt(
            self.app_core.customer_manager.toggle_customer_active_status(customer_id, self.app_core.current_user.id)
        )
        if future: future.add_done_callback(self._handle_toggle_active_result)
        else: self._handle_toggle_active_result(None)

    def _handle_toggle_active_result(self, future):
        if future is None: QMessageBox.critical(self, "Task Error", "Failed to schedule customer status toggle."); return
        try:
            result: Result[Customer] = future.result()
            if result.is_success:
                action_verb_past = "activated" if result.value and result.value.is_active else "deactivated"
                QMessageBox.information(self, "Success", f"Customer {action_verb_past} successfully.")
                schedule_task_from_qt(self._load_customers()) # Refresh list
            else:
                QMessageBox.warning(self, "Error", f"Failed to toggle customer status:\n{', '.join(result.errors)}")
        except Exception as e:
            self.app_core.logger.error(f"Error handling toggle active status result: {e}", exc_info=True)
            QMessageBox.critical(self, "Error", f"An unexpected error occurred: {str(e)}")

