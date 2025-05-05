import secrets
import string
from datetime import timedelta
from odoo import models, fields, api
import logging

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
    
    # Status fields
    survey_sent = fields.Boolean('Survey Sent', default=False, tracking=True)
    survey_started = fields.Boolean('Survey Started', default=False)
    survey_completed = fields.Boolean('Survey Completed', default=False, tracking=True)
    
    date_sent = fields.Datetime('Date Sent')
    date_started = fields.Datetime('Date Started')
    date_completed = fields.Datetime('Date Completed')
    
    # Follow-up tracking
    next_session_date = fields.Date('Next Session Date', compute='_compute_next_session', store=True)
    previous_participant_id = fields.Many2one('inclue.participant', string='Previous Participation')
    
    user_input_id = fields.Many2one('survey.user_input', string='Survey Response', readonly=True)
    
    @api.model
    def create(self, vals):
        if not vals.get('access_token'):
            vals['access_token'] = self._generate_token()
        return super().create(vals)
    
    def _generate_token(self):
        """Generate a secure random token"""
        return ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32))
    
    # @api.depends('survey_id', 'access_token')
    # def _compute_survey_url(self):
    #     base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
    #     for record in self:
    #         if record.survey_id and record.access_token:
    #             record.survey_url = f"{base_url}/survey/start/{record.survey_id.id}/{record.access_token}"
    #         else:
    #             record.survey_url = False

    @api.depends('survey_id', 'access_token')
    def _compute_survey_url(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        for record in self:
            if record.survey_id and record.access_token:
                # Use the standard Odoo survey URL format
                survey = record.survey_id
                record.survey_url = f"{base_url}/survey/start/{survey.access_token}/{record.access_token}"
            else:
                record.survey_url = False
    
    @api.depends('survey_completed', 'session_type')
    def _compute_next_session(self):
        for record in self:
            if record.survey_completed and record.session_type != 'followup6':
                config = self.env['inclue.survey.config'].search([
                    ('session_type', '=', record.session_type),
                    ('active', '=', True)
                ], limit=1)
                if config:
                    record.next_session_date = fields.Date.today() + timedelta(days=config.days_until_next)
                else:
                    record.next_session_date = False
            else:
                record.next_session_date = False
    
    # def send_survey(self):
    #     """Send survey email to participant"""
    #     self.ensure_one()
        
    #     template = self.env.ref('inclue_journey_v2.email_template_survey_invitation')
        
    #     try:
    #         template.send_mail(self.id, force_send=True)
    #         self.write({
    #             'survey_sent': True,
    #             'date_sent': fields.Datetime.now()
    #         })
    #         return True
    #     except Exception as e:
    #         _logger.error(f"Failed to send survey to {self.email}: {str(e)}")
    #         return False

    # def send_survey(self):
    #     """Send survey email to participant"""
    #     self.ensure_one()
        
    #     # Try to find existing template
    #     template = self.env.ref('inclue_journey_v2.email_template_survey_invitation', raise_if_not_found=False)
        
    #     # If not found, create a temporary template
    #     if not template:
    #         template = self.env['mail.template'].create({
    #             'name': 'iN-Clue Survey Invitation',
    #             'model_id': self.env['ir.model'].search([('model', '=', 'inclue.participant')], limit=1).id,
    #             'subject': 'Your iN-Clue Journey Survey is Ready',
    #             'email_from': 'noreply@inclue.com',
    #             'email_to': '${object.email}',
    #             'body_html': '''
    #                 <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
    #                     <div style="background-color: #008f8c; color: white; padding: 20px; text-align: center;">
    #                         <h1 style="margin: 0;">iN-Clue Journey</h1>
    #                     </div>
                        
    #                     <div style="padding: 20px; background-color: #f9f9f9;">
    #                         <p>Dear ${object.name},</p>
                            
    #                         <p>Thank you for participating in the <strong>${object.session_type}</strong> session of the iN-Clue Journey.</p>
                            
    #                         <p>Please take a moment to complete your survey by clicking the button below:</p>
                            
    #                         <div style="text-align: center; margin: 30px 0;">
    #                             <a href="${object.survey_url}" 
    #                             style="background-color: #008f8c; 
    #                                     color: white; 
    #                                     padding: 12px 30px; 
    #                                     text-decoration: none; 
    #                                     border-radius: 5px; 
    #                                     display: inline-block;
    #                                     font-weight: bold;">
    #                                 Complete Survey
    #                             </a>
    #                         </div>
                            
    #                         <p><strong>Session Details:</strong></p>
    #                         <ul style="list-style: none; padding-left: 0;">
    #                             <li>📅 Event: ${object.event_id.name}</li>
    #                             <li>👤 Facilitator: ${object.facilitator_id.name}</li>
    #                             <li>👥 Team Lead: ${object.team_lead_name}</li>
    #                             <li>🏢 Company: ${object.company_name}</li>
    #                         </ul>
                            
    #                         <p>This survey link is unique to you and requires no login.</p>
                            
    #                         <p>Thank you for your participation!</p>
                            
    #                         <p>Best regards,<br/>The iN-Clue Team</p>
    #                     </div>
                        
    #                     <div style="background-color: #333; color: white; padding: 10px; text-align: center; font-size: 12px;">
    #                         <p style="margin: 0;">© 2024 iN-Clue Journey. All rights reserved.</p>
    #                     </div>
    #                 </div>
    #             ''',
    #         })
    #         # Save the template ID for future use
    #         self.env['ir.model.data'].create({
    #             'name': 'email_template_survey_invitation',
    #             'module': 'inclue_journey_v2',
    #             'model': 'mail.template',
    #             'res_id': template.id,
    #         })
        
    #     # Continue with sending the email
    #     try:
    #         template.send_mail(self.id, force_send=True)
    #         self.write({
    #             'survey_sent': True,
    #             'date_sent': fields.Datetime.now()
    #         })
    #         return True
    #     except Exception as e:
    #         _logger.error(f"Failed to send survey to {self.email}: {str(e)}")
    #         return False
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
    @api.model
    def cron_create_followup_sessions(self):
        """Cron job to create follow-up sessions"""
        today = fields.Date.today()
        
        # Find participants due for follow-up
        participants = self.search([
            ('survey_completed', '=', True),
            ('next_session_date', '<=', today),
            ('session_type', '!=', 'followup6')
        ])
        
        for participant in participants:
            next_session = self._get_next_session_type(participant.session_type)
            if next_session:
                # Create follow-up event
                event_vals = {
                    'name': f"{next_session} - {participant.name}",
                    'is_inclue_event': True,
                    'session_type': next_session,
                    'facilitator_id': participant.facilitator_id.id,
                    'date_begin': fields.Datetime.now(),
                    'date_end': fields.Datetime.now() + timedelta(hours=1),
                }
                
                follow_up_event = self.env['event.event'].create(event_vals)
                
                # Create follow-up participant
                participant_vals = {
                    'name': participant.name,
                    'email': participant.email,
                    'team_lead_name': participant.team_lead_name,
                    'company_name': participant.company_name,
                    'event_id': follow_up_event.id,
                    'previous_participant_id': participant.id,
                }
                
                follow_up = self.create(participant_vals)
                follow_up.send_survey()
                
                # Clear next session date
                participant.next_session_date = False
    
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