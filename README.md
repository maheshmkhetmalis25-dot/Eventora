
# Eventora — polished Flask + MySQL Event Management System

## 1. Database
Open MySQL Workbench and run `database/schema.sql` in the `event_planner` database.
IMPORTANT: this schema is intended as a clean final-project schema and drops/recreates project tables.

## 2. Configure MySQL
Open `app.py` and change:
    password=os.environ.get("MYSQL_PASSWORD", "YOUR_MYSQL_PASSWORD")
to your MySQL root password, or set the MYSQL_PASSWORD environment variable.

## 3. Install
pip install -r requirements.txt

## 4. Run
python app.py

Open http://127.0.0.1:5000/

Admin:
email: admin@gmail.com
password: admin123

## Notes
- The UI is responsive and uses local SVG artwork so it works without downloading image assets.
- The payment flow is intentionally demo/sandbox-style for a diploma project; real Razorpay/Stripe verification should be added before production.
- Passwords created through registration are hashed with Werkzeug.
- The starter admin account in schema.sql uses a hash compatible with Werkzeug.
>>>>>>> af97564 (My first commit)
