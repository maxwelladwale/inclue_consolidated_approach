from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)

class ResPartner(models.Model):
    _inherit = 'res.partner'
    
    is_contact = fields.Boolean(
        string='Is Contact Person',
        default=False,
        help="Mark this record as a contact person for filtering purposes"
    )
    
    is_hr_contact = fields.Boolean(
        string='Is HR Contact',
        default=False,
        help="Mark this as an HR/People/Talent related contact"
    )
    is_team_leader = fields.Boolean(
        string='Is Team Leader',
        default=False,
        help="Mark this as a team leader for filtering purposes"
    )
    is_finance_contact = fields.Boolean(
        string='Is Finance Contact',
        default=False,
        help="Mark this as a Finance/Accounting/Billing related contact"
    )
    customer_rank = fields.Integer(
        string='Customer Rank',
        default=0,
        help="Rank of this partner as a customer"
    )

    managed_countries_json = fields.Json(
        string='Managed Countries Configuration',
        help='JSON configuration for countries managed by this country manager',
        default=lambda self: {'country_ids': [], 'updated_by': None, 'updated_date': None}
    )

    managed_country_ids = fields.Many2many(
        'res.country',
        compute='_compute_managed_country_ids',
        string='Managed Countries (Computed)',
        help='Computed field based on JSON configuration'
    )
    
    is_facilitator = fields.Boolean('Is Facilitator', default=False)
    is_country_manager = fields.Boolean('Is Country Manager', default=False)
    facilitated_event_ids = fields.One2many('event.event', 'facilitator_id', string='Facilitated Events')
    facilitation_count = fields.Integer('Facilitation Count', compute='_compute_facilitation_stats')
    
    @api.depends('facilitated_event_ids')
    def _compute_facilitation_stats(self):
        for partner in self:
            partner.facilitation_count = len(partner.facilitated_event_ids)

    @api.model
    def create(self, vals):
        """Override create to auto-set contact flags based on context and data"""
        partner = super(ResPartner, self).create(vals)
        partner._auto_set_contact_flags()
        return partner
    
    def write(self, vals):
        """Override write to update contact flags when relevant fields change"""
        result = super(ResPartner, self).write(vals)
        
        # Update flags if function or other relevant fields change
        if 'function' in vals or 'is_company' in vals or 'parent_id' in vals:
            for partner in self:
                partner._auto_set_contact_flags()
        
        return result
    
    def _auto_set_contact_flags(self):
        """Automatically set contact flags based on partner data"""
        for partner in self:
            # Auto-set is_contact flag
            if not partner.is_company and partner.id not in [2, 4, 5, 6, 8]:  # Exclude system records
                # Set as contact if it's an individual and not a system record
                if not partner.name or 'template' not in partner.name.lower():
                    partner.is_contact = True
            
            # Auto-set HR contact flag based on function
            if partner.function:
                hr_terms = ['hr', 'human resource', 'people', 'talent', 'recruitment', 'learning', 'development', 'training']
                if any(term in partner.function.lower() for term in hr_terms):
                    partner.is_hr_contact = True
                else:
                    partner.is_hr_contact = False
            
            # Auto-set finance contact flag based on function
            if partner.function:
                finance_terms = ['finance', 'accounting', 'billing', 'procurement', 'purchasing', 'accounts', 'treasury']
                if any(term in partner.function.lower() for term in finance_terms):
                    partner.is_finance_contact = True
                else:
                    partner.is_finance_contact = False
    
    @api.model
    def update_existing_contact_flags(self):
        """
        One-time method to update existing records with contact flags
        Run this after installing the new fields
        """
        _logger.info("Starting to update existing contact flags...")
        
        # Get all partners
        all_partners = self.search([])
        
        for partner in all_partners:
            partner._auto_set_contact_flags()
        
        _logger.info("Finished updating %d partner records with contact flags", len(all_partners))
        
        return True

    @api.depends('managed_countries_json')
    def _compute_managed_country_ids(self):
        """Compute managed countries from JSON field"""
        for record in self:
            if record.managed_countries_json and record.managed_countries_json.get('country_ids'):
                country_ids = record.managed_countries_json['country_ids']
                record.managed_country_ids = [(6, 0, country_ids)]
            else:
                record.managed_country_ids = [(5, 0, 0)]  # Clear all
    
    def get_managed_country_ids(self):
        """Get list of managed country IDs from JSON"""
        if self.managed_countries_json:
            return self.managed_countries_json.get('country_ids', [])
        return []
    
    def set_managed_countries(self, country_ids, updated_by=None):
        """Set managed countries with metadata"""
        from datetime import datetime
        
        self.managed_countries_json = {
            'country_ids': country_ids,
            'updated_by': updated_by or self.env.user.name,
            'updated_date': datetime.now().isoformat(),
            'total_countries': len(country_ids)
        }
    
    def add_managed_country(self, country_id):
        """Add a country to managed list"""
        current_ids = self.get_managed_country_ids()
        if country_id not in current_ids:
            current_ids.append(country_id)
            self.set_managed_countries(current_ids)
    
    def remove_managed_country(self, country_id):
        """Remove a country from managed list"""
        current_ids = self.get_managed_country_ids()
        if country_id in current_ids:
            current_ids.remove(country_id)
            self.set_managed_countries(current_ids)
    
    def manages_country(self, country_id):
        """Check if this partner manages the given country"""
        return country_id in self.get_managed_country_ids()
    
    def get_managed_countries(self):
        """Get managed countries as recordset"""
        country_ids = self.get_managed_country_ids()
        return self.env['res.country'].browse(country_ids)
    
    def get_managed_countries_info(self):
        """Get detailed info about managed countries"""
        if not self.managed_countries_json:
            return {}
        
        return {
            'countries': self.get_managed_countries().mapped('name'),
            'country_count': len(self.get_managed_country_ids()),
            'last_updated': self.managed_countries_json.get('updated_date'),
            'updated_by': self.managed_countries_json.get('updated_by')
        }
    
    @api.model
    def get_country_managers_for_country(self, country_id):
        """Get all country managers who manage a specific country"""
        return self.search([
            ('is_country_manager', '=', True),
            ('managed_countries_json', '!=', False)
        ]).filtered(lambda p: p.manages_country(country_id))