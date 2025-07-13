from flask import Flask, request
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_cors import CORS
from pymongo import MongoClient
from bson import ObjectId
from datetime import datetime
import os
import json
import random

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
CORS(app, origins="*")
socketio = SocketIO(app, cors_allowed_origins="*", logger=True, engineio_logger=True)

# MongoDB connection
try:
    client = MongoClient('mongodb://localhost:27017/')
    db = client['collaborative_editor']
    documents_collection = db['documents']
    users_collection = db['users']
    print("Connected to MongoDB successfully")
except Exception as e:
    print(f"Error connecting to MongoDB: {e}")
    db = None

# In-memory storage for users and active sessions
active_users = {}
document_sessions = {}

# Helper functions
def get_user_color():
    colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', '#DDA0DD', '#98D8C8']
    return random.choice(colors)

def serialize_document(doc):
    """Convert MongoDB document to JSON serializable format"""
    if doc:
        doc['_id'] = str(doc['_id'])
        return doc
    return None

def get_documents():
    """Get all documents from database"""
    if db:
        docs = list(documents_collection.find().sort('updatedAt', -1))
        return [serialize_document(doc) for doc in docs]
    return []

def get_document(doc_id):
    """Get single document by ID"""
    if db:
        doc = documents_collection.find_one({'_id': ObjectId(doc_id)})
        return serialize_document(doc)
    return None

def create_document(title, content=""):
    """Create new document"""
    if db:
        doc = {
            'title': title,
            'content': content,
            'createdAt': datetime.now(),
            'updatedAt': datetime.now(),
            'collaborators': []
        }
        result = documents_collection.insert_one(doc)
        doc['_id'] = str(result.inserted_id)
        return doc
    return None

def update_document(doc_id, content, title=None):
    """Update document content and/or title"""
    if db:
        update_data = {
            'content': content,
            'updatedAt': datetime.now()
        }
        if title:
            update_data['title'] = title
        
        documents_collection.update_one(
            {'_id': ObjectId(doc_id)},
            {'$set': update_data}
        )
        return get_document(doc_id)
    return None

# Socket event handlers
@socketio.on('connect')
def handle_connect():
    print(f'Client connected: {request.sid}')
    emit('document_list', get_documents())

@socketio.on('disconnect')
def handle_disconnect():
    print(f'Client disconnected: {request.sid}')
    if request.sid in active_users:
        user = active_users[request.sid]
        # Remove user from all document sessions
        for doc_id, session in document_sessions.items():
            if request.sid in session['users']:
                session['users'].pop(request.sid)
                # Notify other users in the document
                socketio.to(doc_id).emit('users_update', list(session['users'].values()))
        
        # Remove user from active users
        active_users.pop(request.sid)

@socketio.on('join')
def handle_join(data):
    username = data['username']
    user_info = {
        'id': request.sid,
        'username': username,
        'color': get_user_color()
    }
    active_users[request.sid] = user_info
    
    # Send updated document list
    emit('document_list', get_documents())
    print(f'User {username} joined with ID {request.sid}')

@socketio.on('create_document')
def handle_create_document(data):
    if request.sid not in active_users:
        return
    
    title = data['title']
    doc = create_document(title)
    
    if doc:
        # Send updated document list to all users
        socketio.emit('document_list', get_documents())
        print(f'Document created: {title}')

@socketio.on('join_document')
def handle_join_document(data):
    if request.sid not in active_users:
        return
    
    doc_id = data['documentId']
    user = active_users[request.sid]
    
    # Leave previous document rooms
    for room_id in document_sessions.keys():
        if request.sid in document_sessions[room_id]['users']:
            leave_room(room_id)
            document_sessions[room_id]['users'].pop(request.sid)
            socketio.to(room_id).emit('users_update', list(document_sessions[room_id]['users'].values()))
    
    # Join new document room
    join_room(doc_id)
    
    # Initialize document session if it doesn't exist
    if doc_id not in document_sessions:
        document_sessions[doc_id] = {
            'users': {},
            'content': ''
        }
    
    # Add user to document session
    document_sessions[doc_id]['users'][request.sid] = user
    
    # Get document content
    doc = get_document(doc_id)
    if doc:
        emit('document_content', doc)
        # Update document session content
        document_sessions[doc_id]['content'] = doc['content']
    
    # Send updated user list to all users in the document
    socketio.to(doc_id).emit('users_update', list(document_sessions[doc_id]['users'].values()))
    
    print(f'User {user["username"]} joined document {doc_id}')

@socketio.on('content_change')
def handle_content_change(data):
    if request.sid not in active_users:
        return
    
    doc_id = data['documentId']
    content = data['content']
    
    # Update document session content
    if doc_id in document_sessions:
        document_sessions[doc_id]['content'] = content
    
    # Broadcast content change to all users in the document except sender
    socketio.to(doc_id).emit('content_update', {
        'content': content,
        'userId': request.sid
    }, include_self=False)
    
    print(f'Content updated for document {doc_id}')

@socketio.on('save_document')
def handle_save_document(data):
    if request.sid not in active_users:
        return
    
    doc_id = data['documentId']
    content = data['content']
    title = data.get('title')
    
    # Update document in database
    updated_doc = update_document(doc_id, content, title)
    
    if updated_doc:
        # Send updated document to all users in the document
        socketio.to(doc_id).emit('document_content', updated_doc)
        # Send updated document list to all users
        socketio.emit('document_list', get_documents())
        print(f'Document {doc_id} saved')

@socketio.on('cursor_move')
def handle_cursor_move(data):
    if request.sid not in active_users:
        return
    
    doc_id = data['documentId']
    position = data['position']
    
    # Broadcast cursor position to all users in the document except sender
    socketio.to(doc_id).emit('cursor_update', {
        'userId': request.sid,
        'position': position,
        'user': active_users[request.sid]
    }, include_self=False)

# REST API endpoints (optional - for external integrations)
@app.route('/api/documents', methods=['GET'])
def api_get_documents():
    return {'documents': get_documents()}

@app.route('/api/documents/<doc_id>', methods=['GET'])
def api_get_document(doc_id):
    doc = get_document(doc_id)
    if doc:
        return {'document': doc}
    return {'error': 'Document not found'}, 404

@app.route('/api/documents', methods=['POST'])
def api_create_document():
    data = request.get_json()
    title = data.get('title', 'Untitled Document')
    content = data.get('content', '')
    
    doc = create_document(title, content)
    if doc:
        return {'document': doc}, 201
    return {'error': 'Failed to create document'}, 500

@app.route('/api/documents/<doc_id>', methods=['PUT'])
def api_update_document(doc_id):
    data = request.get_json()
    content = data.get('content', '')
    title = data.get('title')
    
    doc = update_document(doc_id, content, title)
    if doc:
        return {'document': doc}
    return {'error': 'Failed to update document'}, 500

@app.route('/health', methods=['GET'])
def health_check():
    return {'status': 'healthy', 'database': 'connected' if db else 'disconnected'}

if __name__ == '__main__':
    print("Starting Collaborative Document Editor Server...")
    print("Make sure MongoDB is running on localhost:27017")
    socketio.run(app, debug=True, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)