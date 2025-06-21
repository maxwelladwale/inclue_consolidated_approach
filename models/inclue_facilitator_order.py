from datetime import datetime
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)

class FacilitatorOrder(models.Model):
    _name = "inclue.facilitator.order"
    _description = "Facilitator Order"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = "create_date desc"
    
    name = fields.Char("Order Reference", required=True, copy=False, readonly=True, 
                       default=lambda self: 'New')
    
    # Facilitator information
    facilitator_id = fields.Many2one(
        'res.partner', 
        string='Facilitator',
        required=True,
        tracking=True
    )
    facility_language_id = fields.Many2one(
        'res.lang', 
        string='Facility Language', 
        required=True,
        tracking=True
    )
    facilitator_type = fields.Selection([
        ('internal', 'In-House Facilitator'),
        ('external', 'External Facilitator')
    ], string='Facilitator Type', required=True, tracking=True)
    
    company_id = fields.Many2one(
        'res.company', 
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        tracking=True
    )

     # Invoice Auto-processing fields
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
    
    # Replace individual quantity fields with order lines
    order_line_ids = fields.One2many(
        'inclue.facilitator.order.line', 
        'order_id', 
        string='Order Lines'
    )
    
    # Keep legacy fields for backward compatibility (computed from order lines)
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
    
    # Shipping information
    shipping_address = fields.Text(string='Shipping Address', tracking=True)
    shipping_country_id = fields.Many2one('res.country', string='Shipping Country', tracking=True)
    contact_person = fields.Char(string='Contact Person', tracking=True)
    
    # Invoice information
    invoice_company_name = fields.Char(string='Invoice Company Name', tracking=True)
    invoice_address = fields.Text(string='Invoice Address', tracking=True)
    invoice_country_id = fields.Many2one('res.country', string='Invoice Country', tracking=True)
    po_number = fields.Char(string='PO Number', tracking=True)

    is_latest = fields.Boolean(string='Is Latest Order', default=True, tracking=True)
    
    # Calculated fields
    total_price = fields.Monetary(
        string='Total Price',
        compute='_compute_total_price',
        store=True,
        currency_field='currency_id'
    )
    
    currency_id = fields.Many2one(
        'res.currency', 
        string='Currency',
        default=lambda self: self.env.company.currency_id,
        required=True
    )
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('invoiced', 'Invoiced'),
        ('shipped', 'Shipped'),
        ('done', 'Done'),
        ('cancel', 'Cancelled')
    ], string='Status', default='draft', tracking=True)
    
    # Companion fields
    has_been_processed = fields.Boolean(string='Processed', default=False, tracking=True)
    invoice_id = fields.Many2one('account.move', string='Invoice', tracking=True)
    
    @api.model
    def create(self, vals):
        """Override create to handle auto-processing"""
        _logger.info("=== CREATING NEW FACILITATOR ORDER ===")
        _logger.info(f"Order data: {vals}")
        
        # Generate sequence
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('inclue.facilitator.order') or 'New'
            _logger.info(f"Generated order number: {vals['name']}")
        
        # Create the order
        order = super(FacilitatorOrder, self).create(vals)
        _logger.info(f"Order created with ID: {order.id}, Name: {order.name}")
        _logger.info(f"Order lines count: {len(order.order_line_ids)}")
        for line in order.order_line_ids:
            _logger.info(f"Order line: {line.product_id.name} x {line.quantity}")
        
        # Check if this is being created from API (skip auto-processing if so)
        skip_auto_processing = self.env.context.get('skip_auto_processing', False)
        
        # Auto-process if enabled and not skipped
        if order.auto_process and not skip_auto_processing:
            _logger.info(f"Auto-processing enabled for order {order.name}")
            order._auto_process_order()
        else:
            if skip_auto_processing:
                _logger.info(f"Auto-processing skipped for API creation: {order.name}")
            else:
                _logger.info(f"Auto-processing disabled for order {order.name}")
            order._log_processing_step("Auto-processing disabled - order created in draft state")
        
        return order
    
    @api.depends('order_line_ids.quantity', 'order_line_ids.product_id')
    def _compute_legacy_quantities(self):
        """Compute legacy quantity fields from order lines for backward compatibility"""
        for order in self:
            # Initialize all quantities to 0
            gift_qty = followup_qty = participant_qty = facilitator_qty = 0
            
            for line in order.order_line_ids:
                if line.product_id.inclue_card_type == 'gift_card':
                    gift_qty += line.quantity
                elif line.product_id.inclue_card_type == 'followup_card':
                    followup_qty += line.quantity
                elif line.product_id.inclue_card_type == 'participant_deck':
                    participant_qty += line.quantity
                elif line.product_id.inclue_card_type == 'facilitator_deck':
                    facilitator_qty += line.quantity
            
            order.gift_card_qty = gift_qty
            order.followup_card_qty = followup_qty
            order.participant_deck_qty = participant_qty
            order.facilitator_deck_qty = facilitator_qty
    
    @api.depends('order_line_ids.subtotal')
    def _compute_total_price(self):
        for order in self:
            order.total_price = sum(order.order_line_ids.mapped('subtotal'))
    
    def _get_facilitator_pricelist(self):
        """Get the appropriate pricelist for this facilitator type"""
        if self.facilitator_type == 'internal':
            _logger.debug("Using internal facilitator pricelist for order %s", self.name)
            return self.env.ref('inclue_journey_v2.pricelist_internal_facilitator', raise_if_not_found=False)
        else:
            _logger.debug("Using external facilitator pricelist for order %s", self.name)
            return self.env.ref('inclue_journey_v2.pricelist_external_facilitator', raise_if_not_found=False)

    def _get_payment_journal(self):
        """Get the default payment journal"""
        # Try to find cash journal first, then bank
        journal = self.env['account.journal'].search([
            ('type', 'in', ['cash', 'bank']),
            ('company_id', '=', self.company_id.id)
        ], limit=1)
        
        if not journal:
            raise UserError(_("No cash or bank journal found for automatic payment registration."))
        
        return journal

    def _auto_process_order(self):
        """Complete automated processing with detailed logging"""
        self.ensure_one()
        
        processing_start = datetime.now()
        log_entries = []
        
        try:
            log_entries.append(f"🚀 AUTO-PROCESSING STARTED at {processing_start.strftime('%Y-%m-%d %H:%M:%S')}")
            log_entries.append(f"📋 Order: {self.name}")
            log_entries.append(f"👤 Facilitator: {self.facilitator_id.name}")
            log_entries.append(f"🏢 Company: {self.company_id.name}")
            log_entries.append(f"💰 Total Amount: {self.total_price:.2f} {self.currency_id.name}")
            log_entries.append(f"🎯 Facilitator Type: {self.facilitator_type}")
            
            # Step 1: Confirm Order
            log_entries.append("\n--- STEP 1: CONFIRMING ORDER ---")
            if self.state == 'draft':
                self.action_confirm()
                log_entries.append("✅ Order confirmed successfully")
                log_entries.append(f"📧 Confirmation email sent to procurement team")
                _logger.info(f"Order {self.name} confirmed successfully")
            else:
                log_entries.append(f"⚠️ Order already in state: {self.state}")
            
            # Step 2: Handle Invoice Creation
            log_entries.append("\n--- STEP 2: INVOICE PROCESSING ---")
            
            # Check if there are any order lines to invoice
            invoiceable_lines = self.order_line_ids.filtered(lambda l: l.quantity > 0)
            
            if invoiceable_lines:
                log_entries.append(f"💵 Order with items detected (Total: {self.total_price:.2f} {self.currency_id.name})")
                log_entries.append("🧾 Creating invoice...")
                
                # Create invoice
                self.action_invoice()
                
                if self.invoice_id:
                    log_entries.append(f"✅ Invoice created: {self.invoice_id.name}")
                    log_entries.append(f"📄 Invoice ID: {self.invoice_id.id}")
                    log_entries.append(f"💰 Invoice Amount: {self.invoice_id.amount_total:.2f} {self.invoice_id.currency_id.name}")
                    
                    # Auto-post invoice
                    if self.invoice_id.state == 'draft':
                        log_entries.append("📮 Posting invoice...")
                        self.invoice_id.action_post()
                        log_entries.append("✅ Invoice posted successfully")
                        _logger.info(f"Invoice {self.invoice_id.name} posted for order {self.name}")
                    
                    # Auto-send invoice email
                    log_entries.append("📧 Sending invoice email to customer...")
                    try:
                        self.invoice_id.action_invoice_sent()
                        log_entries.append("✅ Invoice email sent successfully")
                        log_entries.append(f"📬 Sent to: {self.invoice_id.partner_id.email}")
                        _logger.info(f"Invoice email sent for order {self.name}")
                    except Exception as email_error:
                        log_entries.append(f"❌ Failed to send invoice email: {str(email_error)}")
                        _logger.warning(f"Failed to send invoice email for order {self.name}: {str(email_error)}")
                    
                    # Optional: Auto-register payment for internal orders
                    if self.facilitator_type == 'internal' and hasattr(self, 'auto_pay_internal') and self.auto_pay_internal:
                        log_entries.append("💳 Auto-registering payment (internal order)...")
                        if self._register_automatic_payment():
                            log_entries.append("✅ Payment registered automatically")
                        else:
                            log_entries.append("❌ Auto-payment failed")
                    
                    # STOP HERE - All orders with items stop at invoiced for payment
                    log_entries.append("🛑 Stopping at invoiced state - awaiting payment confirmation")
                    
                else:
                    log_entries.append("❌ Failed to create invoice")
                    raise ValidationError("Invoice creation failed")
                    
            else:
                log_entries.append("🆓 No items to invoice - empty order")
                log_entries.append("📦 Moving directly to shipped state...")
                self.write({'state': 'shipped'})
                log_entries.append("✅ Order marked as shipped")
                _logger.info(f"Empty order {self.name} moved to shipped state")
            
            # Step 3: Finalization
            log_entries.append("\n--- STEP 3: FINALIZATION ---")
            processing_end = datetime.now()
            processing_duration = (processing_end - processing_start).total_seconds()
            
            self.write({
                'auto_processed': True,
                'last_processing_error': False,  # Clear any previous errors
            })
            
            log_entries.append(f"✅ AUTO-PROCESSING COMPLETED at {processing_end.strftime('%Y-%m-%d %H:%M:%S')}")
            log_entries.append(f"⏱️ Processing Duration: {processing_duration:.2f} seconds")
            log_entries.append(f"🎉 Final State: {self.state}")
            
            # Update processing log
            self.processing_log = "\n".join(log_entries)
            
            # Post success message to chatter
            self.message_post(
                body=f"""
                <h3>🎉 Order Auto-Processing Complete</h3>
                <ul>
                    <li><strong>Order:</strong> {self.name}</li>
                    <li><strong>Amount:</strong> {self.total_price:.2f} {self.currency_id.name}</li>
                    <li><strong>Final State:</strong> {self.state}</li>
                    <li><strong>Duration:</strong> {processing_duration:.2f} seconds</li>
                    {f'<li><strong>Invoice:</strong> {self.invoice_id.name}</li>' if self.invoice_id else ''}
                </ul>
                """,
                subject="Auto-Processing Success",
                message_type='notification'
            )
            
            _logger.info(f"=== AUTO-PROCESSING COMPLETED FOR ORDER {self.name} IN {processing_duration:.2f}s ===")
            return True
            
        except Exception as e:
            # Handle errors with detailed logging
            processing_end = datetime.now()
            processing_duration = (processing_end - processing_start).total_seconds()
            
            error_msg = str(e)
            log_entries.append(f"\n❌ ERROR OCCURRED: {error_msg}")
            log_entries.append(f"⏱️ Failed after: {processing_duration:.2f} seconds")
            log_entries.append(f"🔧 Troubleshooting: Check order configuration and try manual processing")
            
            self.write({
                'last_processing_error': error_msg,
                'processing_log': "\n".join(log_entries)
            })
            
            # Post error message to chatter
            self.message_post(
                body=f"""
                <h3>❌ Auto-Processing Failed</h3>
                <ul>
                    <li><strong>Order:</strong> {self.name}</li>
                    <li><strong>Error:</strong> {error_msg}</li>
                    <li><strong>Duration:</strong> {processing_duration:.2f} seconds</li>
                </ul>
                <p><em>Manual processing may be required.</em></p>
                """,
                subject="Auto-Processing Failed",
                message_type='notification'
            )
            
            _logger.error(f"Auto-processing failed for order {self.name}: {error_msg}")
            _logger.error(f"Full processing log: {self.processing_log}")
            
            return False
    
    def _register_automatic_payment(self):
        """Register automatic payment for the invoice"""
        self.ensure_one()
        
        if not self.invoice_id or self.invoice_id.payment_state == 'paid':
            return False
            
        try:
            # Create payment record
            payment_vals = {
                'payment_type': 'inbound',
                'partner_type': 'customer',
                'partner_id': self.invoice_id.partner_id.id,
                'amount': self.invoice_id.amount_total,
                'currency_id': self.invoice_id.currency_id.id,
                'payment_date': fields.Date.context_today(self),
                'communication': f"Auto-payment for {self.name}",
                'journal_id': self._get_payment_journal().id,
                'company_id': self.company_id.id,
            }
            
            payment = self.env['account.payment'].create(payment_vals)
            payment.action_post()
            
            # Reconcile with invoice
            payment_lines = payment.line_ids.filtered(lambda l: l.account_id.user_type_id.type in ('receivable', 'payable'))
            invoice_lines = self.invoice_id.line_ids.filtered(lambda l: l.account_id.user_type_id.type in ('receivable', 'payable'))
            
            (payment_lines + invoice_lines).reconcile()
            
            self._log_processing_step(f"💳 Payment registered: {payment.name}")
            return True
            
        except Exception as e:
            self._log_processing_step(f"❌ Payment registration failed: {str(e)}")
            _logger.error(f"Failed to register automatic payment for order {self.name}: {str(e)}")
            return False
    
    def _log_processing_step(self, message):
        """Helper method to add single log entry"""
        current_log = self.processing_log or ""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        new_entry = f"[{timestamp}] {message}"
        
        if current_log:
            self.processing_log = f"{current_log}\n{new_entry}"
        else:
            self.processing_log = new_entry
    
    def action_retry_auto_processing(self):
        """Manual action to retry auto-processing"""
        self.ensure_one()
        
        if self.auto_processed:
            raise UserError(_("This order has already been auto-processed successfully."))
        
        if self.state not in ['draft', 'confirmed']:
            raise UserError(_("Auto-processing can only be retried for draft or confirmed orders."))
        
        _logger.info(f"Manually retrying auto-processing for order {self.name}")
        self._log_processing_step("🔄 Manual retry triggered by user")
        
        success = self._auto_process_order()
        
        if success:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Success!',
                    'message': f'Order {self.name} processed successfully',
                    'type': 'success',
                }
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Processing Failed',
                    'message': f'Auto-processing failed. Check the processing log for details.',
                    'type': 'danger',
                }
            }
    
    def action_trigger_auto_processing(self):
        """Trigger auto-processing for API-created orders"""
        self.ensure_one()
        
        _logger.info(f"API triggering auto-processing for order {self.name}")
        self._log_processing_step("🔄 Auto-processing triggered after order lines creation")
        
        if self.auto_process:
            return self._auto_process_order()
        else:
            _logger.info(f"Auto-processing disabled for order {self.name}")
            return False
    
    def action_view_processing_log(self):
        """Action to view detailed processing log"""
        self.ensure_one()
        
        return {
            'type': 'ir.actions.act_window',
            'name': f'Processing Log - {self.name}',
            'res_model': 'inclue.facilitator.order',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_processing_log': self.processing_log}
        }

    def action_confirm(self):
        """Enhanced confirmation with logging"""
        for order in self:
            _logger.info(f"Confirming order {order.name}")
            order._log_processing_step(f"📋 Order confirmation started")
            order.write({'state': 'confirmed'})
            order._log_processing_step(f"✅ Order confirmed - State: {order.state}")
            _logger.info(f"Order {order.name} confirmed successfully")
        return True
    
    def action_invoice(self):
        """Enhanced invoicing with logging"""
        for order in self:
            _logger.info(f"Creating invoice for order {order.name}")
            order._log_processing_step(f"🧾 Invoice creation started")
            
            # Check if order has invoiceable lines
            if not order.order_line_ids.filtered(lambda l: l.unit_price > 0):
                order._log_processing_step(f"⚠️ No invoiceable lines found")
                continue
            
            # Prepare invoice values
            invoice_vals = order._prepare_invoice_values()
            invoice_vals['invoice_line_ids'] = order._prepare_invoice_lines()
            
            # Create the invoice
            invoice = self.env['account.move'].create(invoice_vals)
            
            order.write({
                'invoice_id': invoice.id,
                'state': 'invoiced'
            })
            
            if order.invoice_id:
                order._log_processing_step(f"✅ Invoice created: {order.invoice_id.name}")
                _logger.info(f"Invoice {order.invoice_id.name} created for order {order.name}")
            else:
                order._log_processing_step(f"❌ Invoice creation failed")
                _logger.warning(f"Invoice creation failed for order {order.name}")
                
        return True

    def _prepare_invoice_values(self):
        """Prepare the invoice values"""
        self.ensure_one()

        partner = self.facilitator_id

        # Override partner if specific invoice company is provided
        if self.invoice_company_name:
            overridden_partner = self.env['res.partner'].search([
                ('name', '=', self.invoice_company_name),
                ('type', '=', 'invoice')
            ], limit=1)
            if overridden_partner:
                partner = overridden_partner

        return {
            'move_type': 'out_invoice',
            'partner_id': partner.id,
            'invoice_date': fields.Date.context_today(self),
            'ref': self.name,
            'narration': f"Order Reference: {self.name}",
            'invoice_origin': self.name,
            'currency_id': self.company_id.currency_id.id,
            'company_id': self.company_id.id,
        }
    
    def _prepare_invoice_lines(self):
        """Prepare invoice lines from order lines"""
        invoice_lines = []
        
        for line in self.order_line_ids.filtered(lambda l: l.unit_price > 0):
            invoice_lines.append((0, 0, {
                'product_id': line.product_id.id,
                'name': line.product_id.display_name,
                'quantity': line.quantity,
                'price_unit': line.unit_price,
                'product_uom_id': line.product_id.uom_id.id,
            }))
        
        return invoice_lines
    
    def action_view_invoice(self):
        """Open the invoice related to this order"""
        self.ensure_one()
        if not self.invoice_id:
            raise UserError(_("No invoice exists for this order."))
            
        return {
            'type': 'ir.actions.act_window',
            'name': _('Invoice'),
            'res_model': 'account.move',
            'res_id': self.invoice_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
        
    def action_set_shipped(self):
        """Mark order as shipped and send notification email"""
        for order in self:
            order.write({'state': 'shipped'})
            order._log_processing_step(f"📦 Order marked as shipped")
            
        template = self.env.ref('inclue_journey_v2.email_template_order_shipped', False)
        if template:
            for order in self:
                template.send_mail(order.id, force_send=True)
                order._log_processing_step(f"📧 Shipping notification sent")
        return True
    
    def action_set_done(self):
        """Mark order as done/completed"""
        for order in self:
            order.write({'state': 'done'})
            order._log_processing_step(f"✅ Order marked as completed")
        return True
    
    def action_cancel(self):
        """Cancel the order"""
        for order in self:
            order.write({'state': 'cancel'})
            order._log_processing_step(f"❌ Order cancelled")
        return True


class FacilitatorOrderLine(models.Model):
    """Order line items for facilitator orders"""
    _name = 'inclue.facilitator.order.line'
    _description = 'Facilitator Order Line'
    
    order_id = fields.Many2one(
        'inclue.facilitator.order', 
        required=True, 
        ondelete='cascade',
        string='Order'
    )
    product_id = fields.Many2one(
        'product.product', 
        required=True, 
        domain="[('is_inclue_card', '=', True)]",
        string='Product'
    )
    quantity = fields.Float(
        'Quantity', 
        default=1.0, 
        required=True,
        digits='Product Unit of Measure'
    )
    
    unit_price = fields.Monetary(
        string='Unit Price', 
        compute='_compute_unit_price', 
        store=True,
        currency_field='currency_id'
    )
    subtotal = fields.Monetary(
        string='Subtotal', 
        compute='_compute_subtotal', 
        store=True,
        currency_field='currency_id'
    )
    currency_id = fields.Many2one(
        related='order_id.currency_id', 
        store=True,
        string='Currency'
    )
    
    @api.depends('product_id', 'order_id.facilitator_type')
    def _compute_unit_price(self):
        """Compute unit price based on facilitator type and pricelist"""
        for line in self:
            if line.product_id and line.order_id:
                pricelist = line.order_id._get_facilitator_pricelist()
                if pricelist:
                    # Use pricelist to get price
                    try:
                        price = pricelist.get_product_price(line.product_id, 1.0, line.order_id.facilitator_id)
                        line.unit_price = price
                        _logger.debug(f"Pricelist price for {line.product_id.name}: {price}")
                    except Exception as e:
                        _logger.warning(f"Failed to get pricelist price: {e}, using list price")
                        line.unit_price = line.product_id.list_price
                else:
                    # Fallback to product list price
                    line.unit_price = line.product_id.list_price
                    _logger.debug(f"Using list price for {line.product_id.name}: {line.unit_price}")
            else:
                line.unit_price = 0.0
    
    @api.depends('quantity', 'unit_price')
    def _compute_subtotal(self):
        """Compute line subtotal"""
        for line in self:
            line.subtotal = line.quantity * line.unit_price
    
    @api.onchange('product_id')
    def _onchange_product_id(self):
        """Update pricing when product changes"""
        if self.product_id:
            self._compute_unit_price()
    
    def name_get(self):
        """Custom display name for order lines"""
        result = []
        for line in self:
            name = f"{line.order_id.name} - {line.product_id.name}"
            result.append((line.id, name))
        return result