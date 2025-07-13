import React, { useState, useEffect, useRef } from 'react';
import io from 'socket.io-client';
import './App.css';

const App = () => {
  const [socket, setSocket] = useState(null);
  const [documents, setDocuments] = useState([]);
  const [currentDoc, setCurrentDoc] = useState(null);
  const [content, setContent] = useState('');
  const [title, setTitle] = useState('');
  const [users, setUsers] = useState([]);
  const [username, setUsername] = useState('');
  const [isConnected, setIsConnected] = useState(false);
  const [cursors, setCursors] = useState({});
  const textareaRef = useRef(null);

  useEffect(() => {
    const newSocket = io('http://localhost:5000');
    setSocket(newSocket);

    newSocket.on('connect', () => {
      setIsConnected(true);
      console.log('Connected to server');
    });

    newSocket.on('disconnect', () => {
      setIsConnected(false);
      console.log('Disconnected from server');
    });

    newSocket.on('document_list', (docs) => {
      setDocuments(docs);
    });

    newSocket.on('document_content', (doc) => {
      setCurrentDoc(doc);
      setContent(doc.content);
      setTitle(doc.title);
    });

    newSocket.on('content_update', (data) => {
      setContent(data.content);
    });

    newSocket.on('users_update', (userList) => {
      setUsers(userList);
    });

    newSocket.on('cursor_update', (data) => {
      setCursors(prev => ({
        ...prev,
        [data.userId]: data.position
      }));
    });

    return () => {
      newSocket.close();
    };
  }, []);

  const handleLogin = () => {
    if (username.trim() && socket) {
      socket.emit('join', { username });
    }
  };

  const createDocument = () => {
    const docTitle = prompt('Enter document title:');
    if (docTitle && socket) {
      socket.emit('create_document', { title: docTitle });
    }
  };

  const openDocument = (docId) => {
    if (socket) {
      socket.emit('join_document', { documentId: docId });
    }
  };

  const handleContentChange = (e) => {
    const newContent = e.target.value;
    setContent(newContent);
    
    if (socket && currentDoc) {
      socket.emit('content_change', {
        documentId: currentDoc._id,
        content: newContent
      });
    }
  };

  const handleCursorMove = (e) => {
    if (socket && currentDoc) {
      const position = e.target.selectionStart;
      socket.emit('cursor_move', {
        documentId: currentDoc._id,
        position: position
      });
    }
  };

  const saveDocument = () => {
    if (socket && currentDoc) {
      socket.emit('save_document', {
        documentId: currentDoc._id,
        content: content,
        title: title
      });
    }
  };

  if (!isConnected) {
    return (
      <div className="loading">
        <h2>Connecting to server...</h2>
      </div>
    );
  }

  if (!username) {
    return (
      <div className="login-container">
        <div className="login-form">
          <h2>Join Collaborative Editor</h2>
          <input
            type="text"
            placeholder="Enter your username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && handleLogin()}
          />
          <button onClick={handleLogin}>Join</button>
        </div>
      </div>
    );
  }

  return (
    <div className="app">
      <div className="sidebar">
        <div className="sidebar-header">
          <h3>Documents</h3>
          <button onClick={createDocument} className="create-btn">
            + New Document
          </button>
        </div>
        
        <div className="document-list">
          {documents.map(doc => (
            <div
              key={doc._id}
              className={`document-item ${currentDoc?._id === doc._id ? 'active' : ''}`}
              onClick={() => openDocument(doc._id)}
            >
              <h4>{doc.title}</h4>
              <p>{new Date(doc.updatedAt).toLocaleDateString()}</p>
            </div>
          ))}
        </div>

        <div className="users-section">
          <h4>Online Users ({users.length})</h4>
          <div className="users-list">
            {users.map(user => (
              <div key={user.id} className="user-item">
                <div className="user-avatar" style={{backgroundColor: user.color}}></div>
                <span>{user.username}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="editor-container">
        {currentDoc ? (
          <>
            <div className="editor-header">
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                className="title-input"
                placeholder="Document title"
              />
              <div className="editor-controls">
                <button onClick={saveDocument} className="save-btn">
                  Save
                </button>
                <span className="status">
                  {isConnected ? 'Connected' : 'Disconnected'}
                </span>
              </div>
            </div>

            <div className="editor-content">
              <textarea
                ref={textareaRef}
                value={content}
                onChange={handleContentChange}
                onSelect={handleCursorMove}
                onKeyUp={handleCursorMove}
                placeholder="Start typing your document..."
                className="content-textarea"
              />
            </div>

            <div className="editor-footer">
              <span>Characters: {content.length}</span>
              <span>Words: {content.split(/\s+/).filter(word => word.length > 0).length}</span>
              <span>Last saved: {currentDoc.updatedAt ? new Date(currentDoc.updatedAt).toLocaleTimeString() : 'Never'}</span>
            </div>
          </>
        ) : (
          <div className="welcome-screen">
            <h2>Welcome to Collaborative Editor</h2>
            <p>Select a document from the sidebar or create a new one to get started.</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default App;