from datetime import datetime
from app import app, Exam, User, Question

with app.app_context():
    # Check scheduled exams
    scheduled_exams = Exam.query.filter_by(is_scheduled=True).all()
    print(f"Found {len(scheduled_exams)} scheduled exams:")
    
    for exam in scheduled_exams:
        print(f"- {exam.title}")
        print(f"  Scheduled: {exam.scheduled_start} to {exam.scheduled_end}")
        
        # Get questions for this exam
        questions = Question.query.filter_by(exam_id=exam.id).all()
        print(f"  Questions: {len(questions)}")
        
        # Check status
        now = datetime.now()
        if now < exam.scheduled_start:
            status = "Upcoming"
        elif exam.scheduled_start <= now <= exam.scheduled_end:
            status = "Active"
        else:
            status = "Completed"
        print(f"  Status: {status}")
        print()
    
    # Check users
    users = User.query.all()
    print(f"Found {len(users)} users in database")
    for user in users:
        print(f"- {user.username} ({user.role})")