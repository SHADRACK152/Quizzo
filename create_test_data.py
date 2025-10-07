from datetime import datetime, timedelta
from app import app, db, Exam, Question

with app.app_context():
    # Create some test scheduled exams
    now = datetime.now()
    
    # Exam 1: Upcoming exam (tomorrow)
    exam1 = Exam()
    exam1.title = 'Python Programming Midterm'
    exam1.lecturer_id = 1
    exam1.created_at = now
    exam1.is_scheduled = True
    exam1.scheduled_start = now + timedelta(days=1, hours=2)
    exam1.scheduled_end = exam1.scheduled_start + timedelta(hours=2)
    db.session.add(exam1)
    db.session.flush()
    
    # Add sample questions to exam1
    for i in range(5):
        q = Question()
        q.exam_id = exam1.id
        q.text = f'Python question {i+1}: What is the output of this code?'
        q.question_type = 'multiple_choice'
        q.option_a = 'Option A'
        q.option_b = 'Option B'
        q.option_c = 'Option C'
        q.option_d = 'Option D'
        q.correct_option = 'A'
        db.session.add(q)
    
    # Exam 2: Active exam (running now)
    exam2 = Exam()
    exam2.title = 'Database Design Quiz'
    exam2.lecturer_id = 1
    exam2.created_at = now
    exam2.is_scheduled = True
    exam2.scheduled_start = now - timedelta(minutes=30)
    exam2.scheduled_end = now + timedelta(minutes=30)
    db.session.add(exam2)
    db.session.flush()
    
    # Add sample questions to exam2
    for i in range(3):
        q = Question()
        q.exam_id = exam2.id
        q.text = f'Database question {i+1}: Which SQL command is used to...?'
        q.question_type = 'multiple_choice'
        q.option_a = 'SELECT'
        q.option_b = 'INSERT'
        q.option_c = 'UPDATE'
        q.option_d = 'DELETE'
        q.correct_option = 'A'
        db.session.add(q)
    
    # Exam 3: Scheduled for next week
    exam3 = Exam()
    exam3.title = 'Web Development Final'
    exam3.lecturer_id = 1
    exam3.created_at = now
    exam3.is_scheduled = True
    exam3.scheduled_start = now + timedelta(days=7)
    exam3.scheduled_end = exam3.scheduled_start + timedelta(hours=3)
    db.session.add(exam3)
    db.session.flush()
    
    # Add sample questions to exam3
    for i in range(8):
        q = Question()
        q.exam_id = exam3.id
        q.text = f'Web dev question {i+1}: How do you implement...?'
        q.question_type = 'multiple_choice'
        q.option_a = 'Method A'
        q.option_b = 'Method B'
        q.option_c = 'Method C'
        q.option_d = 'Method D'
        q.correct_option = 'B'
        db.session.add(q)
    
    db.session.commit()
    print('Created 3 scheduled test exams with questions')
    print(f'1. Python Programming Midterm - {exam1.scheduled_start}')
    print(f'2. Database Design Quiz - {exam2.scheduled_start} (ACTIVE)')
    print(f'3. Web Development Final - {exam3.scheduled_start}')