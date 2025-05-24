# app.py - Your secure payment API
from flask import Flask, request, jsonify
from flask_cors import CORS
import stripe
import os
from datetime import datetime
import logging

# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Allow requests from your desktop app

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

stripe.api_key = os.getenv('STRIPE_SECRET_KEY')

# Add error handling
if not stripe.api_key:
    logger.error("STRIPE_SECRET_KEY environment variable not set!")
    raise ValueError("Stripe configuration missing")

# Price IDs for your plans
PRICE_IDS = {
    'basic': 'price_1RSQMiHYveGHjElbaTQctoS0',  # Replace with your basic plan price ID
    'premium': 'price_1RSQMiHYveGHjElbaTQctoS0'  # Your premium plan price ID
}

@app.route('/')
def home():
    """Health check endpoint"""
    return jsonify({
        'status': 'active',
        'service': 'SuperSpeedySolutions Payment API',
        'timestamp': datetime.utcnow().isoformat()
    })

@app.route('/create-checkout', methods=['POST'])
def create_checkout():
    """Create Stripe checkout session"""
    try:
        # Get data from request
        data = request.get_json()
        plan_type = data.get('plan_type', 'premium').lower()
        success_url = data.get('success_url', 'https://yourdomain.com/success')
        cancel_url = data.get('cancel_url', 'https://yourdomain.com/cancel')
        customer_email = data.get('customer_email')
        
        # Validate plan type
        if plan_type not in PRICE_IDS:
            return jsonify({
                'success': False,
                'error': 'Invalid plan type. Must be "basic" or "premium"'
            }), 400
        
        # Get the price ID for the selected plan
        price_id = PRICE_IDS[plan_type]
        
        # Create checkout session parameters
        session_params = {
            'payment_method_types': ['card'],
            'line_items': [{
                'price': price_id,
                'quantity': 1,
            }],
            'mode': 'subscription',  # Change to 'payment' for one-time payments
            'success_url': success_url + '?session_id={CHECKOUT_SESSION_ID}',
            'cancel_url': cancel_url,
            'metadata': {
                'plan_type': plan_type,
                'app_version': data.get('app_version', 'unknown'),
                'user_id': data.get('user_id', 'anonymous')
            }
        }
        
        # Add customer email if provided
        if customer_email:
            session_params['customer_email'] = customer_email
        
        # Create the checkout session
        session = stripe.checkout.sessions.create(**session_params)
        
        # Log successful creation
        logger.info(f"Created checkout session {session.id} for plan: {plan_type}")
        
        return jsonify({
            'success': True,
            'checkout_url': session.url,
            'session_id': session.id,
            'plan_type': plan_type
        })
        
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Payment system error. Please try again.'
        }), 400
        
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500

@app.route('/verify-payment', methods=['POST'])
def verify_payment():
    """Verify payment completion"""
    try:
        data = request.get_json()
        session_id = data.get('session_id')
        
        if not session_id:
            return jsonify({
                'success': False,
                'error': 'Session ID required'
            }), 400
        
        # Retrieve the session from Stripe
        session = stripe.checkout.sessions.retrieve(session_id)
        
        # Check payment status
        if session.payment_status == 'paid':
            logger.info(f"Payment verified for session {session_id}")
            return jsonify({
                'success': True,
                'payment_status': 'paid',
                'customer_email': session.customer_details.email if session.customer_details else None,
                'plan_type': session.metadata.get('plan_type', 'unknown')
            })
        else:
            return jsonify({
                'success': False,
                'payment_status': session.payment_status,
                'error': 'Payment not completed'
            })
            
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error during verification: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Unable to verify payment'
        }), 400
        
    except Exception as e:
        logger.error(f"Error during payment verification: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Verification failed'
        }), 500

@app.route('/webhook', methods=['POST'])
def stripe_webhook():
    """Handle Stripe webhooks (optional but recommended for production)"""
    try:
        payload = request.get_data()
        sig_header = request.headers.get('Stripe-Signature')
        endpoint_secret = os.getenv('STRIPE_WEBHOOK_SECRET')
        
        if not endpoint_secret:
            logger.warning("Webhook received but no webhook secret configured")
            return jsonify({'received': True})
        
        # Verify webhook signature
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
        
        # Handle the event
        if event['type'] == 'checkout.session.completed':
            session = event['data']['object']
            logger.info(f"Payment completed for session {session['id']}")
            # Here you could update your database, send confirmation emails, etc.
            
        elif event['type'] == 'customer.subscription.created':
            subscription = event['data']['object']
            logger.info(f"Subscription created: {subscription['id']}")
            
        else:
            logger.info(f"Unhandled event type: {event['type']}")
        
        return jsonify({'received': True})
        
    except Exception as e:
        logger.error(f"Webhook error: {str(e)}")
        return jsonify({'error': 'Webhook failed'}), 400

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug_mode = os.environ.get('FLASK_ENV') == 'development'
    
    logger.info(f"Starting SuperSpeedySolutions Payment API on port {port}")
    app.run(host='0.0.0.0', port=port, debug=debug_mode)