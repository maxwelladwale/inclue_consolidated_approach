from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class InternalFacilitatorOrder(models.Model):
    _name = "inclue.facilitator.order"
    _description = "Internal Facilitator Order"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = "create_date desc"
    
    # Add dummy fields to avoid errors during transition
    # These will be removed in a future update after data migration
    event_id = fields.Integer(string='Legacy Event ID', help="Technical field for compatibility", store=False)
    auto_create_event = fields.Boolean(string='Legacy Auto-Create', help="Technical field for compatibility", store=False)
    
    name = fields.Char("Order Reference", required=True, copy=False, readonly=True, 
                       default=lambda self: 'New')
    
    # Facilitator information
    facilitator_id = fields.Many2one(
        'res.partner', 
        string='Facilitator',
        required=True,
        domain="[('is_facilitator', '=', True), ('category_id', 'ilike', 'Internal Facilitator')]",
        tracking=True
    )
    company_id = fields.Many2one(
        'res.company', 
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        tracking=True
    )
    
    # Card ordering options
    order_gift_cards = fields.Boolean(
        string="Gift Cards", 
        help="Free gift cards",
        tracking=True
    )
    order_followup_cards = fields.Boolean(
        string="Follow-up Cards", 
        help="Free follow-up cards",
        tracking=True
    )
    order_participant_deck = fields.Boolean(
        string="Participant Deck", 
        help="Paid participant deck",
        tracking=True
    )
    order_facilitator_deck = fields.Boolean(
        string="Facilitator Deck", 
        help="Paid facilitator deck",
        tracking=True
    )
    
    # Session information
    facility_country_id = fields.Many2one(
        'res.country', 
        string='Facility Country', 
        tracking=True
    )
    facility_language_id = fields.Many2one(
        'res.lang', 
        string='Language', 
        tracking=True
    )
    facility_date = fields.Date(
        string='Facilitation Date', 
        tracking=True
    )
    team_lead_name = fields.Char(
        string='Team Lead Name', 
        tracking=True
    )
    attendee_count = fields.Integer(
        string='Number of Attendees', 
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
    contact_person = fields.Char(
        string='Contact Person', 
        tracking=True
    )
    po_number = fields.Char(
        string='PO Number', 
        tracking=True
    )
    
    # Calculated fields
    price_per_participant = fields.Float(
        string='Price per Participant',
        compute='_compute_price_per_participant',
        store=True
    )
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
        
        order = super(InternalFacilitatorOrder, self).create(vals)
        return order
    
    @api.depends('attendee_count', 'order_participant_deck')
    def _compute_price_per_participant(self):
        for order in self:
            if not order.order_participant_deck:
                order.price_per_participant = 0.0
                continue
                
            if order.attendee_count <= 10:
                order.price_per_participant = 10.0  # €10 per participant
            elif order.attendee_count <= 15:
                order.price_per_participant = 15.0  # €15 per participant
            else:
                order.price_per_participant = 20.0  # €20 per participant
    
    @api.depends('attendee_count', 'price_per_participant', 'order_facilitator_deck')
    def _compute_total_price(self):
        for order in self:
            participant_total = 0.0
            facilitator_deck_price = 0.0
            
            if order.order_participant_deck and order.attendee_count > 0:
                participant_total = order.price_per_participant * order.attendee_count
                
            if order.order_facilitator_deck:
                facilitator_deck_price = 50.0  # Base price for facilitator deck
                
            order.total_price = participant_total + facilitator_deck_price
    
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
                raise UserError(_("Cannot create invoice: Order has no billable items."))
                
            # Check if invoice already exists
            if order.invoice_id:
                raise UserError(_("An invoice has already been created for this order."))
                
            # Create invoice values
            invoice_vals = {
                'move_type': 'out_invoice',
                'partner_id': order.facilitator_id.id,
                'invoice_date': fields.Date.context_today(order),
                'ref': order.name,
                'narration': f"Order: {order.name} - Facilitation Date: {order.facility_date}",
                'invoice_origin': order.name,
                'currency_id': order.company_id.currency_id.id,
                'company_id': order.company_id.id,
                'invoice_line_ids': [],
            }
            
            # If specific invoice information is provided, use it
            if order.invoice_company_name:
                # Try to find partner by name
                partner = self.env['res.partner'].search([
                    ('name', '=', order.invoice_company_name),
                    ('type', '=', 'invoice')
                ], limit=1)
                
                if partner:
                    invoice_vals['partner_id'] = partner.id
            
            # Add invoice line for participant deck if ordered
            if order.order_participant_deck and order.attendee_count > 0:
                # Get or create product for participant deck
                participant_deck_product = self._get_or_create_product(
                    'Participant Deck', 
                    'service', 
                    order.price_per_participant
                )
                
                invoice_vals['invoice_line_ids'].append((0, 0, {
                    'product_id': participant_deck_product.id,
                    'name': f"Participant Deck ({order.attendee_count})",
                    'quantity': order.attendee_count,
                    'price_unit': order.price_per_participant,
                }))
            
            # Add invoice line for facilitator deck if ordered
            if order.order_facilitator_deck:
                # Get or create product for facilitator deck
                facilitator_deck_product = self._get_or_create_product(
                    'Facilitator Deck', 
                    'service', 
                    50.0
                )
                
                invoice_vals['invoice_line_ids'].append((0, 0, {
                    'product_id': facilitator_deck_product.id,
                    'name': "Facilitator Deck",
                    'quantity': 1,
                    'price_unit': 50.0,
                }))
            
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
                'standard_price': price,
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
        return True
    
    def action_set_done(self):
        self.write({'state': 'done'})
        return True
    
    def action_cancel(self):
        self.write({'state': 'cancel'})
        return True