from odoo import http
from odoo.http import request
from odoo import fields
import logging

_logger = logging.getLogger(__name__)

class InClueSurveyController(http.Controller):
    
    @http.route('/survey/participant/<string:email>', type='http', auth='public', website=True)
    def participant_survey_redirect(self, email, **kwargs):
        """Smart redirect for participants based on their progress"""
        
        participant = request.env['inclue.participant'].sudo().get_participant_by_email(email)
        
        if not participant:
            return request.render('http_routing.http_error', {
                'status_code': 'Welcome!',
                'status_message': 'Please contact your facilitator to begin your iN-Clue Journey with the kickoff session.'
            })
        
        if participant.survey_id and participant.user_input_id:
            survey_token = participant.survey_id.access_token
            user_input_token = participant.user_input_id.access_token
            return request.redirect(f'/survey/inclue/{survey_token}/{user_input_token}')
        else:
            return request.render('http_routing.http_error', {
                'status_code': 'Error',
                'status_message': 'Survey not properly configured. Please contact support.'
            })
    
    @http.route('/survey/inclue/<string:survey_token>/<string:user_input_token>', 
                type='http', auth='public', website=True)
    def survey_start(self, survey_token, user_input_token, **kwargs):
        """Start survey with tokens (no login required)"""
        
        participant = request.env['inclue.participant'].sudo().search([
            ('access_token', '=', user_input_token)
        ], limit=1)

        _logger.info(f"Survey Token: {survey_token}, User Input Token: {user_input_token}")
        _logger.info(f"Participant found: {participant.name if participant else 'None'}")
        
        if not participant:
            return request.render('http_routing.http_error', {
                'status_code': 'Oops',
                'status_message': 'Invalid survey link or token'
            })
        
        if participant.survey_id.access_token != survey_token:
            _logger.error(f"Survey token mismatch: expected {participant.survey_id.access_token}, got {survey_token}")
            return request.render('http_routing.http_error', {
                'status_code': 'Error',
                'status_message': 'Invalid survey token'
            })
        
        
        user_input = participant.user_input_id
        if not user_input:
            user_input = request.env['survey.user_input'].sudo().create({
                'survey_id': participant.survey_id.id,
                'access_token': user_input_token,
                'email': participant.email,
                'nickname': participant.name,
                'state': 'new',
            })
            participant.sudo().write({'user_input_id': user_input.id})
        

        
        _logger.info(f"Redirecting to survey URL: /survey/{survey_token}/{user_input_token}")
        return request.redirect(f'/survey/{survey_token}/{user_input_token}')
    
    @http.route('/survey/submit/<int:survey_id>/<string:token>', type='http', auth='public', methods=['POST'], website=True)
    def survey_submit(self, survey_id, token, **post):
        """Handle survey submission - this may not be needed as the computed field handles state sync"""
        participant = request.env['inclue.participant'].sudo().search([
            ('access_token', '=', token), 
            ('survey_id', '=', survey_id)
        ], limit=1)

        if participant:
            _logger.info(f"Survey submitted for participant: {participant.name}")
        
        try:
            return request.env['survey.survey'].sudo().browse(survey_id).submit_survey(token, **post)
        except Exception as e:
            _logger.error(f"Error submitting survey {survey_id} with token {token}: {str(e)}")
            return request.render('http_routing.http_error', {
                'status_code': 'Error',
                'status_message': 'Survey submission failed'
            })