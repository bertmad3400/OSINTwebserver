#!/usr/bin/python3

import psycopg2
postgresqlPassword = ""

from flask import Flask
from flask import render_template
from flask import request

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
    profiles = request.args.get('profiles', '*').split(";")
    keywords = request.args.get('keywords', '').split(";")

    if profiles[0] == '*':
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
        return "<h2>400 - Problem with the profile query paramater</h2> \n <p> \"{}\" isn't recognized as a profile stored in our database. </p>".format(OSINTwebserver.verifyProfiles(profiles, conn, 'articles')), 400


@app.route('/api')
def api():
    conn = psycopg2.connect("dbname=osinter user=postgres password=" + postgresqlPassword)
    return OSINTdatabase.requestOGTagsFromDB(conn, 'articles', OSINTdatabase.requestProfileListFromDB(conn, 'articles'))

if __name__ == '__main__':
    app.run(debug=True)
