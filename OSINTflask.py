#!/usr/bin/python3

import markdown
import psycopg2

articleTable = "articles"
userTable = "osinter_users"

from flask import Flask, abort
from flask import render_template
from flask import request

import werkzeug

import json

import re

from pathlib import Path

from OSINTmodules import *

app = Flask(__name__)
app.static_folder = "./static"
app.template_folder = "./templates"

def openDBConn(user="reader", password=""):
    return psycopg2.connect("dbname=osinter user={} password={}".format(user, password))

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

def renderMDFile(MDFilePath):
    if Path('./MDFiles/{}.md'.format(MDFilePath)).exists():
        with open('./MDFiles/{}.md'.format(MDFilePath)) as MDFile:
            MDContents = markdown.markdown(MDFile.read())
            return render_template("githubMD.html", markdown=MDContents)
    else:
        abort(404)

def createFeedURLList(idList, conn, tableName):
    URLList = []
    for articleId in idList:
        articleMDFile = OSINTdatabase.returnArticleFilePathById(conn, articleId, tableName)
        internURL = '/renderMarkdownByProfile/{}/'.format(articleMDFile)
        URLList.append(internURL)

    return URLList



@app.errorhandler(werkzeug.exceptions.HTTPException)
def handleHTTPErrors(e):
    return render_template("HTTPError.html", errorCode=e.code, errorName=e.name, errorDescription=e.description), e.code

@app.route('/')
def showFrontpage():
    # Opening connection to database for OG tag retrieval
    conn = openDBConn()

    limit = extractLimitParamater(request)
    profiles = extractProfileParamaters(request, conn)
    username = request.args.get('username', "")

    # Get a list of scrambled OG tags
    scrambledOGTags = OSINTtags.scrambleOGTags(OSINTdatabase.requestOGTagsFromDB(conn, articleTable, profiles, limit))

    # Will order the OG tags in a dict containing individual lists with IDs, URLs, imageURLs, titles and descriptions
    listCollection = OSINTwebserver.collectFeedDetails(scrambledOGTags)

    if username != "":
        username = re.sub(r'[^\w\d]*', '', username)
        listCollection['marked'] = OSINTdatabase.checkIfArticleMarked(conn, userTable, listCollection['id'], username)
    else:
        listCollection['marked'] = []


    # Will change the URLs to intern URLs if the user has reading mode turned on
    if request.args.get('reading', False):
        listCollection['url'] = createFeedURLList(listCollection['id'], conn, articleTable)
    else:
        listCollection['url'] = listCollection['url']

    URLAndTitleList = zip(listCollection['url'], listCollection['title'])

    return (render_template("feed.html", detailList=listCollection, username=username, URLAndTitleList=URLAndTitleList))

@app.route('/login')
def chooseUser():
    return render_template("selectUser.html")

@app.route('/config')
def configureNewsSources():
    # Opening connection to database for a list of stored profiles
    conn = openDBConn()
    sourcesDetails = OSINTprofiles.collectWebsiteDetails(conn, articleTable)
    return render_template("chooseNewsSource.html", sourceDetailsDict={source: sourcesDetails[source] for source in sorted(sourcesDetails)})

@app.route('/renderMarkdownByProfile/<profile>/<fileName>/')
def renderMDFileByProfile(profile, fileName):
    profileName = OSINTmisc.fileSafeString(profile)
    MDFileName = OSINTmisc.fileSafeString(fileName)
    return renderMDFile('{}/{}'.format(profileName, MDFileName))

@app.route('/renderMarkdownById/<int:articleId>/')
def renderMDFileById(articleId):
    if type(articleId) != int:
        abort(422)

    MDFilePath = OSINTdatabase.returnArticleFilePathById(openDBConn(), articleId, 'articles')
    if MDFilePath:
        return renderMDFile(MDFilePath)
    else:
        abort(404)


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

@app.route('/api/markArticles/ID/<int:articleID>/', methods=['POST'])
def markArticleByID(articleID):
    postgresqlPassword = Path("./credentials/article_marker.password").read_text()
    conn = openDBConn(user="article_marker", password = postgresqlPassword)
    OSINTdatabase.(conn, articleTable, userTable, user, articleID )

if __name__ == '__main__':
    app.run(debug=True)
