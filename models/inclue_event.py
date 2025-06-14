from odoo import models, fields, api
from datetime import datetime, timedelta

import logging

_logger = logging.getLogger(__name__)

class InclueEvent(models.Model):
    _inherit = 'event.event'
    
    is_inclue_event = fields.Boolean('iN-Clue Event', default=False)

    cohort = fields.Char(
        string='Cohort ID',
        help="Unique identifier for this cohort (e.g., 'CompanyA_CohortA')",
        index=True
    )

    # team_leader_id = fields.Many2one(
    #     'res.partner',
    #     string='Team Leader',
    #     help="The team leader associated with this cohort"
    # )

    team_leader = fields.Char(
        string='Team Leader',
        help="The team leader associated with this cohort"
    )

    # Journey Completion Fields
    completion_survey_triggered = fields.Boolean(
        'Completion Survey Triggered', 
        default=False, 
        help="Whether the completion survey has been triggered for this journey"
    )
    
    journey_completed = fields.Boolean(
        'Journey Completed', 
        default=False,
        help="Whether this journey has been officially completed"
    )
    
    completion_date = fields.Datetime(
        'Completion Date',
        help="Date when the journey was officially completed"
    )
    
    completion_trigger_date = fields.Datetime(
        'Completion Trigger Date',
        help="Date when the completion process was triggered"
    )
    
    completion_user_input_id = fields.Many2one(
        'survey.user_input',
        'Completion Survey Response',
        help="The survey response for the completion survey"
    )
    
    completion_survey_url = fields.Char(
        'Completion Survey URL',
        help="URL for the completion survey"
    )

    parent_kickoff_id = fields.Many2one(
        'event.event',
        string='Parent Kickoff',
        help="The kickoff event that this follow-up belongs to"
    )
    session_type = fields.Selection([
        ('kickoff', 'KickOff Session'),
        ('followup1', 'Follow-up Session 1'),
        ('followup2', 'Follow-up Session 2'),
        ('followup3', 'Follow-up Session 3'),
        ('followup4', 'Follow-up Session 4'),
        ('followup5', 'Follow-up Session 5'),
        ('followup6', 'Follow-up Session 6'),
    ], string='Session Type', default='kickoff')
    
    contact_person = fields.Char(
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
    team_commitment = fields.Text("Team Commitment", help="Commitment from the team to participate in the iN-Clue Journey")
    desired_differences = fields.Text("Desired Differences", help="What changes the team wants to see after the iN-Clue Journey")
    company_support = fields.Text("Company Support", help="How the company can support the team during the iN-Clue Journey")
    
    # New fields for invoice tracking
    invoice_id = fields.Many2one('account.move', string='Generated Invoice', readonly=True)
    invoice_created = fields.Boolean('Invoice Created', default=False, readonly=True)

    @api.model
    def create(self, vals):
        """Override create to automatically generate invoice for iN-Clue events"""
        event = super(InclueEvent, self).create(vals)

        if event.is_inclue_event and event.session_type == 'kickoff' and not event.cohort:
            event.cohort = event._generate_cohort_id()
        
        # Create invoice if this is an iN-Clue event
        if event.is_inclue_event and event.session_type == 'kickoff':
            try:
                event._create_event_invoice()
                _logger.info("Invoice created automatically for iN-Clue event ID %s", event.id)
            except Exception as e:
                _logger.error("Failed to create invoice for event ID %s: %s", event.id, str(e))
        
        return event
    
    def _create_event_invoice(self):
        """Create, post, and send invoice for the iN-Clue event"""
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

            # Post the invoice (i.e., confirm it)
            invoice.action_post()

            # Optionally attach message with invoice email
            if self.invoice_info_id and self.invoice_info_id.email:
                invoice.message_post(
                    body=f"Invoice should be sent to: {self.invoice_info_id.email}",
                    subject="Invoice Email Information"
                )

            # Send invoice via email
            invoice.action_invoice_sent()

            # Update event
            self.write({
                'invoice_id': invoice.id,
                'invoice_created': True
            })

            _logger.info("Successfully created and sent invoice ID %s for event ID %s", invoice.id, self.id)
            return invoice

        except Exception as e:
            _logger.error("Error creating invoice for event ID %s: %s", self.id, str(e))
            raise


    def _generate_cohort_id(self):
        """Generate unique cohort ID like 'CompanyA_CohortA'"""
        self.ensure_one()
        
        # Base name from company or facilitator
        base_name = "Unknown"
        if self.invoice_info_id and self.invoice_info_id.company_name:
            base_name = self.invoice_info_id.company_name.replace(' ', '')[:10]
        elif self.facilitator_id:
            base_name = self.facilitator_id.name.replace(' ', '')[:10]
        
        # Find existing cohorts for this facilitator to determine suffix
        existing_cohorts = self.env['event.event'].search([
            ('facilitator_id', '=', self.facilitator_id.id),
            ('session_type', '=', 'kickoff'),
            ('is_inclue_event', '=', True),
            ('cohort', '!=', False),
            ('id', '!=', self.id)
        ])
        
        # Generate suffix (A, B, C, etc.)
        suffix_num = len(existing_cohorts)
        suffix = chr(65 + suffix_num)  # A=65, B=66, etc.
        
        return f"{base_name}_Cohort{suffix}"


    def create_followup_sessions(self, followup_dates):
        """Create all follow-up sessions for this kickoff cohort"""
        self.ensure_one()
        
        if self.session_type != 'kickoff':
            raise ValueError("Can only create follow-ups from kickoff sessions")
        
        session_types = ['followup1', 'followup2', 'followup3', 'followup4', 'followup5', 'followup6']
        created_sessions = []
        
        for session_type in session_types:
            if session_type not in followup_dates:
                continue
                
            date_begin = followup_dates[session_type]
            if isinstance(date_begin, str):
                try:
                    date_begin = datetime.strptime(date_begin, "%Y-%m-%dT%H:%M:%S")
                except ValueError:
                    date_begin = fields.Datetime.from_string(date_begin)
            
            # Copy all relevant fields from kickoff
            followup_vals = {
                'name': f"{self.name} - {session_type.title()}",
                'session_type': session_type,
                'is_inclue_event': True,
                'facilitator_id': self.facilitator_id.id,
                'company_id': self.company_id.id,
                'date_begin': date_begin,
                'date_end': date_begin,
                'cohort': self.cohort,  # SAME COHORT!
                'parent_kickoff_id': self.id,  # Link to parent
                'contact_person': self.contact_person,
                'division_id': self.division_id.id if self.division_id else False,
                'country_id': self.country_id.id if self.country_id else False,
                'language_id': self.language_id.id if self.language_id else False,
                'invoice_info_id': self.invoice_info_id.id if self.invoice_info_id else False,
                'team_commitment': self.team_commitment,
                'desired_differences': self.desired_differences,
                'company_support': self.company_support,
            }
            
            followup_session = self.env['event.event'].create(followup_vals)
            created_sessions.append(followup_session)
            _logger.info("Created follow-up session %s for cohort %s", session_type, self.cohort)
        
        return created_sessions

    def write(self, vals):
        """Override write to create invoice if is_inclue_event is set to True"""
        result = super(InclueEvent, self).write(vals)
        
        # If is_inclue_event was just set to True and no invoice exists yet
        if vals.get('is_inclue_event'):
            for event in self:
                if not event.invoice_created and event.session_type == 'kickoff':
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
        
    def action_trigger_completion(self):
        """
        Manual action to trigger completion survey from Odoo interface
        """
        self.ensure_one()
        
        if self.session_type != 'kickoff':
            raise ValueError("Completion can only be triggered from kickoff events")
            
        if self.completion_survey_triggered:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Already Triggered',
                    'message': 'Completion survey has already been triggered for this journey.',
                    'type': 'warning',
                }
            }
        
        try:
            # Get completion survey configuration
            completion_survey_config = self.env['inclue.survey.config'].search([
                ('session_type', '=', 'completion'),
                ('active', '=', True)
            ], limit=1)

            if not completion_survey_config:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Configuration Missing',
                        'message': 'No completion survey configured. Please contact administrator.',
                        'type': 'danger',
                    }
                }

            # Create completion survey user input for facilitator
            completion_survey = completion_survey_config.survey_id
            facilitator_user = self.facilitator_id.user_ids[0] if self.facilitator_id.user_ids else None
            
            if not facilitator_user:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Error',
                        'message': 'Facilitator has no user account configured.',
                        'type': 'danger',
                    }
                }

            # Create completion survey user input
            user_input = self.env['survey.user_input'].create({
                'survey_id': completion_survey.id,
                'email': facilitator_user.email,
                'nickname': facilitator_user.name,
                'state': 'new',
                'completion_journey_id': self.id
            })

            # Generate completion survey URL
            base_url = self.env['ir.config_parameter'].get_param('web.base.url')
            # completion_url = f"{base_url}/survey/{completion_survey.access_token}/{user_input.access_token}"
            completion_url = f"{base_url}/survey/{completion_survey.access_token}/{user_input.access_token}?access_token={user_input.access_token}"

            # Update event with completion info
            self.write({
                'completion_survey_triggered': True,
                'completion_user_input_id': user_input.id,
                'completion_survey_url': completion_url,
                'completion_trigger_date': fields.Datetime.now()
            })

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Completion Survey Created',
                    'message': f'Completion survey created. URL: {completion_url}',
                    'type': 'success',
                }
            }

        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error',
                    'message': f'Failed to create completion survey: {str(e)}',
                    'type': 'danger',
                }
            }