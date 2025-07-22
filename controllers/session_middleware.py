from odoo import http
from odoo.http import request
import logging

_logger = logging.getLogger(__name__)

class SessionMiddleware(http.Controller):
    """
    Middleware to intercept and control web interface access
    """
    
    @http.route([
        '/web/database/selector',
        '/web/database/manager', 
        '/web/database/create',
        '/web/webclient',
        '/web/action',
    ], type='http', auth='user', methods=['GET', 'POST'])
    def block_web_interface_routes(self, **kwargs):
        """
        Block access to key web interface routes for API-only sessions
        """
        if request.session.get('api_only'):
            _logger.warning("API-only session blocked from accessing: %s", 
                          request.httprequest.path)
            return self._redirect_to_block_page()
        
        # Allow normal access - this requires manual route handling
        # TODO: may need to implement specific route handlers or use werkzeug routing
        return request.not_found()
    
    def _redirect_to_block_page(self):
        """Redirect to the block page"""
        return request.redirect('/web')
