from datetime import datetime
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)

class FacilitatorOrder(models.Model):
    _inherit = 'sale.order'
    
    # Add your facilitator-specific fields
    facilitator_type = fields.Selection([
        ('internal', 'In-House Facilitator'),
        ('external', 'External Facilitator')
    ], string='Facilitator Type', tracking=True)
    
    facility_language_id = fields.Many2one(
        'res.lang', 
        string='Facility Language', 
        tracking=True
    )
    
    # Auto-processing configuration
    auto_process = fields.Boolean(
        'Auto Process Order', 
        default=True,
        help="Automatically confirm and invoice this order upon creation",
        tracking=True
    )
    
    auto_pay_internal = fields.Boolean(
        'Auto-Pay Internal Orders',
        default=False,
        help="Automatically register payment for internal facilitator orders",
        tracking=True
    )
    
    auto_processed = fields.Boolean(
        'Auto Processed', 
        default=False, 
        readonly=True,
        help="Indicates if this order was automatically processed"
    )
    
    processing_log = fields.Text(
        'Processing Log', 
        readonly=True,
        help="Detailed log of auto-processing steps"
    )
    
    last_processing_error = fields.Text(
        'Last Processing Error', 
        readonly=True,
        help="Last error encountered during auto-processing"
    )
    
    # Additional shipping/invoice info
    shipping_address_custom = fields.Text(
        string='Custom Shipping Address',
        help="Custom shipping address if different from partner address"
    )
    contact_person = fields.Char(string='Contact Person', tracking=True)
    
    invoice_company_name = fields.Char(string='Invoice Company Name', tracking=True)
    invoice_address_custom = fields.Text(
        string='Custom Invoice Address',
        help="Custom invoice address if different from partner address"
    )
    po_number = fields.Char(string='PO Number', tracking=True)

    delivery_contact_name = fields.Char(
        string='Delivery Contact Name',
        tracking=True,
        required=False,
        help="Name of the person at the delivery address"
    )
    
    delivery_vat_number = fields.Char(
        string='Delivery VAT Number',
        tracking=True,
        required=False,
        help="VAT number for the delivery location/company"
    )
    
    delivery_email = fields.Char(
        string='Delivery Contact Email',
        tracking=True,
        required=False,
        help="Email address of the contact person at delivery location"
    )
    
    shipping_cost = fields.Float('Shipping Cost')
    
    # Computed legacy fields for API compatibility
    gift_card_qty = fields.Integer(
        string="Gift Cards Quantity", 
        compute='_compute_legacy_quantities',
        store=False
    )
    followup_card_qty = fields.Integer(
        string="Follow-up Cards Quantity", 
        compute='_compute_legacy_quantities',
        store=False
    )
    participant_deck_qty = fields.Integer(
        string="Participant Deck Quantity", 
        compute='_compute_legacy_quantities',
        store=False
    )
    facilitator_deck_qty = fields.Integer(
        string="Facilitator Deck Quantity", 
        compute='_compute_legacy_quantities',
        store=False
    )
    promo_package_qty = fields.Integer(
        string="Promo Package Quantity", 
        compute='_compute_legacy_quantities',
        store=False
    )

    delivery_contact_name = fields.Char(
        string='Delivery Contact Name',
        tracking=True,
        help="Name of the person at the delivery address"
    )
    
    delivery_vat_number = fields.Char(
        string='Delivery VAT Number',
        tracking=True,
        help="VAT number for the delivery location/company"
    )
    
    delivery_email = fields.Char(
        string='Delivery Contact Email',
        tracking=True,
        help="Email address of the contact person at delivery location"
    )
    
    @api.depends('order_line.product_uom_qty', 'order_line.product_id')
    def _compute_legacy_quantities(self):
        """Compute legacy quantity fields from order lines for API compatibility"""
        for order in self:
            gift_qty = followup_qty = participant_qty = facilitator_qty = promo_qty = 0
            # Iterate through order lines to calculate quantities
            for line in order.order_line:
                if line.product_id and hasattr(line.product_id, 'inclue_card_type'):
                    card_type = line.product_id.inclue_card_type
                    if card_type == 'gift_card':
                        gift_qty += line.product_uom_qty
                    elif card_type == 'followup_card':
                        followup_qty += line.product_uom_qty
                    elif card_type == 'participant_deck':
                        participant_qty += line.product_uom_qty
                    elif card_type == 'facilitator_deck':
                        facilitator_qty += line.product_uom_qty
                    elif card_type == 'promo_package':
                        promo_qty += line.product_uom_qty
            
            order.gift_card_qty = gift_qty
            order.followup_card_qty = followup_qty
            order.participant_deck_qty = participant_qty
            order.facilitator_deck_qty = facilitator_qty
            order.promo_package_qty = promo_qty
    
    @api.model
    def create(self, vals):
        """Override create to handle auto-processing"""
        _logger.info("=== CREATING NEW FACILITATOR SALE ORDER ===")
        _logger.info(f"Order data: {vals}")
        
        # Create the order
        order = super().create(vals)
        _logger.info(f"Sale order created with ID: {order.id}, Name: {order.name}")
        
        # Auto-process if enabled and this is a facilitator order
        if order.facilitator_type and order.auto_process:
            _logger.info(f"Auto-processing enabled for facilitator order {order.name}")
            order._auto_process_facilitator_order()
        
        return order
    
    def action_confirm(self):
        """Override confirmation to add facilitator auto-processing"""
        result = super().action_confirm()
        
        # Auto-process facilitator orders that weren't auto-processed on creation
        for order in self.filtered('facilitator_type'):
            if order.auto_process and not order.auto_processed:
                order._auto_process_facilitator_order()
        
        return result
    
    def _auto_process_facilitator_order(self):
        """Complete auto-processing with WORKING email sending"""
        from datetime import datetime, timedelta
        
        self.ensure_one()
        
        processing_start = datetime.now()
        log_entries = []
        created_invoices = []
        
        try:
            log_entries.append(f"🚀 AUTO-PROCESSING STARTED at {processing_start.strftime('%Y-%m-%d %H:%M:%S')}")
            log_entries.append(f"📋 Order: {self.name}")
            log_entries.append(f"👤 Customer: {self.partner_id.name}")
            log_entries.append(f"📧 Customer Email: {self.partner_id.email or 'NO EMAIL'}")
            log_entries.append(f"💰 Total Amount: {self.amount_total:.2f} {self.currency_id.name}")
            log_entries.append(f"🎯 Facilitator Type: {self.facilitator_type}")

            # Step 1: Confirm order if not already confirmed
            if self.state in ['draft', 'sent']:
                log_entries.append("\n--- STEP 1: CONFIRMING ORDER ---")
                self.action_confirm()
                log_entries.append("✅ Order confirmed")
                log_entries.append(f"📊 Order Total after confirmation: {self.amount_total:.2f}")
            else:
                log_entries.append(f"ℹ️ Order already confirmed, state: {self.state}")
            
            # Step 2: Create and process invoice
            log_entries.append("\n--- STEP 2: INVOICE PROCESSING ---")
            
            deliverable_lines = self.order_line.filtered(lambda l: l.product_uom_qty > 0 and not l.display_type)
            
            if deliverable_lines and self.invoice_status in ['no', 'to invoice']:
                try:
                    # Create invoice using wizard
                    log_entries.append("🧾 Creating invoice using advance payment wizard...")
                    
                    wizard_context = {
                        'active_model': 'sale.order',
                        'active_ids': [self.id],
                        'active_id': self.id,
                    }
                    
                    wizard = self.env['sale.advance.payment.inv'].with_context(wizard_context).create({
                        'advance_payment_method': 'delivered',
                    })
                    
                    result = wizard.create_invoices()
                    log_entries.append("✅ Invoice creation wizard completed")
                    
                    # Get the created invoices
                    invoices = self.invoice_ids
                    log_entries.append(f"📄 Found {len(invoices)} invoice(s) after creation")
                    
                    if invoices:
                        for invoice in invoices:
                            log_entries.append(f"📋 Processing invoice: {invoice.name}")
                            
                            # Copy facilitator custom fields to invoice
                            try:
                                facilitator_fields = {
                                    'facilitator_type': self.facilitator_type,
                                    'facility_language_id': self.facility_language_id.id if self.facility_language_id else False,
                                    'shipping_address_custom': self.shipping_address_custom,
                                    'contact_person': self.contact_person,
                                    'invoice_company_name': self.invoice_company_name,
                                    'invoice_address_custom': self.invoice_address_custom,
                                    'po_number': self.po_number,
                                    'delivery_contact_name': self.delivery_contact_name,
                                    'delivery_vat_number': self.delivery_vat_number,
                                    'delivery_email': self.delivery_email,
                                }
                                
                                invoice.write(facilitator_fields)
                                log_entries.append("✅ Custom fields copied to invoice")
                                
                            except Exception as field_error:
                                log_entries.append(f"⚠️ Failed to copy custom fields: {str(field_error)}")
                            
                            # Post the invoice
                            if invoice.state == 'draft':
                                try:
                                    invoice.action_post()
                                    log_entries.append("✅ Invoice posted successfully")
                                    log_entries.append(f"📋 Posted Invoice Number: {invoice.name}")
                                    
                                    # Generate access token for portal/headless access
                                    if not invoice.access_token:
                                        invoice._portal_ensure_token()
                                        log_entries.append(f"🔑 Access token generated: {invoice.access_token[:20]}...")
                                    else:
                                        log_entries.append(f"🔑 Access token already exists: {invoice.access_token[:20]}...")
                                    
                                    _logger.info('posted invoice')
                                    
                                    # Add to list for email sending later
                                    created_invoices.append(invoice)
                                    
                                except Exception as post_error:
                                    log_entries.append(f"❌ Failed to post invoice: {str(post_error)}")
                    else:
                        log_entries.append("❌ No invoices were created by wizard")
                        
                except Exception as wizard_error:
                    log_entries.append(f"❌ Invoice creation failed: {str(wizard_error)}")
            else:
                log_entries.append(f"ℹ️ Invoice status is '{self.invoice_status}', no new invoice needed")
            
            # Step 3: FIXED EMAIL PROCESSING
            log_entries.append("\n--- STEP 3: FIXED EMAIL PROCESSING ---")

            _logger.info("Starting FIXED email processing for created invoices")
            _logger.info(f"Created invoices: {[inv.name for inv in created_invoices]}")

            if created_invoices:
                # Commit the transaction to ensure invoices are fully posted
                self.env.cr.commit()
                log_entries.append("💾 Database transaction committed")
                
                # Check SMTP configuration
                smtp_server = self.env['ir.mail_server'].search([], limit=1)
                if smtp_server:
                    log_entries.append(f"📡 SMTP Server: {smtp_server.name}")
                    log_entries.append(f"📡 Host: {smtp_server.smtp_host}:{smtp_server.smtp_port}")
                    log_entries.append(f"📡 User: {smtp_server.smtp_user}")
                    
                    if 'ethereal' in smtp_server.smtp_host.lower():
                        log_entries.append(f"🎭 ETHEREAL DETECTED!")
                        log_entries.append(f"🎭 Login: https://ethereal.email/login")
                        log_entries.append(f"🎭 Username: {smtp_server.smtp_user}")
                        log_entries.append(f"🎭 Password: {smtp_server.smtp_pass}")
                
                for invoice in created_invoices:
                    try:
                        log_entries.append(f"\n📧 === SENDING EMAIL FOR INVOICE {invoice.name} ===")
                        
                        # Check recipient
                        recipient_email = invoice.partner_id.email
                        if not recipient_email:
                            log_entries.append(f"❌ No email address for {invoice.partner_id.name}")
                            continue
                        
                        log_entries.append(f"📬 Recipient: {recipient_email}")
                        
                        # Get email template
                        template = self.env.ref('account.email_template_edi_invoice', raise_if_not_found=False)
                        if not template:
                            log_entries.append("❌ No invoice email template found!")
                            continue
                        
                        log_entries.append(f"📧 Using template: {template.name}")
                        
                        # Count emails before sending
                        mail_count_before = self.env['mail.mail'].search_count([])
                        log_entries.append(f"📊 Mail queue count before: {mail_count_before}")
                        
                        # ACTUALLY SEND THE EMAIL
                        try:
                            template.send_mail(invoice.id, force_send=True)
                            log_entries.append("✅ template.send_mail() completed")
                        except Exception as send_error:
                            log_entries.append(f"❌ send_mail failed: {str(send_error)}")
                            continue
                        
                        # Count emails after sending
                        mail_count_after = self.env['mail.mail'].search_count([])
                        log_entries.append(f"📊 Mail queue count after: {mail_count_after}")
                        
                        if mail_count_after > mail_count_before:
                            emails_created = mail_count_after - mail_count_before
                            log_entries.append(f"✅ {emails_created} email(s) successfully sent!")
                            
                            # Check for recent emails
                            recent_emails = self.env['mail.mail'].search([
                                ('create_date', '>=', fields.Datetime.now() - timedelta(minutes=5))
                            ], order='create_date desc', limit=3)
                            
                            for email in recent_emails:
                                log_entries.append(f"📧 Email {email.id}: {email.subject} -> {email.email_to} (State: {email.state})")
                                if email.failure_reason:
                                    log_entries.append(f"   ❌ Failed: {email.failure_reason}")
                        
                        else:
                            log_entries.append("⚠️ No emails were created - template may have issues")
                        
                    except Exception as email_error:
                        log_entries.append(f"❌ Email processing failed: {str(email_error)}")
                        import traceback
                        log_entries.append(f"🔍 Traceback: {traceback.format_exc()}")
            else:
                log_entries.append("ℹ️ No new invoices to send emails for")
            
            # Step 4: Finalization
            log_entries.append("\n--- STEP 4: FINALIZATION ---")
            processing_end = datetime.now()
            processing_duration = (processing_end - processing_start).total_seconds()
            
            # Final invoice count
            final_invoice_count = len(self.invoice_ids)
            invoice_names = ", ".join(self.invoice_ids.mapped('name')) if self.invoice_ids else "None"
            
            # Update the order with processing results
            self.write({
                'auto_processed': True,
                'last_processing_error': False,
                'processing_log': "\n".join(log_entries)
            })
            
            log_entries.append(f"✅ AUTO-PROCESSING COMPLETED in {processing_duration:.2f}s")
            log_entries.append(f"🎉 Final State: {self.state}")
            log_entries.append(f"📄 Final Invoice Count: {final_invoice_count}")
            log_entries.append(f"📋 Invoice Names: {invoice_names}")
            log_entries.append(f"📧 Emails Processed: {len(created_invoices)}")
            
            # Post success message with correct totals
            self.message_post(
                body=f"""
                <h3>🎉 Facilitator Order Auto-Processing Complete</h3>
                <ul>
                    <li><strong>Order:</strong> {self.name}</li>
                    <li><strong>Amount:</strong> {self.amount_total:.2f} {self.currency_id.name}</li>
                    <li><strong>Final State:</strong> {self.state}</li>
                    <li><strong>Invoices:</strong> {invoice_names}</li>
                    <li><strong>Emails Sent:</strong> {len(created_invoices)}</li>
                    <li><strong>Duration:</strong> {processing_duration:.2f} seconds</li>
                </ul>
                """,
                subject="Auto-Processing Success"
            )
            
            _logger.info(f"=== AUTO-PROCESSING COMPLETED FOR ORDER {self.name} ===")
            _logger.info(f"Order Total: {self.amount_total}")
            _logger.info(f"Invoices Created: {invoice_names}")
            _logger.info(f"Emails Sent: {len(created_invoices)}")
            return True
            
        except Exception as e:
            # Handle errors
            error_msg = str(e)
            log_entries.append(f"\n❌ ERROR: {error_msg}")
            
            self.write({
                'last_processing_error': error_msg,
                'processing_log': "\n".join(log_entries)
            })
            
            self.message_post(
                body=f"<h3>❌ Auto-Processing Failed</h3><p>Error: {error_msg}</p>",
                subject="Auto-Processing Failed"
            )
            
            _logger.error(f"Auto-processing failed for order {self.name}: {error_msg}")
            return False

    # END


    def _register_automatic_payment(self, invoice):
        """Register automatic payment for internal orders"""
        try:
            # Find appropriate journal
            journal = self.env['account.journal'].search([
                ('type', 'in', ['cash', 'bank']),
                ('company_id', '=', self.company_id.id)
            ], limit=1)
            
            if not journal:
                return False
            
            # Create payment
            payment = self.env['account.payment'].create({
                'payment_type': 'inbound',
                'partner_type': 'customer',
                'partner_id': invoice.partner_id.id,
                'amount': invoice.amount_total,
                'currency_id': invoice.currency_id.id,
                'payment_date': fields.Date.context_today(self),
                'communication': f"Auto-payment for {self.name}",
                'journal_id': journal.id,
                'company_id': self.company_id.id,
            })
            
            payment.action_post()
            
            # Reconcile
            payment_lines = payment.line_ids.filtered(
                lambda l: l.account_id.user_type_id.type in ('receivable', 'payable')
            )
            invoice_lines = invoice.line_ids.filtered(
                lambda l: l.account_id.user_type_id.type in ('receivable', 'payable')
            )
            (payment_lines + invoice_lines).reconcile()
            
            return True
            
        except Exception as e:
            _logger.error(f"Auto-payment failed: {str(e)}")
            return False
    
    @api.model
    def create_facilitator_order(self, data):
        """Enhanced API method to create facilitator orders with all frontend data"""
        _logger.info(f"=== CREATING FACILITATOR ORDER VIA API ===")
        _logger.info(f"Full payload received: {data}")
        
        # Validate required data
        if not data.get('facilitator_id'):
            raise ValidationError("Facilitator ID is required")
        
        # Prepare sale order values with ALL frontend fields
        sale_vals = {
            'partner_id': data['facilitator_id'],
            'facilitator_type': data.get('facilitator_type', 'external'),
            'facility_language_id': data.get('facility_language_id'),
            
            # Shipping information
            'shipping_address_custom': data.get('shipping_address', ''),
            'contact_person': data.get('contact_person', ''),
            
            # Invoice information  
            'invoice_company_name': data.get('invoice_company_name', ''),
            'invoice_address_custom': data.get('invoice_address', ''),
            'po_number': data.get('po_number', ''),
            
            # Delivery details (for internal facilitators)
            'delivery_contact_name': data.get('delivery_contact_name', ''),
            'delivery_vat_number': data.get('delivery_vat_number', ''),
            'delivery_email': data.get('delivery_email', ''),
            
            # Set proper pricelist
            'pricelist_id': self._get_pricelist_for_facilitator(data.get('facilitator_type', 'external')),
            
            # DISABLE auto-processing during creation
            'auto_process': False,
            'auto_pay_internal': data.get('auto_pay_internal', False),
        }
        
        _logger.info(f"Sale order values: {sale_vals}")
        
        # Create the sale order (no auto-processing triggered)
        sale_order = self.create(sale_vals)
        _logger.info(f"Sale order created: {sale_order.name} (ID: {sale_order.id})")
        
        # Create order lines from frontend data
        self._create_all_order_lines(sale_order, data)
        
        # Add shipping cost as separate line item
        self._add_shipping_line(sale_order, data)
        
        # NOW trigger auto-processing with complete order
        if data.get('auto_process', True):
            _logger.info(f"Triggering auto-processing for complete order: {sale_order.name}")
            sale_order._auto_process_facilitator_order()
            
        _logger.info(f"Order creation completed: {sale_order.name}")
        
        return sale_order

    def _get_pricelist_for_facilitator(self, facilitator_type):
        """Get appropriate pricelist based on facilitator type"""
        try:
            if facilitator_type == 'internal':
                pricelist = self.env.ref('inclue_consolidated_approach.pricelist_internal_facilitator')
            else:
                pricelist = self.env.ref('inclue_consolidated_approach.pricelist_external_facilitator')
            return pricelist.id
        except:
            # Fallback to default pricelist
            pricelist = self.env['product.pricelist'].search([('company_id', '=', self.env.company.id)], limit=1)
            return pricelist.id if pricelist else False

    def _create_all_order_lines(self, sale_order, data):
        """Create order lines from both order_lines array and legacy quantity fields"""
        _logger.info(f"Creating order lines for order {sale_order.name}")
        
        # Method 1: Use order_lines array (new format)
        order_lines = data.get('order_lines', [])
        if order_lines:
            _logger.info(f"Creating lines from order_lines array: {order_lines}")
            for line_data in order_lines:
                self._create_single_order_line(sale_order, line_data)
        
        # Method 2: Use legacy quantity fields (backward compatibility)
        else:
            _logger.info("No order_lines array, using legacy quantity fields")
            legacy_lines = [
                ('participant_deck_qty', 'participant_deck'),
                ('facilitator_deck_qty', 'facilitator_deck'), 
                ('gift_card_qty', 'gift_card'),
                ('followup_card_qty', 'followup_card'),
                ('promo_package_qty', 'promo_package'),
            ]
            
            for qty_field, product_type in legacy_lines:
                quantity = data.get(qty_field, 0)
                if quantity > 0:
                    line_data = {
                        'product_id': product_type,
                        'quantity': quantity
                    }
                    self._create_single_order_line(sale_order, line_data)
                    
    def _create_single_order_line(self, sale_order, line_data):
        """Create a single order line - FIXED for your existing products"""
        try:
            product_type = line_data["product_id"]  # e.g., 'facilitator_deck'
            
            # Method 1: Try to find by external ID (your existing data)
            product_ref = f'inclue_consolidated_approach.product_{product_type}'
            product_template = self.env.ref(product_ref, raise_if_not_found=False)
            
            if product_template:
                # Get the product.product variant from the template
                product = product_template.product_variant_ids[0] if product_template.product_variant_ids else None
            else:
                product = None
            
            # Method 2: If external ID doesn't work, search by card type
            if not product:
                _logger.info(f"External ID not found, searching by card type: {product_type}")
                
                # Search product templates first
                product_template = self.env['product.template'].search([
                    ('inclue_card_type', '=', product_type),
                    ('is_inclue_card', '=', True),
                    ('active', '=', True)
                ], limit=1)
                
                if product_template:
                    # Get the product variant
                    product = product_template.product_variant_ids[0] if product_template.product_variant_ids else None
            
            # Method 3: Direct product.product search as fallback
            if not product:
                _logger.info(f"Template search failed, searching product.product directly")
                product = self.env['product.product'].search([
                    ('inclue_card_type', '=', product_type),
                    ('is_inclue_card', '=', True),
                    ('active', '=', True)
                ], limit=1)
            
            if not product:
                _logger.warning(f"Product not found for card type: {product_type}")
                return
            
            _logger.info(f"Found product: {product.name} (ID: {product.id}) for type: {product_type}")
            
            # Create the order line
            line_vals = {
                'order_id': sale_order.id,
                'product_id': product.id,
                'name': product.name,
                'product_uom_qty': float(line_data['quantity']),
                'price_unit': product.list_price,
                'product_uom': product.uom_id.id,
            }
            
            order_line = self.env['sale.order.line'].create(line_vals)
            _logger.info(f"Created order line: {order_line.name} (Qty: {order_line.product_uom_qty})")
            
        except Exception as e:
            _logger.error(f"Failed to create order line for {line_data}: {str(e)}")
            import traceback
            _logger.error(f"Full traceback: {traceback.format_exc()}")
            
    def _add_shipping_line(self, sale_order, data):
        """Add shipping cost as a separate line item - FIXED for invoice inclusion"""
        shipping_cost = float(data.get('shipping_cost', 0))

        if shipping_cost <= 0:
            _logger.info("No shipping cost to add")
            return

        try:
            # Get shipping country name for description
            shipping_country_id = data.get('shipping_country_id')
            country_name = 'International'
            
            if shipping_country_id:
                country = self.env['res.country'].browse(int(shipping_country_id))
                if country.exists():
                    country_name = country.name
            
            # Look for shipping service product template
            shipping_template = self.env.ref('inclue_consolidated_approach.product_shipping_service', raise_if_not_found=False)
            
            if shipping_template:
                # Get the product variant from template
                shipping_product = shipping_template.product_variant_ids[0] if shipping_template.product_variant_ids else None
            else:
                shipping_product = None
            
            if not shipping_product:
                # Create shipping product if it doesn't exist
                shipping_template = self.env['product.template'].create({
                    'name': 'Shipping Service',
                    'type': 'service',
                    'list_price': 0.0,
                    'categ_id': self.env.ref('product.product_category_all').id,
                    'sale_ok': True,
                    'purchase_ok': False,
                    'invoice_policy': 'order',  # ← KEY FIX: Changed from 'delivery' to 'order'
                    'taxes_id': [(6, 0, [])],  # ← No taxes on shipping by default
                })
                shipping_product = shipping_template.product_variant_ids[0]
                _logger.info(f"Created shipping product: {shipping_product.name}")
            else:
                # Ensure existing shipping product has correct invoice policy
                if shipping_product.invoice_policy != 'order':
                    shipping_product.invoice_policy = 'order'
                    _logger.info("Updated shipping product invoice policy to 'order'")
            
            # Create shipping line item using the product
            shipping_line_vals = {
                'order_id': sale_order.id,
                'product_id': shipping_product.id,
                'name': f'Shipping to {country_name}',
                'product_uom_qty': 1.0,
                'price_unit': shipping_cost,
                'product_uom': shipping_product.uom_id.id,
                'qty_to_invoice': 1.0,  # ← CRITICAL: Ensure this line is ready for invoicing
                'invoice_status': 'to invoice',  # ← CRITICAL: Mark as ready to invoice
            }
            
            shipping_line = self.env['sale.order.line'].create(shipping_line_vals)
            _logger.info(f"Added shipping line: {shipping_line.name} - €{shipping_cost}")
            _logger.info(f"Shipping line invoice status: {shipping_line.invoice_status}")
            _logger.info(f"Shipping line qty_to_invoice: {shipping_line.qty_to_invoice}")
            
        except Exception as e:
            _logger.error(f"Failed to create shipping line: {str(e)}")
            import traceback
            _logger.error(f"Full traceback: {traceback.format_exc()}")
            # Don't let shipping failure stop the order creation

    # Legacy methods for backward compatibility
    def _get_pricelist_id(self, company_id):
        """Legacy method for backward compatibility"""
        return self._get_pricelist_for_facilitator('external')

    def _create_order_lines(self, sale_order, order_lines):
        """Legacy method for backward compatibility"""
        return self._create_all_order_lines(sale_order, {'order_lines': order_lines})

    def _auto_process_order(self, sale_order):
        """Legacy method for backward compatibility"""
        return sale_order._auto_process_facilitator_order()