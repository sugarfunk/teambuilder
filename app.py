from flask import Flask, render_template, request, url_for, session, redirect, escape, flash
from passlib.hash import sha256_crypt
import pymysql
from flask_sqlalchemy import SQLAlchemy
import yaml
import collections

app = Flask(__name__)

#Configure db
db = yaml.load(open('db.yaml'))
"""
app.config['MYSQL_HOST'] = db['mysql_host']
app.config['MYSQL_USER'] = db['mysql_user']
app.config['MYSQL_PASSWORD'] = db['mysql_password']
app.config['MYSQL_DB'] = db['mysql_db']
"""

myApp = pymysql.connect(host=db['mysql_host'], user=db['mysql_user'], password=db['mysql_password'], db=db['mysql_db'], charset='utf8mb4',
                             cursorclass=pymysql.cursors.DictCursor)

profile = True # if profile was filled out

@app.route('/', methods = ["GET"]) 
def index():
	if 'username' in session:
		username = session['username']
		# check if user filled out profile + has matches
		cur = myApp.cursor()
		cur.execute("SELECT userID FROM user WHERE username=%s", [username])
		userID = cur.fetchone()['userID']
		cur.execute("SELECT hackathonID FROM usertohackathon WHERE userID=%s", [userID])
		if cur.fetchone() is not None:
			return render_template('index.html', username=username, profile=profile)
		return render_template('index.html', username=username)
	return render_template('index.html')

@app.route('/login', methods = ["GET", "POST"]) 
def login():
	error = None
	if 'username' in session:
		return redirect(url_for('index'))
	if request.method == 'POST':
		username_form  = request.form['username']
		password_form  = request.form['password']
		cur = myApp.cursor()
		cur.execute("SELECT COUNT(1) FROM user WHERE username = %s;", [username_form]) # CHECKS IF USERNAME EXISTS
		if cur.fetchone() is not None:
			cur.execute("SELECT password FROM user WHERE username = %s;", [username_form]) # FETCH THE PASSWORD
			for row in cur.fetchall():
				if sha256_crypt.verify(password_form, row['password']):
					session['username'] = request.form['username']
					cur.close()
					return redirect(url_for('index'))
				else:
					error = "Wrong password"
		else:
			error = "Username not found"
		cur.close()
	return render_template('login.html', error=error)

@app.route('/register', methods = ["GET","POST"]) 
def register():
	error = []
	isIssue = False
	if request.method == 'POST':
		# fetch form data
		userDetails = request.form
		username = userDetails['username']
		email = userDetails['email']
		password = userDetails['password']
		confirm_password = userDetails['confirm_password']

		cur = myApp.cursor()
		cur.execute("SELECT * FROM user WHERE username = %s", [username])
		
		#error handling
		if cur.fetchone() is not None:
			error.append('Please choose a different username.')
			isIssue = True

		cur.execute("SELECT * FROM user WHERE email = %s", [email])
		
		if cur.fetchone() is not None:
			error.append('Email already registered.')
			isIssue = True

		if password != confirm_password:
			error.append('Passwords do not match.')
			isIssue = True

		if isIssue: # if any errors
			return render_template('register.html', error = error)

		# if no errors, add to database
		cur.execute("INSERT INTO user(email, username, password) VALUES(%s, %s, %s)", [email, username, sha256_crypt.encrypt(password)])
		myApp.commit()
		cur.close() 
		flash('Congrats! You are now a registered hacker.')
		return redirect(url_for('login'))
	return render_template('register.html')

@app.route('/logout')
def logout():
	session.pop('username', None)
	return redirect(url_for('index'))

