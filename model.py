from pymongo import MongoClient
from datetime import datetime
from bson import ObjectId
import json

class DatabaseManager:
    def __init__(self, connection_string='mongodb://localhost:27017/', database_name='collaborative_editor'):
        self.client = MongoClient(connection_string)
        self.db = self.client[database_name]
        self.documents = self.db.documents
        self.users = self.db.users
        self.sessions = self.db.sessions
        
        # Create indexes for better performance
        self.create_indexes()
    
    def create_indexes(self):
        """Create database indexes for better query performance"""
        try:
            # Index on document title for searching
            self.documents.create_index("title")
            
            # Index on updatedAt for sorting
            self.documents.create_index("updatedAt")
            
            # Index on createdAt
            self.documents.create_index("createdAt")
            
            # Compound index for user sessions
            self.sessions.create_index([("userId", 1), ("documentId", 1)])
            
            print("Database indexes created successfully")
        except Exception as e:
            print(f"Error creating indexes: {e}")

class Document:
    def __init__(self, db_manager):
        self.db = db_manager
        self.collection = db_manager.documents
    
    def create(self, title, content="", creator_id=None):
        """Create a new document"""
        document = {
            "title": title,
            "content": content,
            "createdAt": datetime.now(),
            "updatedAt": datetime.now(),
            "createdBy": creator_id,
            "collaborators": [],
            "version": 1,
            "isPublic": True,
            "tags": [],
            "metadata": {
                "wordCount": len(content.split()) if content else 0,
                "characterCount": len(content) if content else 0,
                "language": "en"
            }
        }
        
        result = self.collection.insert_one(document)
        document['_id'] = str(result.inserted_id)