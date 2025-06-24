from odoo import models, fields, api

class SaleOrderInclueSession(models.Model):
    _inherit = 'sale.order'

    x_session_date = fields.Date(
        string='Session Date',
        help="Date when the session will be conducted"
    )
    x_session_time = fields.Char(
        string='Session Time',
        help="Time when the session will be conducted"
    )
    x_company_name = fields.Char(
        string='Client Company',
        help="Name of the company receiving the session"
    )
    x_lead_name = fields.Char(
        string='Lead Name',
        help="Name of the lead/contact person"
    )
    x_special_requirements = fields.Text(
        string='Special Requirements',
        help="Any special requirements or notes"
    )
    x_follow_up_required = fields.Boolean(
        string='Follow-up Required',
        default=False,
        help="Whether this session requires a follow-up session"
    )

    # Computed field to check if this order contains iN-Clue sessions
    x_is_inclue_session_order = fields.Boolean(
        string='Contains iN-Clue Sessions',
        compute='_compute_is_inclue_session_order',
        store=True
    )

    @api.depends('order_line.product_id.is_inclue_session')
    def _compute_is_inclue_session_order(self):
        for order in self:
            order.x_is_inclue_session_order = any(
                line.product_id.is_inclue_session for line in order.order_line
            )