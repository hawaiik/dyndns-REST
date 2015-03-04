#!/usr/bin/env python
from flask import Flask, jsonify, abort, make_response, request
from pymongo import Connection
import json
from bson import json_util
from pwgen import pwgen
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)
app.config.from_pyfile('config.cfg')
connection = Connection('localhost', 27017)
db = connection.mydb

@app.route('/')
def index():
    return "Hello, World!"

@app.route('/ddns',methods=['GET'])
def get_subdomains():
	if not 'token' in request.args or \
	not check_password_hash(app.config['TOKEN'],request.args['token']):
		abort(401)
	results = db['subdomains'].find({ }, { 'subdomain': 1, 'ip': 1, '_id': 0 })
	json_results = []
	for result in results:
		json_results.append(result)
	return toJson(json_results)

@app.route('/ddns/info/<subdomain>',methods=['GET'])
def get_subdomain(subdomain):
	if not 'token' in request.args or \
	not check_password_hash(app.config['TOKEN'],request.args['token']):
		abort(401)
	result = db['subdomains'].find_one({'subdomain':subdomain},\
		{'subdomain':1,'ip':1,'_id':0})
	if result is None:
		abort(404)
	return toJson(result)

@app.route('/ddns/create',methods=['POST'])
def create_subdomain():
	if not 'token' in request.json or \
	not check_password_hash(app.config['TOKEN'],request.json['token']):
		abort(401)
	status = 'created'
	if not request.json or not 'subdomain' in request.json or \
	not 'username' in request.json:
		return jsonify({'Comment': 'To create a subdomain, send...'}),400
	if checksub(request.json['subdomain']):
		return jsonify({'Comment':'Subdomain already exists'}),400
	password = pwgen(10, no_symbols=True)
	entry = {
		'subdomain': request.json['subdomain'],
		'username': request.json['username'],
		'password': generate_password_hash(password),
		'ip': '',
		'last_update': '',
		'created': datetime.utcnow()
	}
	db['subdomains'].insert(entry)
	return jsonify({'state':'created','subdomain':entry['subdomain'],\
		'username':entry['username'],'password':password}),201

@app.route('/ddns/update',methods=['GET'])
def update_subdomain():
	if not 'subdomain' in request.args or not 'username' in request.args or \
	not 'password' in request.args:
		return jsonify({'Comment': 'To update a subdomain, send...'}),400
	entry = getEntry(request.args['subdomain'])
	if len(entry) == 0:
		abort(404)
	if not request.args['username']	== entry['username'] or \
	not check_password_hash(entry['password'],request.args['password']):
		abort(401)
	if 'ip' in request.args:
		ip = request.args['ip']
	else:
		ip = request.environ['REMOTE_ADDR']
	db['subdomains'].update({'subdomain':entry['subdomain']},\
		{'$set':{'ip':ip,'last_update':datetime.utcnow()}},\
		upsert=False, multi=False)
	return jsonify({'result':'Subdomain updated.'})

@app.route('/ddns/delete/<subdomain>', methods=['DELETE'])
def delete_subdomain(subdomain):
	if not 'token' in request.args or \
	not check_password_hash(app.config['TOKEN'],request.args['token']):
		abort(401)
	if checksub(subdomain):
		db['subdomains'].remove({'subdomain':subdomain})
		return jsonify({'result':'Subdomain deleted.'})
	abort(404)

def getEntry(subdomain):
	entry = db['subdomains'].find_one({'subdomain':subdomain})
	if entry is None:
		entry = []
		return entry
	return entry

def checksub(subdomain):
	entry = db['subdomains'].find_one({'subdomain':subdomain},\
		{'subdomain':1,'_id':0})
	if entry is None:
		return False
	return True

def toJson(data):
	"""Convert Mongo object(s) to JSON"""
	return json.dumps(data, default=json_util.default)

@app.errorhandler(404)
def not_found(error):
    return make_response(jsonify({'error': 'Not found'}), 404)

@app.errorhandler(401)
def not_found(error):
    return make_response(jsonify({'error': 'Bad Auth'}), 401)

@app.errorhandler(400)
def not_found(error):
    return make_response(jsonify({'error': 'Bad Request'}), 400)

if __name__ == '__main__':
    app.run(debug=True,host='0.0.0.0')