from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)

class InclueEventInvoiceInfo(models.Model):
    _name = 'inclue.invoice.info'
    _description = 'Invoice Contact Information'

    company_name = fields.Char("Invoicing Company")
    address = fields.Text("Billing Address")
    contact_person = fields.Char("Contact Person")
    po_number = fields.Char("PO Number")
    email = fields.Char("Invoice Email")

    event_ids = fields.One2many('event.event', 'invoice_info_id', string="Events")
