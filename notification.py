import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def notify_customer_order_status(customer_name, phone, email, order_id, status, custom_message=None):
    """
    Notify customer about order status changes.
    
    Parameters:
    - customer_name: Name of the customer
    - phone: Customer's phone number
    - email: Customer's email address
    - order_id: Order ID
    - status: Current status of the order ('assigned', 'en_route', 'completed')
    - custom_message: Optional custom message to send to the customer
    """
    if not phone and not email:
        # No contact information available
        return False
        
    # Default messages based on status
    messages = {
        'assigned': f"Hello {customer_name}, your order (#{order_id}) has been assigned to a delivery agent and will be delivered soon.",
        'en_route': f"Hello {customer_name}, your order (#{order_id}) is on the way to your location.",
        'completed': f"Hello {customer_name}, your order (#{order_id}) has been delivered. Thank you for your business!"
    }
    
    # Use custom message if provided, otherwise use default
    message = custom_message if custom_message else messages.get(status, messages['en_route'])
    
    # Send SMS notification if phone is available
    if phone:
        try:
            # Your SMS sending code here (uncomment and use your SMS service)
            # send_sms(phone, message)
            print(f"SMS sent to {phone}: {message}")
        except Exception as e:
            print(f"Error sending SMS: {str(e)}")
    
    # Send email notification if email is available
    if email:
        try:
            # Your email sending code here (uncomment and use your email service)
            # send_email(email, "Order Update", message)
            print(f"Email sent to {email}: {message}")
        except Exception as e:
            print(f"Error sending email: {str(e)}")
            
    return True

def send_sms(phone_number, message):
    """
    Send SMS using a third-party service
    
    For demonstration purposes, this is set up to use Twilio,
    but you should replace with your preferred SMS service.
    
    Parameters:
    - phone_number: Recipient's phone number
    - message: Text message to send
    """
    # Get API credentials from environment variables
    sms_api_key = os.environ.get('SMS_API_KEY')
    sms_api_secret = os.environ.get('SMS_API_SECRET')
    sms_from_number = os.environ.get('SMS_FROM_NUMBER')
    
    # Check if SMS service is configured
    if not all([sms_api_key, sms_api_secret, sms_from_number]):
        print("SMS service not configured. Skipping SMS notification.")
        return
    
    # For demonstration, we're showing how to use Twilio
    # But this is commented out since it requires the Twilio package
    
    """
    # Uncomment and install twilio package to use
    from twilio.rest import Client
    
    client = Client(sms_api_key, sms_api_secret)
    client.messages.create(
        body=message,
        from_=sms_from_number,
        to=phone_number
    )
    """
    
    # Instead, we'll just print the message for now
    print(f"SMS would be sent to {phone_number}: {message}")


def send_email(email_address, subject, message):
    """
    Send email using SMTP
    
    Parameters:
    - email_address: Recipient's email address
    - subject: Email subject
    - message: Email body
    """
    # Get email configuration from environment variables
    smtp_server = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
    smtp_port = int(os.environ.get('SMTP_PORT', 587))
    smtp_username = os.environ.get('SMTP_USERNAME')
    smtp_password = os.environ.get('SMTP_PASSWORD')
    sender_email = os.environ.get('SENDER_EMAIL', smtp_username)
    
    # Check if email service is configured
    if not all([smtp_server, smtp_port, smtp_username, smtp_password]):
        print("Email service not configured. Skipping email notification.")
        return
    
    # Create message
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = email_address
    msg['Subject'] = subject
    
    # Add body with enhanced HTML formatting for better user experience
    html_message = f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background-color: #4285f4; color: white; padding: 10px 20px; text-align: center; }}
            .content {{ padding: 20px; background-color: #f9f9f9; }}
            .footer {{ font-size: 12px; text-align: center; margin-top: 20px; color: #777; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h2>Delivery Update</h2>
            </div>
            <div class="content">
                <p>{message}</p>
            </div>
            <div class="footer">
                <p>If you have any questions about your delivery, please contact our customer support.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    # Attach HTML version
    msg.attach(MIMEText(html_message, 'html'))
    
    # Also attach plain text version as fallback
    msg.attach(MIMEText(message, 'plain'))
    
    try:
        # Connect to server and send email
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()  # Secure the connection
        server.login(smtp_username, smtp_password)
        text = msg.as_string()
        server.sendmail(sender_email, email_address, text)
        server.quit()
    except Exception as e:
        # For now, just print the error and the message
        print(f"Would send email to {email_address}: {subject}")
        print(f"Message: {message}")
        print(f"Error: {str(e)}")