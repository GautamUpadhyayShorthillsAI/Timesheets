import os
from functools import wraps
from datetime import datetime
from flask import Flask, render_template, redirect, url_for, request, flash, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager,
    login_user,
    login_required,
    logout_user,
    current_user,
)
from flask_migrate import Migrate
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev_secret_key")

# Database setup (SQLite)
basedir = os.path.abspath(os.path.dirname(__file__))
os.makedirs(basedir, exist_ok=True)
db_path = os.path.join(basedir, "db.sqlite")
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Initialize extensions
db = SQLAlchemy(app)
migrate = Migrate(app, db)
login_manager = LoginManager(app)
login_manager.login_view = "login"

# Models import (make sure Team & TeamMember exist in models.py)
from models import (
    User,
    Customer,
    Project,
    Activity,
    TimesheetEntry,
    Team,
)  # noqa: E402


# Flask-Login user loader
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# Role-based decorator
def role_required(role):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated or current_user.role != role:
                abort(403)
            return f(*args, **kwargs)

        return wrapped

    return decorator


# ----------------------------------------
# Authentication & Approval
# ----------------------------------------
@app.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("home"))
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        uname = request.form.get("username", "").strip()
        pwd = request.form.get("password", "")
        if User.query.filter_by(username=uname).first():
            flash("Username already exists.", "warning")
        else:
            u = User(username=uname, role="ROLE_USER", is_approved=False)
            u.set_password(pwd)
            db.session.add(u)
            db.session.commit()
            flash("Registered! Await admin approval.", "success")
            return redirect(url_for("login"))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        uname = request.form.get("username", "").strip()
        pwd = request.form.get("password", "")
        user = User.query.filter_by(username=uname).first()
        if user and user.check_password(pwd):
            if not user.is_approved:
                flash("Account pending approval.", "warning")
                return redirect(url_for("login"))
            login_user(user)
            if user.role == "ROLE_ADMIN":
                return redirect(url_for("admin_dashboard"))
            if user.role == "ROLE_TEAMLEAD":
                return redirect(url_for("lead_dashboard"))
            return redirect(url_for("user_dashboard"))
        flash("Invalid credentials.", "danger")
    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Logged out.", "info")
    return redirect(url_for("login"))


# ----------------------------------------
# Dashboards
# ----------------------------------------
@app.route("/home")
@login_required
def home():
    if current_user.role == "ROLE_ADMIN":
        return redirect(url_for("admin_dashboard"))
    if current_user.role == "ROLE_TEAMLEAD":
        return redirect(url_for("lead_dashboard"))
    return redirect(url_for("user_dashboard"))


@app.route("/admin")
@login_required
@role_required("ROLE_ADMIN")
def admin_dashboard():
    return render_template("admin_dashboard.html", user=current_user)


@app.route("/lead")
@login_required
@role_required("ROLE_TEAMLEAD")
def lead_dashboard():
    return render_template("lead_dashboard.html", user=current_user)


@app.route("/dashboard")
@login_required
@role_required("ROLE_USER")
def user_dashboard():
    return render_template("user_dashboard.html", user=current_user)


# ----------------------------------------
# Customer, Project & Activity CRUD (Admin)
# ----------------------------------------
@app.route("/customers")
@login_required
@role_required("ROLE_ADMIN")
def list_customers():
    customers = Customer.query.order_by(Customer.name).all()
    return render_template("customers.html", customers=customers)


@app.route("/customers/new", methods=["GET", "POST"])
@login_required
@role_required("ROLE_ADMIN")
def new_customer():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if name:
            db.session.add(Customer(name=name))
            db.session.commit()
            flash("Customer created.", "success")
            return redirect(url_for("list_customers"))
    return render_template("customer_form.html")


@app.route("/projects")
@login_required
@role_required("ROLE_ADMIN")
def list_projects():
    projects = Project.query.order_by(Project.name).all()
    return render_template("projects.html", projects=projects)


@app.route("/projects/new", methods=["GET", "POST"])
@login_required
@role_required("ROLE_ADMIN")
def new_project():
    customers = Customer.query.filter_by(is_active=True).all()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        cid = request.form.get("customer_id")
        if name and cid:
            db.session.add(Project(name=name, customer_id=int(cid)))
            db.session.commit()
            flash("Project created.", "success")
            return redirect(url_for("list_projects"))
    return render_template("project_form.html", customers=customers)


