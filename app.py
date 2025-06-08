from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
from functools import wraps
import os
from dotenv import load_dotenv
from supabase import create_client
from route_optimizer import RouteOptimizer, DeliveryLocation
import pandas as pd
import json
from notification import notify_customer_order_status
from datetime import datetime, timedelta

app = Flask(__name__)

# Load environment variables
load_dotenv()

# Supabase setup
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Flask config
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', '9d7eb48fb46ab3d4b1661ba36e6947d4')

# Admin credentials (only one admin allowed)
ADMIN_EMAIL = "99220041514@klu.ac.in"
ADMIN_PASSWORD = "admin123"  # Should be securely stored in production

# Authentication decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Admin-only decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session or session['user']['role'] != 'admin':
            flash('You do not have permission to access this page.')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# Agent-only decorator
def agent_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session or session['user']['role'] != 'agent':
            flash('You do not have permission to access this page.')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    if 'user' in session:
        if session['user']['role'] == 'admin':
            return redirect(url_for('admin_dashboard'))
        elif session['user']['role'] == 'agent':
            return redirect(url_for('agent_dashboard'))
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        phone = request.form.get('phone', '')
        
        # Check if trying to register as admin
        if email == ADMIN_EMAIL:
            flash('This email is reserved. Please use a different email.')
            return redirect(url_for('register'))
        
        # Only allow agent registration through public form
        role = 'agent'
        
        # First register with Supabase Auth
        try:
            auth_response = supabase.auth.sign_up({
                "email": email,
                "password": password
            })
            
            if auth_response.user:
                # Then add user details to our users table
                user_data = {
                    "id": auth_response.user.id,
                    "username": username,
                    "email": email,
                    "role": role,
                    "phone": phone
                }
                
                response = supabase.table('users').insert(user_data).execute()
                
                flash('Registration successful! Please login.')
                return redirect(url_for('login'))
            else:
                flash('Registration failed. Please try again.')
        except Exception as e:
            flash(f'Registration error: {str(e)}')
        
        return redirect(url_for('register'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        try:
            # Special handling for admin login
            if email == ADMIN_EMAIL and password == ADMIN_PASSWORD:
                # Check if admin exists in users table, if not create it
                admin_response = supabase.table('users').select('*').eq('email', ADMIN_EMAIL).execute()
                
                if not admin_response.data:
                    # Create admin user in the database
                    try:
                        # First create in auth
                        auth_response = supabase.auth.sign_up({
                            "email": ADMIN_EMAIL,
                            "password": ADMIN_PASSWORD
                        })
                        
                        if auth_response.user:
                            admin_id = auth_response.user.id
                            # Then add to users table
                            admin_data = {
                                "id": admin_id,
                                "username": "Admin",
                                "email": ADMIN_EMAIL,
                                "role": "admin"
                            }
                            supabase.table('users').insert(admin_data).execute()
                        else:
                            # Admin might already exist in auth but not in users table
                            # Try to sign in to get the ID
                            auth_response = supabase.auth.sign_in_with_password({
                                "email": ADMIN_EMAIL,
                                "password": ADMIN_PASSWORD
                            })
                            admin_id = auth_response.user.id
                            admin_data = {
                                "id": admin_id,
                                "username": "Admin",
                                "email": ADMIN_EMAIL,
                                "role": "admin"
                            }
                            supabase.table('users').insert(admin_data).execute()
                    except Exception as e:
                        # Admin might already exist in auth
                        pass
                        
                    # Refresh admin data
                    admin_response = supabase.table('users').select('*').eq('email', ADMIN_EMAIL).execute()
                
                if admin_response.data:
                    admin_data = admin_response.data[0]
                    session['user'] = {
                        'id': admin_data['id'],
                        'username': admin_data['username'],
                        'email': admin_data['email'],
                        'role': 'admin'
                    }
                    return redirect(url_for('admin_dashboard'))
                else:
                    flash('Admin account setup failed. Please contact support.')
            else:
                # Regular user authentication
                auth_response = supabase.auth.sign_in_with_password({
                    "email": email,
                    "password": password
                })
                
                if auth_response.user:
                    # Get user details from our users table
                    user_id = auth_response.user.id
                    response = supabase.table('users').select('*').eq('id', user_id).execute()
                    
                    if response.data:
                        user_data = response.data[0]
                        
                        # Prevent regular users from accessing admin account
                        if user_data['email'] == ADMIN_EMAIL and user_data['role'] != 'admin':
                            flash('Unauthorized access attempt.')
                            return redirect(url_for('login'))
                        
                        # Store user in session
                        session['user'] = {
                            'id': user_id,
                            'username': user_data['username'],
                            'email': user_data['email'],
                            'role': user_data['role'],
                            'phone': user_data.get('phone', '')
                        }
                        
                        # Redirect based on role
                        if user_data['role'] == 'admin':
                            return redirect(url_for('admin_dashboard'))
                        else:
                            return redirect(url_for('agent_dashboard'))
                    else:
                        flash('User details not found')
                else:
                    flash('Invalid email or password')
        except Exception as e:
            flash(f'Login error: {str(e)}')
        
        return redirect(url_for('login'))
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    supabase.auth.sign_out()
    session.pop('user', None)
    flash('You have been logged out.')
    return redirect(url_for('index'))

@app.route('/admin/dashboard')
@login_required
@admin_required
def admin_dashboard():
    try:
        # Get all orders
        orders_response = supabase.table('orders').select('*').execute()
        orders = orders_response.data
        
        # Get all agents
        agents_response = supabase.table('users').select('*').eq('role', 'agent').execute()
        agents = agents_response.data
        
        # Group orders by area
        orders_by_area = {}
        area_stats = {}
        
        for order in orders:
            area = order['area']
            
            # Initialize area if not exists
            if area not in orders_by_area:
                orders_by_area[area] = []
                area_stats[area] = {
                    'count': 0,
                    'pending': 0,
                    'assigned': 0,
                    'completed': 0
                }
            
            # Add order to area group
            orders_by_area[area].append(order)
            
            # Update area statistics
            area_stats[area]['count'] += 1
            if order['status'] == 'completed':
                area_stats[area]['completed'] += 1
            elif order['agent_id']:
                area_stats[area]['assigned'] += 1
            else:
                area_stats[area]['pending'] += 1
        
        return render_template('admin_dashboard.html', 
                            orders_by_area=orders_by_area,
                            area_stats=area_stats,
                            agents=agents)
    except Exception as e:
        flash(f'Error loading dashboard: {str(e)}')
        return redirect(url_for('index'))

@app.route('/assign_order', methods=['POST'])
@login_required
@admin_required
def assign_order():
    order_id = request.form.get('order_id')
    agent_id = request.form.get('agent_id')
    
    try:
        # Update order in database
        supabase.table('orders').update({'agent_id': agent_id, 'status': 'assigned'}).eq('id', order_id).execute()
        
        # Get agent details for notification
        agent_response = supabase.table('users').select('*').eq('id', agent_id).execute()
        
        if agent_response.data:
            agent = agent_response.data[0]
            # Here you would send notification to agent (SMS/email) - Implement notification
            
        # Get order details
        order_response = supabase.table('orders').select('*').eq('id', order_id).execute()
        if order_response.data:
            order = order_response.data[0]
            # Notify customer
            notify_customer_order_status(
                order['customer_name'],
                order.get('phone'),
                order.get('email'),
                order_id,
                'assigned'
            )
            
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/agent/dashboard')
@login_required
@agent_required
def agent_dashboard():
    agent_id = session['user']['id']
    
    try:
        # Get orders assigned to this agent
        orders_response = supabase.table('orders').select('*').eq('agent_id', agent_id).execute()
        orders = orders_response.data
        
        # Separate orders by status
        pending_orders = [order for order in orders if order['status'] == 'pending' or order['status'] == 'assigned']
        completed_orders = [order for order in orders if order['status'] == 'completed']
        
        return render_template('agent_dashboard.html', 
                            pending_orders=pending_orders,
                            completed_orders=completed_orders)
    except Exception as e:
        flash(f'Error loading dashboard: {str(e)}')
        return redirect(url_for('index'))

@app.route('/optimize_route')
@login_required
@agent_required
def optimize_route():
    agent_id = session['user']['id']
    
    try:
        # Get only orders with "assigned" status for this agent
        orders_response = supabase.table('orders').select('*').eq('agent_id', agent_id).eq('status', 'assigned').execute()
        orders = orders_response.data
        
        if not orders:
            return jsonify({'error': 'No assigned orders to optimize'}), 404
        
        # Determine depot location based on delivery area
        # If orders exist, use the first order's area to determine the region
        if orders:
            # Get the area of the first order to determine region
            area = orders[0]['area']
            
            # Map of areas to approximate coordinates
            area_coordinates = {
                'East Marret': {'lat': 9.9252, 'lng': 78.1198},  # Madurai
                'West Marret': {'lat': 9.9252, 'lng': 78.1198},  # Madurai
                'North Madurai': {'lat': 9.9252, 'lng': 78.1198},  # Madurai
                'South Madurai': {'lat': 9.9252, 'lng': 78.1198},  # Madurai
                'Chennai': {'lat': 13.0827, 'lng': 80.2707},
                'Mumbai': {'lat': 19.0760, 'lng': 72.8777},
                'Delhi': {'lat': 28.6139, 'lng': 77.2090},
                'Bangalore': {'lat': 12.9716, 'lng': 77.5946}
                # Add more areas as needed
            }
            
            # Get coordinates for the area, default to Madurai if not found
            depot_coords = area_coordinates.get(area, {'lat': 9.9252, 'lng': 78.1198})
            depot = DeliveryLocation(0, depot_coords['lat'], depot_coords['lng'])
        else:
            # Default to Madurai if no orders or area not found
            depot = DeliveryLocation(0, 9.9252, 78.1198)
            
        # Create delivery locations from orders
        delivery_locations = [
            DeliveryLocation(order['id'], order['latitude'], order['longitude'])
            for order in orders
        ]
        
        # Optimize route
        optimizer = RouteOptimizer(depot)
        optimized_route = optimizer.optimize_route(delivery_locations)
        route_details = optimizer.get_route_details(optimized_route)
        
        # Format route for frontend
        route_data = []
        
        # Add depot as first point
        route_data.append({
            'id': 0,
            'lat': depot.latitude,
            'lng': depot.longitude,
            'type': 'depot',
            'info': 'Starting Point'
        })
        
        # Add optimized delivery points
        for location in optimized_route[1:-1]:  # Skip first and last (depot)
            order = next((o for o in orders if o['id'] == location.id), None)
            if order:
                route_data.append({
                    'id': order['id'],
                    'lat': order['latitude'],
                    'lng': order['longitude'],
                    'type': 'delivery',
                    'info': {
                        'customer': order['customer_name'],
                        'address': order['address'],
                        'status': order['status'],
                        'phone': order.get('phone', 'N/A'),
                        'email': order.get('email', 'N/A')
                    }
                })
        
        # Add depot as last point
        route_data.append({
            'id': 0,
            'lat': depot.latitude,
            'lng': depot.longitude,
            'type': 'depot',
            'info': 'End Point'
        })
        
        return jsonify({
            'route': route_data,
            'details': route_details
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/update_order_status', methods=['POST'])
@login_required
@agent_required
def update_order_status():
    agent_id = session['user']['id']
    order_id = request.form.get('order_id')
    new_status = request.form.get('status')
    
    try:
        # Verify order belongs to this agent
        order_response = supabase.table('orders').select('*').eq('id', order_id).execute()
        
        if not order_response.data or order_response.data[0]['agent_id'] != agent_id:
            return jsonify({'error': 'Unauthorized'}), 403
        
        # Update order status
        supabase.table('orders').update({'status': new_status}).eq('id', order_id).execute()
        
        # If completed, send notification to customer
        if new_status == 'completed':
            order = order_response.data[0]
            # Notification to customer
            notify_customer_order_status(
                order['customer_name'],
                order.get('phone'),
                order.get('email'),
                order_id,
                'completed'
            )
            
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/send_delivery_notification', methods=['POST'])
@login_required
@agent_required
def send_delivery_notification():
    try:
        data = request.get_json()
        order_id = data.get('order_id')
        eta_minutes = data.get('eta_minutes', 30)  # Default 30 minutes if not specified
        
        if not order_id:
            return jsonify({'error': 'Order ID is required'}), 400
            
        # Get order details
        order_response = supabase.table('orders').select('*').eq('id', order_id).execute()
        
        if not order_response.data:
            return jsonify({'error': 'Order not found'}), 404
            
        order = order_response.data[0]
        
        # Calculate estimated delivery time
        delivery_time = datetime.now() + timedelta(minutes=eta_minutes)
        formatted_time = delivery_time.strftime('%I:%M %p')  # Format like "2:30 PM"
        
        # Send notification to customer
        message = f"Your order will be delivered today at approximately {formatted_time} (within {eta_minutes} minutes). Thank you for your patience!"
        
        # Send notification using your existing function
        notify_customer_order_status(
            order['customer_name'],
            order.get('phone'),
            order.get('email'),
            order_id,
            'en_route',
            custom_message=message
        )
        
        return jsonify({
            'success': True, 
            'customer_name': order['customer_name'],
            'eta': formatted_time
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/add_order', methods=['GET', 'POST'])
@login_required
@admin_required
def add_order():
    if request.method == 'POST':
        try:
            # Get form data
            customer_name = request.form.get('customer_name')
            address = request.form.get('address')
            area = request.form.get('area')
            latitude = float(request.form.get('latitude'))
            longitude = float(request.form.get('longitude'))
            phone = request.form.get('phone', '')
            email = request.form.get('email', '')
            
            # Create new order
            order_data = {
                "customer_name": customer_name,
                "address": address,
                "area": area,
                "latitude": latitude,
                "longitude": longitude,
                "phone": phone,
                "email": email,
                "status": "pending"
            }
            
            # Insert into database
            response = supabase.table('orders').insert(order_data).execute()
            
            if response.data:
                flash('Order added successfully!')
            else:
                flash('Failed to add order.')
                
            return redirect(url_for('admin_dashboard'))
        except Exception as e:
            flash(f'Error adding order: {str(e)}')
            return redirect(url_for('add_order'))
    
    return render_template('add_order.html')

@app.route('/view_agent_route/<agent_id>')
@login_required
@admin_required
def view_agent_route(agent_id):
    try:
        # Get agent details
        agent_response = supabase.table('users').select('*').eq('id', agent_id).execute()
        
        if not agent_response.data:
            flash('Agent not found.')
            return redirect(url_for('admin_dashboard'))
        
        agent = agent_response.data[0]
        
        # Get orders assigned to this agent
        orders_response = supabase.table('orders').select('*').eq('agent_id', agent_id).neq('status', 'completed').execute()
        orders = orders_response.data
        
        return render_template('view_agent_route.html', agent=agent, orders=orders)
    except Exception as e:
        flash(f'Error loading agent route: {str(e)}')
        return redirect(url_for('admin_dashboard'))

@app.route('/bulk_assign', methods=['POST'])
@login_required
@admin_required
def bulk_assign():
    try:
        agent_id = request.form.get('agent_id')
        order_ids = request.form.getlist('order_ids')
        
        if not agent_id or not order_ids:
            return jsonify({'error': 'Missing required parameters'}), 400
        
        # Update orders in database
        for order_id in order_ids:
            supabase.table('orders').update({'agent_id': agent_id, 'status': 'assigned'}).eq('id', order_id).execute()
            
            # Get order details for notification
            order_response = supabase.table('orders').select('*').eq('id', order_id).execute()
            if order_response.data:
                order = order_response.data[0]
                # Notify customer
                notify_customer_order_status(
                    order['customer_name'],
                    order.get('phone'),
                    order.get('email'),
                    order_id,
                    'assigned'
                )
        
        return jsonify({'success': True, 'message': f'Successfully assigned {len(order_ids)} orders'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/reports')
@login_required
@admin_required
def reports():
    try:
        # Get date range from query parameters (default to last 30 days)
        from_date = request.args.get('from_date')
        to_date = request.args.get('to_date')
        
        # Get all orders
        query = supabase.table('orders').select('*')
        
        # Apply date filters if provided
        if from_date:
            query = query.gte('created_at', from_date)
        if to_date:
            query = query.lte('created_at', to_date)
            
        orders_response = query.execute()
        orders = orders_response.data
        
        # Calculate statistics
        total_orders = len(orders)
        completed_orders = sum(1 for order in orders if order['status'] == 'completed')
        pending_orders = sum(1 for order in orders if order['status'] == 'pending')
        assigned_orders = sum(1 for order in orders if order['status'] == 'assigned')
        
        # Group by area
        area_stats = {}
        for order in orders:
            area = order['area']
            if area not in area_stats:
                area_stats[area] = {
                    'total': 0,
                    'completed': 0,
                    'pending': 0,
                    'assigned': 0
                }
            
            area_stats[area]['total'] += 1
            if order['status'] == 'completed':
                area_stats[area]['completed'] += 1
            elif order['status'] == 'pending':
                area_stats[area]['pending'] += 1
            elif order['status'] == 'assigned':
                area_stats[area]['assigned'] += 1
        
        # Get agent statistics
        agent_stats = {}
        for order in orders:
            agent_id = order.get('agent_id')
            if agent_id and agent_id not in agent_stats:
                agent_stats[agent_id] = {
                    'total': 0,
                    'completed': 0,
                    'pending': 0,
                    'assigned': 0
                }
            
            if agent_id:
                agent_stats[agent_id]['total'] += 1
                if order['status'] == 'completed':
                    agent_stats[agent_id]['completed'] += 1
                elif order['status'] == 'pending':
                    agent_stats[agent_id]['pending'] += 1
                elif order['status'] == 'assigned':
                    agent_stats[agent_id]['assigned'] += 1
        
        # Get agent names
        agent_names = {}
        if agent_stats:
            agent_ids = list(agent_stats.keys())
            agents_response = supabase.table('users').select('id,username').in_('id', agent_ids).execute()
            
            for agent in agents_response.data:
                agent_names[agent['id']] = agent['username']
        
        return render_template('reports.html',
                            total_orders=total_orders,
                            completed_orders=completed_orders,
                            pending_orders=pending_orders,
                            assigned_orders=assigned_orders,
                            area_stats=area_stats,
                            agent_stats=agent_stats,
                            agent_names=agent_names,
                            from_date=from_date,
                            to_date=to_date)
    except Exception as e:
        flash(f'Error generating reports: {str(e)}')
        return redirect(url_for('admin_dashboard'))

if __name__ == '__main__':
    app.run(debug=True)