from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)

class InclueEventInvoiceInfo(models.Model):
    _name = 'inclue.invoice.info'
    _description = 'Invoice Contact Information'
    _rec_name = 'company_name'

    company_name = fields.Char("Invoicing Company", required=True)
    address = fields.Text("Billing Address", required=True)
    contact_person = fields.Char("Contact Person", required=True)
    po_number = fields.Char("PO Number")
    email = fields.Char("Invoice Email", required=True, help="Email address where invoice should be sent")
    
    phone = fields.Char("Phone Number")
    tax_id = fields.Char("Tax ID/VAT Number")
    payment_terms = fields.Char("Payment Terms", default="Net 30")
    currency_id = fields.Many2one('res.currency', string="Preferred Currency", 
                                  default=lambda self: self.env.company.currency_id)
    
    event_ids = fields.One2many('event.event', 'invoice_info_id', string="Events")
    partner_id = fields.Many2one('res.partner', string="Related Partner",
                                help="If this invoice info is linked to an existing partner")
    
    event_count = fields.Integer("Event Count", compute='_compute_event_count')
    
    @api.depends('event_ids')
    def _compute_event_count(self):
        for record in self:
            record.event_count = len(record.event_ids)
    
    def name_get(self):
        """Custom name display"""
        result = []
        for record in self:
            if record.po_number:
                name = f"{record.company_name} (PO: {record.po_number})"
            else:
                name = record.company_name
            result.append((record.id, name))
        return result
    
    @api.model
    def create(self, vals):
        """Override create to potentially create/link partner"""
        record = super().create(vals)
        
        # Optionally create a partner if one doesn't exist
        if not record.partner_id and record.company_name:
            partner = record._find_or_create_partner()
            if partner:
                record.partner_id = partner.id
        
        return record
    
    def _find_or_create_partner(self):
        """Find existing partner or create new one based on invoice info"""
        # Search for existing partner by name or email
        partner = self.env['res.partner'].search([
            '|',
            ('name', '=', self.company_name),
            ('email', '=', self.email)
        ], limit=1)
        
        if not partner:
            # Create new partner
            partner_vals = {
                'name': self.company_name,
                'email': self.email,
                'phone': self.phone,
                'is_company': True,
                'street': self.address,
                'vat': self.tax_id,
                'customer_rank': 1,  # Mark as customer
            }
            
            try:
                partner = self.env['res.partner'].create(partner_vals)
                _logger.info("Created new partner ID %s for invoice info ID %s", partner.id, self.id)
            except Exception as e:
                _logger.error("Failed to create partner for invoice info ID %s: %s", self.id, str(e))
                partner = False
        
        return partner
    
    def action_view_events(self):
        """Action to view related events"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Related Events',
            'res_model': 'event.event',
            'view_mode': 'tree,form',
            'domain': [('invoice_info_id', '=', self.id)],
            'context': {'default_invoice_info_id': self.id}
        }
    
    def action_create_partner(self):
        """Manual action to create/update partner"""
        partner = self._find_or_create_partner()
        if partner:
            self.partner_id = partner.id
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Partner Created/Updated',
                    'message': f'Partner "{partner.name}" has been created/linked.',
                    'type': 'success',
                }
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error',
                    'message': 'Failed to create partner.',
                    'type': 'danger',
                }
            }