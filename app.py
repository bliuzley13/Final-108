from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from datetime import time
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView

app = Flask(__name__)
CORS(app)

app.secret_key = "super secret key"

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///school.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)
admin = Admin(app, name='School Admin', template_mode='bootstrap4')  # 'bootstrap4' for modern UI


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(10), nullable=False)  # 'student', 'teacher', 'admin'
    role = db.Column(db.String(10), nullable=False)  # 'student', 'teacher', 'admin'
    enrollments = db.relationship('Enrollment', back_populates='user')  # Fixed here


class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    capacity = db.Column(db.Integer, nullable=False)
    start_time = db.Column(db.Time, nullable=False)  # Start time of the course
    end_time = db.Column(db.Time, nullable=False)  # End time of the course
    nofstudents = db.Column(db.Integer, nullable=False)
    teacher = db.Column(db.String(100), nullable=False)
    students = db.relationship('Enrollment', back_populates='course')


class Enrollment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    grade = db.Column(db.Float, nullable=True)
    user = db.relationship('User', back_populates='enrollments')
    course = db.relationship('Course', back_populates='students')


# Add models to the admin interface
admin.add_view(ModelView(User, db.session))
admin.add_view(ModelView(Course, db.session))


class EnrollmentModelView(ModelView):
    column_list = ('id', 'user_id', 'course_id', 'grade')  # Specify the fields to be shown
    column_labels = {
        'id': 'Enrollment ID',
        'user_id': 'User ID',
        'course_id': 'Course ID',
        'grade': 'Grade'
    }

    # Optionally, you can format the user_id and course_id to show related information, if needed
    column_formatters = {
        'user_id': lambda v, c, m, p: m.user.username if m.user else None,
        'course_id': lambda v, c, m, p: m.course.name if m.course else None
    }


# Add Enrollment to the admin interface with the customized view
admin.add_view(EnrollmentModelView(Enrollment, db.session))


@app.route('/enrollments', methods=['GET'])
def get_all_enrollments():
    enrollments = Enrollment.query.all()  # Fetch all enrollments
    result = []

    for enrollment in enrollments:
        user = enrollment.user  # Get the related user for this enrollment
        course = enrollment.course  # Get the related course for this enrollment

        result.append({
            "enrollment_id": enrollment.id,
            "user_id": user.id,
            "user_username": user.username,
            "course_id": course.id,
            "course_name": course.name,
            "course_teacher": course.teacher,
            "grade": enrollment.grade if enrollment.grade is not None else "Not graded",
            "start_time": course.start_time.strftime('%I:%M %p'),
            "end_time": course.end_time.strftime('%I:%M %p'),
        })

    return jsonify(result)


def check_time_conflict(user_id, new_course):
    """Check if a user's current courses conflict with the new course's time."""
    current_enrollments = Enrollment.query.filter_by(user_id=user_id).all()
    for enrollment in current_enrollments:
        enrolled_course = enrollment.course
        # Check if times overlap
        if not (new_course.end_time <= enrolled_course.start_time or new_course.start_time >= enrolled_course.end_time):
            return True  # Conflict found
    return False


@app.route('/courses', methods=['GET'])
def get_courses():
    print("you work")
    courses = Course.query.all()
    return jsonify([{
        "id": course.id,
        "name": course.name,
        "capacity": course.capacity,
        "start_time": course.start_time.strftime('%I:%M %p'),
        "end_time": course.end_time.strftime('%I:%M %p'),
        "teacher": course.teacher,
        "nofstudents": course.nofstudents  # Ensure this line is present

    } for course in courses])


@app.route('/users', methods=['GET'])
def get_users():
    users = User.query.all()
    return jsonify([
        {"id": user.id, "username": user.username, "password": user.password, "role": user.role}
        for user in users
    ])


