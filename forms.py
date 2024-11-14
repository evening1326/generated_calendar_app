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
