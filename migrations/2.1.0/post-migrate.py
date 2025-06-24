# migrations/2.1.0/post-migrate.py
import logging
from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)

def migrate(cr, version):
    """
    Migrate existing facilitator orders to use the new product-based order lines
    """
    if not version:
        return
    
    env = api.Environment(cr, SUPERUSER_ID, {})
    
    _logger.info("Starting migration of facilitator orders to product-based system...")
    
    # Find all existing orders that don't have order lines yet
    orders = env['inclue.facilitator.order'].search([
        ('order_line_ids', '=', False)
    ])
    
    if not orders:
        _logger.info("No orders to migrate")
        return
    
    _logger.info("Found %s orders to migrate", len(orders))
    
    # Get the card products
    products = {}
    card_types = ['gift_card', 'followup_card', 'participant_deck', 'facilitator_deck', 'promo_package']
    
    for card_type in card_types:
        product = env['product.product'].search([
            ('is_inclue_card', '=', True),
            ('inclue_card_type', '=', card_type)
        ], limit=1)
        
        if product:
            products[card_type] = product
            _logger.info("Found product for %s: %s", card_type, product.name)
        else:
            _logger.error("Product not found for card type: %s", card_type)
    
    if len(products) != 4:
        _logger.error("Not all required products found. Skipping migration.")
        return
    
    migrated_count = 0
    
    for order in orders:
        try:
            order_lines_to_create = []
            
            # Map legacy quantities to order lines
            quantity_mappings = [
                (order.gift_card_qty, 'gift_card'),
                (order.followup_card_qty, 'followup_card'),
                (order.participant_deck_qty, 'participant_deck'),
                (order.facilitator_deck_qty, 'facilitator_deck'),
                (order.promo_package_qty, 'promo_package'),
            ]
            
            for quantity, card_type in quantity_mappings:
                if quantity > 0 and card_type in products:
                    order_lines_to_create.append({
                        'order_id': order.id,
                        'product_id': products[card_type].id,
                        'quantity': quantity,
                    })
            
            # Create order lines
            if order_lines_to_create:
                for line_vals in order_lines_to_create:
                    env['inclue.facilitator.order.line'].create(line_vals)
                
                migrated_count += 1
                _logger.info("Migrated order %s (%s lines)", order.name, len(order_lines_to_create))
            
        except Exception as e:
            _logger.error("Error migrating order %s: %s", order.name, str(e))
    
    _logger.info("Migration completed. Migrated %s out of %s orders", migrated_count, len(orders))

# Alternative: Manual migration function that can be called from Odoo
def manual_migrate_orders():
    """
    Function that can be called manually to migrate existing orders
    Usage: Execute this in Odoo's debug console or create a server action
    """
    orders = env['inclue.facilitator.order'].search([
        ('order_line_ids', '=', False)
    ])
    
    products = {}
    for card_type in ['gift_card', 'followup_card', 'participant_deck', 'facilitator_deck', 'promo_package']:
        product = env['product.product'].search([
            ('is_inclue_card', '=', True),
            ('inclue_card_type', '=', card_type)
        ], limit=1)
        if product:
            products[card_type] = product
    
    migrated_count = 0
    for order in orders:
        order_lines_to_create = []
        
        # Convert legacy quantities to order lines
        if order.gift_card_qty > 0 and 'gift_card' in products:
            order_lines_to_create.append({
                'order_id': order.id,
                'product_id': products['gift_card'].id,
                'quantity': order.gift_card_qty,
            })
        
        if order.followup_card_qty > 0 and 'followup_card' in products:
            order_lines_to_create.append({
                'order_id': order.id,
                'product_id': products['followup_card'].id,
                'quantity': order.followup_card_qty,
            })
            
        if order.participant_deck_qty > 0 and 'participant_deck' in products:
            order_lines_to_create.append({
                'order_id': order.id,
                'product_id': products['participant_deck'].id,
                'quantity': order.participant_deck_qty,
            })
            
        if order.facilitator_deck_qty > 0 and 'facilitator_deck' in products:
            order_lines_to_create.append({
                'order_id': order.id,
                'product_id': products['facilitator_deck'].id,
                'quantity': order.facilitator_deck_qty,
            })
        if order.promo_package_qty > 0 and 'promo_package' in products:
            order_lines_to_create.append({
                'order_id': order.id,
                'product_id': products['promo_package'].id,
                'quantity': order.promo_package_qty,
            })
        
        # Create the order lines
        for line_vals in order_lines_to_create:
            env['inclue.facilitator.order.line'].create(line_vals)
        
        if order_lines_to_create:
            migrated_count += 1
    
    return f"Migrated {migrated_count} orders successfully"