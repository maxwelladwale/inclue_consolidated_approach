from odoo import models, fields

class ResUsers(models.Model):
    _inherit = 'res.users'

    is_facilitator = fields.Boolean(
        related='partner_id.is_facilitator',
        string='Is Facilitator',
        readonly=False
    )
    is_country_manager = fields.Boolean(
        related='partner_id.is_country_manager',
        string='Is Country Manager',
        readonly=False
    )
    facilitation_count = fields.Integer(
        related='partner_id.facilitation_count',
        string='Facilitation Count'
    )
    facilitated_event_ids = fields.One2many(
        related='partner_id.facilitated_event_ids',
        string='Facilitated Events',
        readonly=True
    )
    
    #  country management fields
    managed_countries_json = fields.Json(
        related='partner_id.managed_countries_json',
        string='Managed Countries Configuration',
        readonly=False
    )
    managed_country_ids = fields.Many2many(
        related='partner_id.managed_country_ids',
        string='Managed Countries',
        readonly=False
    )
    
    #  partner tags/categories
    category_id = fields.Many2many(
        related='partner_id.category_id',
        string='Tags',
        readonly=False,
        help='Tags for this user (Internal/External Facilitator, Country Manager, etc.)'
    )
    
    # Helper methods for easier country management
    def get_managed_country_ids(self):
        """Get list of managed country IDs"""
        return self.partner_id.get_managed_country_ids()
    
    def set_managed_countries(self, country_ids):
        """Set managed countries for this user"""
        return self.partner_id.set_managed_countries(country_ids, self.name)
    
    def manages_country(self, country_id):
        """Check if this user manages a specific country"""
        return self.partner_id.manages_country(country_id)
    
    # Action methods for the buttons in the view
    def action_view_country_orders(self):
        """Open a view showing orders from managed countries"""
        if not self.is_country_manager:
            return
        
        managed_country_ids = self.get_managed_country_ids()
        if not managed_country_ids:
            return
        
        # Create domain to filter orders by managed countries
        domain = [
            ('partner_id.country_id', 'in', managed_country_ids),
            ('facilitator_type', '!=', False),
            ('state', '!=', 'cancel')
        ]
        
        return {
            'name': f'Orders from Managed Countries - {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'view_mode': 'tree,form',
            'domain': domain,
            'context': {
                'default_partner_id': False,
                'search_default_group_by_country': 1,
            },
            'target': 'current',
        }
    
    def action_add_common_countries(self):
        """Quick action to add commonly managed countries"""
        common_country_codes = ['BE', 'NL', 'FR', 'DE', 'UK', 'US', 'CA']
        common_countries = self.env['res.country'].search([
            ('code', 'in', common_country_codes)
        ])
        
        current_ids = self.get_managed_country_ids()
        new_ids = list(set(current_ids + common_countries.ids))
        self.set_managed_countries(new_ids)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }
    
    def action_add_eu_countries(self):
        """Quick action to add all EU countries"""
        try:
            eu_group = self.env.ref('base.europe', raise_if_not_found=False)
            if eu_group:
                eu_countries = eu_group.country_ids
            else:
                # Fallback to manual EU country codes
                eu_codes = [
                    'AT', 'BE', 'BG', 'HR', 'CY', 'CZ', 'DK', 'EE', 'FI', 'FR',
                    'DE', 'GR', 'HU', 'IE', 'IT', 'LV', 'LT', 'LU', 'MT', 'NL',
                    'PL', 'PT', 'RO', 'SK', 'SI', 'ES', 'SE'
                ]
                eu_countries = self.env['res.country'].search([
                    ('code', 'in', eu_codes)
                ])
            
            current_ids = self.get_managed_country_ids()
            new_ids = list(set(current_ids + eu_countries.ids))
            self.set_managed_countries(new_ids)
            
            return {
                'type': 'ir.actions.client',
                'tag': 'reload',
            }
        except Exception:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': 'Could not load EU countries',
                    'type': 'warning',
                }
            }
    
    def action_country_statistics(self):
        """Show statistics for managed countries"""
        if not self.is_country_manager:
            return
        
        managed_countries = self.managed_country_ids
        if not managed_countries:
            return
        
        # You can create a custom wizard or view for statistics
        return {
            'name': f'Country Statistics - {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'res.country',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', managed_countries.ids)],
            'context': {
                'search_default_managed_countries': 1,
            },
            'target': 'current',
        }