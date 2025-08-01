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
            
            for line in order.order_line:
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
        """Complete automated processing for facilitator orders"""
        self.ensure_one()
        
        processing_start = datetime.now()
        log_entries = []
        
        try:
            log_entries.append(f"🚀 AUTO-PROCESSING STARTED at {processing_start.strftime('%Y-%m-%d %H:%M:%S')}")
            log_entries.append(f"📋 Order: {self.name}")
            log_entries.append(f"👤 Customer: {self.partner_id.name}")
            log_entries.append(f"💰 Total Amount: {self.amount_total:.2f} {self.currency_id.name}")
            log_entries.append(f"🎯 Facilitator Type: {self.facilitator_type}")

            if self.facilitator_type == 'internal':
                log_entries.append(f"📦 Delivery Contact: {self.delivery_contact_name}")
                log_entries.append(f"🏢 Delivery VAT: {self.delivery_vat_number}")
                log_entries.append(f"📧 Delivery Email: {self.delivery_email}")
    
            
            # Step 1: Confirm order if not already confirmed
            if self.state in ['draft', 'sent']:
                log_entries.append("\n--- STEP 1: CONFIRMING ORDER ---")
                super().action_confirm()  # Use Odoo's standard confirmation
                log_entries.append("✅ Order confirmed using standard Odoo workflow")
            
            # Step 2: Create and process invoice
            log_entries.append("\n--- STEP 2: INVOICE PROCESSING ---")
            
            # Check if there are chargeable items
            chargeable_lines = self.order_line.filtered(lambda l: l.price_subtotal > 0)
            
            if chargeable_lines:
                log_entries.append(f"💵 Order with chargeable items (Total: {self.amount_total:.2f})")
                log_entries.append("🧾 Creating invoice using Odoo standard workflow...")
                
                # Use Odoo's standard invoice creation
                invoices = self._create_invoices()
                
                if invoices:
                    invoice = invoices[0]
                    log_entries.append(f"✅ Invoice created: {invoice.name}")
                    log_entries.append(f"💰 Invoice Amount: {invoice.amount_total:.2f} {invoice.currency_id.name}")
                    log_entries.append(f"🏛️ Taxes automatically calculated by Odoo")
                    
                    # Auto-post invoice
                    if invoice.state == 'draft':
                        invoice.action_post()
                        log_entries.append("✅ Invoice posted automatically")
                    
                    # Send invoice email
                    try:
                        invoice.action_invoice_sent()
                        log_entries.append("📧 Invoice email sent to customer")
                    except Exception as email_error:
                        log_entries.append(f"❌ Email failed: {str(email_error)}")
                    
                    # Auto-register payment for internal orders if enabled
                    if self.facilitator_type == 'internal' and self.auto_pay_internal:
                        log_entries.append("💳 Auto-registering payment (internal order)...")
                        if self._register_automatic_payment(invoice):
                            log_entries.append("✅ Payment registered automatically")
                        else:
                            log_entries.append("❌ Auto-payment failed")
                
            else:
                log_entries.append("🆓 No chargeable items - order completed without invoice")
            
            # Step 3: Finalization
            log_entries.append("\n--- STEP 3: FINALIZATION ---")
            processing_end = datetime.now()
            processing_duration = (processing_end - processing_start).total_seconds()
            
            self.write({
                'auto_processed': True,
                'last_processing_error': False,
                'processing_log': "\n".join(log_entries)
            })
            
            log_entries.append(f"✅ AUTO-PROCESSING COMPLETED in {processing_duration:.2f}s")
            log_entries.append(f"🎉 Final State: {self.state}")
            
            # Post success message
            self.message_post(
                body=f"""
                <h3>🎉 Facilitator Order Auto-Processing Complete</h3>
                <ul>
                    <li><strong>Order:</strong> {self.name}</li>
                    <li><strong>Amount:</strong> {self.amount_total:.2f} {self.currency_id.name}</li>
                    <li><strong>Final State:</strong> {self.state}</li>
                    <li><strong>Duration:</strong> {processing_duration:.2f} seconds</li>
                </ul>
                """,
                subject="Auto-Processing Success"
            )
            
            _logger.info(f"=== AUTO-PROCESSING COMPLETED FOR ORDER {self.name} ===")
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
    # def create_facilitator_order(self, data):
    #     """API method to create facilitator orders"""
    #     _logger.info(f"Creating facilitator sale order via API: {data}")
        
    #     # Prepare sale order values
    #     sale_vals = {
    #         'partner_id': data['facilitator_id'],
    #         'facilitator_type': data.get('facilitator_type', 'internal'),
    #         'facility_language_id': data.get('facility_language_id'),
    #         'shipping_address_custom': data.get('shipping_address'),
    #         'invoice_company_name': data.get('invoice_company_name'),
    #         'invoice_address_custom': data.get('invoice_address'),
    #         'po_number': data.get('po_number'),
    #         'contact_person': data.get('contact_person'),
    #         'auto_process': data.get('auto_process', True),
    #         'auto_pay_internal': data.get('auto_pay_internal', False),
    #     }
        
    #     # Set pricelist based on facilitator type
    #     facilitator_type = data.get('facilitator_type', 'internal')
    #     if facilitator_type == 'internal':
    #         pricelist = self.env.ref('inclue_consolidated_approach.pricelist_internal_facilitator')
    #     else:
    #         pricelist = self.env.ref('inclue_consolidated_approach.pricelist_external_facilitator')
        
    #     sale_vals['pricelist_id'] = pricelist.id
        
    #     # Create sale order
    #     sale_order = self.create(sale_vals)
        
    #     # Add order lines
    #     line_items = [
    #         ('participant_deck_qty', 'participant_deck'),
    #         ('facilitator_deck_qty', 'facilitator_deck'),
    #         ('gift_card_qty', 'gift_card'),
    #         ('followup_card_qty', 'followup_card'),
    #         ('promo_package_qty', 'promo_package'),
    #     ]
        
    #     for qty_field, card_type in line_items:
    #         quantity = data.get(qty_field, 0)
    #         if quantity > 0:
    #             product = self.env['product.product'].search([
    #                 ('is_inclue_card', '=', True),
    #                 ('inclue_card_type', '=', card_type),
    #                 ('active', '=', True),
    #                 '|',
    #                 ('facilitator_access', '=', 'all'),
    #                 ('facilitator_access', '=', facilitator_type)
    #             ], limit=1)

    #             if product:
    #                 self.env['sale.order.line'].create({
    #                     'order_id': sale_order.id,
    #                     'product_id': product.id,
    #                     'product_uom_qty': quantity,
    #                     'name': product.name,
    #                     'price_unit': product.lst_price,
    #                     'product_uom': product.uom_id.id,
    #                 })
        
    #     return sale_order

    def create_facilitator_order(self, data):
        # Prepare order vals
        order_vals = {
            'partner_id': data['facilitator_id'],
            'facilitator_type': data.get('facilitator_type'),
            'facility_language_id': data.get('facility_language_id'),
            'shipping_address_custom': data.get('shipping_address'),
            'invoice_company_name': data.get('invoice_company_name'),
            'invoice_address_custom': data.get('invoice_address'),
            'po_number': data.get('po_number', ''),
            'contact_person': data.get('contact_person', ''),
            'pricelist_id': self._get_pricelist_id(data.get('company_id')),
            
            'delivery_contact_name': data.get('delivery_contact_name', ''),
            'delivery_vat_number': data.get('delivery_vat_number', ''),
            'delivery_email': data.get('delivery_email', ''),
        }

        # Create the sale order
        sale_order = self.env['sale.order'].create(order_vals)

        # Create order lines
        self._create_order_lines(sale_order, data.get('order_lines', []))

        # Auto process (confirm + invoice + post) if flagged or default True
        if data.get('auto_process', True):
            self._auto_process_order(sale_order)

        return sale_order

    def _get_pricelist_id(self, company_id):
        # You can customize this method to select pricelist by company or other criteria
        pricelist = self.env['product.pricelist'].search([('company_id', '=', company_id)], limit=1)
        if not pricelist:
            pricelist = self.env['product.pricelist'].search([], limit=1)
        if not pricelist:
            raise UserError(_("No pricelist found for company %s") % company_id)
        return pricelist.id

    def _create_order_lines(self, sale_order, order_lines):
        Product = self.env['product.product']
        SaleOrderLine = self.env['sale.order.line']
        for line in order_lines:
            # Assuming product_id is external identifier key like 'participant_deck'
            product_ref = 'inclue_consolidated_approach.product_%s' % line['product_id']
            product = self.env.ref(product_ref, raise_if_not_found=False)
            if not product:
                raise UserError(_("Product with external ID %s not found") % product_ref)

            SaleOrderLine.create({
                'order_id': sale_order.id,
                'product_id': product.id,
                'name': product.name,
                'product_uom_qty': line['quantity'],
                'price_unit': product.list_price,
                'product_uom': product.uom_id.id,
            })

    def _auto_process_order(self, sale_order):
        # Confirm the sale order
        sale_order.action_confirm()

        # Create invoice using wizard
        wizard = self.env['sale.advance.payment.inv'].with_context(
            active_ids=sale_order.ids,
            active_model='sale.order'
        ).create({'advance_payment_method': 'delivered'})

        wizard.create_invoices()

        # Post invoices
        for invoice in sale_order.invoice_ids:
            if invoice.state == 'draft':
                invoice.action_post()
