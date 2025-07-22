from odoo import models, fields, api

class ResUsersAPIRestriction(models.Model):
    _inherit = 'res.users'
    
    api_only_access = fields.Boolean(
        'API Only Access',
        default=False,
        help="If enabled, this user can only access the system via API, not the web interface"
    )
    
    last_api_login = fields.Datetime(
        'Last API Login',
        readonly=True,
        help="Last time this user logged in via API"
    )
    
    last_web_login = fields.Datetime(
        'Last Web Login', 
        readonly=True,
        help="Last time this user logged in via web interface"
    )
    
    def write(self, vals):
        """Override write to log login methods"""
        result = super().write(vals)
        
        # Track login methods based on session data
        if hasattr(self, '_context') and self._context.get('login_method'):
            login_method = self._context['login_method']
            if login_method == 'api':
                self.last_api_login = fields.Datetime.now()
            elif login_method == 'web':
                self.last_web_login = fields.Datetime.now()
        
        return result
    
    @api.model
    def check_api_only_restriction(self, user_id):
        """
        Check if user has API-only restriction
        """
        user = self.browse(user_id)
        return user.api_only_access
    
    def action_toggle_api_restriction(self):
        """
        Action to toggle API-only restriction for user
        """
        for user in self:
            user.api_only_access = not user.api_only_access
            
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'API Restriction Updated',
                'message': f'API-only access {"enabled" if self.api_only_access else "disabled"} for {len(self)} user(s)',
                'type': 'success',
            }
        }
