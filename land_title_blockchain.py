#!/usr/bin/env python3
import hashlib
import json
import time
import os
import pickle
from datetime import datetime
from typing import List, Dict, Any, Optional
from flask import Flask, render_template_string, request, jsonify, redirect, url_for

# ==================== BLOCKCHAIN CORE ====================

class Block:
    def __init__(self, index: int, property_data: Dict[str, Any], previous_hash: str, timestamp: float = None):
        self.index = index
        self.timestamp = timestamp or time.time()
        self.property_data = property_data
        self.previous_hash = previous_hash
        self.nonce = 0
        self.hash = self.calculate_hash()
    
    def calculate_hash(self) -> str:
        block_string = json.dumps({
            "index": self.index,
            "timestamp": self.timestamp,
            "property_data": self.property_data,
            "previous_hash": self.previous_hash,
            "nonce": self.nonce
        }, sort_keys=True, default=str)
        return hashlib.sha256(block_string.encode()).hexdigest()
    
    def mine_block(self, difficulty: int):
        target = "0" * difficulty
        while self.hash[:difficulty] != target:
            self.nonce += 1
            self.hash = self.calculate_hash()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "timestamp": self.timestamp,
            "property_data": self.property_data,
            "previous_hash": self.previous_hash,
            "hash": self.hash,
            "nonce": self.nonce
        }

