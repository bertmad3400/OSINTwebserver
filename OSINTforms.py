from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import InputRequired, Length, EqualTo

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[InputRequired(), Length(min=4, message=('Your username is too short. It should be 4 characthers or more.'))])
    password = PasswordField('Password', validators=[InputRequired(), Length(min=4, message=('Your password is too short. It should be 4 characthers or more.'))])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Sign In')

class SignupForm(FlaskForm):
    username = StringField('Username', validators=[InputRequired(), Length(min=4, message='Your username is too short. It should be 4 characthers or more.')])
    password = PasswordField('Password', validators=[InputRequired(), Length(min=4, message='Your password is too short. it should be 4 characthers or more.')])
    confirmPassword = PasswordField('Repeat Password', validators=[InputRequired(), EqualTo("password", message="Passwords should match.")])
    submit = SubmitField('Sign In')
