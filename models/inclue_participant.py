from odoo import models, fields, api
from odoo.exceptions import ValidationError
import logging
from datetime import timedelta
import secrets, string

_logger = logging.getLogger(__name__)

class InclueParticipant(models.Model):
    _name = 'inclue.participant'
    _description = 'iN-Clue Journey Participant'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('Participant Name', required=True, tracking=True)
    email = fields.Char('Email', required=True, tracking=True)
    team_lead_name = fields.Char('Team Lead Name', tracking=True)
    company_name = fields.Char('Company Name', tracking=True)
    is_latest = fields.Boolean('Is Latest', default=True, tracking=True)

    event_id = fields.Many2one('event.event', string='Event', required=True, ondelete='cascade')
    facilitator_id = fields.Many2one('res.partner', related='event_id.facilitator_id', store=True)
    session_type = fields.Selection(related='event_id.session_type', store=True)
    survey_id = fields.Many2one('survey.survey', related='event_id.survey_id', store=True)

    access_token = fields.Char('Access Token', readonly=True, copy=False)
    survey_url = fields.Char('Survey URL', compute='_compute_survey_url')

    survey_sent = fields.Boolean('Survey Sent', default=False, tracking=True)
    survey_started = fields.Boolean('Survey Started', default=False)
    survey_completed = fields.Boolean('Survey Completed', default=False, tracking=True)

    date_sent = fields.Datetime('Date Sent')
    date_started = fields.Datetime('Date Started')
    date_completed = fields.Datetime('Date Completed')

    next_session_date = fields.Date('Next Session Date', compute='_compute_next_session', store=True)
    previous_participant_id = fields.Many2one('inclue.participant', string='Previous Participation')
    user_input_id = fields.Many2one('survey.user_input', string='Survey Response', readonly=True)

    _sql_constraints = [
        ('unique_email_event', 'unique(email, event_id)', 'A participant with this email already exists for this event.')
    ]

    @api.model
    def create_or_update(self, email, facilitator_name, team_lead=None):
        partner = self.env['res.partner'].search([('name', '=', facilitator_name)], limit=1)
        if not partner:
            raise ValidationError(f"Facilitator '{facilitator_name}' not found.")

        # find existing by email (and optionally team lead)
        domain = [('email', '=', email), ('facilitator_id', '=', partner.id)]
        if team_lead:
            domain.append(('team_lead_name', '=', team_lead))
        existing = self.search(domain, limit=1)

        if existing:
            # progress to next session
            next_type = self.get_next_session_type(existing.session_type)
            if not next_type:
                raise ValidationError("No further sessions available.")
            next_event = self.env['event.event'].search([('facilitator_id', '=', partner.id), ('session_type', '=', next_type)], limit=1)
            if not next_event:
                raise ValidationError(f"Next session '{next_type}' not found for {facilitator_name}.")
            existing.write({'event_id': next_event.id})
            return existing
        else:
            # new participant
            vals = {'name': email.split('@')[0], 'email': email}
            vals['access_token'] = secrets.token_urlsafe(24)
            kickoff = self.env['event.event'].search([('facilitator_id', '=', partner.id), ('session_type', '=', 'kickoff')], limit=1)
            if not kickoff:
                raise ValidationError(f"Kickoff session not found for {facilitator_name}.")
            vals.update({'event_id': kickoff.id})
            return self.create(vals)

    def create(self, vals):
        # ensure token
        if not vals.get('access_token'):
            vals['access_token'] = secrets.token_urlsafe(24)
        record = super().create(vals)
        return record

    def get_next_session_type(self, current):
        sequence = ['kickoff', 'followup1', 'followup2', 'followup3', 'followup4', 'followup5', 'followup6']
        try:
            idx = sequence.index(current)
            return sequence[idx + 1] if idx + 1 < len(sequence) else None
        except ValueError:
            return None

    # def _generate_token(self):
    #     """Generate a secure random token"""
    #     return ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32))

    # @api.depends('survey_id', 'access_token')
    # def _compute_survey_url(self):
    #     base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
    #     for record in self:
    #         if record.survey_id and record.access_token:
    #             survey = record.survey_id
    #             record.survey_url = f"{base_url}/survey/start/{survey.access_token}/{record.access_token}"
    #         else:
    #             record.survey_url = False
    
    # @api.depends('survey_id')
    # def _compute_survey_url(self):
    #     base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
    #     for record in self:
    #         if record.survey_id:
    #             record.survey_url = f"{base_url}/survey/start/{record.survey_id.access_token}"
    #         else:
    #             record.survey_url = False

    @api.depends('survey_id', 'access_token')
    def _compute_survey_url(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        for record in self:
            if record.survey_id and record.access_token:
                # _logger('Record', record)
                survey = record.survey_id
                record.survey_url = f"{base_url}/survey/start/{survey.access_token}/{record.access_token}"
            else:
                record.survey_url = False


    @api.depends('survey_completed', 'session_type')
    def _compute_next_session(self):
        for record in self:
            if record.survey_completed and record.session_type != 'followup6':
                config = self.env['inclue.survey.config'].search([('session_type', '=', record.session_type), ('active', '=', True)], limit=1)
                if config:
                    record.next_session_date = fields.Date.today() + timedelta(days=config.days_until_next)
                else:
                    record.next_session_date = False
            else:
                record.next_session_date = False
    
    def send_survey(self):
        """Send survey email to participant"""
        self.ensure_one()
        
        # Create a dynamic template with QWeb syntax
        template = self.env['mail.template'].create({
            'name': 'iN-Clue Survey Invitation',
            'model_id': self.env['ir.model'].search([('model', '=', 'inclue.participant')], limit=1).id,
            'subject': 'Your iN-Clue Journey Survey',
            'email_from': 'noreply@inclue.com',
            'email_to': self.email,
            'body_html': '''
                <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                    <div style="background-color: #008f8c; color: white; padding: 20px; text-align: center;">
                        <h1 style="margin: 0;">iN-Clue Journey</h1>
                    </div>
                    
                    <div style="padding: 20px; background-color: #f9f9f9;">
                        <p>Dear <t t-out="object.name"/>,</p>
                        
                        <p>Thank you for participating in the <strong><t t-out="object.session_type"/></strong> session of the iN-Clue Journey.</p>
                        
                        <p>Please take a moment to complete your survey by clicking the button below:</p>
                        
                        <div style="text-align: center; margin: 30px 0;">
                            <a t-att-href="object.survey_url" 
                            style="background-color: #008f8c; 
                                    color: white; 
                                    padding: 12px 30px; 
                                    text-decoration: none; 
                                    border-radius: 5px; 
                                    display: inline-block;
                                    font-weight: bold;">
                                Complete Survey
                            </a>
                        </div>
                        
                        <p><strong>Session Details:</strong></p>
                        <ul style="list-style: none; padding-left: 0;">
                            <li>📅 Event: <t t-out="object.event_id.name"/></li>
                            <li>👤 Facilitator: <t t-out="object.facilitator_id.name"/></li>
                            <li>👥 Team Lead: <t t-out="object.team_lead_name"/></li>
                            <li>🏢 Company: <t t-out="object.company_name"/></li>
                        </ul>
                        
                        <p>This survey link is unique to you and requires no login.</p>
                        
                        <p>Thank you for your participation!</p>
                        
                        <p>Best regards,<br/>The iN-Clue Team</p>
                    </div>
                    
                    <div style="background-color: #333; color: white; padding: 10px; text-align: center; font-size: 12px;">
                        <p style="margin: 0;">© 2024 iN-Clue Journey. All rights reserved.</p>
                    </div>
                </div>
            ''',
            'auto_delete': False,
        })
        
        # Send the email
        try:
            mail_id = template.send_mail(self.id, force_send=True)
            self.write({
                'survey_sent': True,
                'date_sent': fields.Datetime.now()
            })
            # Delete the temporary template after sending
            template.unlink()
            return True
        except Exception as e:
            _logger.error(f"Failed to send survey to {self.email}: {str(e)}")
            return False

    def advance_to_next_session(self):
        self.ensure_one()
        next_type = self.get_next_session_type(self.session_type)
        if not next_type:
            raise ValidationError("No further sessions available.")

        next_event = self.env['event.event'].search([
            ('facilitator_id', '=', self.facilitator_id.id),
            ('session_type', '=', next_type)
        ], limit=1)
        if not next_event:
            raise ValidationError(f"Next session '{next_type}' not found for facilitator.")

        self.write({'is_latest': False})

        new_vals = self.copy_data()[0]
        new_vals.update({
            'event_id': next_event.id,
            'previous_participant_id': self.id,
            'is_latest': True,
            'survey_completed': False,
            'survey_sent': False,
            'survey_started': False,
            'date_sent': False,
            'date_completed': False,
            'date_started': False,
            'user_input_id': False
        })
        return self.create(new_vals)