class LandTitleBlockchain:
    def __init__(self, chain_file: str = "land_title_data.pkl"):
        self.chain_file = chain_file
        self.chain: List[Block] = []
        self.difficulty = 2
        self.pending_transactions: List[Dict[str, Any]] = []
        self.load_chain()
        
        if not self.chain:
            self.create_genesis_block()
    
    def create_genesis_block(self):
        print("Creating genesis block for Land Title Registry...")
        genesis_data = {
            "property_id": "0",
            "owner": "Government Land Registry",
            "parcel_id": "GENESIS-0000",
            "coordinates": "0,0",
            "area_sqft": 0,
            "property_type": "System Block",
            "transaction_type": "genesis",
            "timestamp": datetime.now().isoformat(),
            "description": "Initial block in land title blockchain"
        }
        genesis_block = Block(0, genesis_data, "0")
        genesis_block.mine_block(self.difficulty)
        self.chain.append(genesis_block)
        self.save_chain()
        print("Genesis block created successfully!")
    
    def register_property(self, property_data: Dict[str, Any]) -> bool:
        required_fields = ["property_id", "owner", "parcel_id", "coordinates", "area_sqft", "property_type"]
        
        for field in required_fields:
            if field not in property_data:
                raise ValueError(f"Missing required field: {field}")
        
        # Add metadata
        property_data["transaction_id"] = self.generate_transaction_id()
        property_data["timestamp"] = datetime.now().isoformat()
        property_data["blockchain_timestamp"] = time.time()
        property_data["transaction_type"] = "initial_registration"
        property_data["previous_owners"] = []
        
        self.pending_transactions.append(property_data)
        return True
    
    def transfer_property(self, property_id: str, new_owner: str, sale_price: float = None):
        """Transfer property to new owner"""
        # Find the current property record
        current_record = self.get_current_property_record(property_id)
        if not current_record:
            raise ValueError(f"Property {property_id} not found")
        
        # Create transfer record
        transfer_data = current_record.copy()
        transfer_data["previous_owners"] = transfer_data.get("previous_owners", []) + [{
            "owner": current_record["owner"],
            "until": datetime.now().isoformat()
        }]
        transfer_data["owner"] = new_owner
        transfer_data["transaction_type"] = "transfer"
        transfer_data["sale_price"] = sale_price
        transfer_data["transaction_id"] = self.generate_transaction_id()
        transfer_data["timestamp"] = datetime.now().isoformat()
        transfer_data["blockchain_timestamp"] = time.time()
        
        self.pending_transactions.append(transfer_data)
        return True
    
    def generate_transaction_id(self) -> str:
        return hashlib.sha256(f"{time.time()}{len(self.pending_transactions)}".encode()).hexdigest()[:16]
    
    def mine_pending_transactions(self) -> List[Block]:
        if not self.pending_transactions:
            return []
        
        mined_blocks = []
        print(f"Mining {len(self.pending_transactions)} pending transactions...")
        
        for transaction in self.pending_transactions:
            new_block = Block(
                index=len(self.chain),
                property_data=transaction,
                previous_hash=self.get_latest_block().hash
            )
            print(f"Mining block #{new_block.index}...")
            new_block.mine_block(self.difficulty)
            self.chain.append(new_block)
            mined_blocks.append(new_block)
            print(f"✓ Block #{new_block.index} mined successfully! Hash: {new_block.hash[:16]}...")
        
        self.pending_transactions = []
        self.save_chain()
        print(f"✓ All blocks mined! Total chain length: {len(self.chain)}")
        return mined_blocks
    
    def get_latest_block(self) -> Block:
        return self.chain[-1]
    
    def is_chain_valid(self) -> Dict[str, Any]:
        issues = []
        
        for i in range(1, len(self.chain)):
            current_block = self.chain[i]
            previous_block = self.chain[i-1]
            
            if current_block.hash != current_block.calculate_hash():
                issues.append(f"Block #{current_block.index} has invalid hash")
            
            if current_block.previous_hash != previous_block.hash:
                issues.append(f"Block #{current_block.index} has invalid previous hash")
        
        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "chain_length": len(self.chain)
        }
    
    def get_property_history(self, property_id: str) -> List[Dict[str, Any]]:
        property_history = []
        for block in self.chain[1:]:  # Skip genesis block
            if block.property_data.get("property_id") == property_id:
                property_history.append(block.property_data)
        return property_history
    
    def get_current_property_record(self, property_id: str) -> Optional[Dict[str, Any]]:
        history = self.get_property_history(property_id)
        return history[-1] if history else None
    
    def get_all_properties(self) -> List[str]:
        properties = set()
        for block in self.chain[1:]:
            properties.add(block.property_data["property_id"])
        return sorted(list(properties))
    
    def verify_ownership(self, property_id: str, owner_name: str) -> Dict[str, Any]:
        current_record = self.get_current_property_record(property_id)
        if not current_record:
            return {"verified": False, "error": "Property not found"}
        
        is_owner = current_record["owner"].lower() == owner_name.lower()
        return {
            "verified": is_owner,
            "current_owner": current_record["owner"],
            "property_id": property_id,
            "parcel_id": current_record["parcel_id"],
            "verification_date": datetime.now().isoformat()
        }
    
    def search_properties_by_owner(self, owner_name: str) -> List[Dict[str, Any]]:
        owner_properties = []
        for prop_id in self.get_all_properties():
            current_record = self.get_current_property_record(prop_id)
            if current_record and current_record["owner"].lower() == owner_name.lower():
                owner_properties.append(current_record)
        return owner_properties
    
    def get_blockchain_stats(self) -> Dict[str, Any]:
        validity = self.is_chain_valid()
        return {
            "total_blocks": len(self.chain),
            "total_property_records": len(self.chain) - 1,
            "total_unique_properties": len(self.get_all_properties()),
            "pending_transactions": len(self.pending_transactions),
            "chain_validity": validity,
            "difficulty": self.difficulty
        }
    
    def save_chain(self):
        with open(self.chain_file, 'wb') as f:
            pickle.dump(self.chain, f)
    
    def load_chain(self):
        if os.path.exists(self.chain_file):
            print(f"Loading blockchain from {self.chain_file}...")
            with open(self.chain_file, 'rb') as f:
                self.chain = pickle.load(f)
            print(f"✓ Land title blockchain loaded with {len(self.chain)} blocks")
        else:
            print("No existing blockchain found. Starting fresh...")

# ==================== FLASK WEB APP ====================

app = Flask(__name__)
app.secret_key = 'land-title-blockchain-secret-key-2024'

# Initialize blockchain
blockchain = LandTitleBlockchain()

# ==================== HTML TEMPLATES ====================

