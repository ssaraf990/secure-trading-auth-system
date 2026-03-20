"""
🧠 Microsoft Threat Modeling (STRIDE) Routes
Flask Blueprint for threat modeling endpoints
"""
import json
import os
from flask import Blueprint, jsonify, send_from_directory

threat_bp = Blueprint('threats', __name__, url_prefix='/api/threats')

@threat_bp.route('/', methods=['GET'])
def get_threat_model():
    """🧠 Get the threat model JSON"""
    try:
        threat_model_path = os.path.join(
            os.path.dirname(__file__),
            'threat_model.json'
        )
        with open(threat_model_path, 'r') as f:
            threat_model = json.load(f)
        return jsonify({
            'success': True,
            'threat_model': threat_model
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@threat_bp.route('/components', methods=['GET'])
def get_components():
    """🧠 Get threat components"""
    try:
        threat_model_path = os.path.join(
            os.path.dirname(__file__),
            'threat_model.json'
        )
        with open(threat_model_path, 'r') as f:
            threat_model = json.load(f)
        return jsonify({
            'success': True,
            'components': threat_model.get('components', {})
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@threat_bp.route('/stride', methods=['GET'])
def get_stride():
    """🧠 Get STRIDE categories"""
    try:
        threat_model_path = os.path.join(
            os.path.dirname(__file__),
            'threat_model.json'
        )
        with open(threat_model_path, 'r') as f:
            threat_model = json.load(f)
        return jsonify({
            'success': True,
            'stride': threat_model.get('stride_categories', {})
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