@app.route('/preferences', methods = ["GET","POST"])
def prefs():
	isError = False
	error = []

	# redirect to home page if no one is logged in
	if 'username' not in session:
		return render_template('index.html')
	username_session = escape(session['username'])
	username = escape(session['username'])

	# Render profile page if form was already filled out
	cur = myApp.cursor()
	cur.execute("SELECT userID FROM user WHERE username=%s", [username])
	userID = cur.fetchone()[0]
	cur.execute("SELECT hackathonID FROM usertohackathon WHERE userID=%s", [userID])
	if cur.fetchone() is not None:
		return redirect(url_for('profile', profile=profile))

	if request.method == 'POST':
		
		# simple fields 
		projIdea_form  = request.form.get('projIdea', None)
		compLevel_form = request.form.get('comp', None)
		exper_form = request.form.get('exper', None)
		gitLink_form = request.form.get('gitLink', None) # unique
		resume_form = request.form.get('resume', None) # unique

		#many to many relationships
		hackathon_form  = request.form['hackathon']
		#arrays
		tech = request.form.getlist('tech[]')
		languages = request.form.getlist('languages[]')
		ints = request.form.getlist('interests[]')
		hardware = request.form.getlist('hardware[]')

		
		cur = myApp.cursor()
		cur.execute("SELECT userID FROM user WHERE username=%s", [username])
		userID = cur.fetchone()[0]

		# hackathon
		cur.execute("SELECT hackathonID FROM hackathons WHERE hackathon=%s", [hackathon_form])
		hackathonID = cur.fetchone()[0]
		cur.execute("INSERT INTO usertohackathon VALUES(%s, %s)", [userID, hackathonID])

		# multiselect fields: cycle through, add each one as a row in many-to-many table

		#technologies 
		if len(tech) != 0:
			for i in range(0, len(tech)):
				cur.execute("SELECT techID FROM tech WHERE tech=%s", [tech[i]])
				techID = cur.fetchone()[0]
				cur.execute("INSERT INTO usertotech VALUES(%s, %s)", [userID, techID])

		# languages 
		if len(languages) != 0:
			for i in range(0, len(languages)):
				cur.execute("SELECT langID FROM langs WHERE lang=%s", [languages[i]])
				langID = cur.fetchone()[0]
				cur.execute("INSERT INTO usertolang VALUES(%s, %s)", [userID, langID])

		# interests 
		if len(ints) != 0:
			for i in range(0, len(ints)):
				cur.execute("SELECT intID FROM interests WHERE interest=%s", [ints[i]])
				intID = cur.fetchone()[0]
				cur.execute("INSERT INTO usertointerests VALUES(%s, %s)", [userID, intID])

		# hardware 
		if len(hardware) != 0:
			for i in range(0, len(hardware)):
				cur.execute("SELECT hwID FROM hw WHERE hw=%s", [hardware[i]])
				hwID = cur.fetchone()[0]
				cur.execute("INSERT INTO usertohw VALUES(%s, %s)", [userID, hwID])

		if projIdea_form is not None:
			cur.execute("UPDATE user SET projIdea=%s WHERE username=%s", [projIdea_form, username]) 
			myApp.commit()

		# radio options
		if exper_form is not None:
			cur.execute("UPDATE user SET exper=%s WHERE username=%s", [exper_form, username]) 
			myApp.commit()

		if compLevel_form is not None:
			cur.execute("UPDATE user SET comp=%s WHERE username=%s", [compLevel_form, username]) 
			myApp.commit()


		# links
		if gitLink_form is not None:
			cur.execute("SELECT * FROM user WHERE gitLink=%s", [gitLink_form])
			if cur.fetchone() is not None:
				error.append('GitHub link not unique.')
				isError = True
			else:
				cur.execute("UPDATE user SET gitLink=%s WHERE username=%s", [gitLink_form, username]) 
				myApp.commit()

		if resume_form is not None:
			cur.execute("SELECT * FROM user WHERE resume=%s", [resume_form])
			if cur.fetchone() is not None:
				error.append('Resume link not unique.')
				isError = True
			else:
				cur.execute("UPDATE user SET resume=%s WHERE username=%s", [resume_form, username]) 
				myApp.commit()


		# if error(s), render template early
		if isError: 
			render_template('prefs.html', error = error)

		# fix this message?
		flash('Thanks for filling out your profile! Scroll down to explore your matches.')
		
		return redirect(url_for('matches'))
	return render_template('prefs.html', username=username_session)

