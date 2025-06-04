from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)

class InclueEvent(models.Model):
    _inherit = 'event.event'
    
    is_inclue_event = fields.Boolean('iN-Clue Event', default=False)
    session_type = fields.Selection([
        ('kickoff', 'KickOff Session'),
        ('followup1', 'Follow-up Session 1'),
        ('followup2', 'Follow-up Session 2'),
        ('followup3', 'Follow-up Session 3'),
        ('followup4', 'Follow-up Session 4'),
        ('followup5', 'Follow-up Session 5'),
        ('followup6', 'Follow-up Session 6'),
    ], string='Session Type', default='kickoff')
    
    contactPerson = fields.Char(
        string='Contact Person',
        help="Name of the contact person for the iN-Clue event",
        required=True
    )
    survey_id = fields.Many2one(
        'survey.survey',
        string='Survey',
        compute='_compute_survey_id',
        store=True,
        readonly=False
    )
    
    facilitator_id = fields.Many2one(
        'res.partner',
        string='Facilitator',
        domain="[('is_facilitator', '=', True)]"
    )
    
    participant_ids = fields.One2many(
        'inclue.participant',
        'event_id',
        string='Participants'
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        help="Company that is organizing the iN-Clue event",
        required=True
    )
    division_id = fields.Many2one('hr.department', string="Division")
    country_id = fields.Many2one('res.country', string="Country")
    language_id = fields.Many2one('res.lang', string="Preferred Language")
    hr_contact_id = fields.Many2one('res.partner', string="Responsible HR")
    invoice_info_id = fields.Many2one('inclue.invoice.info', string="Invoice Info")
    team_commitment = fields.Text("Team Commitment", help="Commitment from the team to participate in the iN-Clue Journey", required=True)
    desired_differences = fields.Text("Desired Differences", help="What changes the team wants to see after the iN-Clue Journey", required=True)
    company_support = fields.Text("Company Support", help="How the company can support the team during the iN-Clue Journey", required=True)
    
    # New fields for invoice tracking
    invoice_id = fields.Many2one('account.move', string='Generated Invoice', readonly=True)
    invoice_created = fields.Boolean('Invoice Created', default=False, readonly=True)

    @api.model
    def create(self, vals):
        """Override create to automatically generate invoice for iN-Clue events"""
        event = super(InclueEvent, self).create(vals)
        
        # Create invoice if this is an iN-Clue event
        if event.is_inclue_event:
            try:
                event._create_event_invoice()
                _logger.info("Invoice created automatically for iN-Clue event ID %s", event.id)
            except Exception as e:
                _logger.error("Failed to create invoice for event ID %s: %s", event.id, str(e))
        
        return event

    def write(self, vals):
        """Override write to create invoice if is_inclue_event is set to True"""
        result = super(InclueEvent, self).write(vals)
        
        # If is_inclue_event was just set to True and no invoice exists yet
        if vals.get('is_inclue_event') and not self.invoice_created:
            for event in self:
                try:
                    event._create_event_invoice()
                    _logger.info("Invoice created for existing event ID %s after marking as iN-Clue", event.id)
                except Exception as e:
                    _logger.error("Failed to create invoice for event ID %s: %s", event.id, str(e))
        
        return result
    
    def _create_event_invoice(self):
        """Create an invoice for the iN-Clue event"""
        self.ensure_one()
        
        if self.invoice_created:
            _logger.warning("Invoice already exists for event ID %s", self.id)
            return
        
        if not self.facilitator_id:
            _logger.warning("Cannot create invoice for event ID %s: No facilitator assigned", self.id)
            return
        
        invoice_vals = self._prepare_invoice_vals()
        
        try:
            invoice = self.env['account.move'].create(invoice_vals)
            
            invoice_lines = self._prepare_invoice_lines()
            for line_vals in invoice_lines:
                line_vals['move_id'] = invoice.id
                self.env['account.move.line'].create(line_vals)
            
            if self.invoice_info_id and self.invoice_info_id.email:
                invoice.message_post(
                    body=f"Invoice should be sent to: {self.invoice_info_id.email}",
                    subject="Invoice Email Information"
                )
            
            self.write({
                'invoice_id': invoice.id,
                'invoice_created': True
            })
            
            _logger.info("Successfully created invoice ID %s for event ID %s", invoice.id, self.id)
            return invoice
            
        except Exception as e:
            _logger.error("Error creating invoice for event ID %s: %s", self.id, str(e))
            raise
    
    def _prepare_invoice_vals(self):
        """Prepare invoice header values"""
        partner = self.facilitator_id
        
        narration = f'Invoice for iN-Clue Event: {self.name}\nSession Type: {dict(self._fields["session_type"].selection).get(self.session_type)}'
        
        # Add invoice info details to narration if available
        if self.invoice_info_id:
            invoice_info = self.invoice_info_id
            narration += f'\n\nBilling Details:'
            if invoice_info.company_name:
                narration += f'\nCompany: {invoice_info.company_name}'
            if invoice_info.contact_person:
                narration += f'\nContact: {invoice_info.contact_person}'
            if invoice_info.po_number:
                narration += f'\nPO Number: {invoice_info.po_number}'
            if invoice_info.address:
                narration += f'\nAddress: {invoice_info.address}'
        
        invoice_vals = {
            'move_type': 'out_invoice',
            'partner_id': partner.id,
            'invoice_date': fields.Date.today(),
            'ref': f'Event: {self.name}' + (f' - PO: {self.invoice_info_id.po_number}' if self.invoice_info_id and self.invoice_info_id.po_number else ''),
            'narration': narration,
            'company_id': self.env.company.id,
        }
        
        # Override partner invoice address if invoice info has address
        if self.invoice_info_id and self.invoice_info_id.address:
            pass
            
        return invoice_vals
    
    def _prepare_invoice_lines(self):
        """Prepare invoice line values"""
        session_pricing = self._get_session_pricing()
        
        lines = []
        
        lines.append({
            'name': f'iN-Clue {dict(self._fields["session_type"].selection).get(self.session_type)} - {self.name}',
            'quantity': 1,
            'price_unit': session_pricing.get('base_price', 1000.0),  # Default price
            'account_id': self._get_income_account().id,
        })
        
        participant_count = len(self.participant_ids)
        if participant_count > session_pricing.get('included_participants', 10):
            extra_participants = participant_count - session_pricing.get('included_participants', 10)
            lines.append({
                'name': f'Additional participants ({extra_participants} participants)',
                'quantity': extra_participants,
                'price_unit': session_pricing.get('per_participant_price', 50.0),
                'account_id': self._get_income_account().id,
            })
        
        return lines
    
    def _get_session_pricing(self):
        """Get pricing configuration for different session types"""
        pricing = {
            'kickoff': {
                'base_price': 2000.0,
                'included_participants': 15,
                'per_participant_price': 75.0
            },
            'followup1': {
                'base_price': 1500.0,
                'included_participants': 15,
                'per_participant_price': 50.0
            },
            'followup2': {
                'base_price': 1500.0,
                'included_participants': 15,
                'per_participant_price': 50.0
            },
            'followup3': {
                'base_price': 1500.0,
                'included_participants': 15,
                'per_participant_price': 50.0
            },
            'followup4': {
                'base_price': 1500.0,
                'included_participants': 15,
                'per_participant_price': 50.0
            },
            'followup5': {
                'base_price': 1500.0,
                'included_participants': 15,
                'per_participant_price': 50.0
            },
            'followup6': {
                'base_price': 1800.0,
                'included_participants': 15,
                'per_participant_price': 60.0
            },
        }
        
        return pricing.get(self.session_type, {'base_price': 1000.0, 'included_participants': 10, 'per_participant_price': 50.0})
    
    def _get_income_account(self):
        """Get the income account for invoicing"""
        income_account = self.env['account.account'].search([
            ('account_type', '=', 'income'),
            ('company_id', '=', self.env.company.id)
        ], limit=1)
        
        if not income_account:
            income_account = self.env['account.account'].search([
                ('account_type', '=', 'income')
            ], limit=1)
        
        if not income_account:
            raise ValueError("No income account found. Please configure accounting properly.")
        
        return income_account
    
    @api.depends('session_type', 'is_inclue_event')
    def _compute_survey_id(self):
        for event in self:
            _logger.debug("Computing survey_id for event ID %s (session_type: %s, is_inclue_event: %s)", event.id, event.session_type, event.is_inclue_event)
            if event.is_inclue_event and event.session_type:
                config = self.env['inclue.survey.config'].search([
                    ('session_type', '=', event.session_type),
                    ('active', '=', True)
                ], limit=1)
                
                if config:
                    event.survey_id = config.survey_id
                    _logger.info("Assigned survey ID %s to event ID %s", event.survey_id.id, event.id)
                else:
                    event.survey_id = False
                    _logger.warning("No active survey configuration found for event ID %s with session_type %s", event.id, event.session_type)
            else:
                event.survey_id = False
                _logger.debug("Event ID %s is not an iN-Clue event or has no session_type, survey_id set to False", event.id)
    
    def action_send_surveys(self):
        """Send surveys to all participants"""
        self.ensure_one()
        sent_count = 0
        _logger.debug("Starting to send surveys for event ID %s", self.id)

        for participant in self.participant_ids.filtered(lambda p: not p.survey_sent):
            try:
                _logger.debug("Sending survey to participant ID %s", participant.id)
                if participant.send_survey():
                    sent_count += 1
                    _logger.info("Survey sent successfully to participant ID %s", participant.id)
                else:
                    _logger.warning("Failed to send survey to participant ID %s", participant.id)
            except Exception as e:
                _logger.error("Error sending survey to participant ID %s: %s", participant.id, str(e))
        
        _logger.info("Successfully sent %d surveys for event ID %s", sent_count, self.id)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Surveys Sent',
                'message': f'Successfully sent {sent_count} surveys',
                'type': 'success',
            }
        }
    
    def action_view_invoice(self):
        """Action to view the generated invoice"""
        self.ensure_one()
        if not self.invoice_id:
            return False
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Event Invoice',
            'res_model': 'account.move',
            'res_id': self.invoice_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    def action_create_invoice_manual(self):
        """Manual action to create invoice if not already created"""
        self.ensure_one()
        if self.invoice_created:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Invoice Already Exists',
                    'message': 'An invoice has already been created for this event.',
                    'type': 'warning',
                }
            }
        
        try:
            self._create_event_invoice()
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Invoice Created',
                    'message': 'Invoice has been created successfully.',
                    'type': 'success',
                }
            }
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error',
                    'message': f'Failed to create invoice: {str(e)}',
                    'type': 'danger',
                }
            }