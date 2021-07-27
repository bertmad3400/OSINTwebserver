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

def openDBConn():
    return psycopg2.connect("dbname=osinter user=reader")

def extractLimitParamater(request):
    try:
        limit = int(request.args.get('limit', 10))
    except:
        abort(422)
    if limit > 100 or limit < 0:
        abort(422)
    else:
        return limit

def extractProfileParamaters(request, conn):
    profiles = request.args.getlist('profiles')

    if profiles == []:
        # Get a list of scrambled OG tags
        return OSINTdatabase.requestProfileListFromDB(conn, articleTable)
    # Making sure that the profiles given by the user both exist as local profiles and in the DB
    elif OSINTwebserver.verifyProfiles(profiles, conn, articleTable):
        # Just simply return the list of profiles
        return profiles
    else:
        abort(422)

@app.errorhandler(werkzeug.exceptions.HTTPException)
def handleHTTPErrors(e):
    return render_template("HTTPError.html", errorCode=e.code, errorName=e.name, errorDescription=e.description), e.code

@app.route('/')
def showFrontpage():
    # Opening connection to database for OG tag retrieval
    conn = openDBConn()

    limit = extractLimitParamater(request)

    profiles = extractProfileParamaters(request, conn)

    # Get a list of scrambled OG tags
    scrambledOGTags = OSINTtags.scrambleOGTags(OSINTdatabase.requestOGTagsFromDB(conn, articleTable, profiles, limit))
    # Generating the HTML, CSS and JS from the scrambled OG tags
    HTML, CSS, JS = OSINTwebserver.generatePageDetails(scrambledOGTags)
    return (render_template("feed.html", HTML=HTML, CSS=CSS, JS=JS))


@app.route('/config')
def configureNewsSources():
    # Opening connection to database for a list of stored profiles
    conn = openDBConn()
    sourcesDetails = OSINTprofiles.collectWebsiteDetails(conn, articleTable)
    print({source: sourcesDetails[source] for source in sorted(sourcesDetails)})
    return render_template("chooseNewsSource.html", sourceDetailsDict={source: sourcesDetails[source] for source in sorted(sourcesDetails)})

@app.route('/api')
def listAPIEndpoints():
    APIEndpointList = []
    for rule in app.url_map.iter_rules():
        rule = str(rule)
        if rule.startswith('/api/'):
            APIEndpointList.append(rule)

    return json.dumps(APIEndpointList)

@app.route('/api/newArticles')
def api():
    conn = openDBConn()

    limit = extractLimitParamater(request)

    profiles = extractProfileParamaters(request, conn)

    return OSINTdatabase.requestOGTagsFromDB(conn, articleTable, profiles, limit)

@app.route('/api/profileList')
def apiProfileList():
    conn = openDBConn()
    return json.dumps(OSINTdatabase.requestProfileListFromDB(conn, articleTable))

if __name__ == '__main__':
    app.run(debug=True)
