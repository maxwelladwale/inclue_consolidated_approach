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
