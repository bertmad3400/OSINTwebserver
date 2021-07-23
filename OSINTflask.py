#!/usr/bin/python3

import psycopg2
articleTable = "articles"

from flask import Flask, abort
from flask import render_template
from flask import request

import werkzeug

import json

from OSINTmodules import *

app = Flask(__name__)
app.static_folder = "./static"
app.template_folder = "./templates"

def extractLimitParamater(request):
    try:
        limit = int(request.args.get('limit', 10))
    except:
        abort(422)
    if limit > 100 or limit < 0:
        abort(422)
    else:
        return limit

@app.errorhandler(werkzeug.exceptions.HTTPException)
def handleHTTPErrors(e):
    return render_template("HTTPError.html", errorCode=e.code, errorName=e.name, errorDescription=e.description), e.code

@app.route('/')
def showFrontpage():
    # Opening connection to database for OG tag retrieval
    conn = psycopg2.connect("dbname=osinter user=reader")

    limit = extractLimitParamater(request)

    # Getting the custom profile selection and keywords from the url
    profiles = request.args.getlist('profiles')
    keywords = request.args.get('keywords', '').split(";")

    if profiles == []:
        # Get a list of scrambled OG tags
        scrambledOGTags = OSINTtags.scrambleOGTags(OSINTdatabase.requestOGTagsFromDB(conn, articleTable, OSINTdatabase.requestProfileListFromDB(conn, articleTable), limit))
        # Generating the HTML, CSS and JS from the scrambled OG tags
        HTML, CSS, JS = OSINTwebserver.generatePageDetails(scrambledOGTags)
        return (render_template("feed.html", HTML=HTML, CSS=CSS, JS=JS))
    elif OSINTwebserver.verifyProfiles(profiles, conn, articleTable) == True:
        # Get a list of scrambled OG tags
        scrambledOGTags = OSINTtags.scrambleOGTags(OSINTdatabase.requestOGTagsFromDB(conn, articleTable, profiles, limit))
        # Generating the HTML, CSS and JS from the scrambled OG tags
        HTML, CSS, JS = OSINTwebserver.generatePageDetails(scrambledOGTags)
        return (render_template("feed.html", HTML=HTML, CSS=CSS, JS=JS))
    else:
        abort(422)

@app.route('/config')
def configureNewsSources():
    # Opening connection to database for a list of stored profiles
    conn = psycopg2.connect("dbname=osinter user=reader")

    sourcesDetails = OSINTprofiles.collectWebsiteDetails(conn, articleTable)
    HTML = OSINTwebserver.generateSourcesList({source: sourcesDetails[source] for source in sorted(sourcesDetails)})
    return render_template("chooseNewsSource.html", HTML=HTML)

@app.route('/api/newArticles')
def api():
    conn = psycopg2.connect("dbname=osinter user=reader")

    limit = extractLimitParamater(request)

    return OSINTdatabase.requestOGTagsFromDB(conn, articleTable, OSINTdatabase.requestProfileListFromDB(conn, articleTable), limit)

@app.route('/api/profileList')
def apiProfileList():
    conn = psycopg2.connect("dbname=osinter user=reader")
    return json.dumps(OSINTdatabase.requestProfileListFromDB(conn, articleTable))

if __name__ == '__main__':
    app.run(debug=True)
