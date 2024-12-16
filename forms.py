from flask_wtf import FlaskForm
from wtforms import StringField, DateField, SubmitField, TextAreaField
from wtforms.validators import DataRequired

class EventForm(FlaskForm):
    title = StringField('Event Title', validators=[DataRequired()])
    date = DateField('Date', format='%Y-%m-%d', validators=[DataRequired()])
    description = TextAreaField('Description')
    time = StringField('Time')  # New field for time
    location = StringField('Location')  # New field for location
    submit = SubmitField('Add Event')

class ChatForm(FlaskForm):
    prompt = StringField('Smart Action', validators=[DataRequired()], render_kw={"title": "Simply describe what you wish to add/remove/modify and click 'Send' to have the action performed for you!"})
    submit = SubmitField('Send')