@app.route("/activities")
@login_required
@role_required("ROLE_ADMIN")
def list_activities():
    activities = Activity.query.order_by(Activity.name).all()
    return render_template("activities.html", activities=activities)


@app.route("/activities/new", methods=["GET", "POST"])
@login_required
@role_required("ROLE_ADMIN")
def new_activity():
    projects = Project.query.filter_by(is_active=True).all()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        pid = request.form.get("project_id")
        bill = bool(request.form.get("is_billable"))
        if name and pid:
            db.session.add(Activity(name=name, project_id=int(pid), is_billable=bill))
            db.session.commit()
            flash("Activity created.", "success")
            return redirect(url_for("list_activities"))
    return render_template("activity_form.html", projects=projects)


# ----------------------------------------
# Timesheet Entries
# ----------------------------------------
@app.route("/entries")
@login_required
@role_required("ROLE_USER")
def list_my_entries():
    entries = (
        TimesheetEntry.query.filter_by(user_id=current_user.id)
        .order_by(TimesheetEntry.start_time.desc())
        .all()
    )
    return render_template("entries.html", entries=entries)


@app.route("/entries/new", methods=["GET", "POST"])
@login_required
@role_required("ROLE_USER")
def new_entry():
    activities = Activity.query.filter_by(is_active=True).all()
    if request.method == "POST":
        s = datetime.fromisoformat(request.form["start_time"])
        e = datetime.fromisoformat(request.form["end_time"])
        act_id = int(request.form["activity_id"])
        desc = request.form.get("description", "")
        bill = bool(request.form.get("is_billable"))
        dur = (e - s).total_seconds() / 3600
        proj_id = Activity.query.get(act_id).project_id

        entry = TimesheetEntry(
            user_id=current_user.id,
            project_id=proj_id,
            activity_id=act_id,
            start_time=s,
            end_time=e,
            duration_hours=dur,
            is_billable=bill,
            description=desc,
            is_approved=False,
        )
        db.session.add(entry)
        db.session.commit()
        flash("Entry created.", "success")
        return redirect(url_for("list_my_entries"))
    return render_template("entry_form.html", activities=activities)


@app.route("/entries/pending")
@login_required
@role_required("ROLE_TEAMLEAD")
def pending_entries():
    entries = (
        TimesheetEntry.query.filter_by(is_approved=False)
        .order_by(TimesheetEntry.start_time.desc())
        .all()
    )
    return render_template("entries_pending.html", entries=entries)


@app.route("/entries/<int:id>/approve", methods=["POST"])
@login_required
@role_required("ROLE_TEAMLEAD")
def approve_entry(id):
    entry = TimesheetEntry.query.get_or_404(id)
    entry.is_approved = True
    db.session.commit()
    flash("Entry approved.", "success")
    return redirect(url_for("pending_entries"))


@app.route("/entries/all")
@login_required
@role_required("ROLE_ADMIN")
def all_entries():
    entries = TimesheetEntry.query.order_by(TimesheetEntry.start_time.desc()).all()
    return render_template("entries_all.html", entries=entries)

@app.route("/entries/all_lead")
@login_required
@role_required("ROLE_TEAMLEAD")
def all_entries_lead():
    user = User.query.all()
    team = Team.query.all()
    print(user[0].__dict__)
    entries = TimesheetEntry.query.order_by(TimesheetEntry.start_time.desc()).all()
    print(list(entries)[0].__dict__)
    return render_template("entries_all.html", entries=entries)


# ----------------------------------------
# User Management & Approval (Admin)
# ----------------------------------------
@app.route("/users")
@login_required
@role_required("ROLE_ADMIN")
def list_users():
    users = User.query.order_by(User.username).all()
    return render_template("users.html", users=users)


