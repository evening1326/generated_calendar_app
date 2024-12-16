'''
Nick DeMaestri
12/16/2024
CS-391

Final Project: Calendar App
(Generated with OpenAI and GitHub Copilot)

!!! WILL NEED A CONFIG.PY FILE WITH YOUR OPENAI API
'''

from flask import Flask, render_template, redirect, url_for, request, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta, date
import calendar
import holidays
from forms import EventForm, ChatForm
import requests
from sqlalchemy import text
from dateutil.easter import easter
import openai
import config
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired
import re

# Initialize Flask app and configure database
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///events.db'  # Ensure this points to the internal SQLite database
db = SQLAlchemy(app)

# Define Event model
class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255))
    time = db.Column(db.String(10))  # New field for time
    location = db.Column(db.String(100))  # New field for location

# Define ChatForm for user input
class ChatForm(FlaskForm):
    prompt = StringField('Prompt', validators=[DataRequired()])
    submit = SubmitField('Send')

# Function to add US holidays to the database
def add_us_holidays(year):
    us_holidays = holidays.US(years=year)
    additional_holidays = {
        "Easter": easter(year),
        "Independence Day": date(year, 7, 4),
        "Halloween": date(year, 10, 31),
        "Valentine's Day": date(year, 2, 14),
        "St. Patrick's Day": date(year, 3, 17),
        "Mother's Day": holidays.US(years=year).get_named("Mother's Day"),
        "Father's Day": holidays.US(years=year).get_named("Father's Day"),
        "Labor Day": holidays.US(years=year).get_named("Labor Day"),
        "Veterans Day": date(year, 11, 11),
        "Thanksgiving": holidays.US(years=year).get_named("Thanksgiving"),
        "Christmas Eve": date(year, 12, 24),
        "New Year's Eve": date(year, 12, 31)
    }
    
    for name, holiday_date in additional_holidays.items():
        if isinstance(holiday_date, list):
            for single_date in holiday_date:
                us_holidays[single_date] = name
        else:
            us_holidays[holiday_date] = name

    for holiday_date, name in us_holidays.items():
        if not Event.query.filter_by(date=holiday_date, title=name).first():
            event = Event(
                date=holiday_date,
                title=name,
                description="US Holiday"
            )
            db.session.add(event)
    db.session.commit()

# Function to get weather information
def get_weather():
    headers = {
        'User-Agent': 'YourAppName (your-email@example.com)'
    }
    url = "https://api.weather.gov/gridpoints/DTX/65,33/forecast"
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        periods = data.get('properties', {}).get('periods', [])
        if periods:
            current_weather = periods[0]
            return {
                'name': current_weather.get('name'),
                'temperature': current_weather.get('temperature'),
                'shortForecast': current_weather.get('shortForecast')
            }
    return None

# Function to execute SQLite commands
def execute_sqlite_command(command):
    try:
        # Handle INSERT INTO command
        insert_pattern = re.compile(r"INSERT INTO event \(date, title, description, time, location\) VALUES \((.*)\);", re.IGNORECASE)
        insert_match = insert_pattern.search(command)
        if insert_match:
            values = insert_match.group(1)
            values = re.split(r",\s*(?=(?:[^']*'[^']*')*[^']*$)", values)  # Split by comma outside of quotes
            date_str, title, description, time, location = [v.strip().strip("'") for v in values]
            title = title.replace("''", "'")
            description = description.replace("''", "'")
            location = location.replace("''", "'")
            date = datetime.strptime(date_str, '%Y-%m-%d').date()
            event = Event(date=date, title=title, description=description, time=time, location=location)
            db.session.add(event)
            db.session.commit()
            print("Event added successfully!")
            return {"status": "success", "message": "Event added successfully!"}
        
        # Handle DELETE FROM command
        delete_pattern = re.compile(r"DELETE FROM event WHERE (.*);", re.IGNORECASE)
        delete_match = delete_pattern.search(command)
        if delete_match:
            where_clause = delete_match.group(1)
            events = Event.query.filter(text(f"{where_clause}")).all()
            if events:
                for event in events:
                    db.session.delete(event)
                db.session.commit()
                print("Event(s) deleted successfully!")
                return {"status": "success", "message": "Event(s) deleted successfully!"}
            else:
                print("Event(s) not found")
                return {"status": "error", "message": "Event(s) not found"}
        
        # Handle UPDATE command
        update_pattern = re.compile(r"UPDATE event SET (.*) WHERE (.*);", re.IGNORECASE)
        update_match = update_pattern.search(command)
        if update_match:
            set_clause, where_clause = update_match.groups()
            events = Event.query.filter(text(f"{where_clause}")).all()
            if events:
                for event in events:
                    set_statements = set_clause.split(',')
                    for statement in set_statements:
                        column, value = statement.split('=')
                        column = column.strip()
                        value = value.strip().strip("'")
                        if column == 'date':
                            value = datetime.strptime(value, '%Y-%m-%d').date()
                        setattr(event, column, value)
                    db.session.commit()
                print("Event(s) updated successfully!")
                return {"status": "success", "message": "Event(s) updated successfully!"}
            else:
                print("Event(s) not found")
                return {"status": "error", "message": "Event(s) not found"}
        
        print("Invalid command format")
        return {"status": "error", "message": "Invalid command format"}
    except Exception as e:
        db.session.rollback()
        print(f"Error executing command: {e}")
        return {"status": "error", "message": str(e)}

