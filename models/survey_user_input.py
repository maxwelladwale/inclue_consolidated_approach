from odoo import models, fields, api
import logging
import json
import tempfile
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.graphics.shapes import Drawing, Rect, Circle, Line
from reportlab.graphics import renderPDF
import os
import tempfile

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
            filename = f"inclue_completion_report_{self.completion_journey_id.cohort}_{self.id}.pdf"
            pdf_path = os.path.join(temp_dir, filename)
            
            # Create PDF
            doc = SimpleDocTemplate(
                pdf_path, 
                pagesize=A4,
                rightMargin=2*cm,
                leftMargin=2*cm,
                topMargin=3*cm,
                bottomMargin=2*cm
            )
            
            styles = getSampleStyleSheet()
            story = []
            
            # ============================================================================
            # ENHANCED HEADER WITH BRANDING
            # ============================================================================
            
            # Create branded header with geometric elements
            header_style = ParagraphStyle(
                'BrandedHeader',
                parent=styles['Heading1'],
                fontSize=24,
                fontName='Helvetica-Bold',
                textColor=colors.HexColor('#2c3e50'),
                alignment=TA_CENTER,
                spaceAfter=10
            )
            story.append(Paragraph("iN·Clue", header_style))
            
            # Subtitle with accent color
            subtitle_style = ParagraphStyle(
                'Subtitle',
                parent=styles['Normal'],
                fontSize=14,
                fontName='Helvetica',
                textColor=colors.HexColor('#8BC34A'),
                alignment=TA_CENTER,
                spaceAfter=30
            )
            story.append(Paragraph("A CLUE FOR INCLUSION", subtitle_style))
            
            title_style = ParagraphStyle(
                'ModernTitle',
                parent=styles['Heading1'],
                fontSize=20,
                fontName='Helvetica',
                textColor=colors.HexColor('#34495e'),
                alignment=TA_CENTER,
                spaceAfter=40,
                borderWidth=2,
                borderColor=colors.HexColor('#8BC34A'),
                borderPadding=15,
                backColor=colors.HexColor('#f8f9fa')
            )
            story.append(Paragraph("Journey Completion Report", title_style))
            
            # ============================================================================
            # JOURNEY INFO TABLE
            # ============================================================================
            
            journey = self.completion_journey_id
            if journey:
                # Create more detailed journey info
                info_data = [
                    ['🎯 Team', journey.cohort or 'N/A'],
                    ['👤 Team Leader', journey.team_leader or 'N/A'],
                    ['✅ Completion Date', self.create_date.strftime('%B %d, %Y') if self.create_date else 'N/A'],
                    ['🎓 Facilitator', journey.facilitator_id.name if journey.facilitator_id else 'N/A'],
                    ['🏢 Company', journey.invoice_info_id.company_name if journey.invoice_info_id else 'N/A'],
                    ['🌍 Country', journey.country_id.name if journey.country_id else 'N/A'],
                ]
                
                info_table = Table(info_data, colWidths=[3*cm, 12*cm])
                info_table.setStyle(TableStyle([
                    # Header styling
                    ('BACKGROUND', (0,0), (0,-1), colors.HexColor('#34495e')),
                    ('TEXTCOLOR', (0,0), (0,-1), colors.white),
                    ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
                    ('FONTSIZE', (0,0), (0,-1), 11),
                    
                    # Data styling
                    ('BACKGROUND', (1,0), (1,-1), colors.HexColor('#ecf0f1')),
                    ('TEXTCOLOR', (1,0), (1,-1), colors.HexColor('#2c3e50')),
                    ('FONTNAME', (1,0), (1,-1), 'Helvetica'),
                    ('FONTSIZE', (1,0), (1,-1), 11),
                    
                    # Grid and alignment
                    ('ALIGN', (0,0), (-1,-1), 'LEFT'),
                    ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                    ('GRID', (0,0), (-1,-1), 1, colors.HexColor('#bdc3c7')),
                    ('ROWBACKGROUNDS', (0,0), (-1,-1), [colors.white, colors.HexColor('#f8f9fa')]),
                    
                    # Padding
                    ('LEFTPADDING', (0,0), (-1,-1), 12),
                    ('RIGHTPADDING', (0,0), (-1,-1), 12),
                    ('TOPPADDING', (0,0), (-1,-1), 8),
                    ('BOTTOMPADDING', (0,0), (-1,-1), 8),
                ]))
                story.append(info_table)
                story.append(Spacer(1, 30))
            
            # ============================================================================
            # SURVEY RESPONSES SECTION
            # ============================================================================
            
            # Section header with accent line
            response_header_style = ParagraphStyle(
                'ResponseHeader',
                parent=styles['Heading2'],
                fontSize=18,
                fontName='Helvetica-Bold',
                textColor=colors.HexColor('#2c3e50'),
                spaceBefore=20,
                spaceAfter=20,
                borderWidth=0,
                borderPadding=10,
                backColor=colors.HexColor('#ecf0f1'),
                leftIndent=15
            )
            story.append(Paragraph("📝 Survey Responses", response_header_style))
            
            # Sort answers by sequence
            sorted_answers = sorted(answers.values(), key=lambda x: x['sequence'])
            
            for i, answer_data in enumerate(sorted_answers, 1):
                # Question
                question_style = ParagraphStyle(
                    'ModernQuestion',
                    parent=styles['Normal'],
                    fontSize=13,
                    fontName='Helvetica-Bold',
                    textColor=colors.HexColor('#2c3e50'),
                    spaceBefore=15,
                    spaceAfter=8,
                    leftIndent=10,
                    borderWidth=1,
                    borderColor=colors.HexColor('#8BC34A'),
                    borderPadding=10,
                    backColor=colors.HexColor('#e8f5e8')
                )
                story.append(Paragraph(f"Question {i}: {answer_data['question']}", question_style))
                
                # Answer
                answer_style = ParagraphStyle(
                    'ModernAnswer',
                    parent=styles['Normal'],
                    fontSize=12,
                    fontName='Helvetica',
                    textColor=colors.HexColor('#34495e'),
                    leftIndent=25,
                    rightIndent=25,
                    spaceAfter=20,
                    borderWidth=1,
                    borderColor=colors.HexColor('#d5dbdb'),
                    borderPadding=15,
                    backColor=colors.white,
                    leading=16
                )
                story.append(Paragraph(f'"{answer_data["answer"]}"', answer_style))
            
            # ============================================================================
            # FOOTER SECTION
            # ============================================================================
            
            story.append(Spacer(1, 40))
            
            # Thank you message
            footer_style = ParagraphStyle(
                'Footer',
                parent=styles['Normal'],
                fontSize=11,
                fontName='Helvetica-Oblique',
                textColor=colors.HexColor('#7f8c8d'),
                alignment=TA_CENTER,
                spaceBefore=30
            )
            story.append(Paragraph("Thank you for completing your iN-Clue Journey!", footer_style))
            
            # Contact info
            contact_style = ParagraphStyle(
                'Contact',
                parent=styles['Normal'],
                fontSize=9,
                fontName='Helvetica',
                textColor=colors.HexColor('#95a5a6'),
                alignment=TA_CENTER,
                spaceBefore=10
            )
            story.append(Paragraph("For questions about this report, contact your facilitator or the iN-Clue team.", contact_style))
            
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
            # ============================================================================
            # HTML EMAIL TEMPLATE
            # ============================================================================
            
            template_body = f"""
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>iN-Clue Journey Completion</title>
            </head>
            <body style="margin: 0; padding: 0; font-family: 'Helvetica', Arial, sans-serif; background-color: #f8f9fa;">
                
                <!-- Main Container -->
                <div style="max-width: 600px; margin: 0 auto; background-color: white; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                    
                    <!-- Header with Branding -->
                    <div style="background: linear-gradient(135deg, #2c3e50 0%, #34495e 100%); padding: 40px 30px; text-align: center;">
                        <h1 style="color: white; margin: 0; font-size: 28px; font-weight: 300; letter-spacing: 2px;">
                            iN·Clue
                        </h1>
                        <p style="color: #8BC34A; margin: 10px 0 0 0; font-size: 14px; font-weight: 500; letter-spacing: 1px;">
                            A CLUE FOR INCLUSION
                        </p>
                    </div>
                    
                    <!-- Content Area -->
                    <div style="padding: 40px 30px;">
                        
                        <!-- Congratulations Section -->
                        <div style="text-align: center; margin-bottom: 30px;">
                            <div style="width: 60px; height: 60px; background-color: #8BC34A; border-radius: 50%; margin: 0 auto 20px; display: flex; align-items: center; justify-content: center; font-size: 24px;">
                                🎉
                            </div>
                            <h2 style="color: #2c3e50; margin: 0; font-size: 24px; font-weight: 600;">
                                Journey Complete!
                            </h2>
                            <p style="color: #7f8c8d; margin: 10px 0 0 0; font-size: 16px;">
                                Your team has successfully completed their iN-Clue Journey
                            </p>
                        </div>
                        
                        <!-- Personal Message -->
                        <div style="background-color: #f8f9fa; padding: 25px; border-radius: 8px; border-left: 4px solid #8BC34A; margin-bottom: 30px;">
                            <p style="color: #2c3e50; margin: 0; font-size: 16px; line-height: 1.5;">
                                Dear <strong>{journey.team_leader}</strong>,
                            </p>
                            <p style="color: #34495e; margin: 15px 0 0 0; font-size: 15px; line-height: 1.6;">
                                Congratulations! Your team <strong style="color: #8BC34A;">{journey.cohort}</strong> 
                                has successfully completed their iN-Clue Journey. This is a significant milestone 
                                in your team's development and inclusion journey.
                            </p>
                        </div>
                        
                        <!-- Journey Summary Card -->
                        <div style="background: white; border: 1px solid #e9ecef; border-radius: 8px; overflow: hidden; margin-bottom: 30px;">
                            <div style="background-color: #34495e; color: white; padding: 15px 20px;">
                                <h3 style="margin: 0; font-size: 16px; font-weight: 600;">📊 Journey Summary</h3>
                            </div>
                            <div style="padding: 20px;">
                                <table style="width: 100%; border-collapse: collapse;">
                                    <tr>
                                        <td style="padding: 8px 0; color: #7f8c8d; font-size: 14px; width: 40%;">Team:</td>
                                        <td style="padding: 8px 0; color: #2c3e50; font-size: 14px; font-weight: 600;">{journey.cohort}</td>
                                    </tr>
                                    <tr>
                                        <td style="padding: 8px 0; color: #7f8c8d; font-size: 14px;">Facilitator:</td>
                                        <td style="padding: 8px 0; color: #2c3e50; font-size: 14px; font-weight: 600;">{journey.facilitator_id.name if journey.facilitator_id else 'N/A'}</td>
                                    </tr>
                                    <tr>
                                        <td style="padding: 8px 0; color: #7f8c8d; font-size: 14px;">Completion Date:</td>
                                        <td style="padding: 8px 0; color: #2c3e50; font-size: 14px; font-weight: 600;">{self.create_date.strftime('%B %d, %Y') if self.create_date else 'N/A'}</td>
                                    </tr>
                                    <tr>
                                        <td style="padding: 8px 0; color: #7f8c8d; font-size: 14px;">Company:</td>
                                        <td style="padding: 8px 0; color: #2c3e50; font-size: 14px; font-weight: 600;">{journey.invoice_info_id.company_name if journey.invoice_info_id else 'N/A'}</td>
                                    </tr>
                                </table>
                            </div>
                        </div>
                        
                        <!-- Call to Action -->
                        <div style="text-align: center; margin-bottom: 30px;">
                            <p style="color: #34495e; margin: 0 0 20px 0; font-size: 15px;">
                                📎 Please find attached your team's completion report with final reflections
                            </p>
                            <div style="background: linear-gradient(45deg, #8BC34A, #9CCC65); padding: 12px 30px; border-radius: 25px; display: inline-block;">
                                <span style="color: white; font-size: 14px; font-weight: 600;">
                                    ✨ Completion Report Attached
                                </span>
                            </div>
                        </div>
                        
                        <!-- Next Steps -->
                        <div style="background: linear-gradient(135deg, #ecf0f1, #f8f9fa); padding: 25px; border-radius: 8px; margin-bottom: 30px;">
                            <h4 style="color: #2c3e50; margin: 0 0 15px 0; font-size: 16px;">🚀 What's Next?</h4>
                            <ul style="color: #34495e; margin: 0; padding-left: 20px; font-size: 14px; line-height: 1.6;">
                                <li>Review your team's completion responses</li>
                                <li>Share insights with your team members</li>
                                <li>Consider how to implement the learnings</li>
                                <li>Celebrate this achievement with your team!</li>
                            </ul>
                        </div>
                        
                        <!-- Thank You -->
                        <div style="text-align: center;">
                            <p style="color: #34495e; margin: 0; font-size: 15px; line-height: 1.6;">
                                Thank you for participating in the iN-Clue Journey program.<br>
                                Your commitment to inclusion makes a difference.
                            </p>
                        </div>
                        
                    </div>
                    
                    <!-- Footer -->
                    <div style="background-color: #2c3e50; padding: 25px 30px; text-align: center;">
                        <p style="color: white; margin: 0; font-size: 14px; font-weight: 600;">
                            The iN-Clue Team
                        </p>
                        <p style="color: #8BC34A; margin: 10px 0 0 0; font-size: 12px;">
                            Empowering inclusion, one journey at a time
                        </p>
                    </div>
                    
                </div>
                
            </body>
            </html>
            """
            
            # Send email with attachment
            mail_values = {
                'subject': f'🎉 iN-Clue Journey Complete - {journey.cohort}',
                'body_html': template_body,
                'email_to': journey.team_leader_email,
                'email_from': self.env.company.email or 'noreply@inclue.com',
                'attachment_ids': [(0, 0, {
                    'name': f'iN-Clue_Completion_Report_{journey.cohort}.pdf',
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

    # ============================================================================
    # COMPANY LOGO TO PDF
    # ============================================================================

    def _add_logo_to_pdf(self, story):
        """Add company logo to PDF if available"""
        try:
            logo_path = 'https://diversito.be/wp-content/uploads/2024/04/LOGO_INCLUE_puzzel_RGB.jpg.webp'  # Update this path
            
            if os.path.exists(logo_path):
                logo = Image(logo_path, width=3*inch, height=1*inch)
                logo.hAlign = 'CENTER'
                story.insert(0, logo)
                story.insert(1, Spacer(1, 20))
                
        except Exception as e:
            _logger.warning("Could not add logo to PDF: %s", str(e))
        
        return story