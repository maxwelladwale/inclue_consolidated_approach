from odoo import models, fields, api
from datetime import datetime, timedelta
from odoo.exceptions import UserError
import random
import string
import logging

_logger = logging.getLogger(__name__)

class InclueEvent(models.Model):
    _inherit = 'event.event'
# ADDED
    team_lead_email_sent = fields.Boolean(default=False)
    team_lead_email_sent_date = fields.Datetime()
    resolved_team_leader_name = fields.Char(compute='_compute_team_leader', store=False)
    
    is_inclue_event = fields.Boolean('iN-Clue Event', default=False)

    pre_session_email_sent = fields.Boolean(
        'Pre-Session Email Sent', 
        default=False,
        help="Whether the pre-session reminder email has been sent"
    )
    
    pre_session_email_sent_date = fields.Datetime(
        'Pre-Session Email Sent Date',
        help="When the pre-session reminder email was sent"
    )
        
    cohort = fields.Char(
        string='Cohort ID',
        help="Unique identifier for this cohort (e.g., 'CompanyA_CohortA')",
        index=True
    )

    journey_code = fields.Char(
        'Journey Code', 
        size=8, 
        readonly=True, 
        copy=False,
        help="Unique 8-character code for participants to join this journey"
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

    team_leader_email = fields.Char(
        string='Team Leader Email',
        help="The email of the team leader associated with this cohort"
    )
    active = fields.Boolean(default=True)

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

    # def unlink(self):
    #     raise UserError("Events cannot be deleted. Please archive instead.")

    # ADDED
    @api.depends('team_leader', 'parent_kickoff_id.team_leader')
    def _compute_team_leader(self):
        for event in self:
            event.resolved_team_leader_name = event.team_leader or (event.parent_kickoff_id.team_leader if event.parent_kickoff_id else False)

    @api.model
    def create(self, vals):
        """Override create to automatically generate invoice for iN-Clue events"""
        event = super(InclueEvent, self).create(vals)

        if event.is_inclue_event and event.session_type == 'kickoff' and not event.cohort:
            event.cohort = event._generate_cohort_id()
            
         # Generate journey code for kickoff events
        if event.is_inclue_event and event.session_type == 'kickoff' and not event.journey_code:
            event.journey_code = self._generate_journey_code()
            _logger.info("Generated journey code: %s for event: %s", event.journey_code, event.name)
        
        # Create invoice if this is an iN-Clue event
        if event.is_inclue_event and event.session_type == 'kickoff':
            try:
                event._create_event_invoice()
                _logger.info("Invoice created automatically for iN-Clue event ID %s", event.id)
            except Exception as e:
                _logger.error("Failed to create invoice for event ID %s: %s", event.id, str(e))
        
        return event
    
    def _create_event_invoice(self):
        """Create an invoice for the iN-Clue event - IMPROVED VERSION"""
        self.ensure_one()
        
        if self.invoice_created:
            _logger.warning("Invoice already exists for event ID %s", self.id)
            return self.invoice_id
        
        if not self.facilitator_id:
            raise UserError("Cannot create invoice: No facilitator assigned to event.")
        
        # Get the product for this session type
        product = self._get_session_product()
        if not product:
            raise UserError(f"No product configured for session type: {self.session_type}")
        
        try:
            # Create invoice with lines in one operation (IMPROVED)
            invoice_vals = self._prepare_invoice_vals_improved()
            invoice_vals['invoice_line_ids'] = [(0, 0, self._prepare_invoice_line_improved(product))]
            
            invoice = self.env['account.move'].create(invoice_vals)
            
            # Post the invoice automatically
            if invoice.state == 'draft':
                invoice.action_post()
            
            # Send invoice via email if email configured
            if self.invoice_info_id and self.invoice_info_id.email:
                self._send_invoice_email(invoice)
                _logger.info("Invoice email sent to %s for event ID %s", self.invoice_info_id.email, self.id)
            
            # Update event record
            self.write({
                'invoice_id': invoice.id,
                'invoice_created': True
            })
            
            _logger.info("Successfully created invoice ID %s for event ID %s", invoice.id, self.id)
            return invoice
            
        except Exception as e:
            _logger.error("Error creating invoice for event ID %s: %s", self.id, str(e))
            raise UserError(f"Failed to create invoice: {str(e)}")

    def _prepare_invoice_vals_improved(self):
        """Prepare invoice header values - IMPROVED"""
        partner = self._get_invoice_partner()
        
        return {
            'move_type': 'out_invoice',
            'partner_id': partner.id,
            'invoice_date': fields.Date.today(),
            'company_id': self.env.company.id,  # ✅ FIXED: Use current company
            'currency_id': self.env.company.currency_id.id,
            'ref': self._get_invoice_reference(),
            'narration': self._get_invoice_narration(),
            'invoice_origin': f"Event: {self.name}",
        }

    def _prepare_invoice_line_improved(self, product):
        """Prepare single invoice line - IMPROVED"""
        return {
            'product_id': product.id,
            'name': f"{product.name} - {self.name}",  # More descriptive
            'quantity': 1,
            'price_unit': product.lst_price,
            'product_uom_id': product.uom_id.id,
            'account_id': product.property_account_income_id.id or self._get_income_account().id,
            'tax_ids': [(6, 0, product.taxes_id.ids)],  # ✅ ADDED: Include taxes
        }

    def _get_session_product(self):
        """Get product for this session type with proper validation"""
        # First try to find session-specific product
        product = self.env['product.product'].search([
            ('product_tmpl_id.is_inclue_session', '=', True),
            # ('product_tmpl_id.session_type', '=', self.session_type),
            ('active', '=', True)
        ], limit=1)
        
        if not product:
            # Fallback to generic session product
            product = self.env['product.product'].search([
                ('product_tmpl_id.is_inclue_session', '=', True),
                ('active', '=', True)
            ], limit=1)
        
        return product

    def _get_invoice_partner(self):
        """Get the correct partner for invoicing"""
        if self.invoice_info_id and self.invoice_info_id.partner_id:
            return self.invoice_info_id.partner_id
        return self.facilitator_id

    def _get_invoice_reference(self):
        """Generate invoice reference"""
        ref_parts = [f"Event-{self.id}"]
        if self.cohort:
            ref_parts.append(f"Cohort-{self.cohort}")
        if self.invoice_info_id and self.invoice_info_id.po_number:
            ref_parts.append(f"PO-{self.invoice_info_id.po_number}")
        return " | ".join(ref_parts)

    def _get_invoice_narration(self):
        """Generate invoice description"""
        narration = f'Invoice for iN-Clue Event: {self.name}\nSession Type: {dict(self._fields["session_type"].selection).get(self.session_type)}'
        
        # Add invoice info details if available
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
        
        return narration

    def _send_invoice_email(self, invoice):
        """Send invoice via email using Odoo's system"""
        try:
            # Use Odoo's built-in email template
            template = self.env.ref('account.email_template_edi_invoice', False)
            if template:
                # Override email recipient
                template.send_mail(
                    invoice.id, 
                    force_send=True,
                    email_values={'email_to': self.invoice_info_id.email}
                )
            else:
                # Fallback to action_invoice_sent
                invoice.action_invoice_sent()
            _logger.info("Invoice email sent for invoice ID %s", invoice.id)
        except Exception as e:
            _logger.warning("Failed to send invoice email for ID %s: %s", invoice.id, str(e))

    def _get_income_account(self):
        """Get income account with better fallback logic"""
        company = self.env.company
        
        # Try to get from company's default income account
        if hasattr(company, 'default_income_account_id') and company.default_income_account_id:
            return company.default_income_account_id
        
        # Fallback to searching for income account
        income_account = self.env['account.account'].search([
            ('account_type', '=', 'income'),
            ('company_id', '=', company.id),
            ('deprecated', '=', False)
        ], limit=1)
        
        if not income_account:
            raise UserError("No income account found. Please configure accounting properly.")
        
        return income_account
    def _generate_journey_code(self):
        """Generate unique 8-character journey code: 4 letters + 4 numbers"""
        max_attempts = 100
        
        for _ in range(max_attempts):
            # Generate 4 random letters + 4 random numbers
            letters = ''.join(random.choices(string.ascii_uppercase, k=4))
            numbers = ''.join(random.choices(string.digits, k=4))
            code = letters + numbers
            
            # Check if code already exists
            existing = self.env['event.event'].search([
                ('journey_code', '=', code),
                ('is_inclue_event', '=', True)
            ], limit=1)
            
            if not existing:
                return code
        
        # Fallback if we can't generate unique code
        raise ValueError("Unable to generate unique journey code after 100 attempts")
    
    # Add this debug version to your event model to troubleshoot

    @api.model
    def find_journey_by_code(self, journey_code):
        """Find kickoff event by journey code - DEBUG VERSION"""
        _logger.info("=== DEBUGGING JOURNEY CODE SEARCH ===")
        _logger.info("Searching for journey code: '%s'", journey_code)
        _logger.info("Journey code type: %s", type(journey_code))
        _logger.info("Journey code length: %d", len(journey_code))
        
        # First, let's see ALL events with journey codes
        all_events_with_codes = self.search([
            ('journey_code', '!=', False),
            ('is_inclue_event', '=', True)
        ])
        _logger.info("All events with journey codes:")
        for event in all_events_with_codes:
            _logger.info("  Event ID %s: journey_code='%s', session_type='%s', active=%s", 
                        event.id, event.journey_code, event.session_type, event.active)
        
        # Now search with exact criteria
        search_domain = [
            ('journey_code', '=', journey_code.upper()),
            ('session_type', '=', 'kickoff'),
            ('is_inclue_event', '=', True),
            ('active', '=', True)
        ]
        _logger.info("Search domain: %s", search_domain)
        
        result = self.search(search_domain, limit=1)
        _logger.info("Search result: %s", result)
        
        if result:
            _logger.info("Found event: ID %s, Name: %s", result.id, result.name)
        else:
            _logger.warning("No event found with journey code: %s", journey_code)
            
            # Let's check each criteria individually
            _logger.info("=== INDIVIDUAL CRITERIA CHECK ===")
            
            # Check journey_code match
            code_matches = self.search([('journey_code', '=', journey_code.upper())])
            _logger.info("Events matching journey_code '%s': %s", journey_code.upper(), code_matches.ids)
            
            # Check kickoff events
            kickoff_events = self.search([('session_type', '=', 'kickoff'), ('is_inclue_event', '=', True)])
            _logger.info("Kickoff events: %s", kickoff_events.ids)
            
            # Check active events
            active_events = self.search([('active', '=', True), ('is_inclue_event', '=', True)])
            _logger.info("Active events: %s", active_events.ids)
            
            # Check if the specific event exists but doesn't match all criteria
            specific_event = self.search([('journey_code', '=', journey_code.upper())], limit=1)
            if specific_event:
                _logger.info("Found event with code but wrong criteria:")
                _logger.info("  ID: %s, session_type: %s, is_inclue_event: %s, active: %s", 
                            specific_event.id, specific_event.session_type, 
                            specific_event.is_inclue_event, specific_event.active)
        
        _logger.info("=== END DEBUGGING ===")
        return result
    
    
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
    
    # def _create_event_invoice(self):
    #     """Create an invoice for the iN-Clue event"""
    #     self.ensure_one()
        
    #     if self.invoice_created:
    #         _logger.warning("Invoice already exists for event ID %s", self.id)
    #         return
        
    #     if not self.facilitator_id:
    #         _logger.warning("Cannot create invoice for event ID %s: No facilitator assigned", self.id)
    #         return
        
    #     invoice_vals = self._prepare_invoice_vals()
        
    #     try:
    #         invoice = self.env['account.move'].create(invoice_vals)
            
    #         invoice_lines = self._prepare_invoice_lines()
    #         for line_vals in invoice_lines:
    #             line_vals['move_id'] = invoice.id
    #             self.env['account.move.line'].create(line_vals)
            
    #         if self.invoice_info_id and self.invoice_info_id.email:
    #             invoice.message_post(
    #                 body=f"Invoice should be sent to: {self.invoice_info_id.email}",
    #                 subject="Invoice Email Information"
    #             )
            
    #         self.write({
    #             'invoice_id': invoice.id,
    #             'invoice_created': True
    #         })
            
    #         _logger.info("Successfully created invoice ID %s for event ID %s", invoice.id, self.id)
    #         return invoice
            
    #     except Exception as e:
    #         _logger.error("Error creating invoice for event ID %s: %s", self.id, str(e))
    #         raise
    
    # def _prepare_invoice_vals(self):
    #     """Prepare invoice header values"""
    #     partner = self.facilitator_id
        
    #     narration = f'Invoice for iN-Clue Event: {self.name}\nSession Type: {dict(self._fields["session_type"].selection).get(self.session_type)}'
        
    #     # Add invoice info details to narration if available
    #     if self.invoice_info_id:
    #         invoice_info = self.invoice_info_id
    #         narration += f'\n\nBilling Details:'
    #         if invoice_info.company_name:
    #             narration += f'\nCompany: {invoice_info.company_name}'
    #         if invoice_info.contact_person:
    #             narration += f'\nContact: {invoice_info.contact_person}'
    #         if invoice_info.po_number:
    #             narration += f'\nPO Number: {invoice_info.po_number}'
    #         if invoice_info.address:
    #             narration += f'\nAddress: {invoice_info.address}'
        
    #     invoice_vals = {
    #         'move_type': 'out_invoice',
    #         'partner_id': partner.id,
    #         'invoice_date': fields.Date.today(),
    #         'ref': f'Event: {self.name}' + (f' - PO: {self.invoice_info_id.po_number}' if self.invoice_info_id and self.invoice_info_id.po_number else ''),
    #         'narration': narration,
    #         'company_id': 1,
    #     }
        
    #     # Override partner invoice address if invoice info has address
    #     if self.invoice_info_id and self.invoice_info_id.address:
    #         pass
            
    #     return invoice_vals
    
    # def _prepare_invoice_lines(self):
    #     """Prepare invoice line values"""
    #     session_pricing = self._get_session_pricing()
        
    #     lines = []
        
    #     lines.append({
    #         'name': f'iN-Clue {dict(self._fields["session_type"].selection).get(self.session_type)} - {self.name}',
    #         'quantity': 1,
    #         'price_unit': session_pricing.get('base_price', 1000.0),  # Default price
    #         'account_id': self._get_income_account().id,
    #     })
        
    #     participant_count = len(self.participant_ids)
    #     if participant_count > session_pricing.get('included_participants', 10):
    #         extra_participants = participant_count - session_pricing.get('included_participants', 10)
    #         lines.append({
    #             'name': f'Additional participants ({extra_participants} participants)',
    #             'quantity': extra_participants,
    #             'price_unit': session_pricing.get('per_participant_price', 50.0),
    #             'account_id': self._get_income_account().id,
    #         })
        
    #     return lines

    def _prepare_invoice_lines(self):
        """Prepare invoice line using the kickoff session product"""
        self.ensure_one()

        if self.session_type != 'kickoff':
            return []  # Only kickoff is billed

        # Find product
        product = self.env['product.product'].search([
            ('product_tmpl_id.is_inclue_session', '=', True),
            ('product_tmpl_id.is_inclue_session', '=', 'kickoff')
        ], limit=1)

        if not product:
            raise UserError("Kickoff session product not found. Please configure it in the Products module.")

        # Build line
        return [{
            'product_id': product.id,
            'name': product.name,
            'quantity': 1,
            'price_unit': product.lst_price,
            'account_id': product.property_account_income_id.id or self._get_income_account().id,
        }]

    
    # def _get_session_pricing(self):
    #     """Get pricing configuration for different session types"""
    #     pricing = {
    #         'kickoff': {
    #             'base_price': 2000.0,
    #             'included_participants': 15,
    #             'per_participant_price': 75.0
    #         },
    #         'followup1': {
    #             'base_price': 1500.0,
    #             'included_participants': 15,
    #             'per_participant_price': 50.0
    #         },
    #         'followup2': {
    #             'base_price': 1500.0,
    #             'included_participants': 15,
    #             'per_participant_price': 50.0
    #         },
    #         'followup3': {
    #             'base_price': 1500.0,
    #             'included_participants': 15,
    #             'per_participant_price': 50.0
    #         },
    #         'followup4': {
    #             'base_price': 1500.0,
    #             'included_participants': 15,
    #             'per_participant_price': 50.0
    #         },
    #         'followup5': {
    #             'base_price': 1500.0,
    #             'included_participants': 15,
    #             'per_participant_price': 50.0
    #         },
    #         'followup6': {
    #             'base_price': 1800.0,
    #             'included_participants': 15,
    #             'per_participant_price': 60.0
    #         },
    #     }
        
    #     return pricing.get(self.session_type, {'base_price': 1000.0, 'included_participants': 10, 'per_participant_price': 50.0})
    
    def _get_income_account(self):
        """Get the income account for invoicing"""
        income_account = self.env['account.account'].search([
            ('account_type', '=', 'income'),
            ('company_id', '=', 1)
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

    @api.model
    def send_pre_session_reminders(self):
        """
        Cron job method to send pre-session reminder emails
        Runs daily and sends emails for sessions happening tomorrow
        """
        try:
            # Calculate tomorrow's date range
            tomorrow = fields.Date.today() + timedelta(days=1)
            tomorrow_start = fields.Datetime.to_datetime(tomorrow)
            tomorrow_end = tomorrow_start + timedelta(days=1) - timedelta(seconds=1)
            
            _logger.info("Checking for sessions on %s", tomorrow)
            
            # Find all iN-Clue events happening tomorrow that haven't received reminder
            events_tomorrow = self.search([
                ('is_inclue_event', '=', True),
                ('date_begin', '>=', tomorrow_start),
                ('date_begin', '<=', tomorrow_end),
                ('pre_session_email_sent', '=', False),
                ('facilitator_id', '!=', False),
                ('facilitator_id.email', '!=', False),
                ('active', '=', True)
            ])
            
            _logger.info("Found %d events for tomorrow requiring reminders", len(events_tomorrow))
            
            # Get email template
            template = self.env.ref('inclue-consolidated-approach.email_template_pre_session_reminder', False)
            if not template:
                _logger.error("Pre-session email template not found!")
                return {'error': 'Email template not found'}
            
            sent_count = 0
            failed_count = 0
            
            for event in events_tomorrow:
                try:
                    # Debug: Log event details
                    _logger.info("Processing event ID %s: %s (session_type: %s)", 
                            event.id, event.name, event.session_type)
                    
                    # Get journey code (from self or parent kickoff)
                    journey_code = event.journey_code
                    if not journey_code and event.parent_kickoff_id:
                        journey_code = event.parent_kickoff_id.journey_code
                        _logger.info("Using parent kickoff journey code: %s for event %s", 
                                journey_code, event.id)
                    
                    _logger.info("Using journey code: %s for event %s", journey_code, event.id)
                    _logger.info("Event facilitator: %s", event.facilitator_id.name)
                    _logger.info("Event facilitator email: %s", event.facilitator_id.email)
                    
                    if not journey_code:
                        _logger.warning("No journey code found for event ID %s", event.id)
                    
                    # Send email using template
                    mail_values = template.generate_email(event.id, fields=['subject', 'body_html', 'email_from', 'email_to'])
                    
                    # Override email fields if needed
                    if not mail_values.get('email_to'):
                        mail_values['email_to'] = event.facilitator_id.email
                    if not mail_values.get('email_from'):
                        mail_values['email_from'] = event.company_id.email or self.env.user.email
                    
                    # Create and send email
                    mail = self.env['mail.mail'].create(mail_values)
                    mail.send()
                    
                    # Mark as sent
                    event.write({
                        'pre_session_email_sent': True,
                        'pre_session_email_sent_date': fields.Datetime.now()
                    })
                    
                    sent_count += 1
                    _logger.info("Sent pre-session reminder for event ID %s: %s", 
                            event.id, event.name)
                    
                except Exception as e:
                    failed_count += 1
                    _logger.error("Failed to send pre-session reminder for event ID %s: %s", 
                                event.id, str(e))
            
            _logger.info("Pre-session reminder summary: %d sent, %d failed", 
                        sent_count, failed_count)
            
            return {
                'sent': sent_count,
                'failed': failed_count,
                'total_checked': len(events_tomorrow)
            }
            
        except Exception as e:
            _logger.error("Error in send_pre_session_reminders: %s", str(e))
            return {'error': str(e)}
        
    @api.model
    def send_team_lead_reminders(self):
        """
        Send reminder emails to team leads 2 weeks before kickoff,
        or immediately if within 14 days and not yet sent.
        """
        try:
            today = fields.Date.today()
            max_date = today + timedelta(days=14)

            # Only filter by is_inclue_event and kickoff + not yet sent
            events = self.search([
                ('is_inclue_event', '=', True),
                ('session_type', '=', 'kickoff'),
                ('team_lead_email_sent', '=', False),
                ('date_begin', '<=', max_date),
                ('active', '=', True),
            ])

            template = self.env.ref('inclue-consolidated-approach.email_template_team_lead_reminder', raise_if_not_found=False)
            if not template:
                _logger.error("Team Lead email template not found!")
                return

            sent = 0
            for event in events:
                # Resolve leader name and email (fallback to parent kickoff if not set)
                team_leader_name = event.team_leader or event.parent_kickoff_id.team_leader
                team_leader_email = event.team_leader_email or event.parent_kickoff_id.team_leader_email

                if not team_leader_email:
                    _logger.warning("Skipping event ID %s due to missing team lead email", event.id)
                    continue

                try:
                    mail_values = template.generate_email(event.id, fields=['subject', 'body_html', 'email_from', 'email_to'])
                    mail_values['email_to'] = team_leader_email
                    mail_values['email_from'] = event.company_id.email or self.env.user.email

                    mail = self.env['mail.mail'].create(mail_values)
                    mail.send()

                    event.write({
                        'team_lead_email_sent': True,
                        'team_lead_email_sent_date': fields.Datetime.now()
                    })

                    _logger.info("Sent team lead reminder for event ID %s to %s", event.id, team_leader_email)
                    sent += 1

                except Exception as e:
                    _logger.error("Error sending team lead email for event %s: %s", event.id, str(e))

            _logger.info("Team lead reminder summary: %d emails sent", sent)

        except Exception as e:
            _logger.error("Error in send_team_lead_reminders: %s", str(e))


    @api.model
    def send_monthly_hr_reports(self):
        """Cron job: Send monthly completion reports to HR contacts"""
        try:
            from datetime import datetime, timedelta
            from calendar import monthrange
            
            # Get last month's date range
            today = fields.Date.today()
            last_month = today.replace(day=1) - timedelta(days=1)
            first_day = last_month.replace(day=1)
            last_day = last_month.replace(day=monthrange(last_month.year, last_month.month)[1])
            
            _logger.info("Processing HR reports for %s to %s", first_day, last_day)
            
            # Find completed journeys from last month
            completed_surveys = self.env['survey.user_input'].search([
                ('is_completion_survey', '=', True),
                ('state', '=', 'done'),
                ('create_date', '>=', fields.Datetime.to_datetime(first_day)),
                ('create_date', '<=', fields.Datetime.to_datetime(last_day)),
                ('completion_journey_id', '!=', False)
            ])
            
            # Group by HR contact
            hr_groups = {}
            for survey in completed_surveys:
                journey = survey.completion_journey_id
                hr_contact = journey.hr_contact_id
                
                if hr_contact and hr_contact.email:
                    if hr_contact.id not in hr_groups:
                        hr_groups[hr_contact.id] = {
                            'hr_contact': hr_contact,
                            'surveys': []
                        }
                    hr_groups[hr_contact.id]['surveys'].append(survey)
            
            # Send reports to each HR contact
            for hr_data in hr_groups.values():
                self._send_hr_monthly_report(hr_data, first_day, last_day)
            
            _logger.info("Sent monthly HR reports to %d HR contacts", len(hr_groups))
            
        except Exception as e:
            _logger.error("Error in monthly HR reporting: %s", str(e))
    
    def _send_hr_monthly_report(self, hr_data, first_day, last_day):
        """Send monthly report to single HR contact"""
        try:
            hr_contact = hr_data['hr_contact']
            surveys = hr_data['surveys']
            
            # Generate consolidated PDF
            pdf_path = self._generate_hr_monthly_pdf(hr_contact, surveys, first_day, last_day)
            
            if pdf_path:
                # Send email
                template_body = f"""
                <div style="font-family: Arial, sans-serif; max-width: 600px;">
                    <h2 style="color: #2c3e50;">Monthly iN-Clue Journey Completion Report</h2>
                    
                    <p>Dear {hr_contact.name},</p>
                    
                    <p>Please find attached the monthly completion report for teams under your supervision.</p>
                    
                    <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0;">
                        <h3 style="margin-top: 0;">Report Summary:</h3>
                        <ul>
                            <li><strong>Period:</strong> {first_day.strftime('%B %Y')}</li>
                            <li><strong>Completed Teams:</strong> {len(surveys)}</li>
                            <li><strong>Report Date:</strong> {fields.Date.today().strftime('%B %d, %Y')}</li>
                        </ul>
                    </div>
                    
                    <p>Thank you for supporting the iN-Clue Journey program.</p>
                    
                    <p>Best regards,<br/>The iN-Clue Team</p>
                </div>
                """
                
                mail_values = {
                    'subject': f'Monthly iN-Clue Completion Report - {first_day.strftime("%B %Y")}',
                    'body_html': template_body,
                    'email_to': hr_contact.email,
                    'email_from': self.env.company.email or 'noreply@inclue.com',
                    'attachment_ids': [(0, 0, {
                        'name': f'Monthly_Report_{first_day.strftime("%Y_%m")}.pdf',
                        'datas': self._encode_pdf_file(pdf_path),
                        'res_model': 'event.event',
                        'res_id': self.id,
                    })]
                }
                
                mail = self.env['mail.mail'].create(mail_values)
                mail.send()
                
                _logger.info("Sent monthly report to HR: %s", hr_contact.email)
                
        except Exception as e:
            _logger.error("Error sending HR monthly report: %s", str(e))
