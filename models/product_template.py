from odoo import models, fields, api

class ProductTemplate(models.Model):
    _inherit = 'product.template'
    
    is_inclue_card = fields.Boolean('iN-Clue Card Product', default=False)
    inclue_card_type = fields.Selection([
        ('gift_card', 'Gift Card'),
        ('followup_card', 'Follow-up Card'),
        ('participant_deck', 'Participant Deck'),
        ('facilitator_deck', 'Facilitator Deck'),
        ('promo_package', 'Promo Package'),
    ], string='Card Type')

    facilitator_access = fields.Selection([
        ('all', 'All Facilitators'),
        ('external', 'External Facilitators Only'),
        ('internal', 'Internal Facilitators Only'),
    ], string='Facilitator Access', default='all')
    
    facilitator_pricing_type = fields.Selection([
        ('same', 'Same Price for All Facilitators'),
        ('different', 'Different Prices by Facilitator Type'),
    ], string='Pricing Type', default='same')

class ProductProduct(models.Model):
    _inherit = 'product.product'
    
    def get_facilitator_price(self, facilitator_type='external', pricelist=None):
        """Get price for specific facilitator type"""
        self.ensure_one()
        
        if self.facilitator_pricing_type == 'different' and pricelist:
            # Use pricelist to get facilitator-specific pricing
            price = pricelist._get_product_price(self, 1.0, partner=None, date=fields.Date.today())
            return price
        
        # Default to list price
        return self.list_price
