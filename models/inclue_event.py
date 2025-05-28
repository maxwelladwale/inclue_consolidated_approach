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
    division_id = fields.Many2one('hr.department', string="Division")
    country_id = fields.Many2one('res.country', string="Country")
    language_id = fields.Many2one('res.lang', string="Preferred Language")
    hr_contact_id = fields.Many2one('res.partner', string="Responsible HR")
    invoice_info_id = fields.Many2one('inclue.invoice.info', string="Invoice Info")
    team_commitment = fields.Text("Team Commitment", help="Commitment from the team to participate in the iN-Clue Journey", required=True)
    desired_differences = fields.Text("Desired Differences", help="What changes the team wants to see after the iN-Clue Journey", required=True)
    company_support = fields.Text("Company Support", help="How the company can support the team during the iN-Clue Journey", required=True)

    
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
