#!/usr/bin/python3

import psycopg2
postgresqlPassword = ""

from flask import Flask
from flask import render_template
from flask import request

import json

from OSINTmodules import *

app = Flask(__name__)
app.static_folder = "./static"
app.template_folder = "./templates"


#@app.route('/')
#def selectUser():
#    return (render_template("selectUser.html"))

@app.route('/')
def showFrontpage():
    # Opening connection to database for OG tag retrieval
    conn = psycopg2.connect("dbname=osinter user=postgres password=" + postgresqlPassword)

    # Getting the custom profile selection and keywords from the url
    profiles = request.args.getlist('profiles')
    keywords = request.args.get('keywords', '').split(";")

    if profiles == []:
        # Get a list of scrambled OG tags
        scrambledOGTags = OSINTtags.scrambleOGTags(OSINTdatabase.requestOGTagsFromDB(conn, 'articles', OSINTdatabase.requestProfileListFromDB(conn, 'articles'), 10))
        # Generating the HTML, CSS and JS from the scrambled OG tags
        HTML, CSS, JS = OSINTwebserver.generatePageDetails(scrambledOGTags)
        return (render_template("feed.html", HTML=HTML, CSS=CSS, JS=JS))
    elif OSINTwebserver.verifyProfiles(profiles, conn, 'articles') == True:
        # Get a list of scrambled OG tags
        scrambledOGTags = OSINTtags.scrambleOGTags(OSINTdatabase.requestOGTagsFromDB(conn, 'articles', profiles, 20))
        # Generating the HTML, CSS and JS from the scrambled OG tags
        HTML, CSS, JS = OSINTwebserver.generatePageDetails(scrambledOGTags)
        return (render_template("feed.html", HTML=HTML, CSS=CSS, JS=JS))
    else:
        return render_template("400.html", wrongInput=OSINTwebserver.verifyProfiles(profiles, conn, 'articles'), paramater="profiles", fix="Try one of the profiles listed on /api/profileList"), 400

@app.route('/config')
def configureNewsSources():
    sourcesDetails = OSINTprofiles.collectWebsiteDetails()
    HTML = OSINTwebserver.generateSourcesList(sourcesDetails)
    return render_template("chooseNewsSource.html", HTML=HTML)

@app.route('/api/newArticles')
def api():
    conn = psycopg2.connect("dbname=osinter user=postgres password=" + postgresqlPassword)

    try:
        limit = int(request.args.get('limit', 10))
    except:
        return render_template("400.html", wrongInput=request.args.get('limit'), paramater="limit", fix="Are you sure it's a number and not a string?")

    if limit > 100 or limit < 0:
        return render_template("400.html", wrongInput=limit, paramater="limit", fix="Are you sure it's a number between 0 and 100?")

    return OSINTdatabase.requestOGTagsFromDB(conn, 'articles', OSINTdatabase.requestProfileListFromDB(conn, 'articles'), 10)

@app.route('/api/profileList')
def apiProfileList():
    conn = psycopg2.connect("dbname=osinter user=postgres password=" + postgresqlPassword)
    return json.dumps(OSINTdatabase.requestProfileListFromDB(conn, 'articles'))

if __name__ == '__main__':
    app.run(debug=True)
