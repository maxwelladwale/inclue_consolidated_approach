{
    'name': 'iN-Clue Journey Consolidated Approach',
    'version': '2.1',
    'category': 'Events',
    'summary': 'Complete iN-Clue Journey Management System with Product-Based Ordering',
    'description': """
        iN-Clue Journey Management v2.1
        ===============================
        - Multiple survey support per session type
        - No login required for participants
        - Automated follow-up scheduling
        - Token-based survey access
        - Complete journey tracking
        - Product-based card ordering system
        - Flexible pricing with pricelists
        - Invoice automation
    """,
    'author': 'Your Company',
    'depends': [
        'base', 
        'event', 
        'survey', 
        'mail',
        'product',
        'account',
        'sale',
        'hr',
    ],

    'external_dependencies': {
        'python': ['reportlab'],
    },

    'data': [
        # Security
        'security/security.xml',
        'security/ir.model.access.csv',
        
        # Data
        'data/card_products.xml',
        'data/pricelists.xml',
        # 'data/sequences.xml',
        'data/cron_jobs.xml',
        'data/email_template_pre_session.xml',
        'data/email_template_team_lead_reminder.xml',
        # 'data/reset_password_template.xml',
        # 'data/email_templates.xml',
        
        # Views
        'views/inclue_survey_config_views.xml',
        'views/res_partner_views.xml',
        'views/res_user_views.xml',
        # 'views/inclue_facilitator_order_views.xml',
        'views/inclue_invoice_info_views.xml',
        'views/menu_items.xml',
        # 'views/inclue_event_views.xml',
        # 'views/inclue_participant_views.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}