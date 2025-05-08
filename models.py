# models.py
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db  # noqa: E402

# association table for users ↔ teams
team_members = db.Table(
    "team_members",
    db.Column("team_id", db.Integer, db.ForeignKey("teams.id"), primary_key=True),
    db.Column("user_id", db.Integer, db.ForeignKey("users.id"), primary_key=True),
)


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(50), nullable=False, default="ROLE_USER")
    is_approved = db.Column(db.Boolean, nullable=False, default=False)

    # back-ref from Team.lead
    leading_teams = db.relationship(
        "Team",
        back_populates="lead",
        foreign_keys="[Team.lead_id]",
        cascade="all, delete-orphan",
    )

    # many-to-many: which teams this user belongs to
    teams = db.relationship("Team", secondary=team_members, back_populates="members")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Customer(db.Model):
    __tablename__ = "customers"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), unique=True, nullable=False)
    is_active = db.Column(db.Boolean, default=True)


class Project(db.Model):
    __tablename__ = "projects"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=False)
    is_active = db.Column(db.Boolean, default=True)

    customer = db.relationship("Customer", backref=db.backref("projects", lazy=True))


class Activity(db.Model):
    __tablename__ = "activities"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False)
    is_billable = db.Column(db.Boolean, default=True)
    is_active = db.Column(db.Boolean, default=True)

    project = db.relationship("Project", backref=db.backref("activities", lazy=True))


class TimesheetEntry(db.Model):
    __tablename__ = "timesheet_entries"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False)
    activity_id = db.Column(db.Integer, db.ForeignKey("activities.id"), nullable=False)
    #Add a db column to the information of team lead
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    duration_hours = db.Column(db.Float, nullable=False)
    is_billable = db.Column(db.Boolean, default=True)
    description = db.Column(db.Text, nullable=True)
    state = db.Column(db.String(20), default="stopped")
    tags = db.Column(db.String(255), nullable=True)

    # newly added approval flag
    is_approved = db.Column(db.Boolean, nullable=False, default=False)

    user = db.relationship("User", backref=db.backref("entries", lazy=True))
    project = db.relationship("Project", backref=db.backref("entries", lazy=True))
    activity = db.relationship("Activity", backref=db.backref("entries", lazy=True))


class Team(db.Model):
    __tablename__ = "teams"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), unique=True, nullable=False)

    # who is the team lead
    lead_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    lead = db.relationship(
        "User", back_populates="leading_teams", foreign_keys=[lead_id]
    )

    # members of this team
    members = db.relationship("User", secondary=team_members, back_populates="teams")
