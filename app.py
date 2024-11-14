from flask import Flask, render_template, redirect, url_for, request, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta, date
import calendar
import holidays
from forms import EventForm
import requests
from sqlalchemy import text
from dateutil.easter import easter

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///events.db'
db = SQLAlchemy(app)

class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255))
    time = db.Column(db.String(10))  # New field for time
    location = db.Column(db.String(100))  # New field for location

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

@app.route('/', methods=['GET', 'POST'])
def calendar_view():
    if request.method == 'POST':
        selected_year = request.form.get('year', datetime.now().year)
        return redirect(url_for('calendar_view', year=selected_year))
    selected_year = request.args.get('year', datetime.now().year)
    selected_year = int(selected_year)
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
    return render_template('calendar.html', events_by_month=events_by_month, all_months=all_months, selected_year=selected_year, weather=weather)

@app.route('/month/<int:year>/<string:month>', methods=['GET'])
def month_view(year, month):
    month_number = datetime.strptime(month, '%B').month
    events = Event.query.filter(db.extract('year', Event.date) == year, db.extract('month', Event.date) == month_number).order_by(Event.date).all()
    days_with_events = {event.date.day: event for event in events}
    holidays = {event.date.day: event for event in events if event.description == "US Holiday"}
    _, num_days = calendar.monthrange(year, month_number)
    days_in_month = [datetime(year, month_number, day) for day in range(1, num_days + 1)]
    return render_template('month.html', year=year, month=month, days_with_events=days_with_events, holidays=holidays, days_in_month=days_in_month)

@app.route('/add', methods=['GET', 'POST'])
def add_event():
    form = EventForm()
    selected_year = request.args.get('year', datetime.now().year)
    if form.validate_on_submit():
        event = Event(
            date=form.date.data,
            title=form.title.data,
            description=form.description.data
        )
        db.session.add(event)
        db.session.commit()
        flash("Event added successfully!")
        return redirect(url_for('calendar_view') + f"?year={selected_year}")
    return render_template('add_event.html', form=form, selected_year=selected_year)

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

@app.route('/delete/<int:event_id>', methods=['POST'])
def delete_event(event_id):
    event = Event.query.get_or_404(event_id)
    selected_year = request.form.get('year', event.date.year)
    db.session.delete(event)
    db.session.commit()
    flash("Event removed successfully!")
    return redirect(url_for('calendar_view') + f"?year={selected_year}")

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