# Function to get response from ChatGPT
def get_chatgpt_response(prompt):
    print("Running GPT-3.5 model...")
    openai.api_key = config.OPENAI_API_KEY
    events = Event.query.filter(Event.description != "US Holiday").order_by(Event.date.desc()).limit(100).all()  # Exclude US Holidays
    events_data = [
        {
            "date": event.date.strftime('%Y-%m-%d'),
            "title": event.title,
            "description": event.description,
            "time": event.time,
            "location": event.location
        }
        for event in events
    ]
    current_datetime = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": f'''You are a helpful assistant with access to a calendar of user-defined events. 
                                            The current date and time is {current_datetime}.
                                            Please generate all responses in the format of a SQLite command,
                                            make sure the table to be used is 'event' and the columns to be used are 'date', 'title', 'description', 'time', 'location' in that order.
                                            The date should always be formatted as "YYYY-MM-DD". Replace any null fields with ''.
                                            The INSERT INTO command should be in the format: INSERT INTO event (date, title, description, time, location) VALUES ('2024-01-20', 'dad bday', '', '', '');
                                            When modifying/updating an event, please use the format: UPDATE event SET date = '2024-01-09' WHERE title = 'qwerty day';
                                            When deleting an event, please use DELETE FROM rather than UPDATE.
                                            Please make sure that rather than using \' for escaping single quotes, instead use two single quotes ''.
                                            Please make sure the command is all one line.
                                            '''},
            {"role": "user", "content": f"Here are some recent events: {events_data}. {prompt}"}
        ]
    )
    message_content = response.choices[0].message['content']
    
    # Detect and execute SQLite commands
    sqlite_command_pattern = re.compile(r"(INSERT INTO|UPDATE|DELETE FROM) event .*?;", re.IGNORECASE | re.DOTALL)
    match = sqlite_command_pattern.search(message_content)
    if match:
        print("Good!")
        command = match.group(0)
        print(command)
        execute_sqlite_command(command)
    
    return message_content

# API endpoint to remove an event
@app.route('/api/remove_event', methods=['POST'])
def api_remove_event():
    data = request.json
    event_id = data.get('event_id')
    event = Event.query.get(event_id)
    if event and event.description != "US Holiday":
        db.session.delete(event)
        db.session.commit()
        return {"status": "success", "message": "Event removed successfully!"}, 200
    return {"status": "error", "message": "Event not found or cannot be deleted."}, 404

# Function to migrate the database
def migrate_db():
    with app.app_context():
        # Check if the columns already exist
        inspector = db.inspect(db.engine)
        columns = [column['name'] for column in inspector.get_columns('event')]
        with db.engine.connect() as connection:
            if 'time' not in columns:
                connection.execute(text('ALTER TABLE event ADD COLUMN time STRING'))
            if 'location' not in columns:
                connection.execute(text('ALTER TABLE event ADD COLUMN location STRING'))

# Route to display the calendar view
@app.route('/', methods=['GET', 'POST'])
def calendar_view():
    selected_year = request.args.get('year', datetime.now().year)
    selected_year = int(selected_year)
    
    chat_form = ChatForm()
    if chat_form.validate_on_submit():
        get_chatgpt_response(chat_form.prompt.data)
        # Refresh events after executing the command
        add_us_holidays(selected_year)
        events = Event.query.filter(db.extract('year', Event.date) == selected_year).order_by(Event.date).all()
        events_by_month = {}
        for event in events:
            month = event.date.strftime('%B')
            if month not in events_by_month:
                events_by_month[month] = []
            events_by_month[month].append(event)
        all_months = [
            'January', 'February', 'March', 'April', 'May', 'June',
            'July', 'August', 'September', 'October', 'November', 'December'
        ]
        weather = get_weather()
        return render_template('calendar.html', events_by_month=events_by_month, all_months=all_months, selected_year=selected_year, weather=weather, chat_form=chat_form)
    
    if request.method == 'POST' and 'year' in request.form:
        selected_year = request.form.get('year', datetime.now().year)
        return redirect(url_for('calendar_view', year=selected_year))
    
    add_us_holidays(selected_year)
    events = Event.query.filter(db.extract('year', Event.date) == selected_year).order_by(Event.date).all()
    events_by_month = {}
    for event in events:
        month = event.date.strftime('%B')
        if month not in events_by_month:
            events_by_month[month] = []
        events_by_month[month].append(event)
    all_months = [
        'January', 'February', 'March', 'April', 'May', 'June',
        'July', 'August', 'September', 'October', 'November', 'December'
    ]
    weather = get_weather()
    return render_template('calendar.html', events_by_month=events_by_month, all_months=all_months, selected_year=selected_year, weather=weather, chat_form=chat_form)

# Route to display events for a specific month
@app.route('/month/<int:year>/<string:month>', methods=['GET'])
def month_view(year, month):
    month_number = datetime.strptime(month, '%B').month
    events = Event.query.filter(db.extract('year', Event.date) == year, db.extract('month', Event.date) == month_number).order_by(Event.date).all()
    days_with_events = {}
    for event in events:
        day = event.date.day
        if day not in days_with_events:
            days_with_events[day] = []
        days_with_events[day].append(event)
    holidays = {event.date.day: event for event in events if event.description == "US Holiday"}
    _, num_days = calendar.monthrange(year, month_number)
    days_in_month = [datetime(year, month_number, day) for day in range(1, num_days + 1)]
    return render_template('month.html', year=year, month=month, days_with_events=days_with_events, holidays=holidays, days_in_month=days_in_month, selected_year=year)

# Route to add a new event
@app.route('/add', methods=['GET', 'POST'])
def add_event():
    form = EventForm()
    selected_year = request.args.get('year', datetime.now().year)
    if form.validate_on_submit():
        event = Event(
            date=form.date.data,
            title=form.title.data,
            description=form.description.data,
            time=form.time.data,  # Include time field
            location=form.location.data  # Include location field
        )
        db.session.add(event)
        db.session.commit()
        flash("Event added successfully!")
        return redirect(url_for('calendar_view') + f"?year={selected_year}")
    return render_template('add_event.html', form=form, selected_year=selected_year)

# Route to edit an existing event
@app.route('/edit/<int:event_id>', methods=['GET', 'POST'])
def edit_event(event_id):
    event = Event.query.get_or_404(event_id)
    if event.description == "US Holiday":
        flash("Holidays cannot be edited.")
        return redirect(url_for('calendar_view') + f"?year={event.date.year}")
    form = EventForm(obj=event)
    if form.validate_on_submit():
        event.title = form.title.data
        event.date = form.date.data
        event.description = form.description.data
        event.time = form.time.data
        event.location = form.location.data
        db.session.commit()
        flash("Event updated successfully!")
        return redirect(url_for('calendar_view') + f"?year={event.date.year}")
    return render_template('edit_event.html', form=form, event=event)

# Route to delete an event
@app.route('/delete/<int:event_id>', methods=['POST'])
def delete_event(event_id):
    event = Event.query.get_or_404(event_id)
    if event.description == "US Holiday":
        flash("Holidays cannot be deleted.")
        return redirect(url_for('calendar_view') + f"?year={event.date.year}")
    selected_year = request.form.get('year', event.date.year)
    db.session.delete(event)
    db.session.commit()
    flash("Event removed successfully!")
    return redirect(url_for('calendar_view') + f"?year={selected_year}")

# Route to search for events
@app.route('/search', methods=['GET', 'POST'])
def search():
    query = request.form.get('query', '')
    events = Event.query.filter(Event.title.contains(query) | Event.description.contains(query)).order_by(Event.date).all()
    return render_template('search_results.html', events=events, query=query)

if __name__ == '__main__':
    migrate_db()  # Call the migration function before running the app
    with app.app_context():
        db.create_all()
        for year in range(2000, 2030):  # Adjust the range as needed
            add_us_holidays(year)
    app.run(debug=True)
