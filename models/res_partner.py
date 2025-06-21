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
    is_facilitator = fields.Boolean('Is Facilitator', default=False)
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