BASE_HTML = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Land Title Registry Blockchain</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background-color: #f8f9fa; }
        .navbar { margin-bottom: 20px; }
        .card { margin-bottom: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
        .property-card { border-left: 4px solid #0d6efd; }
        .transfer-card { border-left: 4px solid #198754; }
        .verified { color: #198754; }
        .not-verified { color: #dc3545; }
        .history-timeline { border-left: 2px solid #0d6efd; padding-left: 20px; }
    </style>
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-primary">
        <div class="container">
            <a class="navbar-brand" href="/">🏠 Land Title Registry Blockchain</a>
            <div class="navbar-nav">
                <a class="nav-link" href="/">Dashboard</a>
                <a class="nav-link" href="/register">Register Property</a>
                <a class="nav-link" href="/transfer">Transfer Property</a>
                <a class="nav-link" href="/verify">Verify Ownership</a>
                <a class="nav-link" href="/properties">All Properties</a>
                <a class="nav-link" href="/mine">Mine Transactions</a>
            </div>
        </div>
    </nav>

    <div class="container mt-4">
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="alert alert-{{ 'danger' if category == 'error' else 'success' }} alert-dismissible fade show">
                        {{ message }}
                        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                    </div>
                {% endfor %}
            {% endif %}
        {% endwith %}

        {% block content %}{% endblock %}
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
'''

INDEX_HTML = BASE_HTML.replace('{% block content %}{% endblock %}', '''
<div class="row">
    <div class="col-md-8">
        <h1>Land Title Registry Blockchain</h1>
        <p class="lead">Secure, immutable property records using blockchain technology</p>
        <p class="text-muted">No gas fees • Instant transfers • Fraud prevention</p>
    </div>
</div>

<div class="row mt-4">
    <div class="col-md-3">
        <div class="card text-white bg-primary mb-3">
            <div class="card-body">
                <h5 class="card-title">{{ stats.total_blocks }}</h5>
                <p class="card-text">Total Blocks</p>
            </div>
        </div>
    </div>
    <div class="col-md-3">
        <div class="card text-white bg-success mb-3">
            <div class="card-body">
                <h5 class="card-title">{{ stats.total_property_records }}</h5>
                <p class="card-text">Property Records</p>
            </div>
        </div>
    </div>
    <div class="col-md-3">
        <div class="card text-white bg-warning mb-3">
            <div class="card-body">
                <h5 class="card-title">{{ stats.total_unique_properties }}</h5>
                <p class="card-text">Unique Properties</p>
            </div>
        </div>
    </div>
    <div class="col-md-3">
        <div class="card text-white bg-info mb-3">
            <div class="card-body">
                <h5 class="card-title">{{ stats.pending_transactions }}</h5>
                <p class="card-text">Pending Transactions</p>
            </div>
        </div>
    </div>
</div>

<div class="row mt-4">
    <div class="col-md-6">
        <div class="card">
            <div class="card-header">
                <h5>Quick Actions</h5>
            </div>
            <div class="card-body">
                <div class="d-grid gap-2">
                    <a href="/register" class="btn btn-primary">Register New Property</a>
                    <a href="/transfer" class="btn btn-success">Transfer Property</a>
                    <a href="/verify" class="btn btn-info">Verify Ownership</a>
                    <a href="/properties" class="btn btn-secondary">View All Properties</a>
                    <a href="/mine" class="btn btn-warning">Mine Pending Transactions</a>
                </div>
            </div>
        </div>
    </div>
    
    <div class="col-md-6">
        <div class="card">
            <div class="card-header">
                <h5>Blockchain Status</h5>
            </div>
            <div class="card-body">
                <p><strong>Chain Valid:</strong> 
                    <span class="badge bg-{{ 'success' if stats.chain_validity.valid else 'danger' }}">
                        {{ stats.chain_validity.valid }}
                    </span>
                </p>
                <p><strong>Difficulty:</strong> {{ stats.difficulty }}</p>
                <p><strong>Last Block:</strong> #{{ stats.total_blocks - 1 }}</p>
                
                {% if not stats.chain_validity.valid %}
                    <div class="alert alert-danger">
                        <strong>Chain Integrity Issues:</strong>
                        <ul>
                            {% for issue in stats.chain_validity.issues %}
                                <li>{{ issue }}</li>
                            {% endfor %}
                        </ul>
                    </div>
                {% else %}
                    <div class="alert alert-success">
                        <strong>✓ Blockchain integrity verified!</strong>
                    </div>
                {% endif %}
            </div>
        </div>
    </div>
</div>

<div class="row mt-4">
    <div class="col-12">
        <div class="card">
            <div class="card-header">
                <h5>Benefits of Land Title Blockchain</h5>
            </div>
            <div class="card-body">
                <div class="row">
                    <div class="col-md-6">
                        <ul>
                            <li>✅ <strong>Prevents Property Fraud</strong> - Immutable records</li>
                            <li>✅ <strong>Eliminates Notary Fees</strong> - Digital verification</li>
                            <li>✅ <strong>Instant Title Transfers</strong> - No waiting periods</li>
                        </ul>
                    </div>
                    <div class="col-md-6">
                        <ul>
                            <li>✅ <strong>Transparent Ownership History</strong> - Complete audit trail</li>
                            <li>✅ <strong>No Gas Fees</strong> - Free for citizens</li>
                            <li>✅ <strong>Secure & Tamper-Proof</strong> - Cryptographic security</li>
                        </ul>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>
''')

REGISTER_HTML = BASE_HTML.replace('{% block content %}{% endblock %}', '''
<div class="row">
    <div class="col-md-8 mx-auto">
        <div class="card">
            <div class="card-header">
                <h4>Register New Property</h4>
            </div>
            <div class="card-body">
                <form method="POST">
                    <div class="row">
                        <div class="col-md-6">
                            <div class="mb-3">
                                <label for="property_id" class="form-label">Property ID *</label>
                                <input type="text" class="form-control" id="property_id" name="property_id" required 
                                       placeholder="e.g., PROP-001">
                            </div>
                        </div>
                        <div class="col-md-6">
                            <div class="mb-3">
                                <label for="parcel_id" class="form-label">Parcel ID *</label>
                                <input type="text" class="form-control" id="parcel_id" name="parcel_id" required
                                       placeholder="e.g., PARCEL-12345">
                            </div>
                        </div>
                    </div>
                    
                    <div class="mb-3">
                        <label for="owner" class="form-label">Owner Name *</label>
                        <input type="text" class="form-control" id="owner" name="owner" required
                               placeholder="Full legal name">
                    </div>
                    
                    <div class="row">
                        <div class="col-md-6">
                            <div class="mb-3">
                                <label for="coordinates" class="form-label">Coordinates *</label>
                                <input type="text" class="form-control" id="coordinates" name="coordinates" required
                                       placeholder="e.g., 40.7128°N, 74.0060°W">
                            </div>
                        </div>
                        <div class="col-md-6">
                            <div class="mb-3">
                                <label for="area_sqft" class="form-label">Area (sq ft) *</label>
                                <input type="number" class="form-control" id="area_sqft" name="area_sqft" required
                                       placeholder="e.g., 2500">
                            </div>
                        </div>
                    </div>
                    
                    <div class="mb-3">
                        <label for="property_type" class="form-label">Property Type *</label>
                        <select class="form-select" id="property_type" name="property_type" required>
                            <option value="">Select Type</option>
                            <option value="residential">Residential</option>
                            <option value="commercial">Commercial</option>
                            <option value="industrial">Industrial</option>
                            <option value="agricultural">Agricultural</option>
                            <option value="vacant_land">Vacant Land</option>
                        </select>
                    </div>
                    
                    <div class="mb-3">
                        <label for="description" class="form-label">Property Description</label>
                        <textarea class="form-control" id="description" name="description" rows="3"
                                  placeholder="Additional details about the property..."></textarea>
                    </div>
                    
                    <div class="d-grid">
                        <button type="submit" class="btn btn-primary">Register Property</button>
                    </div>
                </form>
            </div>
        </div>
        
        <div class="card mt-4">
            <div class="card-header">
                <h5>Sample Property IDs for Testing</h5>
            </div>
            <div class="card-body">
                <ul>
                    <li><strong>PROP-001</strong> - 123 Main Street</li>
                    <li><strong>PROP-002</strong> - 456 Oak Avenue</li>
                    <li><strong>PROP-003</strong> - 789 Pine Road</li>
                    <li><strong>PROP-004</strong> - 321 Elm Boulevard</li>
                </ul>
            </div>
        </div>
    </div>
</div>
''')

# ==================== FLASK ROUTES ====================

@app.route('/')
def index():
    stats = blockchain.get_blockchain_stats()
    return render_template_string(INDEX_HTML, stats=stats)

@app.route('/register', methods=['GET', 'POST'])
def register_property():
    if request.method == 'POST':
        try:
            property_data = {
                "property_id": request.form['property_id'],
                "owner": request.form['owner'],
                "parcel_id": request.form['parcel_id'],
                "coordinates": request.form['coordinates'],
                "area_sqft": int(request.form['area_sqft']),
                "property_type": request.form['property_type'],
                "description": request.form.get('description', '')
            }
            
            blockchain.register_property(property_data)
            return '''
            <script>
                alert("Property registered successfully! Ready for mining.");
                window.location.href = "/mine";
            </script>
            '''
            
        except Exception as e:
            return f'''
            <script>
                alert("Error registering property: {str(e)}");
                window.location.href = "/register";
            </script>
            '''
    
    return render_template_string(REGISTER_HTML)

@app.route('/transfer', methods=['GET', 'POST'])
def transfer_property():
    if request.method == 'POST':
        try:
            property_id = request.form['property_id']
            new_owner = request.form['new_owner']
            sale_price = request.form.get('sale_price')
            
            blockchain.transfer_property(
                property_id, 
                new_owner, 
                float(sale_price) if sale_price else None
            )
            
            return '''
            <script>
                alert("Property transfer initiated! Ready for mining.");
                window.location.href = "/mine";
            </script>
            '''
            
        except Exception as e:
            return f'''
            <script>
                alert("Error transferring property: {str(e)}");
                window.location.href = "/transfer";
            </script>
            '''
    
    # For GET request, show transfer form
    transfer_html = BASE_HTML.replace('{% block content %}{% endblock %}', '''
    <div class="row">
        <div class="col-md-8 mx-auto">
            <div class="card">
                <div class="card-header">
                    <h4>Transfer Property Ownership</h4>
                </div>
                <div class="card-body">
                    <form method="POST">
                        <div class="mb-3">
                            <label for="property_id" class="form-label">Property ID *</label>
                            <input type="text" class="form-control" id="property_id" name="property_id" required
                                   placeholder="e.g., PROP-001">
                        </div>
                        
                        <div class="mb-3">
                            <label for="new_owner" class="form-label">New Owner Name *</label>
                            <input type="text" class="form-control" id="new_owner" name="new_owner" required
                                   placeholder="Full legal name of new owner">
                        </div>
                        
                        <div class="mb-3">
                            <label for="sale_price" class="form-label">Sale Price (Optional)</label>
                            <input type="number" class="form-control" id="sale_price" name="sale_price"
                                   placeholder="e.g., 350000">
                        </div>
                        
                        <div class="d-grid">
                            <button type="submit" class="btn btn-success">Transfer Property</button>
                        </div>
                    </form>
                </div>
            </div>
        </div>
    </div>
    ''')
    
    return render_template_string(transfer_html)

@app.route('/verify', methods=['GET', 'POST'])
def verify_ownership():
    if request.method == 'POST':
        property_id = request.form['property_id']
        owner_name = request.form['owner_name']
        result = blockchain.verify_ownership(property_id, owner_name)
        
        # Fixed template with proper Jinja2 syntax
        verify_html = BASE_HTML.replace('{% block content %}{% endblock %}', f'''
        <div class="row">
            <div class="col-md-8 mx-auto">
                <div class="card">
                    <div class="card-header">
                        <h4>Ownership Verification Result</h4>
                    </div>
                    <div class="card-body">
                        <h5>Property: {property_id}</h5>
                        <h5>Claimed Owner: {owner_name}</h5>
                        <hr>
                        
                        {'<div class="alert alert-success"><h4>✅ Ownership Verified!</h4><p><strong>Current Owner:</strong> ' + result["current_owner"] + '</p><p><strong>Parcel ID:</strong> ' + result["parcel_id"] + '</p><p><strong>Verification Date:</strong> ' + result["verification_date"] + '</p></div>' if result["verified"] else '<div class="alert alert-danger"><h4>❌ Ownership Not Verified</h4><p><strong>Current Owner:</strong> ' + result.get("current_owner", "Unknown") + '</p><p><strong>Error:</strong> ' + result.get("error", "Verification failed") + '</p></div>'}
                        
                        <div class="mt-3">
                            <a href="/verify" class="btn btn-primary">Verify Another Property</a>
                            <a href="/" class="btn btn-secondary">Back to Dashboard</a>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        ''')
        
        return render_template_string(verify_html)
    
    # GET request - show verification form
    verify_form_html = BASE_HTML.replace('{% block content %}{% endblock %}', '''
    <div class="row">
        <div class="col-md-8 mx-auto">
            <div class="card">
                <div class="card-header">
                    <h4>Verify Property Ownership</h4>
                </div>
                <div class="card-body">
                    <form method="POST">
                        <div class="mb-3">
                            <label for="property_id" class="form-label">Property ID *</label>
                            <input type="text" class="form-control" id="property_id" name="property_id" required
                                   placeholder="e.g., PROP-001">
                        </div>
                        
                        <div class="mb-3">
                            <label for="owner_name" class="form-label">Owner Name *</label>
                            <input type="text" class="form-control" id="owner_name" name="owner_name" required
                                   placeholder="Full legal name to verify">
                        </div>
                        
                        <div class="d-grid">
                            <button type="submit" class="btn btn-primary">Verify Ownership</button>
                        </div>
                    </form>
                </div>
            </div>
        </div>
    </div>
    ''')
    
    return render_template_string(verify_form_html)
    
    # GET request - show verification form
    verify_form_html = BASE_HTML.replace('{% block content %}{% endblock %}', '''
    <div class="row">
        <div class="col-md-8 mx-auto">
            <div class="card">
                <div class="card-header">
                    <h4>Verify Property Ownership</h4>
                </div>
                <div class="card-body">
                    <form method="POST">
                        <div class="mb-3">
                            <label for="property_id" class="form-label">Property ID *</label>
                            <input type="text" class="form-control" id="property_id" name="property_id" required
                                   placeholder="e.g., PROP-001">
                        </div>
                        
                        <div class="mb-3">
                            <label for="owner_name" class="form-label">Owner Name *</label>
                            <input type="text" class="form-control" id="owner_name" name="owner_name" required
                                   placeholder="Full legal name to verify">
                        </div>
                        
                        <div class="d-grid">
                            <button type="submit" class="btn btn-primary">Verify Ownership</button>
                        </div>
                    </form>
                </div>
            </div>
        </div>
    </div>
    ''')
    
    return render_template_string(verify_form_html)

@app.route('/properties')
def list_properties():
    properties = []
    for prop_id in blockchain.get_all_properties():
        current_record = blockchain.get_current_property_record(prop_id)
        if current_record:
            properties.append(current_record)
    
    properties_html = BASE_HTML.replace('{% block content %}{% endblock %}', f'''
    <div class="row">
        <div class="col-12">
            <div class="card">
                <div class="card-header">
                    <h4>All Registered Properties</h4>
                </div>
                <div class="card-body">
                    <div class="table-responsive">
                        <table class="table table-striped">
                            <thead>
                                <tr>
                                    <th>Property ID</th>
                                    <th>Owner</th>
                                    <th>Parcel ID</th>
                                    <th>Type</th>
                                    <th>Area (sq ft)</th>
                                    <th>Coordinates</th>
                                    <th>Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {"".join([f'''
                                <tr>
                                    <td><strong>{prop['property_id']}</strong></td>
                                    <td>{prop['owner']}</td>
                                    <td>{prop['parcel_id']}</td>
                                    <td><span class="badge bg-info">{prop['property_type']}</span></td>
                                    <td>{prop['area_sqft']}</td>
                                    <td><small>{prop['coordinates']}</small></td>
                                    <td>
                                        <a href="/property/{prop['property_id']}" class="btn btn-sm btn-primary">View History</a>
                                    </td>
                                </tr>
                                ''' for prop in properties])}
                            </tbody>
                        </table>
                    </div>
                    
                    <div class="mt-3">
                        <strong>Total Properties:</strong> {len(properties)}
                    </div>
                </div>
            </div>
        </div>
    </div>
    ''')
    
    return render_template_string(properties_html)

@app.route('/property/<property_id>')
def property_history(property_id):
    history = blockchain.get_property_history(property_id)
    current_record = blockchain.get_current_property_record(property_id)
    
    if not current_record:
        return f'''
        <script>
            alert("Property {property_id} not found!");
            window.location.href = "/properties";
        </script>
        '''
    
    history_html = BASE_HTML.replace('{% block content %}{% endblock %}', f'''
    <div class="row">
        <div class="col-md-10 mx-auto">
            <div class="card">
                <div class="card-header bg-primary text-white">
                    <h4>Property History: {property_id}</h4>
                </div>
                <div class="card-body">
                    <div class="row mb-4">
                        <div class="col-md-6">
                            <h5>Current Information</h5>
                            <p><strong>Owner:</strong> {current_record['owner']}</p>
                            <p><strong>Parcel ID:</strong> {current_record['parcel_id']}</p>
                            <p><strong>Type:</strong> {current_record['property_type']}</p>
                        </div>
                        <div class="col-md-6">
                            <h5>Property Details</h5>
                            <p><strong>Area:</strong> {current_record['area_sqft']} sq ft</p>
                            <p><strong>Coordinates:</strong> {current_record['coordinates']}</p>
                            <p><strong>Description:</strong> {current_record.get('description', 'N/A')}</p>
                        </div>
                    </div>
                    
                    <h5>Ownership History Timeline</h5>
                    <div class="history-timeline">
                        {"".join([f'''
                        <div class="card mb-3 {'property-card' if record['transaction_type'] == 'initial_registration' else 'transfer-card'}">
                            <div class="card-body">
                                <h6 class="card-title">
                                    {'🏠 Registered' if record['transaction_type'] == 'initial_registration' else '🔄 Transferred'} 
                                    to {record['owner']}
                                </h6>
                                <p class="card-text">
                                    <small class="text-muted">
                                        {record['timestamp']}
                                        {f"• Sale Price: ${record.get('sale_price', 'N/A')}" if record.get('sale_price') else ''}
                                    </small>
                                </p>
                                <p class="card-text">{record.get('description', '')}</p>
                            </div>
                        </div>
                        ''' for record in reversed(history)])}
                    </div>
                </div>
            </div>
            
            <div class="text-center mt-3">
                <a href="/properties" class="btn btn-secondary">Back to Properties</a>
                <a href="/transfer" class="btn btn-success">Transfer This Property</a>
            </div>
        </div>
    </div>
    ''')
    
    return render_template_string(history_html)

@app.route('/mine')
def mine_transactions():
    mined_blocks = blockchain.mine_pending_transactions()
    if mined_blocks:
        message = f"Successfully mined {len(mined_blocks)} new property transactions!"
    else:
        message = "No pending transactions to mine."
    
    return f'''
    <script>
        alert("{message}");
        window.location.href = "/";
    </script>
    '''

# ==================== DEMO DATA ====================

def add_demo_data():
    """Add sample property records for testing"""
    demo_properties = [
        {
            "property_id": "PROP-001",
            "owner": "Joan Mugure",
            "parcel_id": "PARCEL-1001",
            "coordinates": "40.7128°N, 74.0060°W",
            "area_sqft": 2500,
            "property_type": "residential",
            "description": "Studio Apartments"
        },
        {
            "property_id": "PROP-002",
            "owner": "Griffin Imbwaka",
            "parcel_id": "PARCEL-1002", 
            "coordinates": "34.0522°N, 118.2437°W",
            "area_sqft": 5000,
            "property_type": "commercial",
            "description": "Office Building"
        },
        {
            "property_id": "PROP-003",
            "owner": "Shirley Kerubo",
            "parcel_id": "PARCEL-1003",
            "coordinates": "41.8781°N, 87.6298°W", 
            "area_sqft": 10000,
            "property_type": "industrial",
            "description": "Storage and Distribution"
        }
    ]
    
    added_count = 0
    for prop in demo_properties:
        try:
            blockchain.register_property(prop)
            added_count += 1
        except:
            pass
    
    if added_count > 0:
        blockchain.mine_pending_transactions()
        print(f"✓ Added {added_count} demo properties to blockchain")
        
        # Add a transfer for demo
        try:
            blockchain.transfer_property("PROP-001", "Joan Mugure", 350000)
            blockchain.mine_pending_transactions()
            print("✓ Added demo property transfer")
        except:
            pass

# ==================== MAIN EXECUTION ====================

if __name__ == '__main__':
    print("🏠 Land Title Registry Blockchain System")
    print("=" * 50)
    
    # Add demo data if blockchain is empty (only genesis block)
    if len(blockchain.chain) == 1:
        print("Adding demo property records...")
        add_demo_data()
    
    stats = blockchain.get_blockchain_stats()
    print(f"📊 Blockchain Status:")
    print(f"   • Total Blocks: {stats['total_blocks']}")
    print(f"   • Property Records: {stats['total_property_records']}") 
    print(f"   • Unique Properties: {stats['total_unique_properties']}")
    print(f"   • Chain Valid: {stats['chain_validity']['valid']}")
    print(f"   • Pending Transactions: {stats['pending_transactions']}")
    
    print("\n🌐 Starting web server...")
    print("   Access the system at: http://localhost:5000")
    print("   Press Ctrl+C to stop the server")
    print("=" * 50)
    
    app.run(debug=True, host='0.0.0.0', port=5000)