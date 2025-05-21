from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class FacilitatorOrder(models.Model):
    _name = "inclue.facilitator.order"
    _description = "Facilitator Order"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = "create_date desc"
    
    name = fields.Char("Order Reference", required=True, copy=False, readonly=True, 
                       default=lambda self: 'New')
    
    # Facilitator information
    facilitator_id = fields.Many2one(
        'res.partner', 
        string='Facilitator',
        required=True,
        tracking=True
    )
    facility_language_id = fields.Many2one(
        'res.lang', 
        string='Facility Language', 
        required=True,
        tracking=True
    )
    facilitator_type = fields.Selection([
        ('internal', 'In-House Facilitator'),
        ('external', 'External Facilitator')
    ], string='Facilitator Type', required=True, tracking=True)
    company_id = fields.Many2one(
        'res.company', 
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        tracking=True
    )
    
    # Card ordering options with quantities
    gift_card_qty = fields.Integer(
        string="Gift Cards Quantity", 
        default=0,
        tracking=True
    )
    followup_card_qty = fields.Integer(
        string="Follow-up Cards Quantity", 
        default=0,
        tracking=True
    )
    participant_deck_qty = fields.Integer(
        string="Participant Deck Quantity", 
        default=0,
        tracking=True
    )
    facilitator_deck_qty = fields.Integer(
        string="Facilitator Deck Quantity", 
        default=0,
        tracking=True
    )
    
    # Shipping information
    shipping_address = fields.Text(
        string='Shipping Address', 
        tracking=True
    )
    shipping_country_id = fields.Many2one(
        'res.country', 
        string='Shipping Country', 
        tracking=True
    )
    contact_person = fields.Char(
        string='Contact Person', 
        tracking=True
    )
    
    # Invoice information
    invoice_company_name = fields.Char(
        string='Invoice Company Name', 
        tracking=True
    )
    invoice_address = fields.Text(
        string='Invoice Address', 
        tracking=True
    )
    invoice_country_id = fields.Many2one(
        'res.country', 
        string='Invoice Country',
        tracking=True
    )
    po_number = fields.Char(
        string='PO Number', 
        tracking=True
    )
    
    # Calculated fields
    total_price = fields.Float(
        string='Total Price',
        compute='_compute_total_price',
        store=True
    )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('invoiced', 'Invoiced'),
        ('shipped', 'Shipped'),
        ('done', 'Done'),
        ('cancel', 'Cancelled')
    ], string='Status', default='draft', tracking=True)
    
    # Companion fields
    has_been_processed = fields.Boolean(string='Processed', default=False, tracking=True)
    invoice_id = fields.Many2one('account.move', string='Invoice', tracking=True)
    
    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('inclue.facilitator.order') or 'New'
        
        order = super(FacilitatorOrder, self).create(vals)
        return order
    
    @api.depends('participant_deck_qty', 'facilitator_deck_qty', 'facilitator_type')
    def _compute_total_price(self):
        for order in self:
            total = 0.0
            
            # Participant deck pricing
            if order.participant_deck_qty > 0:
                # Adjust price per deck based on facilitator type
                price_per_deck = 15.0 if order.facilitator_type == 'internal' else 25.0
                total += order.participant_deck_qty * price_per_deck
            
            # Facilitator deck pricing    
            if order.facilitator_deck_qty > 0:
                # Adjust price per facilitator deck based on facilitator type
                price_per_fdeck = 30.0 if order.facilitator_type == 'internal' else 50.0  
                total += order.facilitator_deck_qty * price_per_fdeck
            
            # Gift cards and follow-up cards are free
            order.total_price = total
    
    def action_confirm(self):
        self.write({'state': 'confirmed'})
        
        # Send email notification to admin or procurement team
        template = self.env.ref('inclue_facilitator.email_template_order_confirmed', False)
        if template:
            for order in self:
                template.send_mail(order.id, force_send=True)
                
        return True
    
    def action_invoice(self):
        """Create invoice for this order"""
        for order in self:
            if order.state != 'confirmed':
                continue
                
            if not order.total_price or order.total_price <= 0:
                # For free items, we can skip the invoice and go straight to shipping
                order.write({'state': 'shipped'})
                order.message_post(
                    body="Order contains only free items. Moved directly to shipping stage.",
                    subject="Order Processing: Free Items"
                )
                continue
                
            # Check if invoice already exists
            if order.invoice_id:
                raise UserError(_("An invoice has already been created for this order."))
                
            # Create invoice values
            invoice_vals = self._prepare_invoice_values()
            
            # Add invoice lines
            invoice_vals['invoice_line_ids'] = self._prepare_invoice_lines()
            
            # Create invoice
            invoice = self.env['account.move'].create(invoice_vals)
            
            # Link invoice to order
            order.invoice_id = invoice.id
            
            # Update order state
            order.write({'state': 'invoiced'})
            
            # Log the invoice creation
            order.message_post(
                body=f"📄 Invoice {invoice.name} created for this order.",
                subject=f"Invoice Created: {invoice.name}"
            )
        
        # Open the created invoice
        if len(self) == 1 and self.invoice_id:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Invoice'),
                'res_model': 'account.move',
                'res_id': self.invoice_id.id,
                'view_mode': 'form',
                'target': 'current',
            }
        
        return True

    def _prepare_invoice_values(self):
        """Prepare the invoice values"""
        self.ensure_one()
        
        partner_id = self.facilitator_id.id
        
        # If specific invoice information is provided, try to find the partner
        if self.invoice_company_name:
            partner = self.env['res.partner'].search([
                ('name', '=', self.invoice_company_name),
                ('type', '=', 'invoice')
            ], limit=1)
            
            if partner:
                partner_id = partner.id
        
        return {
            'move_type': 'out_invoice',
            'partner_id': partner_id,
            'invoice_date': fields.Date.context_today(self),
            'ref': self.name,
            'narration': f"Order Reference: {self.name}",
            'invoice_origin': self.name,
            'currency_id': self.company_id.currency_id.id,
            'company_id': self.company_id.id,
        }
    
    def _prepare_invoice_lines(self):
        """Prepare invoice lines based on ordered items"""
        self.ensure_one()
        invoice_lines = []
        
        # Add invoice line for participant decks if ordered
        if self.participant_deck_qty > 0:
            price_per_deck = 15.0 if self.facilitator_type == 'internal' else 25.0
            
            participant_deck_product = self._get_or_create_product(
                'Participant Deck', 
                'service',
                price_per_deck
            )
            
            invoice_lines.append((0, 0, {
                'product_id': participant_deck_product.id,
                'name': f"Participant Deck",
                'quantity': self.participant_deck_qty,
                'price_unit': price_per_deck,
            }))
        
        # Add invoice line for facilitator decks if ordered
        if self.facilitator_deck_qty > 0:
            price_per_fdeck = 30.0 if self.facilitator_type == 'internal' else 50.0
            
            facilitator_deck_product = self._get_or_create_product(
                'Facilitator Deck', 
                'service',
                price_per_fdeck
            )
            
            invoice_lines.append((0, 0, {
                'product_id': facilitator_deck_product.id,
                'name': "Facilitator Deck",
                'quantity': self.facilitator_deck_qty,
                'price_unit': price_per_fdeck,
            }))
        
        return invoice_lines

    def _get_or_create_product(self, name, product_type, price):
        """Get or create a product for invoicing"""
        product = self.env['product.product'].search([
            ('name', '=', name),
            ('type', '=', product_type),
            ('company_id', 'in', [self.company_id.id, False])
        ], limit=1)
        
        if not product:
            product = self.env['product.product'].create({
                'name': name,
                'type': product_type,
                'list_price': price,
                'standard_price': price * 0.8,
                'company_id': self.company_id.id,
                'sale_ok': True,
                'purchase_ok': False,
            })
        
        return product
    
    def action_view_invoice(self):
        """Open the invoice related to this order"""
        self.ensure_one()
        if not self.invoice_id:
            raise UserError(_("No invoice exists for this order."))
            
        return {
            'type': 'ir.actions.act_window',
            'name': _('Invoice'),
            'res_model': 'account.move',
            'res_id': self.invoice_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
        
    def action_set_shipped(self):
        self.write({'state': 'shipped'})
        # Send email notification that items have been shipped
        template = self.env.ref('inclue_facilitator.email_template_order_shipped', False)
        if template:
            for order in self:
                template.send_mail(order.id, force_send=True)
        return True
    
    def action_set_done(self):
        self.write({'state': 'done'})
        return True
    
    def action_cancel(self):
        self.write({'state': 'cancel'})
        return True