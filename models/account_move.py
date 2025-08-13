from odoo import models, fields, api

class AccountMove(models.Model):
    _inherit = 'account.move'
    
    facilitator_type = fields.Selection([
        ('internal', 'In-House Facilitator'),
        ('external', 'External Facilitator')
    ], string='Facilitator Type', tracking=True)
    
    facility_language_id = fields.Many2one(
        'res.lang', 
        string='Facility Language', 
        tracking=True
    )

    auto_processed = fields.Boolean(
        'Auto Processed', 
        default=False, 
        readonly=True,
        help="Indicates if this order was automatically processed"
    )
        
    # Shipping/delivery information
    shipping_address_custom = fields.Text(
        string='Custom Shipping Address',
        help="Custom shipping address if different from partner address"
    )
    contact_person = fields.Char(string='Contact Person', tracking=True)
    
    # Invoice details
    invoice_company_name = fields.Char(string='Invoice Company Name', tracking=True)
    invoice_address_custom = fields.Text(
        string='Custom Invoice Address',
        help="Custom invoice address if different from partner address"
    )
    po_number = fields.Char(string='PO Number', tracking=True)
    
    # Delivery details (for internal facilitators)
    delivery_contact_name = fields.Char(
        string='Delivery Contact Name',
        tracking=True,
        required=False,
        help="Name of the person at the delivery address"
    )
    
    delivery_vat_number = fields.Char(
        string='Delivery VAT Number',
        tracking=True,
        required=False,
        help="VAT number for the delivery location/company"
    )
    
    delivery_email = fields.Char(
        string='Delivery Contact Email',
        tracking=True,
        required=False,
        help="Email address of the contact person at delivery location"
    )
    
    # Computed legacy fields for compatibility
    gift_card_qty = fields.Integer(
        string="Gift Cards Quantity", 
        compute='_compute_facilitator_quantities',
        store=False
    )
    followup_card_qty = fields.Integer(
        string="Follow-up Cards Quantity", 
        compute='_compute_facilitator_quantities',
        store=False
    )
    participant_deck_qty = fields.Integer(
        string="Participant Deck Quantity", 
        compute='_compute_facilitator_quantities',
        store=False
    )
    facilitator_deck_qty = fields.Integer(
        string="Facilitator Deck Quantity", 
        compute='_compute_facilitator_quantities',
        store=False
    )
    promo_package_qty = fields.Integer(
        string="Promo Package Quantity", 
        compute='_compute_facilitator_quantities',
        store=False
    )
    
    @api.depends('invoice_line_ids.product_id', 'invoice_line_ids.quantity')
    def _compute_facilitator_quantities(self):
        """Compute facilitator quantities from invoice lines"""
        for invoice in self:
            gift_qty = followup_qty = participant_qty = facilitator_qty = promo_qty = 0
            
            for line in invoice.invoice_line_ids:
                if line.product_id and hasattr(line.product_id, 'inclue_card_type'):
                    card_type = line.product_id.inclue_card_type
                    if card_type == 'gift_card':
                        gift_qty += line.quantity
                    elif card_type == 'followup_card':
                        followup_qty += line.quantity
                    elif card_type == 'participant_deck':
                        participant_qty += line.quantity
                    elif card_type == 'facilitator_deck':
                        facilitator_qty += line.quantity
                    elif card_type == 'promo_package':
                        promo_qty += line.quantity
            
            invoice.gift_card_qty = gift_qty
            invoice.followup_card_qty = followup_qty
            invoice.participant_deck_qty = participant_qty
            invoice.facilitator_deck_qty = facilitator_qty
            invoice.promo_package_qty = promo_qty
            