# Add this to your controllers/main.py file

from odoo import http
from odoo.http import request
import json
import logging

_logger = logging.getLogger(__name__)

class SignupController(http.Controller):
    
    @http.route('/api/v1/inclue/signup/validate', type='json', auth='none', methods=['POST'], csrf=False, cors='*')
    def validate_signup_token(self, **kwargs):
        """
        Validate a signup token and return user information
        """
        if not kwargs:
            try:
                kwargs = json.loads(request.httprequest.data.decode('utf-8'))
            except json.JSONDecodeError:
                return {'status': 'error', 'message': 'Invalid JSON format.'}
        
        _logger.info("Received signup validate data in api: %s", kwargs)

        try:
            token = kwargs.get('token')
            db = kwargs.get('db')
            
            if not token:
                return {'error': 'Token is required'}
            
            # Use the auth_signup module's methods
            try:
                # Get the user with this signup token
                user = request.env['res.users'].sudo().search([
                    ('signup_token', '=', token),
                    ('signup_type', '!=', False)
                ], limit=1)
                
                if not user:
                    return {'error': 'Invalid or expired token'}
                
                # Check if token is still valid (not expired)
                if user.signup_expiration:
                    from datetime import datetime
                    if datetime.now() > user.signup_expiration:
                        return {'error': 'Token has expired'}
                
                return {
                    'success': True,
                    'user': {
                        'name': user.name,
                        'email': user.email or user.login,
                        'company_name': user.company_id.name if user.company_id else 'Company'
                    }
                }
                
            except Exception as e:
                _logger.error(f"Token validation error: {str(e)}")
                return {'error': 'Invalid or expired token'}
                
        except Exception as e:
            _logger.error(f"Signup validation error: {str(e)}")
            return {'error': 'Server error occurred'}

    @http.route('/api/v1/inclue/signup/complete', type='json', auth='none', methods=['POST'], csrf=False, cors='*')
    def complete_signup(self, **kwargs):
        """
        Complete the signup process by setting the user's password
        """
        if not kwargs:
            try:
                kwargs = json.loads(request.httprequest.data.decode('utf-8'))
            except json.JSONDecodeError:
                return {'status': 'error', 'message': 'Invalid JSON format.'}
        
        _logger.info("Received signup validate data in api: %s", kwargs)
        try:
            token = kwargs.get('token')
            password = kwargs.get('password')
            db = kwargs.get('db')
            
            if not token or not password:
                return {'error': 'Token and password are required'}
            
            if len(password) < 6:
                return {'error': 'Password must be at least 6 characters long'}
            
            try:
                # Find the user with this token
                user = request.env['res.users'].sudo().search([
                    ('signup_token', '=', token),
                    ('signup_type', '!=', False)
                ], limit=1)
                
                if not user:
                    return {'error': 'Invalid or expired token'}
                
                # Check if token is still valid (not expired)
                if user.signup_expiration:
                    from datetime import datetime
                    if datetime.now() > user.signup_expiration:
                        return {'error': 'Token has expired'}
                
                # Set the password and activate the user
                user.write({
                    'password': password,
                    'signup_token': False,
                    'signup_type': False,
                    'signup_expiration': False,
                    'active': True
                })
                
                return {
                    'success': True,
                    'message': 'Account activated successfully'
                }
                
            except Exception as e:
                _logger.error(f"Signup completion error: {str(e)}")
                return {'error': 'Failed to activate account. Token may be invalid or expired.'}
                
        except Exception as e:
            _logger.error(f"Signup completion error: {str(e)}")
            return {'error': 'Server error occurred'}