@app.route('/profile', defaults={'username': None})
@app.route('/profile/<username>')
def profile(username):
	cur = myApp.cursor()
	profile=True # if profile was filled out
	username_session = session['username']

	if username is None:
		username = session['username']

	# use select statements, send all vars to template

	# cols in user table (one to one relationships)
	cur.execute("SELECT userID, projIdea, exper, comp, gitLink, resume, email FROM user WHERE username=%s", [username])
	row = cur.fetchone()
	userID = row['userID'] # need for many-to-many relationships
	projIdea = row['projIdea'] # project idea
	exper = row['exper'] # experience level
	comp = row['comp'] # competition level
	gitLink = row['gitLink'] # github link
	resume = row['resume'] # resume link
	email = row['email'] # email
	
	
	# hackathon
	cur.execute("SELECT hackathonID FROM usertohackathon WHERE userID=%s", [userID])
	hID = cur.fetchone()['hackathonID']
	cur.execute("SELECT hackathon FROM hackathons WHERE hackathonID=%s", [hID])
	hackathon = cur.fetchone()['hackathon']

	# multiselect items: have access to IDs. must select ID, then use it to find name of item in its own table

	# technologies
	cur.execute("SELECT * FROM usertotech WHERE userID=%s", [userID])
	techList = []
	for row in cur.fetchall(): # loop through rows in usertotech
		techID = row['techID']
		cur.execute("SELECT tech FROM tech WHERE techID=%s", [techID])
		tech = cur.fetchone()['tech']
		techList.append(tech)
	if len(techList) == 0:
		techList = None

	#techList = fetch_list('usertotech', 'tech', 'tech', userID)

	# interests
	cur.execute("SELECT * FROM usertointerests WHERE userID=%s", [userID])
	intList = []
	for row in cur.fetchall(): # loop through rows in usertotech
		intID = row['intID']
		cur.execute("SELECT interest FROM interests WHERE intID=%s", [intID])
		interest = cur.fetchone()['interest']
		intList.append(interest)
	if len(intList) == 0:
		intList = None

	# languages
	cur.execute("SELECT * FROM usertolang WHERE userID=%s", [userID])
	langList = []
	for row in cur.fetchall(): # loop through rows in usertotech
		langID = row['langID']
		cur.execute("SELECT lang FROM langs WHERE langID=%s", [langID])
		lang = cur.fetchone()['lang']
		langList.append(lang)
	if len(langList) == 0:
		langList = None

	# hardware
	cur.execute("SELECT * FROM usertohw WHERE userID=%s", [userID])
	hwList = []
	for row in cur.fetchall(): # loop through rows in usertotech
		hwID = row['hwID']
		cur.execute("SELECT hw FROM hw WHERE hwID=%s", [hwID])
		hw = cur.fetchone()['hw']
		hwList.append(hw)
	if len(hwList) == 0:
		hwList = None

	return render_template('profile.html', profile=profile, email=email, username_session=username_session, username=username, hackathon=hackathon, projIdea=projIdea, 
		techList=techList, intList=intList, langList=langList, hwList=hwList, exper=exper, comp=comp, gitLink=gitLink, resume=resume)
	
@app.route('/update', methods=["GET", "POST"])
def update():
	# redirect to home page if no one is logged in
	if 'username' not in session:
		return render_template('index.html')

	isError = False
	error = []
	
	username_session = escape(session['username'])
	username = escape(session['username'])

	if request.method == 'POST':
		
		# simple fields 
		projIdea_form  = request.form.get('projIdea', None)
		compLevel_form = request.form.get('comp', None)
		exper_form = request.form.get('exper', None)
		gitLink_form = request.form.get('gitLink', None) # unique
		resume_form = request.form.get('resume', None) # unique

		#many to many relationships
		hackathon_form  = request.form['hackathon']
		#arrays
		tech = request.form.getlist('tech[]')
		languages = request.form.getlist('languages[]')
		ints = request.form.getlist('interests[]')
		hardware = request.form.getlist('hardware[]')

		
		cur = myApp.cursor()
		cur.execute("SELECT userID FROM user WHERE username=%s", [username])
		userID = cur.fetchone()[0]

		# hackathon
		cur.execute("SELECT hackathonID FROM hackathons WHERE hackathon=%s", [hackathon_form])
		hackathonID = cur.fetchone()[0]
		cur.execute("UPDATE usertohackathon SET hackathonID=%s WHERE userID=%s", [hackathonID, userID])

		# how to do rest of form lol

	return render_template('update.html', username=username, profile=profile)
	
