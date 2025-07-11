from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)

class SurveyUserInput(models.Model):
    _inherit = 'survey.user_input'
    
    cohort_id = fields.Many2one(
        'event.event',
        string='Cohort',
        help="The cohort this answer belongs to"
    )
    completion_journey_id = fields.Many2one(
        'event.event',
        string='Completion Journey',
        help="The kickoff event this completion survey belongs to"
    )
    
    is_completion_survey = fields.Boolean(
        'Is Completion Survey',
        compute='_compute_is_completion_survey',
        store=True
    )
    
    @api.depends('completion_journey_id')
    def _compute_is_completion_survey(self):
        for record in self:
            record.is_completion_survey = bool(record.completion_journey_id)
    
    def write(self, vals):
        """Override write to handle completion survey completion"""
        result = super().write(vals)
        
        if 'state' in vals and vals['state'] == 'done':
            for record in self:
                if record.is_completion_survey and record.completion_journey_id:
                    try:
                        # Mark the journey as completed
                        record.completion_journey_id.sudo().write({
                            'journey_completed': True,
                            'completion_date': fields.Datetime.now()
                        })
                        
                        _logger.info("Journey %s marked as completed via completion survey", 
                                   record.completion_journey_id.cohort)
                    except Exception as e:
                        _logger.error("Error marking journey as completed: %s", str(e))
        
        return result