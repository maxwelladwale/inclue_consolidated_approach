from odoo import models, fields, api

class ResPartner(models.Model):
    _inherit = 'res.partner'
    
    is_facilitator = fields.Boolean('Is Facilitator', default=False)
    facilitated_event_ids = fields.One2many('event.event', 'facilitator_id', string='Facilitated Events')
    facilitation_count = fields.Integer('Facilitation Count', compute='_compute_facilitation_stats')
    
    @api.depends('facilitated_event_ids')
    def _compute_facilitation_stats(self):
        for partner in self:
            partner.facilitation_count = len(partner.facilitated_event_ids)