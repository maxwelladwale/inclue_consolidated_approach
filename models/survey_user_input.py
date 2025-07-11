from odoo import models, fields, api
import logging
import json
import tempfile
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
import os

_logger = logging.getLogger(__name__)

class SurveyUserInput(models.Model):
    _inherit = 'survey.user_input'
    
    pdf_generated = fields.Boolean('PDF Generated', default=False)
    pdf_sent_to_team_lead = fields.Boolean('Sent to Team Lead', default=False)
    pdf_file_path = fields.Char('PDF File Path')
    completion_answers_json = fields.Text('Completion Answers JSON')

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
                        record._process_completion_survey()
                    except Exception as e:
                        _logger.error("Error marking journey as completed: %s", str(e))
        
        return result
    
    def _process_completion_survey(self):
        """Process completion survey and generate PDF"""
        try:
            # Extract completion answers
            answers = self._extract_completion_answers()
            if not answers:
                _logger.warning("No completion answers found for user_input %s", self.id)
                return
            
            # Store answers as JSON
            self.completion_answers_json = json.dumps(answers)
            
            # Generate PDF
            pdf_path = self._generate_completion_pdf(answers)
            if pdf_path:
                self.write({
                    'pdf_generated': True,
                    'pdf_file_path': pdf_path
                })
                
                # Send to team lead
                self._send_pdf_to_team_lead(pdf_path, answers)
                
        except Exception as e:
            _logger.error("Error processing completion survey %s: %s", self.id, str(e))


    def _extract_completion_answers(self):
        """Extract the 3 completion survey answers"""
        self.ensure_one()
        
        # Get completion survey questions (text type)
        completion_lines = self.env['survey.user_input.line'].search([
            ('user_input_id', '=', self.id),
            ('answer_type', '=', 'char_box'),  # Text answers
            ('value_char_box', '!=', False)
        ], order='question_sequence, question_id')
        
        answers = {}
        for line in completion_lines:
            question_title = line.question_id.title
            if isinstance(question_title, dict):
                question_title = question_title.get('en_US', 'Question')
            
            answers[f"question_{line.question_id.id}"] = {
                'question': question_title,
                'answer': line.value_char_box,
                'sequence': line.question_sequence
            }
        
        return answers
    
    def _generate_completion_pdf(self, answers):
        """Generate PDF report with answers"""
        self.ensure_one()
        
        try:
            # Create temporary file
            temp_dir = tempfile.gettempdir()
            filename = f"completion_report_{self.completion_journey_id.cohort}_{self.id}.pdf"
            pdf_path = os.path.join(temp_dir, filename)
            
            # Create PDF
            doc = SimpleDocTemplate(pdf_path, pagesize=letter)
            styles = getSampleStyleSheet()
            story = []
            
            # Title
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=18,
                spaceAfter=30,
                textColor=colors.HexColor('#2c3e50')
            )
            story.append(Paragraph("iN-Clue Journey Completion Report", title_style))
            
            # Journey Info
            journey = self.completion_journey_id
            if journey:
                info_data = [
                    ['Team/Cohort:', journey.cohort or 'N/A'],
                    ['Team Leader:', journey.team_leader or 'N/A'],
                    ['Completion Date:', self.create_date.strftime('%B %d, %Y') if self.create_date else 'N/A'],
                    ['Facilitator:', journey.facilitator_id.name if journey.facilitator_id else 'N/A'],
                ]
                
                info_table = Table(info_data, colWidths=[2*inch, 4*inch])
                info_table.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (0,-1), colors.HexColor('#f8f9fa')),
                    ('TEXTCOLOR', (0,0), (-1,-1), colors.black),
                    ('ALIGN', (0,0), (-1,-1), 'LEFT'),
                    ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
                    ('FONTSIZE', (0,0), (-1,-1), 10),
                    ('GRID', (0,0), (-1,-1), 1, colors.HexColor('#dee2e6'))
                ]))
                story.append(info_table)
                story.append(Spacer(1, 20))
            
            # Survey Answers
            story.append(Paragraph("Survey Responses", styles['Heading2']))
            story.append(Spacer(1, 12))
            
            # Sort answers by sequence
            sorted_answers = sorted(answers.values(), key=lambda x: x['sequence'])
            
            for i, answer_data in enumerate(sorted_answers, 1):
                # Question
                question_style = ParagraphStyle(
                    'Question',
                    parent=styles['Normal'],
                    fontSize=12,
                    fontName='Helvetica-Bold',
                    spaceBefore=10,
                    spaceAfter=5
                )
                story.append(Paragraph(f"Question {i}: {answer_data['question']}", question_style))
                
                # Answer
                answer_style = ParagraphStyle(
                    'Answer',
                    parent=styles['Normal'],
                    fontSize=11,
                    leftIndent=20,
                    spaceAfter=15,
                    borderColor=colors.HexColor('#e9ecef'),
                    borderWidth=1,
                    borderPadding=10,
                    backColor=colors.HexColor('#f8f9fa')
                )
                story.append(Paragraph(answer_data['answer'], answer_style))
            
            # Build PDF
            doc.build(story)
            
            _logger.info("Generated completion PDF: %s", pdf_path)
            return pdf_path
            
        except Exception as e:
            _logger.error("Error generating PDF: %s", str(e))
            return None
        
    def _send_pdf_to_team_lead(self, pdf_path, answers):
        """Send PDF to team leader"""
        self.ensure_one()
        
        journey = self.completion_journey_id
        if not journey or not journey.team_leader_email:
            _logger.warning("No team leader email for journey %s", journey.cohort if journey else 'Unknown')
            return
        
        try:
            # Create email template
            template_body = f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px;">
                <h2 style="color: #2c3e50;">iN-Clue Journey Completion Report</h2>
                
                <p>Dear {journey.team_leader},</p>
                
                <p>Congratulations! Your team <strong>{journey.cohort}</strong> has successfully completed their iN-Clue Journey.</p>
                
                <p>Please find attached the completion report with your team's final reflections.</p>
                
                <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0;">
                    <h3 style="margin-top: 0;">Journey Summary:</h3>
                    <ul>
                        <li><strong>Team/Cohort:</strong> {journey.cohort}</li>
                        <li><strong>Facilitator:</strong> {journey.facilitator_id.name if journey.facilitator_id else 'N/A'}</li>
                        <li><strong>Completion Date:</strong> {self.create_date.strftime('%B %d, %Y') if self.create_date else 'N/A'}</li>
                    </ul>
                </div>
                
                <p>Thank you for participating in the iN-Clue Journey program.</p>
                
                <p>Best regards,<br/>The iN-Clue Team</p>
            </div>
            """
            
            # Send email with attachment
            mail_values = {
                'subject': f'iN-Clue Journey Completion Report - {journey.cohort}',
                'body_html': template_body,
                'email_to': journey.team_leader_email,
                'email_from': self.env.company.email or 'noreply@inclue.com',
                'attachment_ids': [(0, 0, {
                    'name': f'Completion_Report_{journey.cohort}.pdf',
                    'datas': self._encode_pdf_file(pdf_path),
                    'res_model': 'survey.user_input',
                    'res_id': self.id,
                })]
            }
            
            mail = self.env['mail.mail'].create(mail_values)
            mail.send()
            
            self.pdf_sent_to_team_lead = True
            _logger.info("Sent completion PDF to team lead: %s", journey.team_leader_email)
            
        except Exception as e:
            _logger.error("Error sending PDF to team lead: %s", str(e))

    def _encode_pdf_file(self, pdf_path):
        """Encode PDF file for email attachment"""
        import base64
        try:
            with open(pdf_path, 'rb') as pdf_file:
                return base64.b64encode(pdf_file.read())
        except Exception as e:
            _logger.error("Error encoding PDF file: %s", str(e))
            return False
