{
    'name': 'iN-Clue Journey Consolidated Approach',
    'version': '2.0',
    'category': 'Events',
    'summary': 'Complete iN-Clue Journey Management System',
    'description': """
        iN-Clue Journey Management v2
        =============================
        - Multiple survey support per session type
        - No login required for participants
        - Automated follow-up scheduling
        - Token-based survey access
        - Complete journey tracking
    """,
    'author': 'Your Company',
    'depends': ['base', 'event', 'survey', 'mail'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        # 'data/email_templates.xml',
        'data/cron_jobs.xml',
        # 'views/inclue_event_views.xml',
        # 'views/inclue_participant_views.xml',
        # 'views/completion_survey_config.xml',
        'views/inclue_survey_config_views.xml',
        'views/res_partner_views.xml',
        'views/inclue_facilitator_order_views.xml',
        'views/inclue_invoice_info_views.xml',
        'views/menu_items.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}