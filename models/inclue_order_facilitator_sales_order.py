from odoo import models, fields, api

class InclueOrderFacilitatorSalesOrder(models.Model):
    _inherit = 'sale.order'

    x_company_name = fields.Char(
        string='Company Name',
        help="Name of the company receiving the session"
    )
    x_invoice_id = fields.Many2one('account.move', string="Linked Invoice")
    x_contact_person = fields.Many2one(
        comodel_name='res.partner',
        string='Contact Person',
        domain="[('is_contact', '=', True)]",
        help="Contact person for this session's company"
    )

    x_facilitator_type = fields.Selection(
        string='Facilitator Type',
        selection=[('internal', 'Internal'), ('external', 'External')],
        help="Type of facilitator for the session"
    )
    x_number_of_facilitators = fields.Integer(
        string='Number of Facilitators',
        help="Number of facilitators required for the session"
    )
    x_invoice_approved = fields.Boolean(
        string="Invoice Approved",
        default=False,
        help="Check when invoice has been confirmed and approved for facilitator bonus."
    )
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