@app.route('/matches', methods = ["GET", "POST"])
def matches():
	filterType=None
	message = None
	matches=None
	numResults = 0
	currID = None
	results=None
	username = session['username']
	profile = True #if profile was filled out
	cur = myApp.cursor()

	# userID
	cur.execute("SELECT userID FROM user WHERE username=%s", [username])
	userID = cur.fetchone()['userID'] 

	# hackathon
	cur.execute("SELECT hackathonID FROM usertohackathon WHERE userID=%s", [userID])
	hID = cur.fetchone()['hackathonID']

	if hID is None: # return early if no profile
		return render_template('matches.html', username=username, message=["Oops! Looks like you haven't specified your preferences yet."])

	# Generating matches

	cur.execute("SELECT hackathon FROM hackathons WHERE hackathonID=%s", [hID])
	hackathon = cur.fetchone()['hackathon']

	# QUERY ALL OTHER FIELDS FROM CURRENT USER 

	# technologies
	cur.execute("SELECT * FROM usertotech WHERE userID=%s", [userID])
	techList = []
	for row in cur.fetchall(): # loop through rows in usertotech
		techID = row['techID']
		cur.execute("SELECT tech FROM tech WHERE techID=%s", [techID])
		tech = cur.fetchone()['tech']
		techList.append(tech)
	if len(techList) == 0:
		techList = None
		
	# interests
	cur.execute("SELECT * FROM usertointerests WHERE userID=%s", [userID])
	intList = []
	for row in cur.fetchall(): # loop through rows in usertotech
		intID = row['intID']
		cur.execute("SELECT interest FROM interests WHERE intID=%s", [intID])
		interest = cur.fetchone()['interest']
		intList.append(interest)
	if len(intList) == 0:
		intList = None

	# languages
	cur.execute("SELECT * FROM usertolang WHERE userID=%s", [userID])
	langList = []
	for row in cur.fetchall(): # loop through rows in usertotech
		langID = row['langID']
		cur.execute("SELECT lang FROM langs WHERE langID=%s", [langID])
		lang = cur.fetchone()['lang']
		langList.append(lang)
	if len(langList) == 0:
		langList = None

	# hardware
	cur.execute("SELECT * FROM usertohw WHERE userID=%s", [userID])
	hwList = []
	for row in cur.fetchall(): # loop through rows in usertotech
		hwID = row['hwID']
		cur.execute("SELECT hw FROM hw WHERE hwID=%s", [hwID])
		hw = cur.fetchone()['hw']
		hwList.append(hw)
	if len(hwList) == 0:
		hwList = None

	# exper + comp level
	cur.execute("SELECT exper, comp FROM user WHERE userID=%s", [userID])
	r = cur.fetchone()
	exper = r['exper']
	comp = r['comp']

	# select users at the same hackathon
	
	# set up dictionaries to keep track of matches per user by category
	techMatches = dict()
	langMatches = dict()
	intMatches = dict()
	hwMatches = dict()
	
	# values
	match_tech = []
	match_langs = []
	match_ints = []
	match_hw = []

	mydict = dict()
	numRows = cur.execute("SELECT * FROM user WHERE userID !=%s AND userID IN (SELECT userID FROM usertohackathon WHERE hackathonID=%s)", [userID, hID]) 
	if numRows > 0:
		matches = cur.fetchall()
		l = []
		for row in matches:
			currID = row['userID']
			user_name = row['username']

			# account for experience + comp level 
				
			exper_match = row['exper'] # exper = col 6
			comp_match = row['comp'] # comp = col 5

			if exper == exper_match:
				l.insert(0, exper)

			if comp == comp_match:
				if comp == 'Yes':
					l.insert(1, 'Competing')
				else:
					l.insert(1, 'Not Competing')

			if intList is not None:
				cur.execute("SELECT * FROM usertointerests WHERE userID=%s",[currID])
				ints = cur.fetchall()
				for row in ints:
					# fetch string from db using id
					cur.execute("SELECT interest FROM interests WHERE intID=%s", [row['intID']])
					item = cur.fetchone()['interest']
					if item in intList:
						cur.execute("UPDATE user SET numMatches = numMatches + 1 WHERE userID=%s", [currID]) # update numMatches
						l.append(item)
						match_ints.append(item)
			
			if techList is not None:
				cur.execute("SELECT * FROM usertotech WHERE userID=%s",[currID])
				tech = cur.fetchall()
				for row in tech:
					cur.execute("SELECT tech FROM tech WHERE techID=%s", [row['techID']])
					item = cur.fetchone()['tech']
					if item in techList:
						cur.execute("UPDATE user SET numMatches = numMatches + 1 WHERE userID=%s", [currID]) # update numMatches
						l.append(item)
						match_tech.append(item)

			if langList is not None:
				cur.execute("SELECT * FROM usertolang WHERE userID=%s",[currID])
				langs = cur.fetchall()
				for row in langs:
					cur.execute("SELECT lang FROM langs WHERE langID=%s", [row['langID']])
					item = cur.fetchone()['lang']
					if item in langList:
						cur.execute("UPDATE user SET numMatches = numMatches + 1 WHERE userID=%s", [currID]) # update numMatches
						l.append(item)
						match_langs.append(item)

			if hwList is not None:
				cur.execute("SELECT * FROM usertohw WHERE userID=%s",[currID])
				hw = cur.fetchall()
				for row in hw:
					cur.execute("SELECT hw FROM hw WHERE hwID=%s", [row['hwID']])
					item = cur.fetchone()['hw']
					if item in hwList:
						cur.execute("UPDATE user SET numMatches = numMatches + 1 WHERE userID=%s", [currID]) # update numMatches
						l.append(item)
						match_hw.append(item)

			#update dict (sending to html)
				# key: match's userID 
				# value: list of matching attributes
			mydict[user_name] = l
			l = []

			# initialize dictionaries that keep track of number of matches per user in each category
				# key: username
				# value: list of matching attributes
			if len(match_tech) > 0:
				techMatches[user_name] = match_tech
				match_tech = []

			if len(match_langs) > 0:
				langMatches[user_name] = match_langs
				match_langs = []

			if len(match_ints) > 0:
				intMatches[user_name] = match_ints
				match_ints = []

			if len(match_hw) > 0:
				hwMatches[user_name] = match_hw
				match_hw = [] 

		# make results dictionary - will display this in html
			# key: username
			# value: list of matching attributes
		results = dict()
		for k in sorted(mydict, key=lambda k: len(mydict[k]), reverse=True):
			if len(mydict[k]) > 0:
				results[k] = mydict[k] 

		numResults = len(results)
	else:
		message = ["Sorry, there are no other Team Builders at your hackathon.","Please check your hackathon's schedule for a team building event!"]

	if request.method == 'POST':

		dict1 = collections.OrderedDict()
		resFilter = request.form.get('resFilter') # filters: tech, interests, languages, hw, exper level, comp
		
		if resFilter == 'tech':
			for k in sorted(techMatches, key=lambda k: len(techMatches[k]), reverse=True):
				dict1[k] = techMatches[k]
			filterType = 'technology'
			
		elif resFilter == 'ints':
			for k in sorted(intMatches, key=lambda k: len(intMatches[k]), reverse=True):
				dict1[k] = intMatches[k]
			filterType = 'interest'
		
		elif resFilter == 'lang':
			for k in sorted(langMatches, key=lambda k: len(langMatches[k]), reverse=True):
				dict1[k] = langMatches[k]
			filterType = 'language'
		
		elif resFilter == 'hw':
			for k in sorted(hwMatches, key=lambda k: len(hwMatches[k]), reverse=True):
				dict1[k] = hwMatches[k]
			filterType = 'hardware'

		elif resFilter == 'exper':
			for key in results:
				if exper in results[key]:
					dict1[key] = results[key]
			filterType = 'experience level'

		elif resFilter == 'comp':
			c = ' '
			if comp == 'Yes':
				c = 'Competing'
			else:
				c = 'Not competing'

			for key in results:
				if c in results[key]:
					dict1[key] = results[key]
			filterType = 'competition level'

		numResults = len(dict1)
		results = dict1
	
	return render_template('matches.html', filterType=filterType, results = results, currID=currID,profile=profile, username=username, message=message, matches=matches, numResults=numResults)

app.secret_key = 'MVB79L'

if __name__ == '__main__':
	app.config['SESSION_TYPE'] = 'filesystem'
	app.run(debug=True)
