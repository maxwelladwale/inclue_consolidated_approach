from odoo import models, fields, api
from odoo.exceptions import ValidationError

class InclueSurveyConfig(models.Model):
    _name = 'inclue.survey.config'
    _description = 'iN-Clue Survey Configuration'
    _order = 'sequence, id'
    
    name = fields.Char('Name', compute='_compute_name', store=True)
    sequence = fields.Integer('Sequence', default=10)
    session_type = fields.Selection([
        ('kickoff', 'KickOff Session'),
        ('followup1', 'Follow-up Session 1'),
        ('followup2', 'Follow-up Session 2'),
        ('followup3', 'Follow-up Session 3'),
        ('followup4', 'Follow-up Session 4'),
        ('followup5', 'Follow-up Session 5'),
        ('followup6', 'Follow-up Session 6'),
        ('completion', 'Journey Completion Survey'),
    ], string='Session Type', required=True)
    
    survey_id = fields.Many2one('survey.survey', string='Survey Template', required=True)
    days_until_next = fields.Integer('Days Until Next Session', default=180,
                                   help="Number of days to wait before sending next survey")
    active = fields.Boolean('Active', default=True)
    
    @api.depends('session_type', 'survey_id')
    def _compute_name(self):
        for record in self:
            session_name = dict(self._fields['session_type'].selection).get(record.session_type, '')
            record.name = f"{session_name} - {record.survey_id.title if record.survey_id else ''}"
    
    _sql_constraints = [
        ('session_type_unique', 'UNIQUE(session_type)', 'Each session type must be unique!')
    ]