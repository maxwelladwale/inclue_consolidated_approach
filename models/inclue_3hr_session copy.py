from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)

class ProductTemplateInclue3HrSession(models.Model):
    _inherit = 'product.template'
    # REMOVE THIS LINE: _name = 'product.template.inclue.3hr.session' # Explicitly define name if needed for new model, but for _inherit, this just registers an alias.

    # Add a boolean flag to easily identify iN-Clue specific products
    is_inclue_session = fields.Boolean(
        string='iN-Clue 3-Hour Session',
        help="Mark if this product represents an iN-Clue 3-hour session or similar one-off event."
    )

    # Custom fields for the 3-hour session
    # Note: These fields will only be relevant if is_inclue_session is True
    session_date = fields.Date(
        string='Session Date',
        help="The specific date for this 3-hour session."
    )
    session_time = fields.Char(
        string='Session Time',
        help="The specific time for this 3-hour session (e.g., '10:00 AM - 1:00 PM')."
    )
    session_region = fields.Char(
        string='Region',
        help="The region where this session will take place."
    )
    session_country_id = fields.Many2one(
        'res.country',
        string='Country',
        help="The country where this session will take place."
    )
    session_team_leader = fields.Char(
        string='Team Leader Name',
        help="The name of the team leader for this session."
    )
    session_division_id = fields.Many2one(
        'hr.department',
        string='Division',
        help="The division associated with this session."
    )
    session_facilitator_id = fields.Many2one(
        'res.partner',
        string='Facilitator',
        domain="[('is_facilitator', '=', True)]", # Assumes 'is_facilitator' field on res.partner
        help="The facilitator for this 3-hour session."
    )
    session_invoice_info_id = fields.Many2one(
        'inclue.invoice.info', # Make sure this model is loaded/defined elsewhere
        string="Invoice Info for Session",
        help="Specific invoice details for this 3-hour session, if different from general."
    )

    @api.model
    def create(self, vals):
        _logger.info("Attempting to create product.template with values: %s", vals)
        new_record = super(ProductTemplateInclue3HrSession, self).create(vals)
        _logger.info("Successfully created product.template with ID: %s", new_record.id)
        return new_record

    def write(self, vals):
        _logger.info("Attempting to update product.template IDs %s with values: %s", self.ids, vals)
        res = super(ProductTemplateInclue3HrSession, self).write(vals)
        _logger.info("Successfully updated product.template IDs %s. Result: %s", self.ids, res)
        return res

    def unlink(self):
        _logger.warning("Attempting to delete product.template IDs: %s", self.ids)
        res = super(ProductTemplateInclue3HrSession, self).unlink()
        _logger.warning("Successfully deleted product.template IDs %s. Result: %s", self.ids, res)
        return res

    def action_publish_session(self):
        self.write({'active': True})
        _logger.info("Published 3-hour session products: %s", self.mapped('name'))

    def action_unpublish_session(self):
        self.write({'active': False})
        _logger.info("Unpublished 3-hour session products: %s", self.mapped('name'))

    def name_get(self):
        res = []
        for product in self:
            name = product.name
            if product.is_inclue_session:
                details = []
                if product.session_date:
                    details.append(product.session_date.strftime('%Y-%m-%d'))
                if product.session_time:
                    details.append(product.session_time)
                if product.session_country_id:
                    details.append(product.session_country_id.name)
                if product.session_team_leader:
                    details.append(f"TL: {product.session_team_leader}")
                
                if details:
                    name += f" ({', '.join(details)})"
            res.append((product.id, name))
        return res