@app.route("/users/new", methods=["GET", "POST"])
@login_required
@role_required("ROLE_ADMIN")
def new_user():
    if request.method == "POST":
        uname = request.form.get("username", "").strip()
        pwd = request.form.get("password", "")
        role = request.form.get("role", "ROLE_USER")
        if User.query.filter_by(username=uname).first():
            flash("Username already exists.", "warning")
        else:
            u = User(username=uname, role=role, is_approved=True)
            u.set_password(pwd)
            db.session.add(u)
            db.session.commit()
            flash("User created.", "success")
            return redirect(url_for("list_users"))
    return render_template("user_form.html")


@app.route("/users/<int:id>/approve", methods=["POST"])
@login_required
@role_required("ROLE_ADMIN")
def approve_user(id):
    u = User.query.get_or_404(id)
    u.is_approved = True
    db.session.commit()
    flash(f"User '{u.username}' approved.", "success")
    return redirect(url_for("list_users"))


# ----------------------------------------
# Teams Feature (Admin & TeamLead)
# ----------------------------------------


# List all teams (admin only)
@app.route("/teams")
@login_required
@role_required("ROLE_ADMIN")
def list_teams():
    teams = Team.query.order_by(Team.name).all()
    return render_template("teams.html", teams=teams)


# Create a new team (admin only)
@app.route("/teams/new", methods=["GET", "POST"])
@login_required
@role_required("ROLE_ADMIN")
def new_team():
    leads = User.query.filter_by(role="ROLE_TEAMLEAD", is_approved=True).all()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        lead_id = int(request.form.get("lead_id", 0))
        if name and lead_id:
            t = Team(name=name, lead_id=lead_id)
            db.session.add(t)
            db.session.commit()
            flash("Team created.", "success")
            return redirect(url_for("list_teams"))
    return render_template("team_form.html", leads=leads)


# Delete a team (admin only)
@app.route("/teams/<int:id>/delete", methods=["POST"])
@login_required
@role_required("ROLE_ADMIN")
def delete_team(id):
    t = Team.query.get_or_404(id)
    db.session.delete(t)
    db.session.commit()
    flash("Team deleted.", "success")
    return redirect(url_for("list_teams"))


# View & manage members of a team (admin & that team’s lead)
@app.route("/teams/<int:id>/members")
@login_required
def list_team_members(id):
    t = Team.query.get_or_404(id)
    # Only admin or that team’s lead may manage
    if not (current_user.role == "ROLE_ADMIN" or current_user.id == t.lead_id):
        abort(403)

    members = t.members  # relationship from models.py
    # find all approved users who aren’t already members
    available = User.query.filter(
        User.is_approved.is_(True),
        User.role == "ROLE_USER",
        ~User.teams.any(Team.id == id),
    ).all()

    return render_template(
        "team_members.html", team=t, members=members, available=available
    )


# Add member to team (admin only)
@app.route("/teams/<int:id>/members/add", methods=["POST"])
@login_required
@role_required("ROLE_ADMIN")
def add_member(id):
    t = Team.query.get_or_404(id)
    user_id = int(request.form.get("user_id", 0))
    u = User.query.get_or_404(user_id)
    t.members.append(u)
    db.session.commit()
    flash("Member added to team.", "success")
    return redirect(url_for("list_team_members", id=id))


# Remove member from team (admin only)
@app.route("/teams/<int:id>/members/remove", methods=["POST"])
@login_required
@role_required("ROLE_ADMIN")
def remove_member(id):
    t = Team.query.get_or_404(id)
    user_id = int(request.form.get("user_id", 0))
    u = User.query.get_or_404(user_id)
    t.members.remove(u)
    db.session.commit()
    flash("Member removed.", "info")
    return redirect(url_for("list_team_members", id=id))


# Team-lead: view all timesheet entries for users on their team
@app.route("/teams/<int:id>/entries")
@login_required
@role_required("ROLE_TEAMLEAD")
def team_entries(id):
    t = Team.query.get_or_404(id)
    if current_user.id != t.lead_id:
        abort(403)
    user_ids = [u.id for u in t.members]
    entries = (
        TimesheetEntry.query.filter(TimesheetEntry.user_id.in_(user_ids))
        .order_by(TimesheetEntry.start_time.desc())
        .all()
    )
    return render_template("team_entries.html", team=t, entries=entries)


if __name__ == "__main__":
    app.run(debug=True)
