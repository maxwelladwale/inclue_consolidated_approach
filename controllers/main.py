from odoo import http
from odoo.http import request
from odoo import fields
import logging

_logger = logging.getLogger(__name__)

class InClueSurveyController(http.Controller):
    
    # @http.route('/survey/start/<int:survey_id>/<string:token>', type='http', auth='public', website=True)
    # def survey_start(self, survey_id, token, **kwargs):
    #     """Start survey with token (no login required)"""
        
    #     # Find participant by token
    #     participant = request.env['inclue.participant'].sudo().search([
    #         ('access_token', '=', token),
    #         ('survey_id', '=', survey_id)
    #     ], limit=1)
        
    #     if not participant:
    #         return request.render('http_routing.http_error', {
    #             'status_code': 'Error',
    #             'status_message': 'Invalid survey access token'
    #         })
        
    #     # Mark survey as started
    #     if not participant.survey_started:
    #         participant.write({
    #             'survey_started': True,
    #             'date_started': fields.Datetime.now()
    #         })
        
    #     # Create or get user input
    #     user_input = request.env['survey.user_input'].sudo().search([
    #         ('access_token', '=', token),
    #         ('survey_id', '=', survey_id)
    #     ], limit=1)
        
    #     if not user_input:
    #         user_input = request.env['survey.user_input'].sudo().create({
    #             'survey_id': survey_id,
    #             'access_token': token,
    #             'email': participant.email,
    #             'partner_id': False,  # No login required
    #         })
    #         participant.sudo().write({'user_input_id': user_input.id})
        
    #     # Redirect to survey
    #     return request.redirect(f'/survey/fill/{survey_id}/{token}')

    @http.route('/survey/inclue/<int:survey_id>/<string:token>', type='http', auth='public', website=True)
    def survey_start(self, survey_id, token, **kwargs):
        """Start survey with token (no login required)"""
        
        # Find participant by token
        participant = request.env['inclue.participant'].sudo().search([
            ('access_token', '=', token),
            ('survey_id', '=', survey_id)
        ], limit=1)
        
        if not participant:
            return request.render('http_routing.http_error', {
                'status_code': 'Oops',
                'status_message': 'Invalid survey link or token'
            })
        
        # Mark survey as started
        if not participant.survey_started:
            participant.write({
                'survey_started': True,
                'date_started': fields.Datetime.now()
            })
        
        # Create or get survey user_input
        user_input = request.env['survey.user_input'].sudo().search([
            ('access_token', '=', token),
            ('survey_id', '=', survey_id)
        ], limit=1)
        
        if not user_input:
            user_input = request.env['survey.user_input'].sudo().create({
                'survey_id': survey_id,
                'access_token': token,
                'partner_id': False,  # No login required
                'email': participant.email,
                'nickname': participant.name,
            })
            participant.sudo().write({'user_input_id': user_input.id})
        
        # Use the standard Odoo survey start URL
        survey = request.env['survey.survey'].sudo().browse(survey_id)
        return request.redirect(f'/survey/start/{survey.access_token}/{token}')
    
    @http.route('/survey/submit/<int:survey_id>/<string:token>', type='http', auth='public', methods=['POST'], website=True)
    def survey_submit(self, survey_id, token, **post):
        """Handle survey submission"""
        participant = request.env['inclue.participant'].sudo().search([
            ('access_token', '=', token),
            ('survey_id', '=', survey_id)
        ], limit=1)
        
        if participant and not participant.survey_completed:
            participant.write({
                'survey_completed': True,
                'date_completed': fields.Datetime.now()
            })
        
        # Continue with standard submission
        return request.env['survey.survey'].sudo().browse(survey_id).submit_survey(token, **post)