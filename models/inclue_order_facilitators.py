from odoo import models, fields, api
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class InclueOrderFacilitators(models.Model):
    # _name = 'inclue.order.facilitators'
    # _description = 'Inclue Order Facilitators'
    _inherit = 'product.template'

    is_inclue_session = fields.Boolean(
        string='iN-Clue Session Product',
        help="Mark if this product represents an iN-Clue session offering."
    )

    @api.model
    def create(self, vals):
        _logger.info("Creating iN-Clue session product with values: %s", vals)
        new_record = super(InclueOrderFacilitators, self).create(vals)
        _logger.info("Successfully created session product with ID: %s", new_record.id)
        return new_record
    
    def name_get(self):
        """Simple name display for generic products"""
        res = []
        for product in self:
            name = product.name
            if product.is_inclue_session:
                name += " (iN-Clue Session)"
            res.append((product.id, name))
        return res