@app.route('/users/<int:user_id>/courses', methods=['GET'])
def get_user_courses(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    enrolled_courses = [
        {
            "id": enrollment.course.id,
            "name": enrollment.course.name,
            "start_time": enrollment.course.start_time.strftime('%I:%M %p'),
            "end_time": enrollment.course.end_time.strftime('%I:%M %p'),
            "teacher": enrollment.course.teacher,
            "capacity": enrollment.course.capacity,
            "nofstudents": enrollment.course.nofstudents

        }
        for enrollment in user.enrollments
    ]
    return jsonify(enrolled_courses)


@app.route('/courses/<int:course_id>', methods=['PUT'])
def update_course_capacity(course_id):
    course = Course.query.get(course_id)
    if not course:
        return jsonify({"error": "Course not found"}), 404

    data = request.get_json()
    if 'capacity' not in data:
        return jsonify({"error": "Capacity value is required"}), 400

    new_capacity = data['capacity']
    if new_capacity < 0:
        return jsonify({"error": "Capacity cannot be negative"}), 400

    course.capacity = new_capacity
    db.session.commit()
    return jsonify({"message": f"Capacity for course {course.name} updated to {course.capacity}"}), 200


@app.route('/enroll/<int:user_id>/<int:course_id>', methods=['POST'])
def enroll(user_id, course_id):
    user = User.query.get(user_id)
    course = Course.query.get(course_id)
    print("DO SOMETHING")
    if not user or not course:
        return jsonify({"error": "Invalid user or course"}), 404

    if len(course.students) >= course.capacity:
        return jsonify({"error": "Course is full"}), 400

    if check_time_conflict(user_id, course):
        return jsonify({"error": "Time conflict with another enrolled course"}), 400

    # Create the enrollment
    enrollment = Enrollment(user_id=user.id, course_id=course.id)
    db.session.add(enrollment)

    # Update the course capacity
    course.nofstudents += 1  # Decrease the course capacity by 1
    db.session.commit()  # Commit both the enrollment and the course capacity update
    print("fucking work?")
    return jsonify({"message": f"{user.username} enrolled in {course.name} successfully!"}), 201


@app.route('/enroll/<int:user_id>/<int:course_id>', methods=['DELETE'])
def remove_enrollment(user_id, course_id):
    # Find the enrollment by user_id and course_id
    enrollment = Enrollment.query.filter_by(user_id=user_id, course_id=course_id).first()
    course = Course.query.get(course_id)
    course.nofstudents -= 1  # Decrease the course capacity by 1
    # Remove the enrollment from the database
    db.session.delete(enrollment)
    db.session.commit()

    # Return a success message
    return jsonify({"message": "Enrollment removed successfully"}), 200


@app.route('/enrollments/<int:enrollment_id>', methods=['PUT'])
def update_enrollment(enrollment_id):
    enrollment = Enrollment.query.get(enrollment_id)
    if not enrollment:
        return jsonify({"error": "Enrollment not found"}), 404

    data = request.get_json()
    if 'grade' not in data:
        return jsonify({"error": "Grade value is required"}), 400

    # Update grade
    try:
        enrollment.grade = float(data['grade'])
        db.session.commit()
        return jsonify({"message": f"Grade updated to {enrollment.grade} for enrollment ID {enrollment_id}"}), 200
    except ValueError:
        return jsonify({"error": "Invalid grade value"}), 400


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        if not User.query.first():
            db.session.add_all([
                User(username="jimmy", password="1", role="student"),
                User(username="Amon Hepworth", password="2", role="teacher"),
                User(username="Stephanian Haik", password="2", role="teacher"),
                User(username="Renato Farias", password="2", role="teacher"),
                User(username="Borna Hlousek", password="2", role="teacher"),
                User(username="Juan Meza", password="2", role="teacher"),
                User(username="Jill Jim", password="2", role="teacher"),
                User(username="jimbo", password="3", role="student"),
                User(username="admin", password="5", role="admin")
            ])
            db.session.add_all([
                Course(name="Math 101", capacity=30, start_time=time(16, 0), end_time=time(17, 0), nofstudents=0,
                       teacher="Amon Hepworth"),  # 4 PM to 5 PM
                Course(name="History 202", capacity=25, start_time=time(15, 0), end_time=time(16, 0), nofstudents=0,
                       teacher="Stephanian Haik"),  # 3 PM to 4 PM
                Course(name="Math 133", capacity=30, start_time=time(8, 0), end_time=time(9, 0), nofstudents=0,
                       teacher="Renato Farias"),  # 4 PM to 5 PM
                Course(name="CSE 234", capacity=25, start_time=time(10, 0), end_time=time(11, 0), nofstudents=0,
                       teacher="Borna Hlousek"),  # 3 PM to 4 PM
                Course(name="EE 111", capacity=30, start_time=time(16, 0), end_time=time(18, 0), nofstudents=0,
                       teacher="Juan Meza"),  # 4 PM to 5 PM
                Course(name="Philosophy 233", capacity=25, start_time=time(15, 0), end_time=time(17, 0), nofstudents=0,
                       teacher="Jill Jim"),  # 3 PM to 4 PM
            ])
            db.session.add_all([
                Enrollment(user_id=1, course_id=2, grade=93),  # 4 PM to 5 PM
                Enrollment(user_id=8, course_id=2, grade=21)
            ])
            course = Course.query.get(2)
            course.nofstudents += 2
            db.session.commit()  # Commit the users and courses

            db.session.commit()  # Commit the enrollments to the database
    app.run(debug=True)
