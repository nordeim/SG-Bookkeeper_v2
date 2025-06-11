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
