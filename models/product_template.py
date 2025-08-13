from odoo import models, fields, api

class ProductTemplate(models.Model):
    _inherit = 'product.template'
    
    # InClue card specific fields
    is_inclue_card = fields.Boolean(
        string='Is InClue Card',
        default=False,
        help="Check if this product is an InClue educational card"
    )
    
    inclue_card_type = fields.Selection([
        ('participant_deck', 'Participant Deck'),
        ('facilitator_deck', 'Facilitator Deck'),
        ('gift_card', 'Gift Card'),
        ('followup_card', 'Follow-up Card'),
        ('promo_package', 'Promo Package'),
    ], string='InClue Card Type', help="Type of InClue card product")
    
    facilitator_access = fields.Selection([
        ('all', 'All Facilitators'),
        ('internal', 'Internal Only'),
        ('external', 'External Only'),
    ], string='Facilitator Access', default='all',
       help="Which type of facilitators can access this product")
    
    facilitator_pricing_type = fields.Selection([
        ('same', 'Same Price for All'),
        ('different', 'Different Prices'),
    ], string='Pricing Type', default='same',
       help="Whether pricing differs between facilitator types")

class ProductProduct(models.Model):
    _inherit = 'product.product'
    
    def get_facilitator_price(self, facilitator_type, pricelist):
        """Get price based on facilitator type and pricelist"""
        self.ensure_one()
        try:
            price = pricelist.get_product_price(self, 1.0, None)
            return price
        except:
            return self.list_price