#!/usr/bin/python3

from flask import Flask
from flask import render_template
import getOGTagsInHTML

app = Flask(__name__)
app.static_folder = "./static"
app.template_folder = "./templates"

@app.route('/')
def showFrontpage():
    HTML, CSS, JS = getOGTagsInHTML.main()
    return (render_template("index.html", HTML=HTML, CSS=CSS, JS=JS))

if __name__ == '__main__':
    app.run()
