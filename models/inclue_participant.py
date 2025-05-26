import secrets
import string
from datetime import timedelta
from odoo import models, fields, api
import logging
import uuid


_logger = logging.getLogger(__name__)

class InclueParticipant(models.Model):
    _name = 'inclue.participant'
    _description = 'iN-Clue Journey Participant'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    name = fields.Char('Participant Name', required=True, tracking=True)
    email = fields.Char('Email', required=True, tracking=True)
    team_lead_name = fields.Char('Team Lead Name', tracking=True)
    company_name = fields.Char('Company Name', tracking=True)
    
    event_id = fields.Many2one('event.event', string='Event', required=True, ondelete='cascade')
    facilitator_id = fields.Many2one('res.partner', related='event_id.facilitator_id', store=True)
    session_type = fields.Selection(related='event_id.session_type', store=True)
    survey_id = fields.Many2one('survey.survey', related='event_id.survey_id', store=True)
    
    access_token = fields.Char('Access Token', readonly=True, copy=False)
    survey_url = fields.Char('Survey URL', compute='_compute_survey_url')
    
    survey_sent = fields.Boolean('Survey Sent', default=True, tracking=True)
    survey_started = fields.Boolean('Survey Started', default=False)
    survey_completed = fields.Boolean('Survey Completed', default=False, tracking=True)
    survey_state = fields.Selection([
        ('new', 'New'),
        ('in_progress', 'In Progress'),
        ('done', 'Completed')
    ], string='Survey State', compute='_compute_survey_state', store=True)
    
    is_latest = fields.Boolean('Is Latest', default=True, tracking=True)

    date_sent = fields.Datetime('Date Sent', default=fields.Datetime.now)  # Auto-set
    date_started = fields.Datetime('Date Started')
    date_completed = fields.Datetime('Date Completed')
    
    previous_participant_id = fields.Many2one('inclue.participant', string='Previous Participation')
    user_input_id = fields.Many2one('survey.user_input', string='Survey Response', readonly=True)
    
    def _ensure_survey_assignment(self):
        """Ensure participant has proper survey and user_input setup"""
        if not self.survey_id:
            _logger.warning(f"Participant {self.id} has no survey_id - event {self.event_id.name} not configured")
            return False
            
        if not self.user_input_id and self.survey_id:
            user_input = self.env['survey.user_input'].create({
                'survey_id': self.survey_id.id,
                'email': self.email,
                'nickname': self.name,
                'state': 'new'
            })
            self.user_input_id = user_input.id
            self.access_token = user_input.access_token
            _logger.info(f"Created missing user_input {user_input.id} for participant {self.id}")
            return True
        
        return True
    
    @api.model
    def create(self, vals):
        vals['survey_sent'] = True
        vals['date_sent'] = fields.Datetime.now()
        
        participant = super().create(vals)
        
        if participant._ensure_survey_assignment():
            participant.send_survey()
        
        return participant

    @api.depends('user_input_id.state')
    def _compute_survey_state(self):
        """Sync survey state with user_input state and update related fields"""
        for rec in self:
            if rec.user_input_id:
                rec.survey_state = rec.user_input_id.state
                
                if rec.user_input_id.state == 'in_progress':
                    if not rec.survey_started:
                        rec.survey_started = True
                        rec.date_started = fields.Datetime.now()
                    rec.survey_completed = False
                    
                elif rec.user_input_id.state == 'done':
                    rec.survey_started = True
                    if not rec.survey_completed:
                        rec.survey_completed = True
                        rec.date_completed = fields.Datetime.now()
                        
                else:
                    rec.survey_started = False
                    rec.survey_completed = False
            else:
                rec.survey_state = 'new'
    
    @api.depends('survey_id', 'user_input_id')
    def _compute_survey_url(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        for rec in self:
            if rec.survey_id and rec.user_input_id:
                rec.survey_url = f"{base_url}/survey/inclue/{rec.survey_id.access_token}/{rec.user_input_id.access_token}"
                _logger.info(f"Generated custom URL: {rec.survey_url}")
            else:
                rec.survey_url = False
  
    def send_survey(self):
        """Send survey email to participant"""
        self.ensure_one()
        
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
        
        try:
            mail_id = template.send_mail(self.id, force_send=True)
            template.unlink()
            return True
        except Exception as e:
            _logger.error(f"Failed to send survey to {self.email}: {str(e)}")
            return False

    @api.model
    def get_participant_by_email(self, email):
        """Get the appropriate participant record for an email"""
        latest_completed = self.search([
            ('email', '=', email),
            ('survey_completed', '=', True),
            ('is_latest', '=', True)
        ], limit=1)
        
        _logger.info(f"Latest completed participant for {email}: {latest_completed.id if latest_completed else 'None'}")
        if latest_completed:
            next_session = self._get_next_session_type(latest_completed.session_type)
            if next_session:
                next_participant = self.search([
                    ('email', '=', email),
                    ('session_type', '=', next_session)
                ], limit=1)
                
                if next_participant:
                    return next_participant
                else:
                    return self._create_next_session_participant(latest_completed, next_session)
        
        existing_participant = self.search([
            ('email', '=', email),
            ('is_latest', '=', True)
        ], limit=1)
        
        if existing_participant:
            return existing_participant
        return None
    
    def _get_next_session_type(self, current_session):
        """Get the next session type in sequence"""
        sequence = ['kickoff', 'followup1', 'followup2', 'followup3', 
                   'followup4', 'followup5', 'followup6']
        try:
            current_index = sequence.index(current_session)
            if current_index < len(sequence) - 1:
                return sequence[current_index + 1]
        except ValueError:
            pass
        return None
    
    def _create_next_session_participant(self, previous_participant, next_session_type):
        """Create NEW participant for next session (don't override existing)"""
        # Find next session event
        next_event = self.env['event.event'].search([
            ('facilitator_id', '=', previous_participant.facilitator_id.id),
            ('session_type', '=', next_session_type)
        ], limit=1)
        
        if not next_event:
            _logger.warning(f"No event found for session type '{next_session_type}'")
            return None
        
        previous_participant.sudo().write({'is_latest': False})
        
        new_participant = self.create({
            'name': previous_participant.name,
            'email': previous_participant.email,
            'team_lead_name': previous_participant.team_lead_name,
            'company_name': previous_participant.company_name,
            'event_id': next_event.id,
            'previous_participant_id': previous_participant.id,
            'is_latest': True
        })
        
        _logger.info(f"Created new participant {new_participant.id} for {next_session_type} "
                    f"(previous: {previous_participant.id})")
        
        return new_participant
